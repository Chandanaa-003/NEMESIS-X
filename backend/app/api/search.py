import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, and_, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.behavior import BehaviorSnapshot
from app.models.detection import Detection
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.user import User
from app.models.video import Video
from app.schemas.analysis import BoundingBoxInfo
from app.schemas.search import (
    IntelligenceSearchResponse,
    IntelligenceSearchResult,
    SearchDetectionInfo,
    SearchEvidenceReference,
    SearchSourceType,
    TrackSearchResponse,
    TrackSearchResult,
)
from app.services.intelligence_search import (
    ParsedSearchQuery,
    class_matches,
    format_track_code,
    parse_search_query,
)

router = APIRouter(prefix="/search", tags=["Intelligent Search"])
SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4,}\.jpg$")
MAX_SEARCH_CANDIDATES = 2000
MAX_FRAME_RESULTS = 200
SEARCH_HELP = (
    "Search supports source-local track codes (T007, P007, O007), object classes, "
    "event terms such as approach, pickup, unattended, zone entry/exit, anomaly, "
    "and source-relative timestamps such as 00:01:00 to 00:02:00."
)


def _event_track_ids(event: Event | LiveEvent) -> list[int]:
    ids: list[int] = []
    for raw_id in event.involved_track_ids or []:
        try:
            track_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if track_id not in ids:
            ids.append(track_id)
    payload = event.explanation_payload if isinstance(event.explanation_payload, dict) else {}
    for key in ("person_track_id", "object_track_id"):
        raw_id = payload.get(key)
        if raw_id is None:
            continue
        try:
            track_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if track_id not in ids:
            ids.append(track_id)
    return ids


def _event_track_predicate(model: type[Event] | type[LiveEvent], track_id: int):
    values = func.json_each(model.involved_track_ids).table_valued("value").alias("track_values")
    return exists(
        select(1)
        .select_from(values)
        .where(cast(values.c.value, Integer) == track_id)
    )


def _track_label(class_name: str | None, track_id: int) -> str:
    code = format_track_code(track_id)
    if not class_name:
        return f"Track {code}"
    if class_name.lower() == "person":
        return f"Person {code}"
    return f"Object ({class_name}) {code}"


def _payload_track_id(event: Event | LiveEvent, key: str) -> int | None:
    payload = event.explanation_payload if isinstance(event.explanation_payload, dict) else {}
    raw_id = payload.get(key)
    if raw_id is None:
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _class_filter_matches(class_name: str, criteria: ParsedSearchQuery, explicit_class: str | None) -> bool:
    terms = list(criteria.class_terms)
    if explicit_class:
        normalized = " ".join(explicit_class.lower().split())
        if normalized not in terms:
            terms.append(normalized)
    if criteria.track_role == "person" and class_name.lower() != "person":
        return False
    if criteria.track_role == "object" and class_name.lower() == "person":
        return False
    return not terms or any(class_matches(class_name, term) for term in terms)


def _event_text(event: Event | LiveEvent) -> str:
    return " ".join(
        [
            event.event_type,
            event.category,
            event.title,
            event.description,
            json.dumps(event.explanation_payload or {}, ensure_ascii=True),
        ]
    ).lower()


def _matches_event_terms(text: str, terms: tuple[str, ...]) -> bool:
    normalized_text = text.replace("_", " ")
    for term in terms:
        normalized_term = term.replace("_", " ")
        alternatives = [normalized_term]
        if normalized_term in {"unusual", "anomaly", "anomalous", "anomalies"}:
            alternatives.extend(("sudden", "rapid", "direction change", "anomaly"))
        elif normalized_term in {"pickup", "pick up"}:
            alternatives.extend(("pickup", "pick up"))
        elif normalized_term in {"left behind"}:
            alternatives.extend(("unattended", "moved away", "stationary"))
        if any(candidate in normalized_text for candidate in alternatives):
            return True
    return not terms


