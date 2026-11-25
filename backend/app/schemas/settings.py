from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VoiceLanguage = Literal["english", "kannada", "bilingual"]


class UserVoiceSettingsResponse(BaseModel):
    """Persisted voice intelligence and alert priority settings for the current user."""

    model_config = ConfigDict(from_attributes=True)

    voice_language: VoiceLanguage
    voice_alerts_enabled: bool
    alert_volume: float
    announce_high_priority: bool
    announce_medium_priority: bool
    announce_low_priority: bool
    cooldown_seconds: int
    updated_at: datetime


class UserVoiceSettingsUpdate(BaseModel):
    """Validated payload to update authenticated user's voice alert preferences."""

    voice_language: VoiceLanguage
    voice_alerts_enabled: bool
    alert_volume: float = Field(..., ge=0.0, le=1.0)
    announce_high_priority: bool = True
    announce_medium_priority: bool = True
    announce_low_priority: bool = True
    cooldown_seconds: int = Field(default=30, ge=0, le=600)
