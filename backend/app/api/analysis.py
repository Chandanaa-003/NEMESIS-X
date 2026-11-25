import json
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.user import User
from app.models.video import Video
from app.schemas.analysis import (
    AnalysisDetectionsResponse,
    AnalysisListItem,
    AnalysisResultsResponse,
    AnalysisStartRequest,
    AnalysisStartResponse,
    AnalysisStatusResponse,
    AnalysisTracksResponse,
    BoundingBoxInfo,
    DetectedObjectInfo,
    ExtractedFrameInfo,
    TrackDetailResponse,
    TrackFramesResponse,
    TrackSummaryInfo,
    TrackTimelinePointInfo,
)
from app.services.identity_engine import get_track_identity_codes
from app.services.track_explorer import (
    format_track_code,
    get_track_detail_payload,
    get_track_frames_payload,
    load_enriched_tracks_data,
)
from app.workers.analysis_worker import run_video_analysis_job

router = APIRouter(prefix="/analysis", tags=["Analysis"])

SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4}\.jpg$")


def _get_owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
    """Fetch an analysis record only if it belongs to the authenticated user."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
        .first()
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )
    return analysis


def _load_detections_data(
    analysis_id: str,
    api_prefix: str,
    identity_codes: dict[int, str] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Read detections.json if present and return summary + per-filename map."""
    settings = get_settings()
    detections_path = settings.resolved_processed_dir / analysis_id / "detections.json"
    if not detections_path.exists():
        return {}, {}

    try:
        raw_det = json.loads(detections_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read object detection results.",
        ) from exc

    summary = {
        "model_name": raw_det.get("model_name"),
        "tracker_name": raw_det.get("tracker_name"),
        "device": raw_det.get("device", "cpu"),
        "image_size": raw_det.get("image_size"),
        "confidence_threshold": raw_det.get("confidence_threshold"),
        "total_detections": raw_det.get("total_detections", 0),
        "frames_with_detections": raw_det.get("frames_with_detections", 0),
        "class_counts": raw_det.get("class_counts", {}),
    }

    by_filename: dict[str, dict[str, Any]] = {}
    for frame_entry in raw_det.get("frames", []):
        filename = str(frame_entry.get("filename", ""))
        if not SAFE_FRAME_FILENAME_RE.match(filename):
            continue
        parsed_dets: list[DetectedObjectInfo] = []
        for det in frame_entry.get("detections", []):
            bbox = det.get("bbox", {})
            raw_tid = det.get("track_id")
            parsed_dets.append(
                DetectedObjectInfo(
                    track_id=int(raw_tid) if raw_tid is not None else None,
                    track_code=format_track_code(int(raw_tid)) if raw_tid is not None else None,
                    identity_code=(
                        (identity_codes or {}).get(int(raw_tid))
                        if raw_tid is not None
                        else None
                    ),
                    class_id=int(det["class_id"]),
                    class_name=str(det["class_name"]),
                    confidence=float(det["confidence"]),
                    bbox=BoundingBoxInfo(
                        x1=float(bbox["x1"]),
                        y1=float(bbox["y1"]),
                        x2=float(bbox["x2"]),
                        y2=float(bbox["y2"]),
                    ),
                )
            )
        by_filename[filename] = {
            "frame_index": int(frame_entry["frame_index"]),
            "source_frame_index": int(frame_entry["source_frame_index"]),
            "timestamp_seconds": float(frame_entry["timestamp_seconds"]),
            "filename": filename,
            "url": f"{api_prefix}/analysis/{analysis_id}/frames/{filename}",
            "frame_width": frame_entry.get("frame_width"),
            "frame_height": frame_entry.get("frame_height"),
            "detections": parsed_dets,
        }

    return summary, by_filename


