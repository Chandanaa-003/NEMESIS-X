from datetime import date
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.behavior import BehaviorSnapshot
from app.models.event import Event
from app.models.live_session import LiveEvent, LiveSession
from app.models.user import User
from app.schemas.behavior import BehaviorBaselineConfig, BehaviorReportResponse
from app.services.behavior_engine import DEFAULT_BASELINE_CONFIG, build_behavior_report

router = APIRouter(prefix="/behavior", tags=["Behavior Intelligence"])


def _owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Behavior analysis requires a completed video analysis.",
        )
    return analysis


def _owned_live_session(session_id: str, user_id: int, db: Session) -> LiveSession:
    session = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == user_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Live monitoring session not found.")
    return session


def _snapshot(
    *,
    db: Session,
    user_id: int,
    analysis_id: str | None = None,
    live_session_id: str | None = None,
) -> BehaviorSnapshot:
    query = db.query(BehaviorSnapshot).filter(BehaviorSnapshot.user_id == user_id)
    if analysis_id is not None:
        query = query.filter(BehaviorSnapshot.analysis_id == analysis_id)
    else:
        query = query.filter(BehaviorSnapshot.live_session_id == live_session_id)
    row = query.first()
    if row is None:
        row = BehaviorSnapshot(
            user_id=user_id,
            analysis_id=analysis_id,
            live_session_id=live_session_id,
            baseline_config=dict(DEFAULT_BASELINE_CONFIG),
            track_history=[],
            report_payload={},
        )
        db.add(row)
        db.flush()
    return row


def _persist_report(row: BehaviorSnapshot, report: dict[str, Any], db: Session) -> None:
    row.report_payload = report
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not persist behavior report.",
        ) from exc


def _analysis_events(
    *,
    analysis: Analysis,
    analysis_dir: Path,
    db: Session,
) -> list[dict[str, Any]]:
    metadata_path = analysis_dir / "metadata.json"
    frame_lookup: dict[int, tuple[str, float]] = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read frame metadata for behavior evidence.",
            ) from exc
        frame_lookup = {
            int(frame["frame_index"]): (
                str(Path(str(frame["filename"])).name),
                float(frame["timestamp_seconds"]),
            )
            for frame in metadata.get("frames", [])
        }

    settings = get_settings()
    rows = (
        db.query(Event)
        .filter(Event.analysis_id == analysis.id)
        .order_by(Event.start_timestamp.asc(), Event.end_timestamp.asc())
        .all()
    )
    output: list[dict[str, Any]] = []
    for event in rows:
        evidence = [
            {
                "frame_index": int(frame_id),
                "timestamp_seconds": frame_lookup[int(frame_id)][1],
                "url": (
                    f"{settings.api_v1_prefix}/analysis/{analysis.id}/frames/"
                    f"{frame_lookup[int(frame_id)][0]}"
                ),
            }
            for frame_id in (event.evidence_frame_ids or [])
            if int(frame_id) in frame_lookup
        ]
        output.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "category": event.category,
                "description": event.description,
                "start_timestamp": event.start_timestamp,
                "end_timestamp": event.end_timestamp,
                "involved_track_ids": event.involved_track_ids or [],
                "confidence": event.confidence,
                "severity": event.severity,
                "created_at": event.created_at.isoformat(),
                "explanation_payload": event.explanation_payload or {},
                "evidence_references": evidence,
            }
        )
    return output


def _build_analysis_report(
    *,
    analysis: Analysis,
    user_id: int,
    db: Session,
) -> dict[str, Any]:
    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id
    tracks_path = analysis_dir / "tracks.json"
    tracks_data: list[dict[str, Any]] = []
    if tracks_path.is_file():
        try:
            tracks_data = json.loads(tracks_path.read_text(encoding="utf-8")).get("tracks", [])
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read tracked trajectories for behavior analysis.",
            ) from exc

    detections_path = analysis_dir / "detections.json"
    frame_width = 1
    frame_height = 1
    if detections_path.is_file():
        try:
            detections = json.loads(detections_path.read_text(encoding="utf-8"))
            first_frame = next(iter(detections.get("frames", [])), {})
            frame_width = max(1, int(first_frame.get("frame_width") or 1))
            frame_height = max(1, int(first_frame.get("frame_height") or 1))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read detection dimensions for behavior analysis.",
            ) from exc

    snapshot = _snapshot(db=db, user_id=user_id, analysis_id=analysis.id)
    snapshot.track_history = tracks_data
    report = build_behavior_report(
        session_id=analysis.id,
        tracks_data=tracks_data,
        events=_analysis_events(analysis=analysis, analysis_dir=analysis_dir, db=db),
        frame_width=frame_width,
        frame_height=frame_height,
        baseline_config=snapshot.baseline_config or DEFAULT_BASELINE_CONFIG,
    )
    _persist_report(snapshot, report, db)
    return report


