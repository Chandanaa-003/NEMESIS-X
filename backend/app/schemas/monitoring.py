from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

MonitoringSessionType = Literal["recorded", "live"]


class MonitoringHistoryItem(BaseModel):
    """Unified monitoring session item across recorded video analysis and live webcam monitoring."""

    session_id: str
    session_type: MonitoringSessionType
    name: str
    video_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    status: str
    total_detected_objects: int = 0
    unique_tracked_objects: int = 0
    events_discovered: int = 0
    high_priority_events: int = 0
    created_at: datetime


class MonitoringHistoryResponse(BaseModel):
    """Paginated monitoring history response."""

    items: list[MonitoringHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ObjectClassCount(BaseModel):
    class_name: str
    count: int


class TimelineTrendPoint(BaseModel):
    date: str
    sessions_count: int = 0
    events_count: int = 0
    high_priority_count: int = 0


class IntelligenceAnalyticsResponse(BaseModel):
    """Aggregated intelligence analytics computed from actual database records."""

    total_sessions: int = 0
    recorded_sessions_count: int = 0
    live_sessions_count: int = 0
    completed_analyses_count: int = 0
    failed_analyses_count: int = 0
    total_duration_seconds: float = 0.0
    avg_processing_duration_seconds: float = 0.0
    total_frames_processed: int = 0
    total_detections: int = 0
    total_unique_tracks: int = 0
    total_events: int = 0
    anomaly_events: int = 0
    high_priority_events: int = 0
    medium_priority_events: int = 0
    low_priority_events: int = 0
    events_by_category: dict[str, int] = Field(default_factory=dict)
    events_by_severity: dict[str, int] = Field(default_factory=dict)
    top_object_classes: list[ObjectClassCount] = Field(default_factory=list)
    timeline_trends: list[TimelineTrendPoint] = Field(default_factory=list)
    session_status_breakdown: dict[str, int] = Field(default_factory=dict)


class SessionEventDetail(BaseModel):
    id: str
    event_type: str
    category: str
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int] = Field(default_factory=list)
    confidence: float
    severity: str
    why_flagged: str = ""
    observed_sequence: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    evidence_image_urls: list[str] = Field(default_factory=list)
    created_at: datetime


class SessionEvidenceDetail(BaseModel):
    id: str
    event_id: str | None = None
    frame_number: int = 0
    timestamp_seconds: float = 0.0
    evidence_type: str = "annotated_tracking"
    image_url: str
    description: str
    why_flagged: str = ""
    involved_track_ids: list[int] = Field(default_factory=list)
    created_at: datetime


class UnifiedSessionDetailResponse(BaseModel):
    """Complete unified session detail payload for drill-down inspection."""

    session_id: str
    session_type: MonitoringSessionType
    name: str
    video_id: str | None = None
    status: str
    started_at: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    frames_processed: int = 0
    total_frames: int = 0
    frame_width: int | None = None
    frame_height: int | None = None
    confidence_threshold: float = 0.40
    detection_stats: dict[str, Any] = Field(default_factory=dict)
    track_stats: dict[str, Any] = Field(default_factory=dict)
    events: list[SessionEventDetail] = Field(default_factory=list)
    evidence_count: int = 0
    evidence_items: list[SessionEvidenceDetail] = Field(default_factory=list)
    pdf_report_url: str
    ai_explanation_summary: dict[str, Any] = Field(default_factory=dict)
