from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any

import cv2

from app.config import get_settings

COMMON_COCO_CATEGORIES: frozenset[str] = frozenset(
    {
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "airplane",
        "bus",
        "train",
        "truck",
        "boat",
        "traffic light",
        "fire hydrant",
        "stop sign",
        "parking meter",
        "bench",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "backpack",
        "umbrella",
        "handbag",
        "tie",
        "suitcase",
        "bottle",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "chair",
        "couch",
        "potted plant",
        "bed",
        "dining table",
        "tv",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "book",
        "clock",
        "vase",
        "scissors",
    }
)


@dataclass(frozen=True)
class DetectedObjectRecord:
    """Single detected object within an extracted frame."""

    class_id: int
    class_name: str
    confidence: float
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float


@dataclass(frozen=True)
class FrameDetectionsRecord:
    """Object detections and timing metadata for a single frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    frame_width: int
    frame_height: int
    detections: list[DetectedObjectRecord]


@dataclass(frozen=True)
class AnalysisDetectionResult:
    """Aggregated detection output for an entire analysis run."""

    model_name: str
    confidence_threshold: float
    image_size: int
    total_detections: int
    frames_with_detections: int
    class_counts: dict[str, int]
    frames: list[FrameDetectionsRecord]
    detections_path: Path


DetectionProgressCallback = Callable[[int, int], None]

_model_lock = threading.Lock()
_cached_models: dict[str, Any] = {}
_dll_dir_handles: list[Any] = []


def _ensure_windows_vc_runtime() -> None:
    """Register an existing host VC++ runtime DLL folder if System32 lacks msvcp140.dll."""
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    system_dll = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "msvcp140.dll"
    if system_dll.exists():
        return

    candidates: list[Path] = []
    if conda_prefix := os.environ.get("CONDA_PREFIX"):
        candidates.append(Path(conda_prefix) / "Library" / "bin")
    candidates.extend(
        [
            Path(r"C:\ProgramData\anaconda3\Library\bin"),
            Path.home() / "anaconda3" / "Library" / "bin",
            Path.home() / "miniconda3" / "Library" / "bin",
        ]
    )
    for raw_entry in os.environ.get("PATH", "").split(os.pathsep):
        if raw_entry:
            candidates.append(Path(raw_entry))

    seen: set[Path] = set()
    for folder in candidates:
        try:
            resolved = folder.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "msvcp140.dll").is_file():
            try:
                _dll_dir_handles.append(os.add_dll_directory(str(resolved)))
                return
            except OSError:
                continue


def get_detection_model(model_name: str | None = None) -> Any:
    """Load and cache the CPU-only Ultralytics YOLO nano model once for reuse."""
    settings = get_settings()
    resolved_name = model_name or settings.yolo_model_name
    weights_path = settings.resolved_weights_dir / resolved_name

    with _model_lock:
        if resolved_name in _cached_models:
            return _cached_models[resolved_name]

        _ensure_windows_vc_runtime()

        try:
            from ultralytics import YOLO
        except OSError as exc:
            raise RuntimeError(
                "PyTorch/Ultralytics failed to load native DLLs on Windows. "
                "Install Microsoft Visual C++ Redistributable (x64) and restart the backend."
            ) from exc
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is not installed. Run `pip install ultralytics` in the backend environment."
            ) from exc

        try:
            # Pass the weights path inside backend/weights/ so Ultralytics downloads
            # pretrained COCO weights there automatically on first run if absent.
            model = YOLO(str(weights_path))
            _cached_models[resolved_name] = model
            return model
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load YOLO model '{resolved_name}'. On first run, ensure internet "
                "access is available to download pretrained COCO weights."
            ) from exc


def detect_objects_in_analysis(
    *,
    analysis_id: str,
    video_id: str,
    analysis_dir: Path,
    confidence_threshold: float | None = None,
    image_size: int | None = None,
    model_name: str | None = None,
    allowed_categories: frozenset[str] | None = None,
    progress_callback: DetectionProgressCallback | None = None,
) -> AnalysisDetectionResult:
    """Run CPU-only YOLO detection one extracted frame at a time and save detections.json."""
    settings = get_settings()
    conf = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.detection_confidence
    )
    imgsz = image_size if image_size is not None else settings.detection_image_size
    resolved_model_name = model_name or settings.yolo_model_name

    metadata_path = analysis_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError("Frame metadata.json was not found for object detection.")

    raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    frame_entries = raw_meta.get("frames", [])
    frames_dir = analysis_dir / "frames"

    model = get_detection_model(resolved_model_name)

    frame_records: list[FrameDetectionsRecord] = []
    class_counter: Counter[str] = Counter()
    total_detections = 0
    frames_with_detections = 0
    total_frames = len(frame_entries)

    for idx, entry in enumerate(frame_entries):
        filename = str(entry["filename"])
        frame_path = (frames_dir / Path(filename).name).resolve()
        if frame_path.parent != frames_dir.resolve() or not frame_path.exists():
            continue

        frame_img = cv2.imread(str(frame_path))
        if frame_img is None:
            continue

        frame_height, frame_width = frame_img.shape[:2]

        results = model.predict(
            source=frame_img,
            imgsz=imgsz,
            conf=conf,
            device="cpu",
            verbose=False,
        )

        frame_detections: list[DetectedObjectRecord] = []
        if results:
            result = results[0]
            names_map = result.names or {}
            boxes = result.boxes
            if boxes is not None and len(boxes) > 0:
                xyxy_list = boxes.xyxy.tolist()
                conf_list = boxes.conf.tolist()
                cls_list = boxes.cls.tolist()

                for coords, score, cls_raw in zip(xyxy_list, conf_list, cls_list):
                    class_id = int(cls_raw)
                    class_name = str(names_map.get(class_id, f"class_{class_id}"))
                    if allowed_categories is not None and class_name not in allowed_categories:
                        continue

                    x1, y1, x2, y2 = (round(float(v), 2) for v in coords[:4])
                    confidence_val = round(float(score), 4)

                    frame_detections.append(
                        DetectedObjectRecord(
                            class_id=class_id,
                            class_name=class_name,
                            confidence=confidence_val,
                            bbox_x1=x1,
                            bbox_y1=y1,
                            bbox_x2=x2,
                            bbox_y2=y2,
                        )
                    )
                    class_counter[class_name] += 1
                    total_detections += 1

        if frame_detections:
            frames_with_detections += 1

        frame_records.append(
            FrameDetectionsRecord(
                frame_index=int(entry["frame_index"]),
                source_frame_index=int(entry["source_frame_index"]),
                timestamp_seconds=float(entry["timestamp_seconds"]),
                filename=filename,
                frame_width=frame_width,
                frame_height=frame_height,
                detections=frame_detections,
            )
        )

        del frame_img
        del results

        if progress_callback is not None:
            progress_callback(idx + 1, max(total_frames, 1))

    class_counts = dict(class_counter.most_common())
    detections_payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "video_id": video_id,
        "model_name": resolved_model_name,
        "device": "cpu",
        "image_size": imgsz,
        "confidence_threshold": conf,
        "total_detections": total_detections,
        "frames_with_detections": frames_with_detections,
        "class_counts": class_counts,
        "frames": [
            {
                "frame_index": frame_rec.frame_index,
                "source_frame_index": frame_rec.source_frame_index,
                "timestamp_seconds": frame_rec.timestamp_seconds,
                "filename": frame_rec.filename,
                "frame_width": frame_rec.frame_width,
                "frame_height": frame_rec.frame_height,
                "detections": [
                    {
                        "class_id": det.class_id,
                        "class_name": det.class_name,
                        "confidence": det.confidence,
                        "bbox": {
                            "x1": det.bbox_x1,
                            "y1": det.bbox_y1,
                            "x2": det.bbox_x2,
                            "y2": det.bbox_y2,
                        },
                    }
                    for det in frame_rec.detections
                ],
            }
            for frame_rec in frame_records
        ],
    }

    detections_path = analysis_dir / "detections.json"
    detections_path.write_text(json.dumps(detections_payload, indent=2), encoding="utf-8")

    return AnalysisDetectionResult(
        model_name=resolved_model_name,
        confidence_threshold=conf,
        image_size=imgsz,
        total_detections=total_detections,
        frames_with_detections=frames_with_detections,
        class_counts=class_counts,
        frames=frame_records,
        detections_path=detections_path,
    )