def _load_tracks_data(analysis_id: str) -> tuple[dict[str, Any], list[TrackSummaryInfo]]:
    """Read tracks.json if present and return summary + persistent track records."""
    settings = get_settings()
    tracks_path = settings.resolved_processed_dir / analysis_id / "tracks.json"
    if not tracks_path.exists():
        return {}, []

    try:
        raw_tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read object tracking results.",
        ) from exc

    summary = {
        "model_name": raw_tracks.get("model_name"),
        "tracker_name": raw_tracks.get("tracker_name", "bytetrack"),
        "total_tracks": raw_tracks.get("total_tracks", 0),
        "tracks_by_class": raw_tracks.get("tracks_by_class", {}),
    }

    parsed_tracks: list[TrackSummaryInfo] = []
    for item in raw_tracks.get("tracks", []):
        timeline_points = [
            TrackTimelinePointInfo(
                frame_index=int(pt["frame_index"]),
                timestamp_seconds=float(pt["timestamp_seconds"]),
                center_x=float(pt["center_x"]),
                center_y=float(pt["center_y"]),
                confidence=float(pt["confidence"]),
                bbox=BoundingBoxInfo(
                    x1=float(pt["bbox"]["x1"]),
                    y1=float(pt["bbox"]["y1"]),
                    x2=float(pt["bbox"]["x2"]),
                    y2=float(pt["bbox"]["y2"]),
                ),
            )
            for pt in item.get("timeline_points", [])
        ]
        parsed_tracks.append(
            TrackSummaryInfo(
                track_id=int(item["track_id"]),
                class_id=int(item["class_id"]),
                class_name=str(item["class_name"]),
                first_seen_frame=int(item["first_seen_frame"]),
                last_seen_frame=int(item["last_seen_frame"]),
                first_seen_timestamp=float(item["first_seen_timestamp"]),
                last_seen_timestamp=float(item["last_seen_timestamp"]),
                duration_seconds=float(item["duration_seconds"]),
                frame_count=int(item["frame_count"]),
                avg_confidence=float(item["avg_confidence"]),
                max_confidence=float(item["max_confidence"]),
                timeline_points=timeline_points,
            )
        )

    return summary, parsed_tracks


def _decorate_track_summaries(
    tracks: list[TrackSummaryInfo],
    identity_codes: dict[int, str],
) -> list[TrackSummaryInfo]:
    return [
        track.model_copy(update={"identity_code": identity_codes.get(track.track_id)})
        for track in tracks
    ]


def _decorate_observation_frames(
    frames: list[Any],
    identity_codes: dict[int, str],
) -> list[Any]:
    decorated = []
    for frame in frames:
        selected = frame.selected_detection
        selected_detection = selected.model_copy(
            update={"identity_code": identity_codes.get(selected.track_id)}
        )
        others = [
            detection.model_copy(
                update={
                    "identity_code": (
                        identity_codes.get(detection.track_id)
                        if detection.track_id is not None
                        else None
                    )
                }
            )
            for detection in frame.other_detections
        ]
        decorated.append(
            frame.model_copy(
                update={"selected_detection": selected_detection, "other_detections": others}
            )
        )
    return decorated


@router.get(
    "",
    response_model=list[AnalysisListItem],
    summary="List video analyses for the current user",
)
def list_user_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnalysisListItem]:
    """Return all analyses belonging to the authenticated user, newest first."""
    rows = (
        db.query(Analysis, Video.original_filename)
        .join(Video, Analysis.video_id == Video.id)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return [
        AnalysisListItem(
            analysis_id=analysis.id,
            video_id=analysis.video_id,
            video_filename=filename,
            status=analysis.status,  # type: ignore[arg-type]
            progress=analysis.progress,
            extracted_frames=analysis.extracted_frames,
            total_frames=analysis.total_frames,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )
        for analysis, filename in rows
    ]


@router.post(
    "/{video_id}/start",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue video frame extraction, detection, and tracking",
)
def start_analysis(
    video_id: str,
    background_tasks: BackgroundTasks,
    payload: AnalysisStartRequest = Body(default_factory=AnalysisStartRequest),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStartResponse:
    """Start a background preprocessing + YOLO detection + ByteTrack job for an owned video."""
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.user_id == current_user.id)
        .first()
    )
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    active_job = (
        db.query(Analysis)
        .filter(
            Analysis.video_id == video.id,
            Analysis.status.in_(["queued", "processing"]),
        )
        .first()
    )
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An analysis job is already in progress for this video.",
        )

    analysis = Analysis(
        video_id=video.id,
        user_id=current_user.id,
        status="queued",
        progress=0,
        total_frames=0,
        processed_frames=0,
        extracted_frames=0,
        sampling_interval=1,
    )
    video.status = "queued"

    try:
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while queuing analysis job.",
        ) from exc

    background_tasks.add_task(
        run_video_analysis_job,
        analysis.id,
        payload.target_fps,
        payload.confidence_threshold,
    )

    return AnalysisStartResponse(
        analysis_id=analysis.id,
        video_id=video.id,
        status=analysis.status,  # type: ignore[arg-type]
    )


