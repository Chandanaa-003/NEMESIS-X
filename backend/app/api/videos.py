from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoPlaybackPreparationResponse, VideoResponse
from app.services.video_storage import cleanup_saved_file, stream_and_validate_video
from app.services.video_playback import PlaybackJobState, video_playback_jobs

router = APIRouter(prefix="/videos", tags=["Videos"])


def _owned_video(video_id: str, user_id: int, db: Session) -> Video:
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.user_id == user_id)
        .first()
    )
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    return video


def _uploaded_video_path(video: Video) -> Path:
    upload_dir = get_settings().resolved_upload_dir.resolve()
    safe_name = Path(video.stored_filename).name
    target_path = (upload_dir / safe_name).resolve()
    if target_path.parent != upload_dir or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded video file not found on disk.",
        )
    return target_path


def _playback_response(state: PlaybackJobState) -> VideoPlaybackPreparationResponse:
    return VideoPlaybackPreparationResponse(
        status=state.status,
        progress=state.progress,
        message=state.message,
    )


@router.post(
    "/upload",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a video file",
)
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoResponse:
    """Validate, stream to disk, and register a video upload for the authenticated user."""
    saved = await stream_and_validate_video(file)

    video = Video(
        user_id=current_user.id,
        original_filename=saved.original_filename,
        stored_filename=saved.stored_filename,
        file_path=saved.file_path,
        file_size=saved.file_size,
        mime_type=saved.mime_type,
        status="uploaded",
    )

    try:
        db.add(video)
        db.commit()
        db.refresh(video)
    except SQLAlchemyError as exc:
        db.rollback()
        cleanup_saved_file(saved.absolute_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving video metadata.",
        ) from exc

    return VideoResponse.model_validate(video)


@router.get(
    "",
    response_model=list[VideoResponse],
    summary="List uploaded videos for the current user",
)
def list_user_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VideoResponse]:
    """Return uploaded videos belonging to the authenticated user."""
    videos = (
        db.query(Video)
        .filter(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    return [VideoResponse.model_validate(item) for item in videos]


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get metadata for a specific uploaded video",
)
def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoResponse:
    """Fetch a single video owned by the authenticated user."""
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
    return VideoResponse.model_validate(video)


@router.get(
    "/{video_id}/stream",
    summary="Stream or download an uploaded video owned by the current user",
)
def stream_owned_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve an uploaded video file strictly within the configured uploads directory."""
    video = _owned_video(video_id, current_user.id, db)
    target_path = _uploaded_video_path(video)
    return FileResponse(
        path=target_path,
        media_type=video.mime_type or "video/mp4",
        filename=video.original_filename,
    )


@router.post(
    "/{video_id}/playback/prepare",
    response_model=VideoPlaybackPreparationResponse,
    summary="Prepare a browser-compatible playback source",
)
def prepare_owned_video_playback(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoPlaybackPreparationResponse:
    """Inspect an owned upload and convert it only when browser compatibility requires it."""
    video = _owned_video(video_id, current_user.id, db)
    source_path = _uploaded_video_path(video)
    state = video_playback_jobs.prepare(
        video.id,
        source_path,
        get_settings().resolved_playback_dir,
    )
    return _playback_response(state)


@router.get(
    "/{video_id}/playback/status",
    response_model=VideoPlaybackPreparationResponse,
    summary="Get browser playback preparation progress",
)
def get_owned_video_playback_status(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoPlaybackPreparationResponse:
    """Return conversion state only for videos owned by the authenticated user."""
    _owned_video(video_id, current_user.id, db)
    return _playback_response(video_playback_jobs.get_status(video_id))


@router.get(
    "/{video_id}/playback",
    summary="Stream the original or prepared browser-compatible MP4",
)
def stream_owned_video_playback(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve the validated playback source without modifying the uploaded original."""
    video = _owned_video(video_id, current_user.id, db)
    playback_path = video_playback_jobs.get_ready_path(video_id)
    if playback_path is None:
        state = video_playback_jobs.get_status(video_id)
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if state.status == "failed"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=state.message)

    return FileResponse(
        path=playback_path,
        media_type="video/mp4",
        filename=f"{Path(video.original_filename).stem}.playback.mp4",
    )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded video",
)
def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove an uploaded video record and delete its stored file."""
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

    project_root = BACKEND_DIR.parent
    stored_path = (project_root / video.file_path).resolve()

    try:
        db.delete(video)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting video.",
        ) from exc

    if stored_path.parent == (project_root / "storage" / "uploads").resolve():
        cleanup_saved_file(stored_path)
