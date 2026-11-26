from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import BoundingBoxInfo, TrackSummaryInfo

LiveSessionStatus = Literal["active", "stopped", "error"]


class LiveSessionStartRequest(BaseModel):
    """Configuration for starting a live webcam monitoring session."""

    confidence_threshold: float = Field(default=0.40, ge=0.10, le=0.95)
    image_size: int = Field(default=416, ge=256, le=640)


class LiveSessionStartResponse(BaseModel):
    """Response returned when a new live monitoring session starts."""

    session_id: str
    status: LiveSessionStatus
    confidence_threshold: float
    image_size: int
    started_at: datetime


class LiveDetectionInfo(BaseModel):
    """Single tracked object detection returned for the current live frame."""

    track_id: int | None = None
    track_code: str | None = None
    identity_id: str | None = None
    identity_code: str | None = None
    identity_status: Literal["confirmed", "probable", "unknown"] | None = None
    identity_confidence: float | None = None
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBoxInfo


class LiveEventInfo(BaseModel):
    """Discovered event produced from real temporal trajectories during live monitoring."""

    id: str
    session_id: str
    event_type: str
    category: str
    title: str
    description: str
    timestamp_seconds: float
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int] = Field(default_factory=list)
    confidence: float
    severity: str
    frame_index: int
    requires_human_review: bool = False
    alerts_enabled: bool = True
    voice_alerts_enabled: bool = True
    zone_id: str | None = None
    zone_name: str | None = None
    why_flagged: str = ""
    observed_sequence: list[str] = Field(default_factory=list)
    snapshot_url: str | None = None
    created_at: datetime


class LiveFrameProcessResponse(BaseModel):
    """Real detections, ByteTrack tracks, and newly discovered events for one live frame."""

    session_id: str
    status: LiveSessionStatus
    frame_index: int
    timestamp_seconds: float
    frame_width: int
    frame_height: int
    frames_processed: int
    total_detections: int
    unique_tracks_count: int
    events_discovered_count: int
    processing_ms: float
    detections: list[LiveDetectionInfo] = Field(default_factory=list)
    active_tracks: list[TrackSummaryInfo] = Field(default_factory=list)
    new_events: list[LiveEventInfo] = Field(default_factory=list)


class LiveSessionStatusResponse(BaseModel):
    """Current live monitoring session metrics, active tracks, and discovered events."""

    session_id: str
    status: LiveSessionStatus
    confidence_threshold: float
    image_size: int
    frames_processed: int
    total_detections: int
    unique_tracks_count: int
    events_discovered_count: int
    duration_seconds: float
    frame_width: int | None = None
    frame_height: int | None = None
    started_at: datetime
    last_frame_at: datetime | None = None
    stopped_at: datetime | None = None
    active_tracks: list[TrackSummaryInfo] = Field(default_factory=list)
    events: list[LiveEventInfo] = Field(default_factory=list)