def _matches_event_intent(
    event: Event | LiveEvent,
    track_classes: dict[int, str],
    criteria: ParsedSearchQuery,
    *,
    explicit_category: str | None,
    explicit_event_type: str | None,
    explicit_class: str | None,
    track_id: int | None,
) -> bool:
    if explicit_category and event.category.lower() != explicit_category.lower():
        return False
    if explicit_event_type and explicit_event_type.lower() not in event.event_type.lower():
        return False

    text = _event_text(event)
    if criteria.text_terms and not all(term in text for term in criteria.text_terms):
        return False
    if not _matches_event_terms(text, criteria.event_terms):
        return False
    if criteria.event_categories and event.category not in criteria.event_categories:
        if not any(term.replace("_", " ") in text for term in criteria.event_terms):
            return False

    track_ids = _event_track_ids(event)
    if track_id is not None and track_id not in track_ids:
        return False
    if criteria.track_role == "person":
        payload_id = _payload_track_id(event, "person_track_id")
        role_matches = payload_id is not None and payload_id in track_ids
        role_matches = role_matches or any(
            track_classes.get(candidate_id, "").lower() == "person"
            for candidate_id in track_ids
        )
        if not role_matches:
            return False
    elif criteria.track_role == "object":
        payload_id = _payload_track_id(event, "object_track_id")
        role_matches = payload_id is not None and payload_id in track_ids
        role_matches = role_matches or any(
            class_name and class_name.lower() != "person"
            for class_name in (track_classes.get(candidate_id) for candidate_id in track_ids)
        )
        if not role_matches:
            return False

    class_terms = list(criteria.class_terms)
    if explicit_class:
        normalized = " ".join(explicit_class.lower().split())
        if normalized not in class_terms:
            class_terms.append(normalized)
    for term in class_terms:
        if not any(
            class_name is not None and class_matches(class_name, term)
            for class_name in (track_classes.get(candidate_id) for candidate_id in track_ids)
        ):
            return False
    return True


def _load_frame_metadata(analysis_id: str, cache: dict[str, dict[int, dict]]) -> dict[int, dict]:
    if analysis_id in cache:
        return cache[analysis_id]
    metadata_path = get_settings().resolved_processed_dir / analysis_id / "metadata.json"
    if not metadata_path.is_file():
        cache[analysis_id] = {}
        return cache[analysis_id]
    try:
        raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Failed to read stored frame metadata.") from exc

    original = raw_metadata.get("original_dimensions") or {}
    original_width = int(original.get("width") or 0)
    original_height = int(original.get("height") or 0)
    max_width = int(raw_metadata.get("max_width_applied") or original_width)
    frame_width = min(original_width, max_width) if original_width else 0
    frame_height = (
        max(1, round(original_height * frame_width / original_width))
        if frame_width and original_height
        else 0
    )
    index: dict[int, dict] = {}
    for item in raw_metadata.get("frames", []):
        filename = str(item.get("filename", ""))
        if not SAFE_FRAME_FILENAME_RE.fullmatch(filename):
            continue
        index[int(item["frame_index"])] = {
            "filename": filename,
            "timestamp_seconds": float(item["timestamp_seconds"]),
            "frame_width": frame_width or None,
            "frame_height": frame_height or None,
        }
    cache[analysis_id] = index
    return index


def _frame_evidence(
    analysis_id: str,
    frame_index: int,
    metadata_cache: dict[str, dict[int, dict]],
) -> SearchEvidenceReference | None:
    frame = _load_frame_metadata(analysis_id, metadata_cache).get(frame_index)
    if not frame:
        return None
    return SearchEvidenceReference(
        id=f"frame:{analysis_id}:{frame_index}",
        evidence_type="source_frame",
        timestamp_seconds=frame["timestamp_seconds"],
        image_url=f"/analysis/{analysis_id}/frames/{frame['filename']}",
    )


def _read_recorded_evidence(
    event_id: str,
    user_id: int,
    db: Session,
) -> list[SearchEvidenceReference]:
    rows = (
        db.query(Evidence)
        .filter(Evidence.event_id == event_id, Evidence.user_id == user_id)
        .order_by(Evidence.created_at.desc())
        .limit(10)
        .all()
    )
    priority = {"annotated_tracking": 0, "annotated_detection": 1, "original_frame": 2}
    rows.sort(key=lambda row: (priority.get(row.evidence_type, 3), row.frame_number))
    return [
        SearchEvidenceReference(
            id=row.id,
            evidence_type=row.evidence_type,
            timestamp_seconds=row.timestamp_seconds,
            image_url=f"/evidence/{row.id}/image",
        )
        for row in rows[:4]
    ]


