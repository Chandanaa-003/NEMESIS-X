from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
from typing import Any

import cv2

from app.config import get_settings
from app.services.detector import get_detection_model


@dataclass(frozen=True)
class TrackedDetectionRecord:
    """Single detected & tracked object within an extracted frame."""

    track_id: int | None
    class_id: int
    class_name: str
    confidence: float
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float


@dataclass(frozen=True)
class FrameTrackedDetectionsRecord:
    """Tracked detections and timing metadata for a single frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    frame_width: int
    frame_height: int
    detections: list[TrackedDetectionRecord]


@dataclass(frozen=True)
class TrackTimelinePoint:
    """Position and confidence snapshot of a tracked object at a given frame."""

    frame_index: int
    timestamp_seconds: float
    center_x: float
    center_y: float
    confidence: float
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float


@dataclass(frozen=True)
class ObjectTrackSummary:
    """Persistent temporal memory record for one tracked object across a video."""

    track_id: int
    class_id: int
    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    duration_seconds: float
    frame_count: int
    avg_confidence: float
    max_confidence: float
    timeline_points: list[TrackTimelinePoint]


@dataclass(frozen=True)
class AnalysisTrackingResult:
    """Aggregated detection, tracking, and temporal memory output."""

    model_name: str
    tracker_name: str
    confidence_threshold: float
    image_size: int
    total_detections: int
    frames_with_detections: int
    class_counts: dict[str, int]
    total_tracks: int
    tracks_by_class: dict[str, int]
    frames: list[FrameTrackedDetectionsRecord]
    tracks: list[ObjectTrackSummary]
    detections_path: Path
    tracks_path: Path


@dataclass
class _TrackAccumulator:
    track_id: int
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    class_votes: Counter[tuple[int, str]] = field(default_factory=Counter)
    confidences: list[float] = field(default_factory=list)
    timeline_points: list[TrackTimelinePoint] = field(default_factory=list)


TrackingProgressCallback = Callable[[int, int], None]

_tracker_lock = threading.Lock()


def _reset_predictor_trackers(model: Any) -> None:
    """Clear Ultralytics predictor tracker state so IDs never bleed across analyses."""
    predictor = getattr(model, "predictor", None)
    if predictor is not None and hasattr(predictor, "trackers"):
        try:
            del predictor.trackers
        except AttributeError:
            pass
    if predictor is not None:
        model.predictor = None


def track_objects_in_analysis(
    *,
    analysis_id: str,
    video_id: str,
    analysis_dir: Path,
    confidence_threshold: float | None = None,
    image_size: int | None = None,
    model_name: str | None = None,
    tracker_config: str | None = None,
    allowed_categories: frozenset[str] | None = None,
    progress_callback: TrackingProgressCallback | None = None,
) -> AnalysisTrackingResult:
    """Run CPU-only YOLO detection + ByteTrack across extracted frames one frame at a time."""
    settings = get_settings()
    conf = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.detection_confidence
    )
    imgsz = image_size if image_size is not None else settings.detection_image_size
    resolved_model_name = model_name or settings.yolo_model_name
    resolved_tracker = tracker_config or settings.tracker_config

    metadata_path = analysis_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError("Frame metadata.json was not found for object tracking.")

    raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    frame_entries = raw_meta.get("frames", [])
    frames_dir = analysis_dir / "frames"

    model = get_detection_model(resolved_model_name)

    frame_records: list[FrameTrackedDetectionsRecord] = []
    class_counter: Counter[str] = Counter()
    track_map: dict[int, _TrackAccumulator] = {}
    total_detections = 0
    frames_with_detections = 0
    total_frames = len(frame_entries)

    with _tracker_lock:
        _reset_predictor_trackers(model)
        try:
            for idx, entry in enumerate(frame_entries):
                filename = str(entry["filename"])
                frame_path = (frames_dir / Path(filename).name).resolve()
                if frame_path.parent != frames_dir.resolve() or not frame_path.exists():
                    continue

                frame_img = cv2.imread(str(frame_path))
                if frame_img is None:
                    continue

                frame_height, frame_width = frame_img.shape[:2]
                frame_index = int(entry["frame_index"])
                source_frame_index = int(entry["source_frame_index"])
                timestamp_seconds = float(entry["timestamp_seconds"])

                results = model.track(
                    source=frame_img,
                    persist=True,
                    tracker=resolved_tracker,
                    imgsz=imgsz,
                    conf=conf,
                    device="cpu",
                    verbose=False,
                )

                frame_detections: list[TrackedDetectionRecord] = []
                if results:
                    result = results[0]
                    names_map = result.names or {}
                    boxes = result.boxes
                    if boxes is not None and len(boxes) > 0:
                        xyxy_list = boxes.xyxy.tolist()
                        conf_list = boxes.conf.tolist()
                        cls_list = boxes.cls.tolist()
                        id_list = (
                            boxes.id.tolist()
                            if getattr(boxes, "id", None) is not None
                            else [None] * len(xyxy_list)
                        )

                        for coords, score, cls_raw, tid_raw in zip(
                            xyxy_list, conf_list, cls_list, id_list
                        ):
                            class_id = int(cls_raw)
                            class_name = str(names_map.get(class_id, f"class_{class_id}"))
                            if (
                                allowed_categories is not None
                                and class_name not in allowed_categories
                            ):
                                continue

                            track_id = int(tid_raw) if tid_raw is not None else None
                            x1, y1, x2, y2 = (round(float(v), 2) for v in coords[:4])
                            confidence_val = round(float(score), 4)

                            frame_detections.append(
                                TrackedDetectionRecord(
                                    track_id=track_id,
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

                            if track_id is not None:
                                cx = round((x1 + x2) / 2.0, 2)
                                cy = round((y1 + y2) / 2.0, 2)
                                acc = track_map.get(track_id)
                                if acc is None:
                                    acc = _TrackAccumulator(
                                        track_id=track_id,
                                        first_seen_frame=frame_index,
                                        last_seen_frame=frame_index,
                                        first_seen_timestamp=timestamp_seconds,
                                        last_seen_timestamp=timestamp_seconds,
                                    )
                                    track_map[track_id] = acc
                                else:
                                    acc.last_seen_frame = max(acc.last_seen_frame, frame_index)
                                    acc.last_seen_timestamp = max(
                                        acc.last_seen_timestamp, timestamp_seconds
                                    )

                                acc.class_votes[(class_id, class_name)] += 1
                                acc.confidences.append(confidence_val)
                                acc.timeline_points.append(
                                    TrackTimelinePoint(
                                        frame_index=frame_index,
                                        timestamp_seconds=timestamp_seconds,
                                        center_x=cx,
                                        center_y=cy,
                                        confidence=confidence_val,
                                        bbox_x1=x1,
                                        bbox_y1=y1,
                                        bbox_x2=x2,
                                        bbox_y2=y2,
                                    )
                                )

                if frame_detections:
                    frames_with_detections += 1

                frame_records.append(
                    FrameTrackedDetectionsRecord(
                        frame_index=frame_index,
                        source_frame_index=source_frame_index,
                        timestamp_seconds=timestamp_seconds,
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
        finally:
            _reset_predictor_trackers(model)

    track_summaries: list[ObjectTrackSummary] = []
    track_class_counter: Counter[str] = Counter()

    for acc in sorted(
        track_map.values(),
        key=lambda item: (item.first_seen_timestamp, item.track_id),
    ):
        (dominant_cls_id, dominant_cls_name), _ = acc.class_votes.most_common(1)[0]
        duration = round(max(0.0, acc.last_seen_timestamp - acc.first_seen_timestamp), 3)
        avg_conf = round(sum(acc.confidences) / max(len(acc.confidences), 1), 4)
        max_conf = round(max(acc.confidences), 4)

        track_class_counter[dominant_cls_name] += 1
        track_summaries.append(
            ObjectTrackSummary(
                track_id=acc.track_id,
                class_id=dominant_cls_id,
                class_name=dominant_cls_name,
                first_seen_frame=acc.first_seen_frame,
                last_seen_frame=acc.last_seen_frame,
                first_seen_timestamp=acc.first_seen_timestamp,
                last_seen_timestamp=acc.last_seen_timestamp,
                duration_seconds=duration,
                frame_count=len(acc.timeline_points),
                avg_confidence=avg_conf,
                max_confidence=max_conf,
                timeline_points=acc.timeline_points,
            )
        )

    class_counts = dict(class_counter.most_common())
    tracks_by_class = dict(track_class_counter.most_common())

    detections_payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "video_id": video_id,
        "model_name": resolved_model_name,
        "tracker_name": "bytetrack",
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
                        "track_id": det.track_id,
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

    tracks_payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "video_id": video_id,
        "model_name": resolved_model_name,
        "tracker_name": "bytetrack",
        "total_tracks": len(track_summaries),
        "tracks_by_class": tracks_by_class,
        "tracks": [
            {
                "track_id": t.track_id,
                "class_id": t.class_id,
                "class_name": t.class_name,
                "first_seen_frame": t.first_seen_frame,
                "last_seen_frame": t.last_seen_frame,
                "first_seen_timestamp": t.first_seen_timestamp,
                "last_seen_timestamp": t.last_seen_timestamp,
                "duration_seconds": t.duration_seconds,
                "frame_count": t.frame_count,
                "avg_confidence": t.avg_confidence,
                "max_confidence": t.max_confidence,
                "timeline_points": [
                    {
                        "frame_index": pt.frame_index,
                        "timestamp_seconds": pt.timestamp_seconds,
                        "center_x": pt.center_x,
                        "center_y": pt.center_y,
                        "confidence": pt.confidence,
                        "bbox": {
                            "x1": pt.bbox_x1,
                            "y1": pt.bbox_y1,
                            "x2": pt.bbox_x2,
                            "y2": pt.bbox_y2,
                        },
                    }
                    for pt in t.timeline_points
                ],
            }
            for t in track_summaries
        ],
    }

    detections_path = analysis_dir / "detections.json"
    detections_path.write_text(json.dumps(detections_payload, indent=2), encoding="utf-8")

    tracks_path = analysis_dir / "tracks.json"
    tracks_path.write_text(json.dumps(tracks_payload, indent=2), encoding="utf-8")

    return AnalysisTrackingResult(
        model_name=resolved_model_name,
        tracker_name="bytetrack",
        confidence_threshold=conf,
        image_size=imgsz,
        total_detections=total_detections,
        frames_with_detections=frames_with_detections,
        class_counts=class_counts,
        total_tracks=len(track_summaries),
        tracks_by_class=tracks_by_class,
        frames=frame_records,
        tracks=track_summaries,
        detections_path=detections_path,
        tracks_path=tracks_path,
    )
