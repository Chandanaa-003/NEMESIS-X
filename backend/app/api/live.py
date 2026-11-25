from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.live_session import LiveEvent, LiveSession
from app.models.user import User
from app.schemas.live import (
    LiveFrameProcessResponse,
    LiveSessionStartRequest,
    LiveSessionStartResponse,
    LiveSessionStatusResponse,
)
from app.services.live_monitor import (
    get_live_session_status_payload,
    process_live_frame,
    start_live_session,
    stop_live_session,
)

router = APIRouter(prefix="/live", tags=["Live Monitoring"])


def _get_owned_live_session(session_id: str, user_id: int, db: Session) -> LiveSession:
    session_row = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == user_id)
        .first()
    )
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live monitoring session not found.",
        )
    return session_row


@router.post(
    "/start",
    response_model=LiveSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new live webcam monitoring session",
)
def start_live_monitoring(
    payload: LiveSessionStartRequest = Body(default_factory=LiveSessionStartRequest),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiveSessionStartResponse:
    """Create a unique authenticated live monitoring session with isolated ByteTrack state."""
    try:
        return start_live_session(
            user_id=current_user.id,
            confidence_threshold=payload.confidence_threshold,
            image_size=payload.image_size,
            db=db,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/{session_id}/frame",
    response_model=LiveFrameProcessResponse,
    summary="Process one captured webcam JPEG frame for detection, tracking, and events",
)
async def process_live_monitoring_frame(
    session_id: str,
    file: UploadFile = File(...),
    timestamp_seconds: float | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiveFrameProcessResponse:
    """Analyze one live webcam frame using the shared YOLO model and session ByteTrack."""
    session_row = _get_owned_live_session(session_id, current_user.id, db)
    if session_row.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This live monitoring session has already stopped.",
        )

    frame_bytes = await file.read()
    try:
        return process_live_frame(
            session_row=session_row,
            frame_bytes=frame_bytes,
            timestamp_seconds=timestamp_seconds,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{session_id}/stop",
    response_model=LiveSessionStatusResponse,
    summary="Stop an active live monitoring session and release tracker resources",
)
def stop_live_monitoring(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiveSessionStatusResponse:
    """Stop monitoring and clean up in-memory tracker/trajectory state."""
    session_row = _get_owned_live_session(session_id, current_user.id, db)
    return stop_live_session(session_row=session_row, db=db)


@router.get(
    "/{session_id}/status",
    response_model=LiveSessionStatusResponse,
    summary="Get live monitoring session status, counts, active tracks, and discovered events",
)
def get_live_monitoring_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiveSessionStatusResponse:
    """Return status, metrics, tracks, and events for an owned live monitoring session."""
    session_row = _get_owned_live_session(session_id, current_user.id, db)
    return get_live_session_status_payload(session_row=session_row, db=db)


@router.get(
    "/{session_id}/events/{event_id}/snapshot",
    summary="Fetch annotated JPEG snapshot captured for a live monitoring event",
)
def get_live_event_snapshot(
    session_id: str,
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve an annotated evidence snapshot owned by the authenticated user."""
    _get_owned_live_session(session_id, current_user.id, db)
    event_row = (
        db.query(LiveEvent)
        .filter(
            LiveEvent.id == event_id,
            LiveEvent.session_id == session_id,
            LiveEvent.user_id == current_user.id,
        )
        .first()
    )
    if event_row is None or not event_row.snapshot_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live event snapshot not found.",
        )

    live_root = get_settings().resolved_live_dir.resolve()
    target_path = (BACKEND_DIR.parent / event_row.snapshot_path).resolve()
    try:
        target_path.relative_to(live_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid snapshot storage path.",
        ) from exc

    if not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live event snapshot file missing on disk.",
        )

    return FileResponse(path=target_path, media_type="image/jpeg")