def _detections_for_frame(
    analysis_id: str,
    frame_index: int,
    db: Session,
) -> list[SearchDetectionInfo]:
    rows = (
        db.query(Detection)
        .filter(Detection.analysis_id == analysis_id, Detection.frame_index == frame_index)
        .order_by(Detection.id.asc())
        .all()
    )
    return [
        SearchDetectionInfo(
            track_id=row.track_id,
            track_code=format_track_code(row.track_id) if row.track_id is not None else None,
            class_name=row.class_name,
            confidence=row.confidence,
            bbox=BoundingBoxInfo(
                x1=row.bbox_x1,
                y1=row.bbox_y1,
                x2=row.bbox_x2,
                y2=row.bbox_y2,
            ),
        )
        for row in rows
    ]


def _make_event_result(
    event: Event | LiveEvent,
    *,
    source_type: SearchSourceType,
    source_id: str,
    source_label: str,
    analysis_id: str | None,
    video_id: str | None,
    live_session_id: str | None,
    user_id: int,
    track_classes: dict[int, str],
    metadata_cache: dict[str, dict[int, dict]],
    db: Session,
) -> IntelligenceSearchResult:
    track_ids = _event_track_ids(event)
    labels = [_track_label(track_classes.get(track_id), track_id) for track_id in track_ids]
    evidence = (
        _read_recorded_evidence(event.id, user_id, db)
        if isinstance(event, Event)
        else []
    )
    frame_index = None
    if isinstance(event, Event):
        if event.evidence_frame_ids:
            frame_index = int(event.evidence_frame_ids[0])
        elif analysis_id:
            nearest_detection = (
                db.query(Detection)
                .filter(Detection.analysis_id == analysis_id)
                .order_by(func.abs(Detection.timestamp_seconds - event.start_timestamp))
                .first()
            )
            frame_index = nearest_detection.frame_index if nearest_detection else None
        if frame_index is not None:
            frame_ref = _frame_evidence(analysis_id or "", frame_index, metadata_cache)
            if frame_ref and all(item.id != frame_ref.id for item in evidence):
                evidence.append(frame_ref)

    if isinstance(event, LiveEvent) and event.snapshot_path:
        evidence.append(
            SearchEvidenceReference(
                id=f"live-snapshot:{event.id}",
                evidence_type="annotated_tracking",
                timestamp_seconds=event.timestamp_seconds,
                image_url=f"/live/{event.session_id}/events/{event.id}/snapshot",
            )
        )

    frame_meta = (
        _load_frame_metadata(analysis_id or "", metadata_cache).get(frame_index, {})
        if analysis_id and frame_index is not None
        else {}
    )
    detections = (
        _detections_for_frame(analysis_id, frame_index, db)
        if analysis_id and frame_index is not None
        else []
    )
    return IntelligenceSearchResult(
        id=f"event:{source_type}:{event.id}",
        result_type="event",
        source_type=source_type,
        source_id=source_id,
        source_label=source_label,
        analysis_id=analysis_id,
        video_id=video_id,
        live_session_id=live_session_id,
        event_id=event.id,
        event_type=event.event_type,
        event_category=event.category,
        title=event.title,
        explanation=event.description,
        timestamp_seconds=event.start_timestamp,
        end_timestamp_seconds=event.end_timestamp,
        overlay_timestamp_seconds=frame_meta.get("timestamp_seconds"),
        track_ids=track_ids,
        track_labels=labels,
        class_name=None,
        confidence=event.confidence,
        severity=event.severity,
        frame_width=frame_meta.get("frame_width"),
        frame_height=frame_meta.get("frame_height"),
        detections=detections,
        evidence=evidence[:5],
    )


def _matches_time_range(
    start: float,
    end: float,
    lower: float | None,
    upper: float | None,
) -> bool:
    return not (
        (lower is not None and end < lower)
        or (upper is not None and start > upper)
    )


