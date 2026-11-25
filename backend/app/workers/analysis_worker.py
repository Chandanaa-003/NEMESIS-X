from datetime import datetime, timezone
import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import SessionLocal
from app.models.analysis import Analysis
from app.models.detection import Detection
from app.models.track import Track
from app.models.video import Video
from app.services.tracker import track_objects_in_analysis
from app.services.video_processor import extract_video_frames

logger = logging.getLogger(__name__)


def _resolve_safe_video_path(stored_filename: str) -> Path:
    """Resolve an uploaded video path strictly within the configured upload directory."""
    settings = get_settings()
    upload_dir = settings.resolved_upload_dir
    safe_name = Path(stored_filename).name
    candidate = (upload_dir / safe_name).resolve()
    if candidate.parent != upload_dir.resolve():
        raise ValueError("Invalid stored video path.")
    return candidate


def run_video_analysis_job(
    analysis_id: str,
    target_fps: float = 1.0,
    confidence_threshold: float | None = None,
) -> None:
    """Execute frame extraction, CPU YOLO detection, and ByteTrack tracking in one job."""
    settings = get_settings()
    db = SessionLocal()

    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis is None:
            return

        video = db.query(Video).filter(Video.id == analysis.video_id).first()
        if video is None:
            analysis.status = "failed"
            analysis.error_message = "Associated video record was not found."
            analysis.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        analysis.status = "processing"
        analysis.progress = 1
        analysis.started_at = datetime.now(timezone.utc)
        analysis.error_message = None
        video.status = "processing"
        db.commit()

        video_path = _resolve_safe_video_path(video.stored_filename)
        output_dir = settings.resolved_processed_dir / analysis.id

        # Stage 1 (1%..55%): Sequential OpenCV frame extraction
        def on_extract_progress(
            processed_frames: int,
            total_frames: int,
            progress_pct: int,
            sampling_interval: int,
        ) -> None:
            try:
                scaled_pct = min(55, max(1, int(progress_pct * 0.55)))
                analysis.processed_frames = processed_frames
                analysis.total_frames = total_frames
                analysis.progress = scaled_pct
                analysis.sampling_interval = sampling_interval
                db.commit()
            except SQLAlchemyError:
                db.rollback()

        extract_result = extract_video_frames(
            analysis_id=analysis.id,
            video_id=video.id,
            video_path=video_path,
            output_dir=output_dir,
            target_fps=target_fps,
            max_frames=settings.max_extracted_frames,
            max_width=settings.max_frame_width,
            jpeg_quality=settings.jpeg_quality,
            progress_callback=on_extract_progress,
        )

        video.duration_seconds = extract_result.duration_seconds
        video.width = extract_result.width
        video.height = extract_result.height
        analysis.total_frames = extract_result.total_frames
        analysis.processed_frames = extract_result.total_frames
        analysis.sampling_interval = extract_result.sampling_interval
        analysis.progress = 55
        db.commit()

        # Stage 2 (55%..98%): Single-frame CPU YOLO detection + ByteTrack temporal association
        last_track_pct = 55

        def on_track_progress(done_frames: int, total_extracted: int) -> None:
            nonlocal last_track_pct
            pct = 55 + int((done_frames / max(total_extracted, 1)) * 43)
            pct = min(98, max(55, pct))
            if pct - last_track_pct < 5 and done_frames < total_extracted:
                return
            last_track_pct = pct
            try:
                analysis.progress = pct
                db.commit()
            except SQLAlchemyError:
                db.rollback()

        tracking_result = track_objects_in_analysis(
            analysis_id=analysis.id,
            video_id=video.id,
            analysis_dir=output_dir,
            confidence_threshold=confidence_threshold,
            image_size=settings.detection_image_size,
            model_name=settings.yolo_model_name,
            tracker_config=settings.tracker_config,
            progress_callback=on_track_progress,
        )

        # Persist per-frame detections (with track_id) and temporal track summaries in SQLite
        db.query(Detection).filter(Detection.analysis_id == analysis.id).delete()
        db.query(Track).filter(Track.analysis_id == analysis.id).delete()

        detection_rows: list[Detection] = []
        for frame_rec in tracking_result.frames:
            for det in frame_rec.detections:
                detection_rows.append(
                    Detection(
                        analysis_id=analysis.id,
                        video_id=video.id,
                        frame_index=frame_rec.frame_index,
                        timestamp_seconds=frame_rec.timestamp_seconds,
                        track_id=det.track_id,
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bbox_x1=det.bbox_x1,
                        bbox_y1=det.bbox_y1,
                        bbox_x2=det.bbox_x2,
                        bbox_y2=det.bbox_y2,
                    )
                )
        if detection_rows:
            db.add_all(detection_rows)

        track_rows = [
            Track(
                analysis_id=analysis.id,
                video_id=video.id,
                track_id=t.track_id,
                class_id=t.class_id,
                class_name=t.class_name,
                first_seen_frame=t.first_seen_frame,
                last_seen_frame=t.last_seen_frame,
                first_seen_timestamp=t.first_seen_timestamp,
                last_seen_timestamp=t.last_seen_timestamp,
                duration_seconds=t.duration_seconds,
                frame_count=t.frame_count,
                avg_confidence=t.avg_confidence,
                max_confidence=t.max_confidence,
            )
            for t in tracking_result.tracks
        ]
        if track_rows:
            db.add_all(track_rows)

        video.status = "completed"
        analysis.status = "completed"
        analysis.progress = 100
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.exception("Video analysis job %s failed", analysis_id)
        db.rollback()
        try:
            failed_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if failed_analysis is not None:
                failed_analysis.status = "failed"
                failed_analysis.error_message = str(exc)[:500] or "Video analysis failed."
                failed_analysis.completed_at = datetime.now(timezone.utc)

                failed_video = (
                    db.query(Video).filter(Video.id == failed_analysis.video_id).first()
                )
                if failed_video is not None:
                    failed_video.status = "failed"
                db.commit()
        except SQLAlchemyError:
            db.rollback()
    finally:
        db.close()
