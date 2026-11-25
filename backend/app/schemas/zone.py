from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ZoneType = Literal["restricted", "safe", "monitoring", "entry", "exit"]


class ZoneSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_frames: int = Field(default=2, ge=1, le=30)
    cooldown_seconds: float = Field(default=10.0, ge=0, le=3600)
    loiter_seconds: float = Field(default=30.0, gt=0, le=86400)
    restricted_group_threshold: int = Field(default=2, ge=2, le=50)
    alerts_enabled: bool = True
    voice_alerts_enabled: bool = True


class ZoneCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str | None = None
    live_session_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    zone_type: ZoneType
    color: str = Field(default="#2563EB", pattern=r"^#[0-9A-Fa-f]{6}$")
    polygon: list[list[float]] = Field(min_length=3, max_length=100)
    settings: ZoneSettings = Field(default_factory=ZoneSettings)

    @model_validator(mode="after")
    def validate_source(self) -> "ZoneCreateRequest":
        if (self.video_id is None) == (self.live_session_id is None):
            raise ValueError("Exactly one of video_id or live_session_id is required.")
        return self

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, polygon: list[list[float]]) -> list[list[float]]:
        for point in polygon:
            if len(point) != 2 or any(not 0 <= coordinate <= 1 for coordinate in point):
                raise ValueError("Polygon points must contain normalized x/y values from 0 to 1.")
        if len({(point[0], point[1]) for point in polygon}) < 3:
            raise ValueError("A polygon must contain at least three distinct points.")
        return polygon


class ZoneUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    zone_type: ZoneType | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    polygon: list[list[float]] | None = Field(default=None, min_length=3, max_length=100)
    settings: ZoneSettings | None = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, polygon: list[list[float]] | None) -> list[list[float]] | None:
        if polygon is None:
            return None
        for point in polygon:
            if len(point) != 2 or any(not 0 <= coordinate <= 1 for coordinate in point):
                raise ValueError("Polygon points must contain normalized x/y values from 0 to 1.")
        if len({(point[0], point[1]) for point in polygon}) < 3:
            raise ValueError("A polygon must contain at least three distinct points.")
        return polygon


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    video_id: str | None
    live_session_id: str | None
    name: str
    zone_type: ZoneType
    color: str
    polygon: list[list[float]]
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ZoneEventResponse(BaseModel):
    id: str
    source_id: str
    event_type: str
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    start_timestamp: float
    end_timestamp: float
    duration_seconds: float
    involved_track_ids: list[int]
    confidence: float
    severity: str
    description: str
    evidence_frame_ids: list[int] = Field(default_factory=list)
    evidence_reference: str | None = None
    voice_alerts_enabled: bool = True
    created_at: datetime


class ZoneActivitySummary(BaseModel):
    source_id: str
    total_events: int
    events_by_type: dict[str, int]
    zones: list[dict[str, Any]]
