from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VideoStatus = Literal["uploaded", "queued", "processing", "completed", "failed"]
PlaybackPreparationStatus = Literal["not_started", "converting", "ready", "failed"]


class VideoResponse(BaseModel):
    """Public metadata returned for an uploaded video."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int
    mime_type: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    status: VideoStatus
    created_at: datetime


class VideoPlaybackPreparationResponse(BaseModel):
    status: PlaybackPreparationStatus
    progress: int
    message: str
