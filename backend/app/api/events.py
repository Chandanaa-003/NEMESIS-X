from collections import Counter
import json
from pathlib import Path
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.detection import Detection
from app.models.event import Event
from app.models.track import Track
from app.models.user import User
from app.schemas.event import (
    EventDiscoveryResponse,
    EventEvidenceFrame,
    EventExplanation,
    EventRecordInfo,
    EventSummaryInfo,
    ImportantTimestampInfo,
)
from app.services.event_engine import discover_events_for_analysis
from app.services.evidence_engine import collect_evidence_for_analysis

router = APIRouter(prefix="/analysis", tags=["Events"])

_active_discovery_lock = threading.Lock()
_active_discovery_ids: set[str] = set()

SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def _get_owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
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


def _load_frame_lookup(analysis_dir: Path, api_prefix: str, analysis_id: str) -> dict[int, EventEvidenceFrame]:
    metadata_path = analysis_dir / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    lookup: dict[int, EventEvidenceFrame] = {}
    for item in raw_meta.get("frames", []):
        f_idx = int(item["frame_index"])
        filename = str(item["filename"])
        lookup[f_idx] = EventEvidenceFrame(
            frame_index=f_idx,
            timestamp_seconds=float(item["timestamp_seconds"]),
            filename=filename,
            url=f"{api_prefix}/analysis/{analysis_id}/frames/{filename}",
        )
    return lookup


