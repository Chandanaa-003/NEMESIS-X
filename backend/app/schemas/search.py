from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import BoundingBoxInfo

SearchSourceType = Literal["analysis", "live_session"]
SearchResultType = Literal["event", "detection", "track"]


class SearchDetectionInfo(BaseModel):
    track_id: int | None = None
    track_code: str | None = None
    class_name: str
    confidence: float
    bbox: BoundingBoxInfo


class SearchEvidenceReference(BaseModel):
    id: str
    evidence_type: str
    timestamp_seconds: float
    image_url: str


class IntelligenceSearchResult(BaseModel):
    id: str
    result_type: SearchResultType
    source_type: SearchSourceType
    source_id: str
    source_label: str
    analysis_id: str | None = None
    video_id: str | None = None
    live_session_id: str | None = None
    event_id: str | None = None
    event_type: str
    event_category: str
    title: str
    explanation: str
    timestamp_seconds: float
    end_timestamp_seconds: float | None = None
    overlay_timestamp_seconds: float | None = None
    track_ids: list[int] = Field(default_factory=list)
    track_labels: list[str] = Field(default_factory=list)
    class_name: str | None = None
    detection_count: int | None = None
    confidence: float | None = None
    severity: str | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    detections: list[SearchDetectionInfo] = Field(default_factory=list)
    evidence: list[SearchEvidenceReference] = Field(default_factory=list)


class IntelligenceSearchResponse(BaseModel):
    query: str
    supported_query: bool
    message: str
    total: int
    limit: int
    offset: int
    has_more: bool
    truncated: bool = False
    results: list[IntelligenceSearchResult]


class TrackSearchResult(BaseModel):
    source_type: SearchSourceType
    source_id: str
    source_label: str
    analysis_id: str | None = None
    video_id: str | None = None
    live_session_id: str | None = None
    track_id: int
    track_code: str
    track_label: str
    class_name: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    evidence: list[SearchEvidenceReference] = Field(default_factory=list)


class TrackSearchResponse(BaseModel):
    query: str
    total: int
    truncated: bool = False
    results: list[TrackSearchResult]