@router.get(
    "/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Get analysis job status and progress",
)
def get_analysis_status(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Return current processing status and progress for an owned analysis job."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        progress=analysis.progress,
        total_frames=analysis.total_frames,
        processed_frames=analysis.processed_frames,
        extracted_frames=analysis.extracted_frames,
        sampling_interval=analysis.sampling_interval,
        error_message=analysis.error_message,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/{analysis_id}/results",
    response_model=AnalysisResultsResponse,
    summary="Get preprocessing summary, extracted frames, detections, and tracks",
)
def get_analysis_results(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResultsResponse:
    """Return frame metadata, detections, and temporal tracks for an owned job."""
    settings = get_settings()
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)

    metadata_path = settings.resolved_processed_dir / analysis.id / "metadata.json"
    frames: list[ExtractedFrameInfo] = []
    summary: dict[str, object] = {
        "total_frames": analysis.total_frames,
        "processed_frames": analysis.processed_frames,
        "sampling_interval": analysis.sampling_interval,
        "extracted_count": 0,
    }
    detections_summary: dict[str, Any] = {}
    tracks_summary: dict[str, Any] = {}
    tracks: list[TrackSummaryInfo] = []

    if analysis.status == "completed":
        if not metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Analysis completed, but frame metadata.json was not found on disk.",
            )
        try:
            raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read analysis metadata.",
            ) from exc

        summary = {
            "duration_seconds": raw_meta.get("duration_seconds"),
            "original_dimensions": raw_meta.get("original_dimensions"),
            "fps": raw_meta.get("fps"),
            "total_frames": raw_meta.get("total_frames", analysis.total_frames),
            "sampling_interval": raw_meta.get("sampling_interval", analysis.sampling_interval),
            "max_width_applied": raw_meta.get("max_width_applied"),
            "extracted_count": raw_meta.get("extracted_count", 0),
        }

        api_prefix = settings.api_v1_prefix
        identity_codes = get_track_identity_codes(
            db,
            source_type="analysis",
            source_id=analysis.id,
        )
        detections_summary, detections_by_file = _load_detections_data(
            analysis.id,
            api_prefix,
            identity_codes,
        )
        tracks_summary, tracks = load_enriched_tracks_data(analysis.id, db=db)
        tracks = _decorate_track_summaries(tracks, identity_codes)

        for item in raw_meta.get("frames", []):
            filename = str(item.get("filename", ""))
            if not SAFE_FRAME_FILENAME_RE.match(filename):
                continue
            det_entry = detections_by_file.get(filename)
            frames.append(
                ExtractedFrameInfo(
                    frame_index=int(item["frame_index"]),
                    source_frame_index=int(item["source_frame_index"]),
                    timestamp_seconds=float(item["timestamp_seconds"]),
                    filename=filename,
                    url=f"{api_prefix}/analysis/{analysis.id}/frames/{filename}",
                    frame_width=det_entry["frame_width"] if det_entry else None,
                    frame_height=det_entry["frame_height"] if det_entry else None,
                    detections=det_entry["detections"] if det_entry else [],
                )
            )

        if len(frames) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Analysis completed, but zero extracted frames were available.",
            )

    return AnalysisResultsResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        progress=analysis.progress,
        sampling_interval=analysis.sampling_interval,
        error_message=analysis.error_message,
        summary=summary,
        detections_summary=detections_summary,
        tracks_summary=tracks_summary,
        tracks=tracks,
        frames=frames,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


