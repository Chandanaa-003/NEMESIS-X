from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceType = Literal["original_frame", "annotated_detection", "annotated_tracking"]


class EvidenceItemInfo(BaseModel):
    """Public metadata and protected image URL for a saved evidence artifact."""

    id: str
    event_id: str
    analysis_id: str
    frame_number: int
    timestamp_seconds: float
    evidence_type: EvidenceType
    image_url: str
    description: str
    event_title: str
    event_category: str
    event_severity: str
    event_confidence: float
    why_flagged: str
    involved_track_ids: list[int] = Field(default_factory=list)
    detection_count: int = 0
    detection_summary: list[str] = Field(default_factory=list)
    created_at: datetime


class AnalysisEvidenceListResponse(BaseModel):
    """Collection of evidence artifacts for an analysis or event."""

    analysis_id: str
    total_evidence: int
    evidence: list[EvidenceItemInfo]
