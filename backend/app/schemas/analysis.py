from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AnalysisStatus = Literal["queued", "processing", "completed", "failed"]


class AnalysisStartRequest(BaseModel):
    """Optional preprocessing configuration when starting an analysis job."""

    target_fps: float = Field(default=1.0, ge=0.1, le=5.0)


class AnalysisStartResponse(BaseModel):
    """Response returned when an analysis job is queued."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus


class AnalysisStatusResponse(BaseModel):
    """Live preprocessing progress and status for polling."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    total_frames: int
    processed_frames: int
    sampling_interval: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class ExtractedFrameInfo(BaseModel):
    """Public metadata and protected URL for a single extracted frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    url: str


class AnalysisResultsResponse(BaseModel):
    """Completed analysis metadata, processing summary, and extracted frame list."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    sampling_interval: int
    error_message: str | None = None
    summary: dict[str, Any]
    frames: list[ExtractedFrameInfo]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
