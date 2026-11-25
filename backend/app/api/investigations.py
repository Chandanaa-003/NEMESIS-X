from collections import defaultdict
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, cast, exists, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.behavior import BehaviorSnapshot
from app.models.detection import Detection
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.investigation import (
    Investigation,
    InvestigationEvent,
    InvestigationNote,
    InvestigationSource,
    InvestigationTrack,
)
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.user import User
from app.models.video import Video
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationDetail,
    InvestigationEventCreate,
    InvestigationEventLinkInfo,
    InvestigationEvidenceItem,
    InvestigationGraphEdge,
    InvestigationGraphNode,
    InvestigationGraphResponse,
    InvestigationNoteCreate,
    InvestigationNoteInfo,
    InvestigationNoteUpdate,
    InvestigationSourceCreate,
    InvestigationSourceInfo,
    InvestigationSummary,
    InvestigationTimelineItem,
    InvestigationTimelineResponse,
    InvestigationTrackCreate,
    InvestigationTrackInfo,
    InvestigationUpdate,
)
from app.services.track_explorer import (
    format_track_code,
    get_track_detail_payload,
    load_enriched_tracks_data,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])
SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4,}\.jpg$")


def _owned_investigation(investigation_id: str, user_id: int, db: Session) -> Investigation:
    row = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id, Investigation.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return row


def _owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
    row = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if row.status != "completed":
        raise HTTPException(status_code=409, detail="Only completed video analyses can be linked.")
    return row


def _owned_live_session(session_id: str, user_id: int, db: Session) -> LiveSession:
    row = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Live monitoring session not found.")
    if row.status != "stopped":
        raise HTTPException(status_code=409, detail="Only completed live monitoring sessions can be linked.")
    return row


