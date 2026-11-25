from datetime import datetime, timezone
import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import SessionLocal
from app.models.analysis import Analysis
from app.models.video import Video
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


def run_video_analysis_job(analysis_id: str, target_fps: float = 1.0) -> None:
    """Execute video preprocessing and frame extraction using an isolated DB session."""
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

        def on_progress(
            processed_frames: int,
            total_frames: int,
            progress_pct: int,
            sampling_interval: int,
        ) -> None:
            try:
                analysis.processed_frames = processed_frames
                analysis.total_frames = total_frames
                analysis.progress = progress_pct
                analysis.sampling_interval = sampling_interval
                db.commit()
            except SQLAlchemyError:
                db.rollback()

        result = extract_video_frames(
            analysis_id=analysis.id,
            video_id=video.id,
            video_path=video_path,
            output_dir=output_dir,
            target_fps=target_fps,
            max_frames=settings.max_extracted_frames,
            max_width=settings.max_frame_width,
            jpeg_quality=settings.jpeg_quality,
            progress_callback=on_progress,
        )

        video.duration_seconds = result.duration_seconds
        video.width = result.width
        video.height = result.height
        video.status = "completed"

        analysis.status = "completed"
        analysis.progress = 100
        analysis.total_frames = result.total_frames
        analysis.processed_frames = result.total_frames
        analysis.sampling_interval = result.sampling_interval
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.exception("Video analysis job %s failed", analysis_id)
        db.rollback()
        try:
            failed_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if failed_analysis is not None:
                failed_analysis.status = "failed"
                failed_analysis.error_message = str(exc)[:500] or "Video preprocessing failed."
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