@router.get(
    "/{analysis_id}/detections",
    response_model=AnalysisDetectionsResponse,
    summary="Get structured per-frame object detections for an owned analysis",
)
def get_analysis_detections(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisDetectionsResponse:
    """Return structured per-frame object detections and summary counts."""
    settings = get_settings()
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)

    detections_summary, detections_by_file = _load_detections_data(
        analysis.id,
        settings.api_v1_prefix,
        get_track_identity_codes(
            db,
            source_type="analysis",
            source_id=analysis.id,
        ),
    )
    frames = [ExtractedFrameInfo(**entry) for entry in detections_by_file.values()]

    return AnalysisDetectionsResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        summary=detections_summary,
        frames=frames,
    )


@router.get(
    "/{analysis_id}/tracks",
    response_model=AnalysisTracksResponse,
    summary="Get persistent object tracks and temporal memory for an owned analysis",
)
def get_analysis_tracks(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisTracksResponse:
    """Return persistent ByteTrack object trajectories and temporal spans."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    tracks_summary, tracks = load_enriched_tracks_data(analysis.id, db=db)
    tracks = _decorate_track_summaries(
        tracks,
        get_track_identity_codes(db, source_type="analysis", source_id=analysis.id),
    )

    return AnalysisTracksResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        status=analysis.status,  # type: ignore[arg-type]
        summary=tracks_summary,
        tracks=tracks,
    )


@router.get(
    "/{analysis_id}/tracks/{track_id}",
    response_model=TrackDetailResponse,
    summary="Get detailed trajectory, position history, frames, and related events for one track",
)
def get_analysis_track_detail(
    analysis_id: str,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrackDetailResponse:
    """Return movement history, last known position, annotated frames, and events for a track."""
    settings = get_settings()
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    payload = get_track_detail_payload(
        analysis=analysis,
        track_id=track_id,
        db=db,
        api_prefix=settings.api_v1_prefix,
    )
    identity_codes = get_track_identity_codes(
        db,
        source_type="analysis",
        source_id=analysis.id,
    )
    return payload.model_copy(
        update={
            "track": _decorate_track_summaries([payload.track], identity_codes)[0],
            "frames": _decorate_observation_frames(payload.frames, identity_codes),
        }
    )


@router.get(
    "/{analysis_id}/tracks/{track_id}/frames",
    response_model=TrackFramesResponse,
    summary="Get all available observation frames containing a specific tracking ID",
)
def get_analysis_track_frames(
    analysis_id: str,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrackFramesResponse:
    """Return chronologically ordered annotated frames containing the selected tracking ID."""
    settings = get_settings()
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    payload = get_track_frames_payload(
        analysis=analysis,
        track_id=track_id,
        db=db,
        api_prefix=settings.api_v1_prefix,
    )
    return payload.model_copy(
        update={
            "frames": _decorate_observation_frames(
                payload.frames,
                get_track_identity_codes(
                    db,
                    source_type="analysis",
                    source_id=analysis.id,
                ),
            )
        }
    )


@router.get(
    "/{analysis_id}/frames/{filename}",
    summary="Fetch an extracted JPEG frame for an owned analysis",
)
def get_extracted_frame_image(
    analysis_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve an extracted frame JPEG strictly inside the owned analysis frames folder."""
    if not SAFE_FRAME_FILENAME_RE.match(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid frame filename.",
        )

    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    settings = get_settings()
    frames_dir = (settings.resolved_processed_dir / analysis.id / "frames").resolve()
    target_path = (frames_dir / Path(filename).name).resolve()

    if target_path.parent != frames_dir or not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted frame not found.",
        )

    return FileResponse(path=target_path, media_type="image/jpeg")