def _build_live_report(
    *,
    session: LiveSession,
    user_id: int,
    db: Session,
) -> dict[str, Any]:
    snapshot = _snapshot(db=db, user_id=user_id, live_session_id=session.id)
    from app.services.live_monitor import (
        _active_live_sessions,
        _build_track_summaries,
        _serialize_tracks_for_events,
        _live_registry_lock,
    )

    with _live_registry_lock:
        runtime = _active_live_sessions.get(session.id)
    if runtime is None:
        tracks_data = snapshot.track_history or []
    else:
        with runtime.session_lock:
            tracks_data = _serialize_tracks_for_events(_build_track_summaries(runtime))
        snapshot.track_history = tracks_data

    settings = get_settings()
    event_rows = (
        db.query(LiveEvent)
        .filter(LiveEvent.session_id == session.id, LiveEvent.user_id == user_id)
        .order_by(LiveEvent.start_timestamp.asc(), LiveEvent.end_timestamp.asc())
        .all()
    )
    events = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "category": event.category,
            "description": event.description,
            "start_timestamp": event.start_timestamp,
            "end_timestamp": event.end_timestamp,
            "involved_track_ids": event.involved_track_ids or [],
            "confidence": event.confidence,
            "severity": event.severity,
            "created_at": event.created_at.isoformat(),
            "explanation_payload": event.explanation_payload or {},
            "evidence_references": (
                [
                    {
                        "timestamp_seconds": event.timestamp_seconds,
                        "url": (
                            f"{settings.api_v1_prefix}/live/{session.id}/events/"
                            f"{event.id}/snapshot"
                        ),
                    }
                ]
                if event.snapshot_path
                else []
            ),
        }
        for event in event_rows
    ]
    report = build_behavior_report(
        session_id=session.id,
        tracks_data=tracks_data,
        events=events,
        frame_width=max(session.frame_width or 1, 1),
        frame_height=max(session.frame_height or 1, 1),
        baseline_config=snapshot.baseline_config or DEFAULT_BASELINE_CONFIG,
    )
    _persist_report(snapshot, report, db)
    return report