def _load_detection_track_counts(
    analysis: Analysis,
    analysis_dir: Path,
    db: Session,
) -> tuple[int, int]:
    detections_path = analysis_dir / "detections.json"
    tracks_path = analysis_dir / "tracks.json"

    total_det: int | None = None
    total_tracks: int | None = None

    if detections_path.exists():
        try:
            raw_det = json.loads(detections_path.read_text(encoding="utf-8"))
            total_det = int(raw_det.get("total_detections", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            total_det = None

    if tracks_path.exists():
        try:
            raw_tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
            total_tracks = int(raw_tracks.get("total_tracks", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            total_tracks = None

    if total_det is None:
        total_det = db.query(Detection).filter(Detection.analysis_id == analysis.id).count()
    if total_tracks is None:
        total_tracks = db.query(Track).filter(Track.analysis_id == analysis.id).count()

    return total_det, total_tracks


def _to_event_record(
    event: Event,
    frame_lookup: dict[int, EventEvidenceFrame],
) -> EventRecordInfo:
    payload: dict[str, Any] = event.explanation_payload or {}
    evidence_frames = [
        frame_lookup[fid] for fid in (event.evidence_frame_ids or []) if fid in frame_lookup
    ]
    explanation = EventExplanation(
        observed_sequence=[str(s) for s in payload.get("observed_sequence", [])],
        why_flagged=str(payload.get("why_flagged", "")),
        evidence_timestamps=[float(t) for t in payload.get("evidence_timestamps", [])],
        confidence_note=str(
            payload.get(
                "confidence_note",
                "Rule-based spatial-temporal analysis combined with YOLO/ByteTrack observations.",
            )
        ),
        requires_human_review=bool(payload.get("requires_human_review", False)),
        person_track_id=payload.get("person_track_id"),
        object_track_id=payload.get("object_track_id"),
        association_uncertainty=payload.get("association_uncertainty"),
        anomaly_score=payload.get("anomaly_score"),
    )

    category_val = event.category
    if category_val not in {
        "people_movement",
        "object_interactions",
        "possible_unattended_objects",
        "other_activities",
    }:
        category_val = "other_activities"

    severity_val = event.severity if event.severity in {"low", "medium", "high"} else "low"

    return EventRecordInfo(
        id=event.id,
        analysis_id=event.analysis_id,
        event_type=event.event_type,
        category=category_val,  # type: ignore[arg-type]
        title=event.title,
        description=event.description,
        start_timestamp=event.start_timestamp,
        end_timestamp=event.end_timestamp,
        involved_track_ids=[int(t) for t in (event.involved_track_ids or [])],
        confidence=event.confidence,
        severity=severity_val,  # type: ignore[arg-type]
        evidence_frame_ids=[int(f) for f in (event.evidence_frame_ids or [])],
        evidence_frames=evidence_frames,
        explanation=explanation,
        created_at=event.created_at,
    )


def _build_event_summary(
    *,
    total_detected_objects: int,
    total_unique_tracks: int,
    events: list[EventRecordInfo],
) -> EventSummaryInfo:
    if not events:
        return EventSummaryInfo(
            total_detected_objects=total_detected_objects,
            total_unique_tracks=total_unique_tracks,
            total_discovered_events=0,
            most_common_categories={},
            important_timestamps=[],
            events_requiring_review=0,
            summary_message=(
                "No supported event patterns were identified from the current detections and tracks."
            ),
        )

    cat_counts = Counter(evt.category for evt in events)
    sorted_cats = dict(cat_counts.most_common())
    review_count = sum(1 for evt in events if evt.explanation.requires_human_review)

    prioritized = sorted(
        events,
        key=lambda e: (SEVERITY_RANK.get(e.severity, 2), e.start_timestamp),
    )[:5]
    important_ts = [
        ImportantTimestampInfo(
            timestamp_seconds=e.start_timestamp,
            event_title=e.title,
            severity=e.severity,
        )
        for e in prioritized
    ]

    msg = (
        f"Identified {len(events)} event(s) across {total_unique_tracks} tracked object(s) "
        f"({total_detected_objects} total detections)."
    )
    if review_count > 0:
        msg += f" {review_count} event(s) are flagged for human review."

    return EventSummaryInfo(
        total_detected_objects=total_detected_objects,
        total_unique_tracks=total_unique_tracks,
        total_discovered_events=len(events),
        most_common_categories=sorted_cats,
        important_timestamps=important_ts,
        events_requiring_review=review_count,
        summary_message=msg,
    )


@router.post(
    "/{analysis_id}/discover-events",
    response_model=EventDiscoveryResponse,
    summary="Run rule-based event discovery on completed detection and tracking results",
)
def discover_events(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventDiscoveryResponse:
    """Analyze existing tracking & detection outputs to discover and store events."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)

    if analysis.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video preprocessing and tracking are still running for this analysis.",
        )
    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event discovery requires a completed video analysis.",
        )

    with _active_discovery_lock:
        if analysis_id in _active_discovery_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event discovery is already running for this analysis.",
            )
        _active_discovery_ids.add(analysis_id)

    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id

    try:
        try:
            output = discover_events_for_analysis(
                analysis_id=analysis.id,
                analysis_dir=analysis_dir,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        try:
            db.query(Event).filter(Event.analysis_id == analysis.id).delete()
            db_events = [
                Event(
                    id=draft.id,
                    analysis_id=analysis.id,
                    event_type=draft.event_type,
                    category=draft.category,
                    title=draft.title,
                    description=draft.description,
                    explanation_payload=draft.explanation_payload,
                    start_timestamp=draft.start_timestamp,
                    end_timestamp=draft.end_timestamp,
                    involved_track_ids=draft.involved_track_ids,
                    confidence=draft.confidence,
                    severity=draft.severity,
                    evidence_frame_ids=draft.evidence_frame_ids,
                )
                for draft in output.events
            ]
            if db_events:
                db.add_all(db_events)
            db.flush()
            collect_evidence_for_analysis(analysis=analysis, events=db_events, db=db)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error while saving discovered events.",
            ) from exc

        saved_events = (
            db.query(Event)
            .filter(Event.analysis_id == analysis.id)
            .order_by(Event.start_timestamp.asc(), Event.end_timestamp.asc())
            .all()
        )
        frame_lookup = _load_frame_lookup(analysis_dir, settings.api_v1_prefix, analysis.id)
        event_records = [_to_event_record(ev, frame_lookup) for ev in saved_events]
        summary = _build_event_summary(
            total_detected_objects=output.total_detected_objects,
            total_unique_tracks=output.total_unique_tracks,
            events=event_records,
        )

        return EventDiscoveryResponse(
            analysis_id=analysis.id,
            video_id=analysis.video_id,
            summary=summary,
            events=event_records,
        )
    finally:
        with _active_discovery_lock:
            _active_discovery_ids.discard(analysis_id)


@router.get(
    "/{analysis_id}/events",
    response_model=EventDiscoveryResponse,
    summary="List discovered events and summary for an owned analysis",
)
def list_analysis_events(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventDiscoveryResponse:
    """Return discovered events and summary statistics for an owned analysis."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id

    saved_events = (
        db.query(Event)
        .filter(Event.analysis_id == analysis.id)
        .order_by(Event.start_timestamp.asc(), Event.end_timestamp.asc())
        .all()
    )

    frame_lookup = _load_frame_lookup(analysis_dir, settings.api_v1_prefix, analysis.id)
    event_records = [_to_event_record(ev, frame_lookup) for ev in saved_events]
    total_det, total_tracks = _load_detection_track_counts(analysis, analysis_dir, db)
    summary = _build_event_summary(
        total_detected_objects=total_det,
        total_unique_tracks=total_tracks,
        events=event_records,
    )

    return EventDiscoveryResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        summary=summary,
        events=event_records,
    )


@router.get(
    "/{analysis_id}/events/{event_id}",
    response_model=EventRecordInfo,
    summary="Get details for a single discovered event",
)
def get_analysis_event_detail(
    analysis_id: str,
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventRecordInfo:
    """Fetch a single event belonging to an owned analysis."""
    analysis = _get_owned_analysis(analysis_id, current_user.id, db)
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.analysis_id == analysis.id)
        .first()
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id
    frame_lookup = _load_frame_lookup(analysis_dir, settings.api_v1_prefix, analysis.id)
    return _to_event_record(event, frame_lookup)
