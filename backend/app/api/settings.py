from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import UserVoiceSettingsResponse, UserVoiceSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


def _get_or_create_settings(user_id: int, db: Session) -> UserSettings:
    record = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if record is not None:
        return record

    record = UserSettings(user_id=user_id)
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while initializing user settings.",
        ) from exc
    return record


@router.get(
    "",
    response_model=UserVoiceSettingsResponse,
    summary="Get voice intelligence and alert settings for the authenticated user",
)
def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserVoiceSettingsResponse:
    """Fetch persisted voice and alert preferences for the signed-in user."""
    record = _get_or_create_settings(current_user.id, db)
    return UserVoiceSettingsResponse.model_validate(record)


@router.put(
    "",
    response_model=UserVoiceSettingsResponse,
    summary="Update voice intelligence and alert settings for the authenticated user",
)
def update_user_settings(
    payload: UserVoiceSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserVoiceSettingsResponse:
    """Persist voice language, volume, enablement, and priority settings in SQLite."""
    record = _get_or_create_settings(current_user.id, db)

    record.voice_language = payload.voice_language
    record.voice_alerts_enabled = payload.voice_alerts_enabled
    record.alert_volume = round(float(payload.alert_volume), 2)
    record.announce_high_priority = payload.announce_high_priority
    record.announce_medium_priority = payload.announce_medium_priority
    record.announce_low_priority = payload.announce_low_priority
    record.cooldown_seconds = payload.cooldown_seconds
    record.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(record)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving user settings.",
        ) from exc

    return UserVoiceSettingsResponse.model_validate(record)