def _owned_source(
    investigation: Investigation,
    source_id: str,
    db: Session,
) -> InvestigationSource:
    source = (
        db.query(InvestigationSource)
        .filter(
            InvestigationSource.id == source_id,
            InvestigationSource.investigation_id == investigation.id,
        )
        .first()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Investigation source not found.")
    return source


def _source_record(source: InvestigationSource, db: Session) -> tuple[str, str, str, datetime]:
    if source.analysis_id is not None:
        analysis = db.query(Analysis).filter(Analysis.id == source.analysis_id).first()
        if analysis is None:
            raise HTTPException(status_code=404, detail="Linked analysis is no longer available.")
        video = db.query(Video).filter(Video.id == analysis.video_id).first()
        filename = video.original_filename if video else "Recorded analysis"
        label = f"{filename} · Analysis {analysis.id[:8]}"
        return "analysis", analysis.id, label, analysis.created_at
    session = db.query(LiveSession).filter(LiveSession.id == source.live_session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Linked live session is no longer available.")
    label = f"Live session · {session.started_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · {session.id[:8]}"
    return "live_session", session.id, label, session.started_at


def _source_info(source: InvestigationSource, db: Session) -> InvestigationSourceInfo:
    source_type, source_id, label, _ = _source_record(source, db)
    if source_type == "analysis":
        track_count = db.query(Track).filter(Track.analysis_id == source_id).count()
        event_count = db.query(Event).filter(Event.analysis_id == source_id).count()
        analysis = db.query(Analysis).filter(Analysis.id == source_id).first()
        video_id = analysis.video_id if analysis else None
        source_status = analysis.status if analysis else "unavailable"
        availability = "Recorded analysis source; stored frames, tracks, events, and evidence are checked individually"
    else:
        snapshot = (
            db.query(BehaviorSnapshot)
            .filter(BehaviorSnapshot.live_session_id == source_id)
            .first()
        )
        track_count = len(snapshot.track_history or []) if snapshot else 0
        event_count = (
            db.query(LiveEvent)
            .filter(LiveEvent.session_id == source_id)
            .count()
        )
        session = db.query(LiveSession).filter(LiveSession.id == source_id).first()
        video_id = None
        source_status = session.status if session else "unavailable"
        availability = (
            "Stored events and recent track samples; live frames are not archived as a full video"
            if track_count or event_count
            else "No persisted tracks or events are available for this session"
        )
    return InvestigationSourceInfo(
        id=source.id,
        source_type=source_type,  # type: ignore[arg-type]
        source_id=source_id,
        source_label=label,
        analysis_id=source.analysis_id,
        video_id=video_id,
        live_session_id=source.live_session_id,
        status=source_status,
        created_at=source.created_at,
        data_availability=availability,
        track_count=track_count,
        event_count=event_count,
    )


def _track_rows_for_source(
    source: InvestigationSource,
    db: Session,
) -> list[dict[str, Any]]:
    source_type, source_id, source_label, _ = _source_record(source, db)
    if source_type == "analysis":
        analysis = _owned_analysis(source_id, source.investigation.user_id, db)
        _, tracks = load_enriched_tracks_data(analysis.id, db=db)
        return [
            {
                "source_id": source.id,
                "source_label": source_label,
                "track_id": track.track_id,
                "class_name": track.class_name,
                "first_seen_timestamp": track.first_seen_timestamp,
                "last_seen_timestamp": track.last_seen_timestamp,
                "detection_count": track.frame_count,
            }
            for track in tracks
        ]
    snapshot = (
        db.query(BehaviorSnapshot)
        .filter(
            BehaviorSnapshot.live_session_id == source_id,
            BehaviorSnapshot.user_id == source.investigation.user_id,
        )
        .first()
    )
    if snapshot is None:
        return []
    return [
        {
            "source_id": source.id,
            "source_label": source_label,
            "track_id": int(track["track_id"]),
            "class_name": str(track.get("class_name", "object")),
            "first_seen_timestamp": float(track.get("first_seen_timestamp", 0.0)),
            "last_seen_timestamp": float(track.get("last_seen_timestamp", 0.0)),
            "detection_count": int(track.get("frame_count", len(track.get("timeline_points", [])))),
        }
        for track in (snapshot.track_history or [])
        if track.get("track_id") is not None
    ]


def _track_class_map_for_source(
    source: InvestigationSource,
    db: Session,
) -> dict[int, str]:
    if source.analysis_id:
        rows = (
            db.query(Track.track_id, Track.class_name)
            .filter(Track.analysis_id == source.analysis_id)
            .all()
        )
        if rows:
            return {int(track_id): str(class_name) for track_id, class_name in rows}
    return {
        int(track["track_id"]): str(track["class_name"])
        for track in _track_rows_for_source(source, db)
    }


def _track_info(
    track: dict[str, Any],
    *,
    linked_track_keys: set[tuple[str, int]],
    link_id: str | None = None,
) -> InvestigationTrackInfo:
    track_id = int(track["track_id"])
    class_name = str(track["class_name"])
    entity_label = "Person" if class_name.lower() == "person" else "Object"
    return InvestigationTrackInfo(
        id=link_id or "",
        source_id=str(track["source_id"]),
        track_id=track_id,
        track_label=format_track_code(track_id),
        entity_label=entity_label,
        class_name=class_name,
        first_seen_timestamp=float(track["first_seen_timestamp"]),
        last_seen_timestamp=float(track["last_seen_timestamp"]),
        detection_count=int(track["detection_count"]),
        linked=(str(track["source_id"]), track_id) in linked_track_keys,
    )


def _track_label(class_name: str | None, track_id: int) -> str:
    code = format_track_code(track_id)
    if class_name is None:
        return f"Track {code}"
    label = "Person" if class_name.lower() == "person" else f"Object ({class_name})"
    return f"{label} {code}"


def _event_track_ids(event: Event | LiveEvent) -> list[int]:
    result = list(dict.fromkeys(int(value) for value in (event.involved_track_ids or [])))
    payload = event.explanation_payload or {}
    for key in ("person_track_id", "object_track_id"):
        value = payload.get(key)
        if value is not None and int(value) not in result:
            result.append(int(value))
    return result


def _event_track_label(
    event: Event | LiveEvent,
    class_name: str | None,
    track_id: int,
) -> str:
    payload = event.explanation_payload or {}
    if payload.get("person_track_id") is not None and int(payload["person_track_id"]) == track_id:
        return f"Person {format_track_code(track_id)}"
    if payload.get("object_track_id") is not None and int(payload["object_track_id"]) == track_id:
        return f"Object {format_track_code(track_id)}"
    return _track_label(class_name, track_id)


def _investigation_counts(investigation: Investigation, db: Session) -> dict[str, int]:
    return {
        "source_count": db.query(InvestigationSource)
        .filter(InvestigationSource.investigation_id == investigation.id)
        .count(),
        "event_count": db.query(InvestigationEvent)
        .filter(InvestigationEvent.investigation_id == investigation.id)
        .count(),
        "track_count": db.query(InvestigationTrack)
        .filter(InvestigationTrack.investigation_id == investigation.id)
        .count(),
        "note_count": db.query(InvestigationNote)
        .filter(InvestigationNote.investigation_id == investigation.id)
        .count(),
    }


def _summary(investigation: Investigation, db: Session) -> InvestigationSummary:
    return InvestigationSummary(
        id=investigation.id,
        title=investigation.title,
        description=investigation.description,
        status=investigation.status,  # type: ignore[arg-type]
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        **_investigation_counts(investigation, db),
    )


def _find_link_event(
    link: InvestigationEvent,
    db: Session,
) -> Event | LiveEvent:
    if link.event_id:
        row = db.query(Event).filter(Event.id == link.event_id).first()
    else:
        row = db.query(LiveEvent).filter(LiveEvent.id == link.live_event_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Linked event is no longer available.")
    return row


def _event_link_info(
    link: InvestigationEvent,
    db: Session,
    source: InvestigationSource | None = None,
    track_classes: dict[int, str] | None = None,
) -> InvestigationEventLinkInfo:
    row = _find_link_event(link, db)
    track_ids = _event_track_ids(row)
    if source is None:
        source = db.query(InvestigationSource).filter(InvestigationSource.id == link.source_id).first()
    if track_classes is None and source is not None:
        track_classes = {
            int(track["track_id"]): str(track["class_name"])
            for track in _track_rows_for_source(source, db)
        }
    track_classes = track_classes or {}
    return InvestigationEventLinkInfo(
        id=link.id,
        source_id=link.source_id,
        event_id=link.event_id,
        live_event_id=link.live_event_id,
        event_type=row.event_type,
        event_category=row.category,
        title=row.title,
        timestamp_seconds=float(row.start_timestamp),
        track_ids=track_ids,
        track_labels=[
            _event_track_label(row, track_classes.get(track_id), track_id)
            for track_id in track_ids
        ],
        confidence=float(row.confidence),
        severity=row.severity,
        created_at=row.created_at,
    )


def _note_info(note: InvestigationNote) -> InvestigationNoteInfo:
    return InvestigationNoteInfo(
        id=note.id,
        investigation_id=note.investigation_id,
        source_id=note.source_id,
        investigation_event_id=note.investigation_event_id,
        timestamp_seconds=note.timestamp_seconds,
        content=note.content,
        author_user_id=note.author_user_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _detail(investigation: Investigation, db: Session) -> InvestigationDetail:
    summary = _summary(investigation, db)
    sources = (
        db.query(InvestigationSource)
        .filter(InvestigationSource.investigation_id == investigation.id)
        .order_by(InvestigationSource.created_at.asc())
        .all()
    )
    event_links = (
        db.query(InvestigationEvent)
        .filter(InvestigationEvent.investigation_id == investigation.id)
        .order_by(InvestigationEvent.created_at.desc())
        .limit(500)
        .all()
    )
    track_links = (
        db.query(InvestigationTrack)
        .filter(InvestigationTrack.investigation_id == investigation.id)
        .order_by(InvestigationTrack.created_at.desc())
        .limit(500)
        .all()
    )
    notes = (
        db.query(InvestigationNote)
        .filter(InvestigationNote.investigation_id == investigation.id)
        .order_by(InvestigationNote.updated_at.desc())
        .limit(500)
        .all()
    )
    linked_track_keys = {(link.source_id, link.track_id) for link in track_links}
    source_by_id = {source.id: source for source in sources}
    track_catalog: dict[tuple[str, int], dict[str, Any]] = {}
    classes_by_source: dict[str, dict[int, str]] = {}
    for source in sources:
        source_tracks = _track_rows_for_source(source, db)
        classes_by_source[source.id] = {
            int(track["track_id"]): str(track["class_name"]) for track in source_tracks
        }
        for track in source_tracks:
            track_catalog[(source.id, int(track["track_id"]))] = track
    return InvestigationDetail(
        **summary.model_dump(),
        sources=[_source_info(source, db) for source in sources],
        linked_events=[
            _event_link_info(
                link,
                db,
                source_by_id.get(link.source_id),
                classes_by_source.get(link.source_id),
            )
            for link in event_links
        ],
        linked_tracks=[
            _track_info(
                track_catalog[(link.source_id, link.track_id)],
                linked_track_keys=linked_track_keys,
                link_id=link.id,
            )
            for link in track_links
            if (link.source_id, link.track_id) in track_catalog
        ],
        notes=[_note_info(note) for note in notes],
    )


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This record is already linked or conflicts with existing data.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save investigation data.") from exc


def _linked_sources(investigation: Investigation, db: Session) -> list[InvestigationSource]:
    return (
        db.query(InvestigationSource)
        .filter(InvestigationSource.investigation_id == investigation.id)
        .order_by(InvestigationSource.created_at.asc())
        .all()
    )


def _frame_lookup(analysis_id: str) -> dict[int, tuple[str, float]]:
    path = get_settings().resolved_processed_dir / analysis_id / "metadata.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[int, tuple[str, float]] = {}
    for frame in payload.get("frames", []):
        filename = Path(str(frame.get("filename", ""))).name
        if not SAFE_FRAME_FILENAME_RE.fullmatch(filename):
            continue
        result[int(frame["frame_index"])] = (filename, float(frame["timestamp_seconds"]))
    return result


def _date_filters(query: Any, model: Any, start_date: date | None, end_date: date | None) -> Any:
    date_column = model.created_at if hasattr(model, "created_at") else model.started_at
    if start_date:
        query = query.filter(func.date(date_column) >= start_date.isoformat())
    if end_date:
        query = query.filter(func.date(date_column) <= end_date.isoformat())
    return query


def _event_track_predicate(model: Any, track_id: int) -> Any:
    track_values = func.json_each(model.involved_track_ids).table_valued("value").alias()
    involved = exists(
        select(1)
        .select_from(track_values)
        .where(cast(track_values.c.value, Integer) == track_id)
    )
    return or_(
        involved,
        model.explanation_payload["person_track_id"].as_integer() == track_id,
        model.explanation_payload["object_track_id"].as_integer() == track_id,
    )


def _timeline_sources(
    investigation: Investigation,
    db: Session,
) -> tuple[list[InvestigationSource], dict[str, InvestigationSourceInfo], dict[str, dict[int, str]]]:
    sources = _linked_sources(investigation, db)
    info = {source.id: _source_info(source, db) for source in sources}
    classes: dict[str, dict[int, str]] = {}
    for source in sources:
        classes[source.id] = _track_class_map_for_source(source, db)
    return sources, info, classes


def _build_timeline(
    *,
    investigation: Investigation,
    db: Session,
    event_category: str | None,
    source_id: str | None,
    track_id: int | None,
    severity: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    offset: int,
) -> InvestigationTimelineResponse:
    sources, source_infos, track_classes = _timeline_sources(investigation, db)
    if source_id:
        sources = [source for source in sources if source.id == source_id]
        if not sources:
            raise HTTPException(status_code=404, detail="Investigation source not found.")
        source_infos = {source.id: source_infos[source.id] for source in sources}
        track_classes = {source.id: track_classes[source.id] for source in sources}
    source_order = {
        source.id: _source_record(source, db)[3]
        for source in sources
    }
    live_ids = [source.live_session_id for source in sources if source.live_session_id]
    linked_event_keys = {
        (link.source_id, link.event_id or link.live_event_id)
        for link in db.query(InvestigationEvent)
        .filter(InvestigationEvent.investigation_id == investigation.id)
        .all()
    }
    fetch_limit = limit + offset + 1
    rows: list[InvestigationTimelineItem] = []
    total = 0
    recorded_events: list[Event] = []
    live_events: list[LiveEvent] = []

    if event_category is None or event_category not in {"detection", "tracking"}:
        for source in sources:
            if source.analysis_id:
                query = db.query(Event).filter(Event.analysis_id == source.analysis_id)
                if event_category:
                    query = query.filter(Event.category == event_category)
                if severity:
                    query = query.filter(Event.severity == severity)
                if track_id is not None:
                    query = query.filter(_event_track_predicate(Event, track_id))
                # Date filters use the source creation date; event seconds remain source-relative.
                query = query.join(Analysis, Analysis.id == Event.analysis_id)
                query = _date_filters(query, Analysis, start_date, end_date)
                total += query.count()
                recorded_events.extend(
                    query.order_by(Event.start_timestamp.asc(), Event.id.asc())
                    .limit(fetch_limit)
                    .all()
                )
            elif source.live_session_id:
                query = db.query(LiveEvent).filter(LiveEvent.session_id == source.live_session_id)
                if event_category:
                    query = query.filter(LiveEvent.category == event_category)
                if severity:
                    query = query.filter(LiveEvent.severity == severity)
                if track_id is not None:
                    query = query.filter(_event_track_predicate(LiveEvent, track_id))
                query = query.join(LiveSession, LiveSession.id == LiveEvent.session_id)
                query = _date_filters(query, LiveSession, start_date, end_date)
                total += query.count()
                live_events.extend(
                    query.order_by(LiveEvent.start_timestamp.asc(), LiveEvent.id.asc())
                    .limit(fetch_limit)
                    .all()
                )

    recorded_event_ids = [event.id for event in recorded_events]
    evidence_by_event: dict[str, list[Evidence]] = defaultdict(list)
    if recorded_event_ids:
        for item in (
            db.query(Evidence)
            .filter(
                Evidence.event_id.in_(recorded_event_ids),
                Evidence.user_id == investigation.user_id,
            )
            .order_by(Evidence.timestamp_seconds.asc(), Evidence.evidence_type.asc())
            .all()
        ):
            evidence_by_event[item.event_id].append(item)

    settings = get_settings()
    for event in recorded_events:
        source = next((row for row in sources if row.analysis_id == event.analysis_id), None)
        if source is None:
            continue
        info = source_infos[source.id]
        ids = _event_track_ids(event)
        explanation = event.explanation_payload or {}
        evidence = [
            {
                "id": item.id,
                "timestamp_seconds": item.timestamp_seconds,
                "evidence_type": item.evidence_type,
                "image_url": f"{settings.api_v1_prefix}/evidence/{item.id}/image",
            }
            for item in evidence_by_event.get(event.id, [])
        ]
        rows.append(
            InvestigationTimelineItem(
                id=f"event:{event.id}",
                record_type="anomaly" if isinstance(explanation.get("anomaly_score"), dict) else "event",
                source_id=source.id,
                source_type="analysis",
                source_label=info.source_label,
                event_id=event.id,
                event_type=event.event_type,
                event_category=event.category,
                title=event.title,
                explanation=event.description,
                timestamp_seconds=event.start_timestamp,
                created_at=event.created_at,
                track_ids=ids,
                track_labels=[
                    _event_track_label(event, track_classes[source.id].get(tid), tid)
                    for tid in ids
                ],
                confidence=event.confidence,
                severity=event.severity,
                evidence=evidence,
                linked=(source.id, event.id) in linked_event_keys,
            )
        )

    for event in live_events:
        source = next((row for row in sources if row.live_session_id == event.session_id), None)
        if source is None:
            continue
        info = source_infos[source.id]
        ids = _event_track_ids(event)
        explanation = event.explanation_payload or {}
        evidence = (
            [
                {
                    "id": event.id,
                    "timestamp_seconds": event.timestamp_seconds,
                    "evidence_type": "annotated_tracking",
                    "image_url": (
                        f"{settings.api_v1_prefix}/live/{event.session_id}/events/"
                        f"{event.id}/snapshot"
                    ),
                }
            ]
            if event.snapshot_path
            else []
        )
        rows.append(
            InvestigationTimelineItem(
                id=f"event:{event.id}",
                record_type="anomaly" if isinstance(explanation.get("anomaly_score"), dict) else "event",
                source_id=source.id,
                source_type="live_session",
                source_label=info.source_label,
                event_id=event.id,
                event_type=event.event_type,
                event_category=event.category,
                title=event.title,
                explanation=event.description,
                timestamp_seconds=event.start_timestamp,
                created_at=event.created_at,
                track_ids=ids,
                track_labels=[
                    _event_track_label(event, track_classes[source.id].get(tid), tid)
                    for tid in ids
                ],
                confidence=event.confidence,
                severity=event.severity,
                evidence=evidence,
                linked=(source.id, event.id) in linked_event_keys,
            )
        )

    if severity is None and (event_category is None or event_category == "detection"):
        detections: list[tuple[Detection, datetime]] = []
        for source in sources:
            if not source.analysis_id:
                continue
            query = (
                db.query(Detection, Analysis.created_at)
                .join(Analysis, Analysis.id == Detection.analysis_id)
                .filter(Detection.analysis_id == source.analysis_id)
            )
            if track_id is not None:
                query = query.filter(Detection.track_id == track_id)
            query = _date_filters(query, Analysis, start_date, end_date)
            total += query.count()
            detections.extend(
                query.order_by(Detection.timestamp_seconds.asc(), Detection.id.asc())
                .limit(fetch_limit)
                .all()
            )
        analysis_source = {source.analysis_id: source for source in sources if source.analysis_id}
        frame_lookups = {source.analysis_id: _frame_lookup(source.analysis_id) for source in sources if source.analysis_id}
        for detection, source_created_at in detections:
            source = analysis_source.get(detection.analysis_id)
            if source is None:
                continue
            info = source_infos[source.id]
            frame = frame_lookups.get(detection.analysis_id, {}).get(detection.frame_index)
            evidence = []
            if frame:
                filename, frame_timestamp = frame
                evidence.append(
                    {
                        "id": f"frame:{detection.analysis_id}:{detection.frame_index}",
                        "timestamp_seconds": frame_timestamp,
                        "evidence_type": "original_frame",
                        "image_url": (
                            f"{settings.api_v1_prefix}/analysis/{detection.analysis_id}/frames/{filename}"
                        ),
                    }
                )
            ids = [detection.track_id] if detection.track_id is not None else []
            class_name = detection.class_name
            rows.append(
                InvestigationTimelineItem(
                    id=f"detection:{detection.analysis_id}:{detection.id}",
                    record_type="detection",
                    source_id=source.id,
                    source_type="analysis",
                    source_label=info.source_label,
                    event_type="detection_observation",
                    event_category="detection",
                    title=f"{class_name.title()} detected",
                    explanation=f"Stored detector observation for {class_name} at frame {detection.frame_index}.",
                    timestamp_seconds=detection.timestamp_seconds,
                    created_at=source_created_at,
                    track_ids=ids,
                    track_labels=[_track_label(class_name, detection.track_id)] if ids else [],
                    confidence=detection.confidence,
                    evidence=evidence,
                )
            )

    linked_track_rows = (
        db.query(InvestigationTrack)
        .filter(InvestigationTrack.investigation_id == investigation.id)
        .all()
    )
    linked_track_keys = {(item.source_id, item.track_id) for item in linked_track_rows}
    if severity is None and (event_category is None or event_category == "tracking") and linked_track_rows:
        for source in sources:
            source_milestones: list[InvestigationTimelineItem] = []
            source_tracks = _track_rows_for_source(source, db)
            for track in source_tracks:
                track_key = (str(track["source_id"]), int(track["track_id"]))
                if track_key not in linked_track_keys:
                    continue
                if track_id is not None and int(track["track_id"]) != track_id:
                    continue
                _, source_id, source_label, source_created_at = _source_record(source, db)
                source_type = "analysis" if source.analysis_id else "live_session"
                for edge, timestamp_key in (
                    ("first", "first_seen_timestamp"),
                    ("last", "last_seen_timestamp"),
                ):
                    timestamp_seconds = float(track[timestamp_key])
                    source_milestones.append(
                        InvestigationTimelineItem(
                            id=f"track:{source.id}:{track['track_id']}:{edge}",
                            record_type="track_observation",
                            source_id=source.id,
                            source_type=source_type,
                            source_label=source_label,
                            event_type=f"track_{edge}_observed",
                            event_category="tracking",
                            title=f"{_track_label(str(track['class_name']), int(track['track_id']))} {edge} observed",
                            explanation="Track boundary derived from saved tracked observations; IDs are local to this source.",
                            timestamp_seconds=timestamp_seconds,
                            created_at=source_created_at,
                            track_ids=[int(track["track_id"])],
                            track_labels=[_track_label(str(track["class_name"]), int(track["track_id"]))],
                        )
                    )
            source_milestones.sort(key=lambda item: (item.timestamp_seconds, item.id))
            total += len(source_milestones)
            rows.extend(source_milestones[:fetch_limit])

    # Live observations are available only when retained in the behavior snapshot.
    if severity is None and live_ids and (event_category is None or event_category == "detection"):
        live_source_by_id = {source.live_session_id: source for source in sources if source.live_session_id}
        for session_id, source in live_source_by_id.items():
            session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
            if session is None:
                continue
            if start_date and session.started_at.date() < start_date:
                continue
            if end_date and session.started_at.date() > end_date:
                continue
            snapshot = (
                db.query(BehaviorSnapshot)
                .filter(BehaviorSnapshot.live_session_id == session_id)
                .first()
            )
            if snapshot is None:
                continue
            info = source_infos[source.id]
            source_observations: list[InvestigationTimelineItem] = []
            for track in snapshot.track_history or []:
                if track_id is not None and int(track.get("track_id", -1)) != track_id:
                    continue
                for point in track.get("timeline_points", []):
                    source_observations.append(
                        InvestigationTimelineItem(
                            id=f"live-detection:{session_id}:{track.get('track_id')}:{point.get('frame_index')}",
                            record_type="detection",
                            source_id=source.id,
                            source_type="live_session",
                            source_label=info.source_label,
                            event_type="stored_track_observation",
                            event_category="detection",
                            title=f"{str(track.get('class_name', 'Object')).title()} observed",
                            explanation="Stored live track sample. No original frame is available unless an event snapshot was saved.",
                            timestamp_seconds=float(point.get("timestamp_seconds", 0.0)),
                            created_at=session.started_at,
                            track_ids=[int(track["track_id"])],
                            track_labels=[
                                _track_label(str(track.get("class_name", "object")), int(track["track_id"]))
                            ],
                            confidence=float(point.get("confidence", track.get("avg_confidence", 0.0))),
                        )
                    )
            source_observations.sort(key=lambda item: (item.timestamp_seconds, item.id))
            total += len(source_observations)
            rows.extend(source_observations[:fetch_limit])

    rows.sort(
        key=lambda item: (
            source_order.get(item.source_id, datetime.min.replace(tzinfo=timezone.utc)),
            item.timestamp_seconds,
            item.id,
        )
    )
    page = rows[offset : offset + limit]
    return InvestigationTimelineResponse(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(page) < total,
    )


@router.post("", response_model=InvestigationDetail, status_code=status.HTTP_201_CREATED)
def create_investigation(
    payload: InvestigationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationDetail:
    row = Investigation(user_id=current_user.id, **payload.model_dump())
    db.add(row)
    _save(db)
    db.refresh(row)
    return _detail(row, db)


@router.get("", response_model=list[InvestigationSummary])
def list_investigations(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|reviewing|closed)$"),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvestigationSummary]:
    query = db.query(Investigation).filter(Investigation.user_id == current_user.id)
    if status_filter:
        query = query.filter(Investigation.status == status_filter)
    if q:
        query = query.filter(Investigation.title.ilike(f"%{q}%"))
    rows = query.order_by(Investigation.updated_at.desc()).offset(offset).limit(limit).all()
    return [_summary(row, db) for row in rows]


@router.get("/{investigation_id}", response_model=InvestigationDetail)
def get_investigation(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationDetail:
    return _detail(_owned_investigation(investigation_id, current_user.id, db), db)


@router.patch("/{investigation_id}", response_model=InvestigationDetail)
def update_investigation(
    investigation_id: str,
    payload: InvestigationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationDetail:
    row = _owned_investigation(investigation_id, current_user.id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    _save(db)
    db.refresh(row)
    return _detail(row, db)


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = _owned_investigation(investigation_id, current_user.id, db)
    db.delete(row)
    _save(db)


@router.post(
    "/{investigation_id}/sources",
    response_model=InvestigationSourceInfo,
    status_code=status.HTTP_201_CREATED,
)
def add_investigation_source(
    investigation_id: str,
    payload: InvestigationSourceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationSourceInfo:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    if payload.analysis_id:
        _owned_analysis(payload.analysis_id, current_user.id, db)
    else:
        _owned_live_session(str(payload.live_session_id), current_user.id, db)
    source = InvestigationSource(
        investigation_id=investigation.id,
        analysis_id=payload.analysis_id,
        live_session_id=payload.live_session_id,
    )
    db.add(source)
    _save(db)
    db.refresh(source)
    return _source_info(source, db)


@router.delete("/{investigation_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_investigation_source(
    investigation_id: str,
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    source = _owned_source(investigation, source_id, db)
    db.delete(source)
    _save(db)


@router.get("/{investigation_id}/tracks", response_model=list[InvestigationTrackInfo])
def search_investigation_tracks(
    investigation_id: str,
    q: str | None = Query(default=None, max_length=100),
    entity: str | None = Query(default=None, pattern="^(person|object)$"),
    source_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvestigationTrackInfo]:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    sources = _linked_sources(investigation, db)
    if source_id:
        sources = [source for source in sources if source.id == source_id]
        if not sources:
            raise HTTPException(status_code=404, detail="Investigation source not found.")
    linked_track_links = (
        db.query(InvestigationTrack)
        .filter(InvestigationTrack.investigation_id == investigation.id)
        .all()
    )
    linked_track_keys = {(item.source_id, item.track_id) for item in linked_track_links}
    results: list[InvestigationTrackInfo] = []
    for source in sources:
        for track in _track_rows_for_source(source, db):
            track_info = _track_info(track, linked_track_keys=linked_track_keys)
            searchable = f"{track_info.track_label} {track_info.class_name} {track_info.entity_label} {track['source_label']}".lower()
            if q and q.lower() not in searchable:
                continue
            if entity and track_info.entity_label.lower() != entity:
                continue
            results.append(track_info)
    results.sort(key=lambda item: (item.source_id, item.first_seen_timestamp, item.track_id))
    return results[:limit]


@router.post(
    "/{investigation_id}/tracks",
    response_model=InvestigationTrackInfo,
    status_code=status.HTTP_201_CREATED,
)
def link_investigation_track(
    investigation_id: str,
    payload: InvestigationTrackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationTrackInfo:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    source = _owned_source(investigation, payload.source_id, db)
    track = next(
        (
            row for row in _track_rows_for_source(source, db)
            if int(row["track_id"]) == payload.track_id
        ),
        None,
    )
    if track is None:
        raise HTTPException(status_code=404, detail="Track ID was not found in this source.")
    if (
        db.query(InvestigationTrack)
        .filter(
            InvestigationTrack.investigation_id == investigation.id,
            InvestigationTrack.source_id == source.id,
            InvestigationTrack.track_id == payload.track_id,
        )
        .first()
    ):
        raise HTTPException(status_code=409, detail="This source-scoped track is already linked.")
    link = InvestigationTrack(
        investigation_id=investigation.id,
        source_id=source.id,
        track_id=payload.track_id,
        class_name=str(track["class_name"]),
    )
    db.add(link)
    _save(db)
    db.refresh(link)
    return _track_info(
        {**track, "source_id": source.id},
        linked_track_keys={(source.id, payload.track_id)},
        link_id=link.id,
    )


@router.delete("/{investigation_id}/tracks/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_investigation_track(
    investigation_id: str,
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    link = (
        db.query(InvestigationTrack)
        .filter(
            InvestigationTrack.id == link_id,
            InvestigationTrack.investigation_id == investigation.id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Investigation track link not found.")
    db.delete(link)
    _save(db)


@router.get("/{investigation_id}/tracks/{source_id}/{track_id}")
def get_investigation_track_detail(
    investigation_id: str,
    source_id: str,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    source = _owned_source(investigation, source_id, db)
    track = next(
        (row for row in _track_rows_for_source(source, db) if int(row["track_id"]) == track_id),
        None,
    )
    if track is None:
        raise HTTPException(status_code=404, detail="Track ID was not found in this source.")
    _, source_db_id, source_label, _ = _source_record(source, db)
    if source.analysis_id:
        analysis = _owned_analysis(source_db_id, current_user.id, db)
        detail = get_track_detail_payload(
            analysis=analysis,
            track_id=track_id,
            db=db,
            api_prefix=get_settings().api_v1_prefix,
        ).model_dump(mode="json")
        return {
            **detail,
            "source_id": source.id,
            "source_label": source_label,
            "entity_label": "Person" if str(track["class_name"]).lower() == "person" else "Object",
            "temporary_id_notice": (
                f"{detail['temporary_id_notice']} This ID is scoped to {source_label} only."
            ),
            "history_availability": "Recorded analysis track history and extracted frames.",
        }

    snapshot = (
        db.query(BehaviorSnapshot)
        .filter(
            BehaviorSnapshot.live_session_id == source_db_id,
            BehaviorSnapshot.user_id == current_user.id,
        )
        .first()
    )
    raw_track = next(
        (
            item for item in (snapshot.track_history or [])
            if int(item.get("track_id", -1)) == track_id
        ),
        None,
    ) if snapshot else None
    if raw_track is None:
        raise HTTPException(status_code=404, detail="Stored live track history is not available.")
    events = (
        db.query(LiveEvent)
        .filter(
            LiveEvent.session_id == source_db_id,
            LiveEvent.user_id == current_user.id,
        )
        .order_by(LiveEvent.start_timestamp.asc())
        .all()
    )
    related = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description,
            "timestamp_seconds": event.start_timestamp,
            "confidence": event.confidence,
            "severity": event.severity,
            "snapshot_url": (
                f"{get_settings().api_v1_prefix}/live/{source_db_id}/events/{event.id}/snapshot"
                if event.snapshot_path
                else None
            ),
        }
        for event in events
        if track_id in [int(value) for value in (event.involved_track_ids or [])]
    ]
    return {
        "source_id": source.id,
        "source_label": source_label,
        "session_id": source_db_id,
        "track_id": track_id,
        "track_label": format_track_code(track_id),
        "entity_label": "Person" if str(raw_track.get("class_name", "")).lower() == "person" else "Object",
        "class_name": raw_track.get("class_name", "object"),
        "first_seen_timestamp": raw_track.get("first_seen_timestamp", 0.0),
        "last_seen_timestamp": raw_track.get("last_seen_timestamp", 0.0),
        "detection_count": raw_track.get("frame_count", 0),
        "detection_history": raw_track.get("timeline_points", []),
        "movement_history": raw_track.get("timeline_points", []),
        "related_events": related,
        "evidence_frames": [event["snapshot_url"] for event in related if event["snapshot_url"]],
        "history_availability": (
            "Only recent track samples persisted for live analysis are available; no continuous "
            "video or per-frame archive is claimed."
        ),
        "temporary_id_notice": f"{format_track_code(track_id)} is local to this live session only.",
    }


@router.post(
    "/{investigation_id}/events",
    response_model=InvestigationEventLinkInfo,
    status_code=status.HTTP_201_CREATED,
)
def link_investigation_event(
    investigation_id: str,
    payload: InvestigationEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationEventLinkInfo:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    source = _owned_source(investigation, payload.source_id, db)
    if payload.event_id:
        if source.analysis_id is None:
            raise HTTPException(status_code=400, detail="A recorded event must use an analysis source.")
        event = (
            db.query(Event)
            .join(Analysis, Analysis.id == Event.analysis_id)
            .filter(
                Event.id == payload.event_id,
                Event.analysis_id == source.analysis_id,
                Analysis.user_id == current_user.id,
            )
            .first()
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Event was not found in this source.")
    else:
        if source.live_session_id is None:
            raise HTTPException(status_code=400, detail="A live event must use a live-session source.")
        event = (
            db.query(LiveEvent)
            .filter(
                LiveEvent.id == payload.live_event_id,
                LiveEvent.session_id == source.live_session_id,
                LiveEvent.user_id == current_user.id,
            )
            .first()
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Live event was not found in this source.")
    link = InvestigationEvent(
        investigation_id=investigation.id,
        source_id=source.id,
        event_id=payload.event_id,
        live_event_id=payload.live_event_id,
    )
    db.add(link)
    _save(db)
    db.refresh(link)
    return _event_link_info(link, db)


@router.delete("/{investigation_id}/events/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_investigation_event(
    investigation_id: str,
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    link = (
        db.query(InvestigationEvent)
        .filter(
            InvestigationEvent.id == link_id,
            InvestigationEvent.investigation_id == investigation.id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Investigation event link not found.")
    db.delete(link)
    _save(db)


@router.get("/{investigation_id}/timeline", response_model=InvestigationTimelineResponse)
def get_investigation_timeline(
    investigation_id: str,
    event_category: str | None = Query(default=None, max_length=64),
    source_id: str | None = None,
    track_id: int | None = Query(default=None, ge=0),
    severity: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationTimelineResponse:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    return _build_timeline(
        investigation=investigation,
        db=db,
        event_category=event_category,
        source_id=source_id,
        track_id=track_id,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get("/{investigation_id}/graph", response_model=InvestigationGraphResponse)
def get_investigation_graph(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationGraphResponse:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    sources, source_infos, classes = _timeline_sources(investigation, db)
    nodes: dict[str, InvestigationGraphNode] = {}
    edges: list[InvestigationGraphEdge] = []
    for source in sources:
        source_info = source_infos[source.id]
        if source.analysis_id:
            events: list[Event | LiveEvent] = (
                db.query(Event)
                .filter(Event.analysis_id == source.analysis_id)
                .order_by(Event.start_timestamp.asc())
                .limit(2000)
                .all()
            )
        else:
            events = (
                db.query(LiveEvent)
                .filter(
                    LiveEvent.session_id == source.live_session_id,
                    LiveEvent.user_id == investigation.user_id,
                )
                .order_by(LiveEvent.start_timestamp.asc())
                .limit(2000)
                .all()
            )
        for event in events:
            event_key = f"event:{source.id}:{event.id}"
            timestamp = float(event.start_timestamp)
            nodes[event_key] = InvestigationGraphNode(
                id=event_key,
                node_type="event",
                label=f"Event {event.id[:8]} · {event.title}",
                source_id=source.id,
                source_label=source_info.source_label,
                timestamp_seconds=timestamp,
                details={
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "category": event.category,
                    "severity": event.severity,
                    "confidence": event.confidence,
                },
            )
            for current_track_id in _event_track_ids(event):
                class_name = classes[source.id].get(current_track_id)
                payload = event.explanation_payload or {}
                if payload.get("person_track_id") is not None and int(payload["person_track_id"]) == current_track_id:
                    kind = "person"
                elif payload.get("object_track_id") is not None and int(payload["object_track_id"]) == current_track_id:
                    kind = "object"
                elif class_name:
                    kind = "person" if class_name.lower() == "person" else "object"
                else:
                    kind = "unknown_track"
                track_key = f"track:{source.id}:{current_track_id}"
                nodes.setdefault(
                    track_key,
                    InvestigationGraphNode(
                        id=track_key,
                        node_type=kind,  # type: ignore[arg-type]
                        label=_event_track_label(event, class_name, current_track_id),
                        source_id=source.id,
                        source_label=source_info.source_label,
                        details={
                            "track_id": current_track_id,
                            "class_name": class_name or "unknown",
                            "identity_scope": source_info.source_label,
                        },
                    ),
                )
                uncertainty = (event.explanation_payload or {}).get("association_uncertainty")
                edges.append(
                    InvestigationGraphEdge(
                        id=f"edge:{source.id}:{event.id}:{current_track_id}",
                        source=track_key,
                        target=event_key,
                        label=f"{kind.replace('_', ' ')} involved",
                        timestamp_seconds=timestamp,
                        confidence=event.confidence,
                        uncertainty=str(uncertainty) if uncertainty else None,
                        event_id=event.id,
                    )
                )

    linked_track_links = (
        db.query(InvestigationTrack)
        .filter(InvestigationTrack.investigation_id == investigation.id)
        .all()
    )
    for link in linked_track_links:
        source = next((item for item in sources if item.id == link.source_id), None)
        if source is None:
            continue
        class_name = classes[source.id].get(link.track_id, link.class_name)
        kind = "person" if class_name.lower() == "person" else "object"
        track_key = f"track:{source.id}:{link.track_id}"
        nodes.setdefault(
            track_key,
            InvestigationGraphNode(
                id=track_key,
                node_type=kind,  # type: ignore[arg-type]
                label=_track_label(class_name, link.track_id),
                source_id=source.id,
                source_label=source_infos[source.id].source_label,
                details={"track_id": link.track_id, "class_name": class_name},
            ),
        )
    return InvestigationGraphResponse(nodes=list(nodes.values()), edges=edges)


@router.get("/{investigation_id}/evidence", response_model=list[InvestigationEvidenceItem])
def get_investigation_evidence(
    investigation_id: str,
    source_id: str | None = None,
    event_link_id: str | None = None,
    event_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvestigationEvidenceItem]:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    sources = _linked_sources(investigation, db)
    if source_id:
        sources = [source for source in sources if source.id == source_id]
        if not sources:
            raise HTTPException(status_code=404, detail="Investigation source not found.")
    if event_link_id:
        event_link = (
            db.query(InvestigationEvent)
            .filter(
                InvestigationEvent.id == event_link_id,
                InvestigationEvent.investigation_id == investigation.id,
            )
            .first()
        )
        if event_link is None:
            raise HTTPException(status_code=404, detail="Investigation event link not found.")
        sources = [source for source in sources if source.id == event_link.source_id]
        event_id = event_link.event_id or event_link.live_event_id
    if event_id and not source_id and not event_link_id:
        raise HTTPException(status_code=400, detail="Provide source_id when requesting one event's evidence.")

    result: list[InvestigationEvidenceItem] = []
    settings = get_settings()
    for source in sources:
        info = _source_info(source, db)
        source_track_classes = _track_class_map_for_source(source, db)
        if source.analysis_id:
            query = (
                db.query(Evidence, Event)
                .join(Event, Event.id == Evidence.event_id)
                .filter(
                    Evidence.analysis_id == source.analysis_id,
                    Evidence.user_id == current_user.id,
                )
            )
            if event_link_id:
                event_link = db.query(InvestigationEvent).filter(InvestigationEvent.id == event_link_id).first()
                query = query.filter(Event.id == event_link.event_id)
            elif event_id:
                query = query.filter(Event.id == event_id)
            for item, event in query.order_by(Evidence.timestamp_seconds.asc(), Evidence.frame_number.asc()).limit(2000):
                linked_tracks = [int(value) for value in (event.involved_track_ids or [])]
                result.append(
                    InvestigationEvidenceItem(
                        id=item.id,
                        source_id=source.id,
                        event_id=event.id,
                        event_title=event.title,
                        timestamp_seconds=item.timestamp_seconds,
                        frame_number=item.frame_number,
                        evidence_type=item.evidence_type,
                        image_url=f"{settings.api_v1_prefix}/evidence/{item.id}/image",
                        explanation=item.description,
                        confidence=event.confidence,
                        track_ids=linked_tracks,
                        track_labels=[
                            _track_label(source_track_classes.get(track_id), track_id)
                            for track_id in linked_tracks
                        ],
                    )
                )
        else:
            query = db.query(LiveEvent).filter(
                LiveEvent.session_id == source.live_session_id,
                LiveEvent.user_id == current_user.id,
                LiveEvent.snapshot_path.isnot(None),
            )
            if event_link_id:
                event_link = db.query(InvestigationEvent).filter(InvestigationEvent.id == event_link_id).first()
                query = query.filter(LiveEvent.id == event_link.live_event_id)
            elif event_id:
                query = query.filter(LiveEvent.id == event_id)
            for event in query.order_by(LiveEvent.timestamp_seconds.asc()).limit(2000):
                track_ids = [int(value) for value in (event.involved_track_ids or [])]
                result.append(
                    InvestigationEvidenceItem(
                        id=event.id,
                        source_id=source.id,
                        event_id=event.id,
                        event_title=event.title,
                        timestamp_seconds=event.timestamp_seconds,
                        frame_number=event.frame_index,
                        evidence_type="annotated_tracking",
                        image_url=(
                            f"{settings.api_v1_prefix}/live/{event.session_id}/events/{event.id}/snapshot"
                        ),
                        annotated_image_url=(
                            f"{settings.api_v1_prefix}/live/{event.session_id}/events/{event.id}/snapshot"
                        ),
                        explanation=event.description,
                        confidence=event.confidence,
                        track_ids=track_ids,
                        track_labels=[
                            _track_label(track_classes[source.id].get(track_id), track_id)
                            for track_id in track_ids
                        ],
                    )
                )
    return result


@router.post(
    "/{investigation_id}/notes",
    response_model=InvestigationNoteInfo,
    status_code=status.HTTP_201_CREATED,
)
def add_investigation_note(
    investigation_id: str,
    payload: InvestigationNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationNoteInfo:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    source_id = payload.source_id
    event_link_id = payload.investigation_event_id
    if source_id:
        _owned_source(investigation, source_id, db)
    if event_link_id:
        event_link = (
            db.query(InvestigationEvent)
            .filter(
                InvestigationEvent.id == event_link_id,
                InvestigationEvent.investigation_id == investigation.id,
            )
            .first()
        )
        if event_link is None:
            raise HTTPException(status_code=404, detail="Investigation event link not found.")
        if source_id and event_link.source_id != source_id:
            raise HTTPException(status_code=400, detail="Note source must match the linked event source.")
        source_id = event_link.source_id
    note = InvestigationNote(
        investigation_id=investigation.id,
        source_id=source_id,
        investigation_event_id=event_link_id,
        timestamp_seconds=payload.timestamp_seconds,
        content=payload.content.strip(),
        author_user_id=current_user.id,
    )
    if not note.content:
        raise HTTPException(status_code=422, detail="Note content cannot be blank.")
    db.add(note)
    _save(db)
    db.refresh(note)
    return _note_info(note)


@router.patch(
    "/{investigation_id}/notes/{note_id}",
    response_model=InvestigationNoteInfo,
)
def update_investigation_note(
    investigation_id: str,
    note_id: str,
    payload: InvestigationNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestigationNoteInfo:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    note = (
        db.query(InvestigationNote)
        .filter(
            InvestigationNote.id == note_id,
            InvestigationNote.investigation_id == investigation.id,
            InvestigationNote.author_user_id == current_user.id,
        )
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Investigation note not found.")
    changes = payload.model_dump(exclude_unset=True)
    next_source_id = changes.get("source_id", note.source_id)
    next_event_link_id = changes.get("investigation_event_id", note.investigation_event_id)
    if next_source_id:
        _owned_source(investigation, next_source_id, db)
    if next_event_link_id:
        event_link = (
            db.query(InvestigationEvent)
            .filter(
                InvestigationEvent.id == next_event_link_id,
                InvestigationEvent.investigation_id == investigation.id,
            )
            .first()
        )
        if event_link is None:
            raise HTTPException(status_code=404, detail="Investigation event link not found.")
        if next_source_id and event_link.source_id != next_source_id:
            raise HTTPException(status_code=400, detail="Note source must match the linked event source.")
        next_source_id = event_link.source_id
    note.source_id = next_source_id
    note.investigation_event_id = next_event_link_id
    if "timestamp_seconds" in changes:
        note.timestamp_seconds = payload.timestamp_seconds
    note.content = payload.content.strip()
    if not note.content:
        raise HTTPException(status_code=422, detail="Note content cannot be blank.")
    _save(db)
    db.refresh(note)
    return _note_info(note)


@router.delete(
    "/{investigation_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_investigation_note(
    investigation_id: str,
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    investigation = _owned_investigation(investigation_id, current_user.id, db)
    note = (
        db.query(InvestigationNote)
        .filter(
            InvestigationNote.id == note_id,
            InvestigationNote.investigation_id == investigation.id,
            InvestigationNote.author_user_id == current_user.id,
        )
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Investigation note not found.")
    db.delete(note)
    _save(db)