def _filtered_records(
    records: list[dict[str, Any]],
    *,
    track_id: int | None,
    event_type: str | None,
    severity: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    result = records
    if track_id is not None:
        result = [record for record in result if track_id in record.get("track_ids", [])]
    if event_type is not None:
        result = [record for record in result if record.get("event_type") == event_type]
    if severity is not None:
        result = [record for record in result if record.get("severity") == severity]
    if start_date is not None:
        result = [
            record
            for record in result
            if record.get("created_at") and date.fromisoformat(record["created_at"][:10]) >= start_date
        ]
    if end_date is not None:
        result = [
            record
            for record in result
            if record.get("created_at") and date.fromisoformat(record["created_at"][:10]) <= end_date
        ]
    return result


def _query_filters(
    track_id: int | None = Query(default=None, ge=0),
    event_type: str | None = None,
    severity: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")
    return {
        "track_id": track_id,
        "event_type": event_type,
        "severity": severity,
        "start_date": start_date,
        "end_date": end_date,
    }


def _filter_values(report: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    return _filtered_records(report["sequences"], **filters)


def _set_baseline(
    *,
    row: BehaviorSnapshot,
    payload: BehaviorBaselineConfig,
    db: Session,
) -> dict[str, Any]:
    row.baseline_config = payload.model_dump()
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save behavior baseline configuration.",
        ) from exc
    return row.baseline_config


@router.get(
    "/analysis/{analysis_id}",
    response_model=BehaviorReportResponse,
    summary="Get behavior report for an owned completed video analysis",
)
def get_analysis_behavior(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BehaviorReportResponse:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    return BehaviorReportResponse(
        **_build_analysis_report(analysis=analysis, user_id=current_user.id, db=db)
    )


@router.get("/analysis/{analysis_id}/summary", summary="Get per-analysis behavior summary")
def get_analysis_behavior_summary(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    report = _build_analysis_report(analysis=analysis, user_id=current_user.id, db=db)
    return {"session_id": analysis.id, **report["summary"], "baseline": report["baseline"]}


@router.get("/analysis/{analysis_id}/sequences", summary="List behavior sequences with filters")
def list_analysis_behavior_sequences(
    analysis_id: str,
    filters: dict[str, Any] = Depends(_query_filters),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    report = _build_analysis_report(analysis=analysis, user_id=current_user.id, db=db)
    return _filter_values(report, filters)


@router.get("/analysis/{analysis_id}/sequences/{sequence_id}")
def get_analysis_behavior_sequence(
    analysis_id: str,
    sequence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    report = _build_analysis_report(analysis=analysis, user_id=current_user.id, db=db)
    sequence = next(
        (item for item in report["sequences"] if item["sequence_id"] == sequence_id),
        None,
    )
    if sequence is None:
        raise HTTPException(status_code=404, detail="Behavior sequence not found.")
    return sequence


@router.get("/analysis/{analysis_id}/sequences/{sequence_id}/evidence")
def get_analysis_behavior_evidence(
    analysis_id: str,
    sequence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    sequence = get_analysis_behavior_sequence(
        analysis_id=analysis_id,
        sequence_id=sequence_id,
        current_user=current_user,
        db=db,
    )
    return sequence["supporting_evidence"]


@router.get("/analysis/{analysis_id}/anomalies", summary="List explainable behavior anomalies")
def list_analysis_behavior_anomalies(
    analysis_id: str,
    filters: dict[str, Any] = Depends(_query_filters),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    report = _build_analysis_report(analysis=analysis, user_id=current_user.id, db=db)
    return _filtered_records(report["anomalies"], **filters)


@router.put("/analysis/{analysis_id}/baseline", summary="Configure this analysis baseline rules")
def configure_analysis_baseline(
    analysis_id: str,
    payload: BehaviorBaselineConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    snapshot = _snapshot(db=db, user_id=current_user.id, analysis_id=analysis.id)
    return {"session_id": analysis.id, "baseline_config": _set_baseline(row=snapshot, payload=payload, db=db)}


@router.get(
    "/live/{session_id}",
    response_model=BehaviorReportResponse,
    summary="Get behavior report for an owned live monitoring session",
)
def get_live_behavior(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BehaviorReportResponse:
    session = _owned_live_session(session_id, current_user.id, db)
    return BehaviorReportResponse(
        **_build_live_report(session=session, user_id=current_user.id, db=db)
    )


@router.get("/live/{session_id}/summary", summary="Get per-session live behavior summary")
def get_live_behavior_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = _owned_live_session(session_id, current_user.id, db)
    report = _build_live_report(session=session, user_id=current_user.id, db=db)
    return {"session_id": session.id, **report["summary"], "baseline": report["baseline"]}


@router.get("/live/{session_id}/sequences", summary="List live behavior sequences with filters")
def list_live_behavior_sequences(
    session_id: str,
    filters: dict[str, Any] = Depends(_query_filters),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    session = _owned_live_session(session_id, current_user.id, db)
    report = _build_live_report(session=session, user_id=current_user.id, db=db)
    return _filter_values(report, filters)


@router.get("/live/{session_id}/sequences/{sequence_id}")
def get_live_behavior_sequence(
    session_id: str,
    sequence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = _owned_live_session(session_id, current_user.id, db)
    report = _build_live_report(session=session, user_id=current_user.id, db=db)
    sequence = next(
        (item for item in report["sequences"] if item["sequence_id"] == sequence_id),
        None,
    )
    if sequence is None:
        raise HTTPException(status_code=404, detail="Behavior sequence not found.")
    return sequence


@router.get("/live/{session_id}/sequences/{sequence_id}/evidence")
def get_live_behavior_evidence(
    session_id: str,
    sequence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    sequence = get_live_behavior_sequence(
        session_id=session_id,
        sequence_id=sequence_id,
        current_user=current_user,
        db=db,
    )
    return sequence["supporting_evidence"]


@router.get("/live/{session_id}/anomalies", summary="List live behavior anomalies")
def list_live_behavior_anomalies(
    session_id: str,
    filters: dict[str, Any] = Depends(_query_filters),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    session = _owned_live_session(session_id, current_user.id, db)
    report = _build_live_report(session=session, user_id=current_user.id, db=db)
    return _filtered_records(report["anomalies"], **filters)


@router.put("/live/{session_id}/baseline", summary="Configure this live session baseline rules")
def configure_live_baseline(
    session_id: str,
    payload: BehaviorBaselineConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = _owned_live_session(session_id, current_user.id, db)
    snapshot = _snapshot(db=db, user_id=current_user.id, live_session_id=session.id)
    return {"session_id": session.id, "baseline_config": _set_baseline(row=snapshot, payload=payload, db=db)}
