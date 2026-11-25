from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse
from app.services.video_storage import cleanup_saved_file, stream_and_validate_video

router = APIRouter(prefix="/videos", tags=["Videos"])


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