def _build_search_results(
    *,
    q: str,
    source_type: Literal["all", "analysis", "live_session"],
    analysis_id: str | None,
    live_session_id: str | None,
    event_category: str | None,
    event_type: str | None,
    class_name: str | None,
    requested_track_id: int | None,
    start_seconds: float | None,
    end_seconds: float | None,
    user_id: int,
    db: Session,
    include_events: bool = True,
    include_detections: bool = True,
    include_tracks: bool = True,
) -> tuple[ParsedSearchQuery, list[IntelligenceSearchResult], bool]:
    criteria = parse_search_query(q)
    track_id = requested_track_id if requested_track_id is not None else criteria.track_id
    lower = start_seconds if start_seconds is not None else criteria.start_seconds
    upper = end_seconds if end_seconds is not None else criteria.end_seconds
    if lower is not None and upper is not None and lower > upper:
        raise HTTPException(status_code=400, detail="start_seconds must not exceed end_seconds.")

    direct_supported = bool(
        analysis_id
        or live_session_id
        or event_category
        or event_type
        or class_name
        or requested_track_id is not None
        or start_seconds is not None
        or end_seconds is not None
    )
    if not criteria.supported and not direct_supported:
        return criteria, [], False

    candidates: list[IntelligenceSearchResult] = []
    truncated = False
    metadata_cache: dict[str, dict[int, dict]] = {}
    class_maps: dict[tuple[str, str], dict[int, str]] = {}

    analysis_candidates = (
        db.query(Analysis, Video)
        .join(Video, Video.id == Analysis.video_id)
        .filter(Analysis.user_id == user_id, Analysis.status == "completed")
        .all()
    )
    if analysis_id:
        analysis_candidates = [
            item for item in analysis_candidates if item[0].id == analysis_id
        ]
    if live_session_id or source_type == "live_session":
        analysis_candidates = []
    analysis_context = {
        row.id: (row, video)
        for row, video in analysis_candidates
    }

    live_candidates = (
        db.query(LiveSession)
        .filter(LiveSession.user_id == user_id)
        .all()
    )
    if live_session_id:
        live_candidates = [item for item in live_candidates if item.id == live_session_id]
    if source_type == "analysis" or analysis_id:
        live_candidates = []
    live_context = {row.id: row for row in live_candidates}

    for analysis_key, (analysis, _) in analysis_context.items():
        rows = (
            db.query(Track.track_id, Track.class_name)
            .filter(Track.analysis_id == analysis_key)
            .all()
        )
        class_maps[("analysis", analysis_key)] = {
            int(track_id_value): str(track_class)
            for track_id_value, track_class in rows
        }
    if live_context:
        for snapshot in (
            db.query(BehaviorSnapshot)
            .filter(
                BehaviorSnapshot.user_id == user_id,
                BehaviorSnapshot.live_session_id.in_(list(live_context)),
            )
            .all()
        ):
            class_maps[("live_session", str(snapshot.live_session_id))] = {
                int(track["track_id"]): str(track.get("class_name", "object"))
                for track in (snapshot.track_history or [])
                if track.get("track_id") is not None
            }

    event_class_terms = list(criteria.class_terms)
    if class_name and class_name.lower() not in event_class_terms:
        event_class_terms.append(class_name.lower())
    query_event_predicate = bool(
        include_events
        and (
            track_id is not None
            or event_category
            or event_type
            or criteria.event_categories
            or criteria.event_terms
            or criteria.text_terms
            or event_class_terms
            or lower is not None
            or upper is not None
        )
    )
    if query_event_predicate and analysis_context:
        event_query = (
            db.query(Event, Analysis, Video)
            .join(Analysis, Analysis.id == Event.analysis_id)
            .join(Video, Video.id == Analysis.video_id)
            .filter(Analysis.user_id == user_id, Analysis.status == "completed")
        )
        if analysis_id:
            event_query = event_query.filter(Event.analysis_id == analysis_id)
        if event_type:
            event_query = event_query.filter(Event.event_type.ilike(f"%{event_type.strip()}%"))
        if event_category:
            event_query = event_query.filter(Event.category == event_category)
        if track_id is not None:
            event_query = event_query.filter(_event_track_predicate(Event, track_id))
        if lower is not None:
            event_query = event_query.filter(Event.end_timestamp >= lower)
        if upper is not None:
            event_query = event_query.filter(Event.start_timestamp <= upper)
        event_rows = (
            event_query.order_by(Event.start_timestamp.asc(), Event.id.asc())
            .limit(MAX_SEARCH_CANDIDATES + 1)
            .all()
        )
        truncated = truncated or len(event_rows) > MAX_SEARCH_CANDIDATES
        for event, analysis, video in event_rows[:MAX_SEARCH_CANDIDATES]:
            tracks_for_event = class_maps.get(("analysis", analysis.id), {})
            if not _matches_event_intent(
                event,
                tracks_for_event,
                criteria,
                explicit_category=event_category,
                explicit_event_type=event_type,
                explicit_class=class_name,
                track_id=track_id,
            ):
                continue
            if not _matches_time_range(
                event.start_timestamp,
                event.end_timestamp,
                lower,
                upper,
            ):
                continue
            candidates.append(
                _make_event_result(
                    event,
                    source_type="analysis",
                    source_id=analysis.id,
                    source_label=video.original_filename,
                    analysis_id=analysis.id,
                    video_id=analysis.video_id,
                    live_session_id=None,
                    user_id=user_id,
                    track_classes=tracks_for_event,
                    metadata_cache=metadata_cache,
                    db=db,
                )
            )

    if query_event_predicate and live_context:
        live_event_query = (
            db.query(LiveEvent, LiveSession)
            .join(LiveSession, LiveSession.id == LiveEvent.session_id)
            .filter(
                LiveEvent.user_id == user_id,
                LiveSession.user_id == user_id,
            )
        )
        if live_session_id:
            live_event_query = live_event_query.filter(LiveEvent.session_id == live_session_id)
        if event_type:
            live_event_query = live_event_query.filter(
                LiveEvent.event_type.ilike(f"%{event_type.strip()}%")
            )
        if event_category:
            live_event_query = live_event_query.filter(LiveEvent.category == event_category)
        if track_id is not None:
            live_event_query = live_event_query.filter(_event_track_predicate(LiveEvent, track_id))
        if lower is not None:
            live_event_query = live_event_query.filter(LiveEvent.end_timestamp >= lower)
        if upper is not None:
            live_event_query = live_event_query.filter(LiveEvent.start_timestamp <= upper)
        live_event_rows = (
            live_event_query.order_by(LiveEvent.start_timestamp.asc(), LiveEvent.id.asc())
            .limit(MAX_SEARCH_CANDIDATES + 1)
            .all()
        )
        truncated = truncated or len(live_event_rows) > MAX_SEARCH_CANDIDATES
        for event, session in live_event_rows[:MAX_SEARCH_CANDIDATES]:
            tracks_for_event = class_maps.get(("live_session", session.id), {})
            if not _matches_event_intent(
                event,
                tracks_for_event,
                criteria,
                explicit_category=event_category,
                explicit_event_type=event_type,
                explicit_class=class_name,
                track_id=track_id,
            ):
                continue
            if not _matches_time_range(
                event.start_timestamp,
                event.end_timestamp,
                lower,
                upper,
            ):
                continue
            candidates.append(
                _make_event_result(
                    event,
                    source_type="live_session",
                    source_id=session.id,
                    source_label=f"Live session {session.id[:8]}",
                    analysis_id=None,
                    video_id=None,
                    live_session_id=session.id,
                    user_id=user_id,
                    track_classes=tracks_for_event,
                    metadata_cache=metadata_cache,
                    db=db,
                )
            )

    class_terms = list(criteria.class_terms)
    if class_name and class_name.lower() not in class_terms:
        class_terms.append(class_name.lower())
    should_search_detections = bool(
        include_detections
        and analysis_context
        and (track_id is not None or class_terms or lower is not None or upper is not None)
    )
    if should_search_detections:
        detection_query = (
            db.query(Detection, Analysis, Video)
            .join(Analysis, Analysis.id == Detection.analysis_id)
            .join(Video, Video.id == Analysis.video_id)
            .filter(Analysis.user_id == user_id, Analysis.status == "completed")
        )
        if analysis_id:
            detection_query = detection_query.filter(Detection.analysis_id == analysis_id)
        if track_id is not None:
            detection_query = detection_query.filter(Detection.track_id == track_id)
        if lower is not None:
            detection_query = detection_query.filter(Detection.timestamp_seconds >= lower)
        if upper is not None:
            detection_query = detection_query.filter(Detection.timestamp_seconds <= upper)
        detection_rows = (
            detection_query.order_by(Detection.timestamp_seconds.asc(), Detection.id.asc())
            .limit(MAX_SEARCH_CANDIDATES + 1)
            .all()
        )
        truncated = truncated or len(detection_rows) > MAX_SEARCH_CANDIDATES
        matching_detections = [
            row for row in detection_rows[:MAX_SEARCH_CANDIDATES]
            if _class_filter_matches(row[0].class_name, criteria, class_name)
        ]
        matching_detections = matching_detections[:MAX_FRAME_RESULTS]
        frame_groups: dict[tuple[str, int], list] = {}
        for detection, analysis, video in matching_detections:
            key = (analysis.id, detection.frame_index)
            frame_groups.setdefault(key, []).append((detection, analysis, video))

        if frame_groups:
            frame_filter = or_(
                *(
                    and_(
                        Detection.analysis_id == analysis_key,
                        Detection.frame_index == frame_index,
                    )
                    for analysis_key, frame_index in frame_groups
                )
            )
            full_frame_rows = db.query(Detection).filter(frame_filter).order_by(Detection.id.asc()).all()
            full_frame_detections: dict[tuple[str, int], list[SearchDetectionInfo]] = {}
            for row in full_frame_rows:
                key = (row.analysis_id, row.frame_index)
                full_frame_detections.setdefault(key, []).append(
                    SearchDetectionInfo(
                        track_id=row.track_id,
                        track_code=format_track_code(row.track_id) if row.track_id is not None else None,
                        class_name=row.class_name,
                        confidence=row.confidence,
                        bbox=BoundingBoxInfo(
                            x1=row.bbox_x1,
                            y1=row.bbox_y1,
                            x2=row.bbox_x2,
                            y2=row.bbox_y2,
                        ),
                    )
                )

            for key, matching_rows in frame_groups.items():
                detection, analysis, video = matching_rows[0]
                frame_meta = _load_frame_metadata(analysis.id, metadata_cache).get(
                    detection.frame_index,
                    {},
                )
                all_detections = full_frame_detections.get(key, [])
                track_ids = list(
                    dict.fromkeys(
                        item.track_id for item in all_detections if item.track_id is not None
                    )
                )
                track_labels = [
                    _track_label(item.class_name, item.track_id)
                    for item in all_detections
                    if item.track_id is not None
                ]
                evidence = _frame_evidence(analysis.id, detection.frame_index, metadata_cache)
                candidates.append(
                    IntelligenceSearchResult(
                        id=f"detection:{analysis.id}:{detection.frame_index}",
                        result_type="detection",
                        source_type="analysis",
                        source_id=analysis.id,
                        source_label=video.original_filename,
                        analysis_id=analysis.id,
                        video_id=analysis.video_id,
                        event_type="detection_observation",
                        event_category="detection",
                        title=f"{detection.class_name.title()} detected",
                        explanation=(
                            f"Stored detection at frame {detection.frame_index}; "
                            "labels use the saved YOLO and ByteTrack result."
                        ),
                        timestamp_seconds=detection.timestamp_seconds,
                        overlay_timestamp_seconds=frame_meta.get("timestamp_seconds"),
                        track_ids=track_ids,
                        track_labels=list(dict.fromkeys(track_labels)),
                        class_name=detection.class_name,
                        confidence=detection.confidence,
                        frame_width=frame_meta.get("frame_width"),
                        frame_height=frame_meta.get("frame_height"),
                        detections=all_detections,
                        evidence=[evidence] if evidence else [],
                    )
                )

    search_for_tracks = bool(
        include_tracks
        and (
            track_id is not None
            or class_terms
            or criteria.evidence_requested
            or re.search(r"\btracks?\b", q, re.IGNORECASE)
        )
    )
    if search_for_tracks and analysis_context:
        track_query = (
            db.query(Track, Analysis, Video)
            .join(Analysis, Analysis.id == Track.analysis_id)
            .join(Video, Video.id == Analysis.video_id)
            .filter(Analysis.user_id == user_id, Analysis.status == "completed")
        )
        if analysis_id:
            track_query = track_query.filter(Track.analysis_id == analysis_id)
        if track_id is not None:
            track_query = track_query.filter(Track.track_id == track_id)
        if lower is not None:
            track_query = track_query.filter(Track.last_seen_timestamp >= lower)
        if upper is not None:
            track_query = track_query.filter(Track.first_seen_timestamp <= upper)
        track_rows = (
            track_query.order_by(Track.first_seen_timestamp.asc(), Track.id.asc())
            .limit(MAX_SEARCH_CANDIDATES + 1)
            .all()
        )
        truncated = truncated or len(track_rows) > MAX_SEARCH_CANDIDATES
        for track, analysis, video in track_rows[:MAX_SEARCH_CANDIDATES]:
            if not _class_filter_matches(track.class_name, criteria, class_name):
                continue
            frame_index = track.first_seen_frame
            evidence = _frame_evidence(analysis.id, frame_index, metadata_cache)
            candidates.append(
                IntelligenceSearchResult(
                    id=f"track:analysis:{analysis.id}:{track.track_id}",
                    result_type="track",
                    source_type="analysis",
                    source_id=analysis.id,
                    source_label=video.original_filename,
                    analysis_id=analysis.id,
                    video_id=analysis.video_id,
                    event_type="track_observation",
                    event_category="tracking",
                    title=_track_label(track.class_name, track.track_id),
                    explanation=(
                        f"Stored ByteTrack record observed from {track.first_seen_timestamp:.2f}s "
                        f"to {track.last_seen_timestamp:.2f}s."
                    ),
                    timestamp_seconds=track.first_seen_timestamp,
                    end_timestamp_seconds=track.last_seen_timestamp,
                    track_ids=[track.track_id],
                    track_labels=[_track_label(track.class_name, track.track_id)],
                    class_name=track.class_name,
                    detection_count=track.frame_count,
                    confidence=track.avg_confidence,
                    evidence=[evidence] if evidence else [],
                )
            )

    if search_for_tracks and live_context:
        live_track_rows = (
            db.query(BehaviorSnapshot)
            .filter(
                BehaviorSnapshot.user_id == user_id,
                BehaviorSnapshot.live_session_id.in_(list(live_context)),
            )
            .all()
        )
        for snapshot in live_track_rows:
            session = live_context.get(str(snapshot.live_session_id))
            if session is None:
                continue
            for track in snapshot.track_history or []:
                if track.get("track_id") is None:
                    continue
                current_track_id = int(track["track_id"])
                current_class = str(track.get("class_name", "object"))
                first_seen = float(track.get("first_seen_timestamp", 0.0))
                last_seen = float(track.get("last_seen_timestamp", first_seen))
                if track_id is not None and current_track_id != track_id:
                    continue
                if not _class_filter_matches(current_class, criteria, class_name):
                    continue
                if not _matches_time_range(first_seen, last_seen, lower, upper):
                    continue
                candidate_events = (
                    db.query(LiveEvent)
                    .filter(
                        LiveEvent.session_id == session.id,
                        LiveEvent.user_id == user_id,
                        _event_track_predicate(LiveEvent, current_track_id),
                    )
                    .order_by(LiveEvent.timestamp_seconds.asc())
                    .limit(1)
                    .all()
                )
                evidence = []
                if candidate_events and candidate_events[0].snapshot_path:
                    event = candidate_events[0]
                    evidence.append(
                        SearchEvidenceReference(
                            id=f"live-snapshot:{event.id}",
                            evidence_type="annotated_tracking",
                            timestamp_seconds=event.timestamp_seconds,
                            image_url=f"/live/{session.id}/events/{event.id}/snapshot",
                        )
                    )
                candidates.append(
                    IntelligenceSearchResult(
                        id=f"track:live_session:{session.id}:{current_track_id}",
                        result_type="track",
                        source_type="live_session",
                        source_id=session.id,
                        source_label=f"Live session {session.id[:8]}",
                        live_session_id=session.id,
                        event_type="track_observation",
                        event_category="tracking",
                        title=_track_label(current_class, current_track_id),
                        explanation=(
                            "Recent stored live track samples are available; continuous live "
                            "video was not archived."
                        ),
                        timestamp_seconds=first_seen,
                        end_timestamp_seconds=last_seen,
                        track_ids=[current_track_id],
                        track_labels=[_track_label(current_class, current_track_id)],
                        class_name=current_class,
                        detection_count=int(track.get("frame_count", len(track.get("timeline_points", [])))),
                        confidence=float(track.get("avg_confidence", 0.0)),
                        evidence=evidence,
                    )
                )

    candidates.sort(
        key=lambda item: (
            item.timestamp_seconds,
            item.source_type,
            item.source_id,
            item.id,
        )
    )
    deduped: dict[str, IntelligenceSearchResult] = {}
    for item in candidates:
        deduped.setdefault(item.id, item)
    return criteria, list(deduped.values()), truncated


