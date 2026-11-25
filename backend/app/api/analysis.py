import json
from pathlib import Path
import re

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.user import User
from app.models.video import Video
from app.schemas.analysis import (
    AnalysisResultsResponse,
    AnalysisStartRequest,
    AnalysisStartResponse,
    AnalysisStatusResponse,
    ExtractedFrameInfo,
)
from app.workers.analysis_worker import run_video_analysis_job

router = APIRouter(prefix="/analysis", tags=["Analysis"])

SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4}\.jpg$")


def _get_owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
    """Fetch an analysis record only if it belongs to the authenticated user."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
        .first()
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )
    return analysis


@router.post(
    "/{video_id}/start",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue video preprocessing and frame extraction",
)
def start_analysis(
    video_id: str,
    background_tasks: BackgroundTasks,
    payload: AnalysisStartRequest = Body(default_factory=AnalysisStartRequest),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStartResponse:
    """Start a background frame-extraction analysis job for an owned uploaded video."""
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.user_id == current_user.id)
        .first()
    )
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    active_job = (
        db.query(Analysis)
        .filter(
            Analysis.video_id == video.id,
            Analysis.status.in_(["queued", "processing"]),
        )
        .first()
    )
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An analysis job is already in progress for this video.",
        )

    analysis = Analysis(
        video_id=video.id,
        user_id=current_user.id,
        status="queued",
        progress=0,
        total_frames=0,
        processed_frames=0,
        sampling_interval=1,
    )
    video.status = "queued"

    try:
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while queuing analysis job.",
        ) from exc

    background_tasks.add_task(run_video_analysis_job, analysis.id, payload.target_fps)

    return AnalysisStartResponse(
        analysis_id=analysis.id,
        video_id=video.id,
        status=analysis.status,  # type: ignore[arg-type]
    )


@router.get(
    "/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Get analysis job status and progress",
)
def get_analysis_status(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Return current preprocessing status and progress for an owned analysis job."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        progress=analysis.progress,
        total_frames=analysis.total_frames,
        processed_frames=analysis.processed_frames,
        sampling_interval=analysis.sampling_interval,
        error_message=analysis.error_message,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/{analysis_id}/results",
    response_model=AnalysisResultsResponse,
    summary="Get preprocessing summary and extracted frames",
)
def get_analysis_results(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResultsResponse:
    """Return extracted frame metadata and summary for an owned analysis job."""
    settings = get_settings()
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)

    metadata_path = settings.resolved_processed_dir / analysis.id / "metadata.json"
    frames: list[ExtractedFrameInfo] = []
    summary: dict[str, object] = {
        "total_frames": analysis.total_frames,
        "processed_frames": analysis.processed_frames,
        "sampling_interval": analysis.sampling_interval,
        "extracted_count": 0,
    }

    if analysis.status == "completed" and metadata_path.exists():
        try:
            raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read analysis metadata.",
            ) from exc

        summary = {
            "duration_seconds": raw_meta.get("duration_seconds"),
            "original_dimensions": raw_meta.get("original_dimensions"),
            "fps": raw_meta.get("fps"),
            "total_frames": raw_meta.get("total_frames", analysis.total_frames),
            "sampling_interval": raw_meta.get("sampling_interval", analysis.sampling_interval),
            "max_width_applied": raw_meta.get("max_width_applied"),
            "extracted_count": raw_meta.get("extracted_count", 0),
        }

        api_prefix = settings.api_v1_prefix
        for item in raw_meta.get("frames", []):
            filename = str(item.get("filename", ""))
            if not SAFE_FRAME_FILENAME_RE.match(filename):
                continue
            frames.append(
                ExtractedFrameInfo(
                    frame_index=int(item["frame_index"]),
                    source_frame_index=int(item["source_frame_index"]),
                    timestamp_seconds=float(item["timestamp_seconds"]),
                    filename=filename,
                    url=f"{api_prefix}/analysis/{analysis.id}/frames/{filename}",
                )
            )

    return AnalysisResultsResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        progress=analysis.progress,
        sampling_interval=analysis.sampling_interval,
        error_message=analysis.error_message,
        summary=summary,
        frames=frames,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/{analysis_id}/frames/{filename}",
    summary="Fetch an extracted JPEG frame for an owned analysis",
)
def get_extracted_frame_image(
    analysis_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve an extracted frame JPEG strictly inside the owned analysis frames folder."""
    if not SAFE_FRAME_FILENAME_RE.match(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid frame filename.",
        )

    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    settings = get_settings()
    frames_dir = (settings.resolved_processed_dir / analysis.id / "frames").resolve()
    target_path = (frames_dir / Path(filename).name).resolve()

    if target_path.parent != frames_dir or not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted frame not found.",
        )

    return FileResponse(path=target_path, media_type="image/jpeg")
