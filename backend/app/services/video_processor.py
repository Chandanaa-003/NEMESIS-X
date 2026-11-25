from collections.abc import Callable
from dataclasses import dataclass
import json
import math
from pathlib import Path

import cv2


@dataclass(frozen=True)
class ExtractedFrameRecord:
    """Metadata for one extracted JPEG frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str


@dataclass(frozen=True)
class VideoProcessingResult:
    """Summary returned after preprocessing and frame extraction complete."""

    duration_seconds: float | None
    width: int
    height: int
    fps: float
    total_frames: int
    sampling_interval: int
    extracted_frames: list[ExtractedFrameRecord]
    metadata_path: Path


ProgressCallback = Callable[[int, int, int, int, int], None]


def _resize_to_max_width(frame, max_width: int):
    """Resize a frame proportionally if its width exceeds max_width."""
    height, width = frame.shape[:2]
    if width <= max_width or width <= 0:
        return frame
    scale = max_width / float(width)
    target_height = max(1, int(round(height * scale)))
    return cv2.resize(frame, (max_width, target_height), interpolation=cv2.INTER_AREA)


def extract_video_frames(
    *,
    analysis_id: str,
    video_id: str,
    video_path: Path,
    output_dir: Path,
    target_fps: float = 1.0,
    max_frames: int = 300,
    max_width: int = 640,
    jpeg_quality: int = 85,
    progress_callback: ProgressCallback | None = None,
) -> VideoProcessingResult:
    """Sequentially decode a video and extract bounded, timestamped JPEG frames."""
    if not video_path.exists():
        raise FileNotFoundError("Uploaded video file could not be found on disk.")

    frames_dir = output_dir / "frames"
    try:
        frames_dir.mkdir(parents=True, exist_ok=True)
        write_probe = frames_dir / ".write_check"
        write_probe.write_text("ok", encoding="utf-8")
        write_probe.unlink(missing_ok=True)
    except OSError as exc:
        raise OSError(f"Output frames directory '{frames_dir}' is not writable.") from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("Unable to open video stream. The file may be corrupted or unsupported.")

    extracted: list[ExtractedFrameRecord] = []

    try:
        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            raise ValueError(
                "Unable to decode video frames. The file may be empty, corrupted, or use an unsupported codec."
            )

        raw_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = raw_fps if math.isfinite(raw_fps) and raw_fps > 0 else 30.0

        frame_height, frame_width = first_frame.shape[:2]
        prop_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        prop_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        width = prop_width if prop_width > 0 else frame_width
        height = prop_height if prop_height > 0 else frame_height

        raw_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        estimated_total = raw_count if raw_count > 0 else 1

        base_interval = max(1, round(fps / target_fps))
        if raw_count > 0 and (raw_count / base_interval) > max_frames:
            sampling_interval = max(base_interval, math.ceil(raw_count / max_frames))
        else:
            sampling_interval = base_interval

        def save_sampled_frame(frame_mat, source_idx: int, pos_msec: float) -> None:
            extracted_idx = len(extracted)
            filename = f"frame_{extracted_idx:04d}.jpg"
            target_file = frames_dir / filename
            resized = _resize_to_max_width(frame_mat, max_width)
            written = cv2.imwrite(
                str(target_file),
                resized,
                [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
            )
            if not written:
                raise OSError(f"Failed to write extracted frame '{filename}'.")

            if source_idx == 0:
                timestamp_sec = 0.0
            elif math.isfinite(pos_msec) and pos_msec > 0:
                timestamp_sec = round(pos_msec / 1000.0, 3)
            else:
                timestamp_sec = round(source_idx / fps, 3)

            extracted.append(
                ExtractedFrameRecord(
                    frame_index=extracted_idx,
                    source_frame_index=source_idx,
                    timestamp_seconds=timestamp_sec,
                    filename=filename,
                )
            )

        # Save frame 0 first, then read the rest sequentially without buffering frames in RAM.
        first_pos_msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
        save_sampled_frame(first_frame, 0, first_pos_msec)
        del first_frame

        source_idx = 0
        last_reported_pct = -1

        if progress_callback is not None:
            pct = min(95, max(1, int((1 / max(estimated_total, 1)) * 100)))
            progress_callback(1, estimated_total, pct, sampling_interval, len(extracted))
            last_reported_pct = pct

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            source_idx += 1
            if source_idx % sampling_interval == 0 and len(extracted) < max_frames:
                pos_msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                save_sampled_frame(frame, source_idx, pos_msec)

            del frame

            processed_count = source_idx + 1
            denom = max(estimated_total, processed_count)
            pct = min(95, max(1, int((processed_count / denom) * 100)))
            if progress_callback is not None and (pct - last_reported_pct >= 5):
                progress_callback(processed_count, denom, pct, sampling_interval, len(extracted))
                last_reported_pct = pct

        if len(extracted) == 0:
            raise ValueError("No frames could be extracted from the uploaded video.")

        actual_total_frames = source_idx + 1
        duration_seconds = round(actual_total_frames / fps, 3) if fps > 0 else None

        metadata_payload = {
            "analysis_id": analysis_id,
            "video_id": video_id,
            "original_dimensions": {"width": width, "height": height},
            "fps": round(fps, 3),
            "duration_seconds": duration_seconds,
            "total_frames": actual_total_frames,
            "sampling_interval": sampling_interval,
            "max_width_applied": min(width, max_width),
            "extracted_count": len(extracted),
            "frames": [
                {
                    "frame_index": item.frame_index,
                    "source_frame_index": item.source_frame_index,
                    "timestamp_seconds": item.timestamp_seconds,
                    "filename": item.filename,
                }
                for item in extracted
            ],
        }

        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata_payload, indent=2), encoding="utf-8")

        return VideoProcessingResult(
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            fps=round(fps, 3),
            total_frames=actual_total_frames,
            sampling_interval=sampling_interval,
            extracted_frames=extracted,
            metadata_path=metadata_path,
        )
    finally:
        cap.release()