@router.get("/intelligence", response_model=IntelligenceSearchResponse)
def search_video_intelligence(
    q: str = Query(default="", max_length=500),
    source_type: Literal["all", "analysis", "live_session"] = "all",
    analysis_id: str | None = None,
    live_session_id: str | None = None,
    event_category: str | None = Query(default=None, max_length=64),
    event_type: str | None = Query(default=None, max_length=64),
    class_name: str | None = Query(default=None, max_length=64),
    track_id: int | None = Query(default=None, ge=0),
    start_seconds: float | None = Query(default=None, ge=0),
    end_seconds: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntelligenceSearchResponse:
    """Search owned stored events, detections, tracks, and linked evidence."""
    if analysis_id and live_session_id:
        raise HTTPException(status_code=400, detail="Choose either analysis_id or live_session_id.")
    if (source_type == "analysis" and live_session_id) or (
        source_type == "live_session" and analysis_id
    ):
        raise HTTPException(status_code=400, detail="The selected source type does not match the source ID.")
    criteria, results, truncated = _build_search_results(
        q=q,
        source_type=source_type,
        analysis_id=analysis_id,
        live_session_id=live_session_id,
        event_category=event_category,
        event_type=event_type,
        class_name=class_name,
        requested_track_id=track_id,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        user_id=current_user.id,
        db=db,
    )
    if not criteria.supported and not any(
        (analysis_id, live_session_id, event_category, event_type, class_name, track_id is not None,
         start_seconds is not None, end_seconds is not None)
    ):
        return IntelligenceSearchResponse(
            query=q,
            supported_query=False,
            message=f"I couldn't identify a supported filter. {SEARCH_HELP}",
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
            results=[],
        )
    total = len(results)
    page = results[offset : offset + limit]
    has_more = offset + len(page) < total or truncated
    message = (
        "Search results are limited to the first 2,000 stored candidates; add a source, class, "
        "track, event, or timestamp filter."
        if truncated
        else (f"{total} stored result(s) matched." if total else "No stored records matched this search.")
    )
    return IntelligenceSearchResponse(
        query=q,
        supported_query=True,
        message=message,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        truncated=truncated,
        results=page,
    )


@router.get("/tracks", response_model=TrackSearchResponse)
def search_owned_tracks(
    q: str = Query(default="", max_length=200),
    source_type: Literal["all", "analysis", "live_session"] = "all",
    analysis_id: str | None = None,
    live_session_id: str | None = None,
    class_name: str | None = Query(default=None, max_length=64),
    track_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrackSearchResponse:
    """Search source-scoped recorded and recently stored live tracks for the owner."""
    if analysis_id and live_session_id:
        raise HTTPException(status_code=400, detail="Choose either analysis_id or live_session_id.")
    if (source_type == "analysis" and live_session_id) or (
        source_type == "live_session" and analysis_id
    ):
        raise HTTPException(status_code=400, detail="The selected source type does not match the source ID.")
    criteria, results, truncated = _build_search_results(
        q=q,
        source_type=source_type,
        analysis_id=analysis_id,
        live_session_id=live_session_id,
        event_category=None,
        event_type=None,
        class_name=class_name,
        requested_track_id=track_id,
        start_seconds=None,
        end_seconds=None,
        user_id=current_user.id,
        db=db,
        include_events=False,
        include_detections=False,
        include_tracks=True,
    )
    track_results = [
        TrackSearchResult(
            source_type=item.source_type,
            source_id=item.source_id,
            source_label=item.source_label,
            analysis_id=item.analysis_id,
            video_id=item.video_id,
            live_session_id=item.live_session_id,
            track_id=item.track_ids[0],
            track_code=format_track_code(item.track_ids[0]),
            track_label=item.title,
            class_name=item.class_name or "object",
            first_seen_timestamp=item.timestamp_seconds,
            last_seen_timestamp=item.end_timestamp_seconds or item.timestamp_seconds,
            detection_count=item.detection_count or 0,
            evidence=item.evidence,
        )
        for item in results
        if item.result_type == "track" and item.track_ids
    ]
    return TrackSearchResponse(
        query=q,
        total=len(track_results),
        truncated=truncated,
        results=track_results[:limit],
    )
