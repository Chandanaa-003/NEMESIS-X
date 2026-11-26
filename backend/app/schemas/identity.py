from typing import Any, Literal

from pydantic import BaseModel, Field

IdentitySourceType = Literal["analysis", "live_session"]
IdentityEntityType = Literal["person", "object"]
IdentityStatus = Literal["confirmed", "probable", "unknown"]


class IdentityCorrectionRequest(BaseModel):
    target_identity_id: str = Field(min_length=36, max_length=36)


class IdentityLegacyCorrectionRequest(BaseModel):
    target_identity_id: str | None = Field(default=None, min_length=36, max_length=36)
    create_new_identity: bool = False
    correction_note: str | None = Field(default=None, max_length=500)


class IdentityObservationResponse(BaseModel):
    track_id: int
    track_code: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    match_confidence: float
    feature_quality: float
    matching_explanation: str
    bbox: dict[str, float] | None = None
    evidence_url: str | None = None


class IdentityRelatedEventResponse(BaseModel):
    event_id: str
    id: str
    event_type: str
    category: str
    title: str
    timestamp_seconds: float
    confidence: float
    severity: str
    involved_track_ids: list[int] = Field(default_factory=list)
    track_codes: list[str] = Field(default_factory=list)


class IdentityTrackAppearanceCompatResponse(BaseModel):
    track_id: int
    track_code: str
    category: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    match_confidence: float | None = None
    match_status: IdentityStatus
    matching_explanation: str
    unresolved_candidate_code: str | None = None
    evidence_url: str | None = None
    manually_corrected: bool = False
    correction_note: str | None = None


class EntityIdentityResponse(BaseModel):
    id: str
    source_type: IdentitySourceType
    source_id: str
    identity_code: str
    entity_type: IdentityEntityType
    class_name: str
    category: str
    status: IdentityStatus
    first_seen_timestamp: float
    last_seen_timestamp: float
    appearance_count: int
    associated_track_ids: list[int]
    associated_track_codes: list[str]
    matching_confidence: float
    matching_explanation: str
    feature_reference: str
    evidence_refs: list[str]
    evidence_urls: list[str]
    related_event_count: int
    merged_into_code: str | None = None
    observations: list[IdentityObservationResponse] = Field(default_factory=list)
    track_appearances: list[IdentityTrackAppearanceCompatResponse] = Field(default_factory=list)
    related_events: list[IdentityRelatedEventResponse] = Field(default_factory=list)


class IdentitySearchResponse(BaseModel):
    source_type: IdentitySourceType
    source_id: str
    total_unique_people: int
    total_unique_objects: int
    total: int
    limit: int
    offset: int
    items: list[EntityIdentityResponse]


class IdentityCountsResponse(BaseModel):
    unique_people: int
    unique_objects: int
    confirmed: int
    probable: int
    unknown: int


class IdentityCorrectionResponse(BaseModel):
    identity: EntityIdentityResponse
    corrected_track_id: int
    previous_identity_code: str
    correction: str