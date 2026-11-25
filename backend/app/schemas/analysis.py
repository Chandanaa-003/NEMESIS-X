from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AnalysisStatus = Literal["queued", "processing", "completed", "failed"]


class AnalysisStartRequest(BaseModel):
    """Optional preprocessing, detection & tracking configuration."""

    target_fps: float = Field(default=1.0, ge=0.1, le=5.0)
    confidence_threshold: float = Field(default=0.40, ge=0.05, le=0.95)


class AnalysisStartResponse(BaseModel):
    """Response returned when an analysis job is queued."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus


class AnalysisStatusResponse(BaseModel):
    """Live preprocessing, detection & tracking progress for polling."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    total_frames: int
    processed_frames: int
    extracted_frames: int
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
    """Object detection entry for a single frame, including optional ByteTrack ID."""

    track_id: int | None = None
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBoxInfo


class ExtractedFrameInfo(BaseModel):
    """Public metadata, protected URL, and tracked detections for a single frame."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    url: str
    frame_width: int | None = None
    frame_height: int | None = None
    detections: list[DetectedObjectInfo] = Field(default_factory=list)


class TrackTimelinePointInfo(BaseModel):
    """Single temporal snapshot for a tracked object."""

    frame_index: int
    timestamp_seconds: float
    center_x: float
    center_y: float
    confidence: float
    bbox: BoundingBoxInfo


class TrackPositionSnapshot(BaseModel):
    """Last known or observation pixel and normalized position for a track."""

    frame_index: int
    timestamp_seconds: float
    center_x: float
    center_y: float
    norm_x: float | None = None
    norm_y: float | None = None
    bbox: BoundingBoxInfo


class TrackSummaryInfo(BaseModel):
    """Persistent object track and temporal memory metadata."""

    track_id: int
    track_code: str | None = None
    class_id: int
    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    duration_seconds: float
    frame_count: int
    avg_confidence: float
    max_confidence: float
    last_known_position: TrackPositionSnapshot | None = None
    timeline_points: list[TrackTimelinePointInfo] = Field(default_factory=list)


class TrackMovementStep(BaseModel):
    """Observed position change between two consecutive track observations."""

    from_frame_index: int
    to_frame_index: int
    from_timestamp: float
    to_timestamp: float
    from_center_x: float
    from_center_y: float
    to_center_x: float
    to_center_y: float
    delta_x: float
    delta_y: float
    displacement_px: float
    displacement_norm: float | None = None
    direction: str


class TrackMovementHistory(BaseModel):
    """Aggregated trajectory distance and step-by-step movement history."""

    total_path_distance_px: float
    net_displacement_px: float
    net_displacement_norm: float | None = None
    dominant_direction: str
    steps: list[TrackMovementStep] = Field(default_factory=list)


class TrackRelatedEventInfo(BaseModel):
    """Discovered event record linked to a specific track."""

    id: str
    event_type: str
    category: str
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    severity: str
    confidence: float
    involved_track_ids: list[int] = Field(default_factory=list)


class TrackObservationFrameInfo(BaseModel):
    """Annotated frame metadata where the selected track was observed."""

    frame_index: int
    source_frame_index: int
    timestamp_seconds: float
    filename: str
    frame_url: str
    frame_available: bool
    frame_width: int | None = None
    frame_height: int | None = None
    selected_detection: DetectedObjectInfo
    center_x: float
    center_y: float
    position_delta_x: float = 0.0
    position_delta_y: float = 0.0
    other_detections: list[DetectedObjectInfo] = Field(default_factory=list)


class TrackDetailResponse(BaseModel):
    """Detailed movement, position, event, and frame inspection payload for one track."""

    analysis_id: str
    video_id: str
    track_code: str
    temporary_id_notice: str
    frame_width: int | None = None
    frame_height: int | None = None
    track: TrackSummaryInfo
    last_known_position: TrackPositionSnapshot | None = None
    movement_history: TrackMovementHistory
    related_events: list[TrackRelatedEventInfo] = Field(default_factory=list)
    frames: list[TrackObservationFrameInfo] = Field(default_factory=list)


class TrackFramesResponse(BaseModel):
    """Annotated observation frames containing a specific track ID."""

    analysis_id: str
    video_id: str
    track_id: int
    track_code: str
    class_name: str
    total_observations: int
    frames: list[TrackObservationFrameInfo] = Field(default_factory=list)


class AnalysisResultsResponse(BaseModel):
    """Completed analysis metadata, processing/detection/tracking summaries, and frames."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    sampling_interval: int
    error_message: str | None = None
    summary: dict[str, Any]
    detections_summary: dict[str, Any] = Field(default_factory=dict)
    tracks_summary: dict[str, Any] = Field(default_factory=dict)
    tracks: list[TrackSummaryInfo] = Field(default_factory=list)
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


class AnalysisListItem(BaseModel):
    """Summary entry for listing a user's analyses."""

    analysis_id: str
    video_id: str
    video_filename: str
    status: AnalysisStatus
    progress: int
    extracted_frames: int
    total_frames: int
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisTracksResponse(BaseModel):
    """Persistent object tracks and temporal memory summary for an analysis."""

    analysis_id: str
    video_id: str
    status: AnalysisStatus
    summary: dict[str, Any]
    tracks: list[TrackSummaryInfo]
