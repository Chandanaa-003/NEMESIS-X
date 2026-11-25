from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AnalysisStatus = Literal["queued", "processing", "completed", "failed"]


class AnalysisStartRequest(BaseModel):
    """Optional preprocessing & detection configuration when starting an analysis job."""

    target_fps: float = Field(default=1.0, ge=0.1, le=5.0)
    confidence_threshold: float = Field(default=0.40, ge=0.05, le=0.95)


class AnalysisStartResponse(BaseModel):
    """Response returned when an analysis job is queued."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus


class AnalysisStatusResponse(BaseModel):
    """Live preprocessing & detection progress and status for polling."""

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


class BoundingBoxInfo(BaseModel):
    """Pixel bounding box coordinates relative to the extracted frame."""

    x1: float
    y1: float
    x2: float
    y2: float


class DetectedObjectInfo(BaseModel):
    """Object detection entry for a single frame."""

    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBoxInfo


class ExtractedFrameInfo(BaseModel):
    """Public metadata, protected URL, and detections for a single extracted frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    url: str
    frame_width: int | None = None
    frame_height: int | None = None
    detections: list[DetectedObjectInfo] = Field(default_factory=list)


class AnalysisResultsResponse(BaseModel):
    """Completed analysis metadata, processing & detection summary, and frame list."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    sampling_interval: int
    error_message: str | None = None
    summary: dict[str, Any]
    detections_summary: dict[str, Any] = Field(default_factory=dict)
    frames: list[ExtractedFrameInfo]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AnalysisDetectionsResponse(BaseModel):
    """Structured per-frame object detection payload."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    summary: dict[str, Any]
    frames: list[ExtractedFrameInfo]
