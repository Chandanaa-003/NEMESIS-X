from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InvestigationStatus = Literal["open", "reviewing", "closed"]


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    status: InvestigationStatus = "open"


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: InvestigationStatus | None = None


class InvestigationSourceCreate(BaseModel):
    analysis_id: str | None = None
    live_session_id: str | None = None

    @model_validator(mode="after")
    def validate_single_source(self) -> "InvestigationSourceCreate":
        if (self.analysis_id is None) == (self.live_session_id is None):
            raise ValueError("Provide exactly one analysis_id or live_session_id.")
        return self


class InvestigationEventCreate(BaseModel):
    source_id: str
    event_id: str | None = None
    live_event_id: str | None = None

    @model_validator(mode="after")
    def validate_single_event(self) -> "InvestigationEventCreate":
        if (self.event_id is None) == (self.live_event_id is None):
            raise ValueError("Provide exactly one event_id or live_event_id.")
        return self


class InvestigationTrackCreate(BaseModel):
    source_id: str
    track_id: int = Field(ge=0)


class InvestigationNoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    source_id: str | None = None
    investigation_event_id: str | None = None
    timestamp_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_context(self) -> "InvestigationNoteCreate":
        if self.timestamp_seconds is not None and self.source_id is None:
            raise ValueError("A timestamp note must identify its investigation source.")
        return self


class InvestigationNoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    source_id: str | None = None
    investigation_event_id: str | None = None
    timestamp_seconds: float | None = Field(default=None, ge=0)


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: InvestigationStatus
    created_at: datetime
    updated_at: datetime
    source_count: int
    event_count: int
    track_count: int
    note_count: int


class InvestigationSourceInfo(BaseModel):
    id: str
    source_type: Literal["analysis", "live_session"]
    source_id: str
    source_label: str
    analysis_id: str | None = None
    video_id: str | None = None
    live_session_id: str | None = None
    status: str
    created_at: datetime
    data_availability: str
    track_count: int
    event_count: int


class InvestigationEventLinkInfo(BaseModel):
    id: str
    source_id: str
    event_id: str | None
    live_event_id: str | None
    event_type: str
    event_category: str
    title: str
    timestamp_seconds: float
    track_ids: list[int]
    track_labels: list[str]
    confidence: float
    severity: str
    created_at: datetime


class InvestigationTrackInfo(BaseModel):
    id: str
    source_id: str
    track_id: int
    track_label: str
    entity_label: str
    class_name: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    linked: bool


class InvestigationNoteInfo(BaseModel):
    id: str
    investigation_id: str
    source_id: str | None
    investigation_event_id: str | None
    timestamp_seconds: float | None
    content: str
    author_user_id: int
    source: Literal["user"] = "user"
    created_at: datetime
    updated_at: datetime


class InvestigationDetail(InvestigationSummary):
    sources: list[InvestigationSourceInfo] = Field(default_factory=list)
    linked_events: list[InvestigationEventLinkInfo] = Field(default_factory=list)
    linked_tracks: list[InvestigationTrackInfo] = Field(default_factory=list)
    notes: list[InvestigationNoteInfo] = Field(default_factory=list)


class InvestigationTimelineItem(BaseModel):
    id: str
    record_type: Literal["event", "detection", "track_observation", "behavior_sequence", "anomaly"]
    source_id: str
    source_type: Literal["analysis", "live_session"]
    source_label: str
    event_id: str | None = None
    event_type: str
    event_category: str
    title: str
    explanation: str
    timestamp_seconds: float
    created_at: datetime | None = None
    track_ids: list[int] = Field(default_factory=list)
    track_labels: list[str] = Field(default_factory=list)
    confidence: float | None = None
    severity: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    linked: bool = False


class InvestigationTimelineResponse(BaseModel):
    items: list[InvestigationTimelineItem]
    total: int
    limit: int
    offset: int
    has_more: bool


class InvestigationGraphNode(BaseModel):
    id: str
    node_type: Literal["person", "object", "unknown_track", "event"]
    label: str
    source_id: str
    source_label: str
    timestamp_seconds: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class InvestigationGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    timestamp_seconds: float
    confidence: float | None = None
    uncertainty: str | None = None
    event_id: str


class InvestigationGraphResponse(BaseModel):
    nodes: list[InvestigationGraphNode]
    edges: list[InvestigationGraphEdge]


class InvestigationEvidenceItem(BaseModel):
    id: str
    source_id: str
    event_id: str
    event_title: str
    timestamp_seconds: float
    frame_number: int
    evidence_type: str
    image_url: str | None
    original_image_url: str | None = None
    annotated_image_url: str | None = None
    explanation: str
    confidence: float | None = None
    track_ids: list[int] = Field(default_factory=list)
    track_labels: list[str] = Field(default_factory=list)
