from typing import Literal

from pydantic import BaseModel, Field

IdentitySourceType = Literal["analysis", "live_session"]
IdentityEntityType = Literal["person", "object"]
IdentityMatchStatus = Literal["confirmed", "probable", "unknown"]


class IdentityTrackAppearanceInfo(BaseModel):
    """One original tracker fragment associated with an anonymous identity."""

    track_id: int
    track_code: str
    category: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    match_confidence: float | None = None
    match_status: IdentityMatchStatus
    matching_explanation: str
    unresolved_candidate_code: str | None = None
    evidence_url: str | None = None
    manually_corrected: bool = False
    correction_note: str | None = None


class IdentityRelatedEventInfo(BaseModel):
    """Stored event associated with one or more original track fragments."""

    id: str
    event_type: str
    category: str
    title: str
    timestamp_seconds: float
    confidence: float
    severity: str
    track_codes: list[str] = Field(default_factory=list)


class EntityIdentitySummary(BaseModel):
    """Anonymous identity metadata scoped to one video analysis or live session."""

    id: str
    identity_code: str
    source_type: IdentitySourceType
    source_id: str
    entity_type: IdentityEntityType
    category: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    appearance_count: int
    matching_confidence: float | None = None
    status: IdentityMatchStatus
    matching_explanation: str
    associated_track_ids: list[int] = Field(default_factory=list)
    associated_track_codes: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    related_event_count: int = 0
    merged_into_code: str | None = None


class EntityIdentityDetail(EntityIdentitySummary):
    """Full source-scoped identity record with track fragments and related events."""

    track_appearances: list[IdentityTrackAppearanceInfo] = Field(default_factory=list)
    related_events: list[IdentityRelatedEventInfo] = Field(default_factory=list)


class IdentitySearchResponse(BaseModel):
    items: list[EntityIdentitySummary]
    total: int
    limit: int
    offset: int


class IdentityCountsResponse(BaseModel):
    unique_people: int
    unique_objects: int
    confirmed: int
    probable: int
    unknown: int


class IdentityCorrectionRequest(BaseModel):
    target_identity_id: str | None = Field(default=None, min_length=1, max_length=36)
    create_new_identity: bool = False
    correction_note: str | None = Field(default=None, max_length=500)
