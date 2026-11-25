from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventSeverity = Literal["low", "medium", "high"]
EventCategory = Literal[
    "people_movement",
    "object_interactions",
    "possible_unattended_objects",
    "other_activities",
]


class EventEvidenceFrame(BaseModel):
    """Reference to an extracted frame supporting a discovered event."""

    frame_index: int
    timestamp_seconds: float
    filename: str
    url: str


class EventExplanation(BaseModel):
    """Structured factual explanation separating observations from rule inference."""

    observed_sequence: list[str]
    why_flagged: str
    evidence_timestamps: list[float]
    confidence_note: str
    requires_human_review: bool
    person_track_id: int | None = None
    object_track_id: int | None = None
    association_uncertainty: str | None = None
    anomaly_score: dict[str, Any] | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    zone_type: str | None = None
    duration_seconds: float | None = None
    alerts_enabled: bool = True
    voice_alerts_enabled: bool = True


class EventRecordInfo(BaseModel):
    """Public representation of a discovered event."""

    id: str
    analysis_id: str
    event_type: str
    category: EventCategory
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int]
    confidence: float
    severity: EventSeverity
    evidence_frame_ids: list[int]
    evidence_frames: list[EventEvidenceFrame] = Field(default_factory=list)
    explanation: EventExplanation
    created_at: datetime


class ImportantTimestampInfo(BaseModel):
    """Key event timestamp highlight in the analysis summary."""

    timestamp_seconds: float
    event_title: str
    severity: EventSeverity


class EventSummaryInfo(BaseModel):
    """High-level summary of detections, tracks, and discovered events."""

    total_detected_objects: int
    total_unique_tracks: int
    total_discovered_events: int
    most_common_categories: dict[str, int]
    important_timestamps: list[ImportantTimestampInfo]
    events_requiring_review: int
    summary_message: str


class EventDiscoveryResponse(BaseModel):
    """Response returned by event discovery and event listing endpoints."""

    analysis_id: str
    video_id: str
    summary: EventSummaryInfo
    events: list[EventRecordInfo]
