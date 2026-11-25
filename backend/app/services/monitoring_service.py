from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.analysis import Analysis
from app.models.detection import Detection
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.video import Video
from app.schemas.monitoring import (
    IntelligenceAnalyticsResponse,
    MonitoringHistoryItem,
    MonitoringHistoryResponse,
    ObjectClassCount,
    SessionEventDetail,
    SessionEvidenceDetail,
    TimelineTrendPoint,
    UnifiedSessionDetailResponse,
)


def _compute_analysis_duration(analysis: Analysis, video: Video | None) -> float:
    if analysis.started_at and analysis.completed_at:
        return max(0.0, (analysis.completed_at - analysis.started_at).total_seconds())
    if video and video.duration_seconds:
        return float(video.duration_seconds)
    return 0.0


def _compute_live_duration(session: LiveSession) -> float:
    end = session.stopped_at or session.last_frame_at
    if end and session.started_at:
        return max(0.0, (end - session.started_at).total_seconds())
    if session.started_at and session.status == "active":
        return max(0.0, (datetime.now(timezone.utc) - session.started_at).total_seconds())
    return 0.0


def get_monitoring_history(
    *,
    user_id: int,
    session_type: str | None = "all",
    status_filter: str | None = None,
    priority_filter: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 10,
    db: Session,
) -> MonitoringHistoryResponse:
    """Fetch, filter, and paginate combined recorded video analyses and live webcam monitoring sessions."""
    items: list[MonitoringHistoryItem] = []
    normalized_search = search.strip().lower() if search else None
    normalized_type = (session_type or "all").lower().strip()
    normalized_priority = priority_filter.lower().strip() if priority_filter else None
    normalized_status = status_filter.lower().strip() if status_filter else None

    # 1. Fetch Recorded Analyses if requested
    if normalized_type in ("all", "recorded"):
        analysis_query = (
            db.query(Analysis, Video)
            .join(Video, Analysis.video_id == Video.id)
            .filter(Analysis.user_id == user_id)
        )

        if normalized_status:
            analysis_query = analysis_query.filter(Analysis.status == normalized_status)

        if date_from:
            analysis_query = analysis_query.filter(Analysis.created_at >= date_from)
        if date_to:
            analysis_query = analysis_query.filter(Analysis.created_at <= date_to)

        analyses_rows = analysis_query.all()
        analysis_ids = [a.id for a, _ in analyses_rows]

        # Batch counts for analyses
        event_counts: dict[str, int] = {}
        high_event_counts: dict[str, int] = {}
        track_counts: dict[str, int] = {}
        det_counts: dict[str, int] = {}

        if analysis_ids:
            for aid, c in (
                db.query(Event.analysis_id, func.count(Event.id))
                .filter(Event.analysis_id.in_(analysis_ids))
                .group_by(Event.analysis_id)
                .all()
            ):
                event_counts[aid] = int(c)

            for aid, c in (
                db.query(Event.analysis_id, func.count(Event.id))
                .filter(Event.analysis_id.in_(analysis_ids), Event.severity == "high")
                .group_by(Event.analysis_id)
                .all()
            ):
                high_event_counts[aid] = int(c)

            for aid, c in (
                db.query(Track.analysis_id, func.count(Track.id))
                .filter(Track.analysis_id.in_(analysis_ids))
                .group_by(Track.analysis_id)
                .all()
            ):
                track_counts[aid] = int(c)

            for aid, c in (
                db.query(Detection.analysis_id, func.count(Detection.id))
                .filter(Detection.analysis_id.in_(analysis_ids))
                .group_by(Detection.analysis_id)
                .all()
            ):
                det_counts[aid] = int(c)

        for analysis, video in analyses_rows:
            name = video.original_filename if video else f"Analysis {analysis.id[:8]}"
            if normalized_search:
                if (
                    normalized_search not in name.lower()
                    and normalized_search not in analysis.id.lower()
                ):
                    continue

            total_events = event_counts.get(analysis.id, 0)
            high_events = high_event_counts.get(analysis.id, 0)

            # Filter by priority if requested
            if normalized_priority:
                if normalized_priority == "high" and high_events == 0:
                    continue
                if normalized_priority in ("medium", "low") and total_events == 0:
                    continue

            dur = _compute_analysis_duration(analysis, video)
            start_t = analysis.started_at or analysis.created_at
            end_t = analysis.completed_at

            items.append(
                MonitoringHistoryItem(
                    session_id=analysis.id,
                    session_type="recorded",
                    name=name,
                    video_id=analysis.video_id,
                    start_time=start_t,
                    end_time=end_t,
                    duration_seconds=dur,
                    status=analysis.status,
                    total_detected_objects=det_counts.get(analysis.id, 0),
                    unique_tracked_objects=track_counts.get(analysis.id, 0),
                    events_discovered=total_events,
                    high_priority_events=high_events,
                    created_at=analysis.created_at,
                )
            )

    # 2. Fetch Live Monitoring Sessions if requested
    if normalized_type in ("all", "live"):
        live_query = db.query(LiveSession).filter(LiveSession.user_id == user_id)

        if normalized_status:
            live_query = live_query.filter(LiveSession.status == normalized_status)

        if date_from:
            live_query = live_query.filter(LiveSession.started_at >= date_from)
        if date_to:
            live_query = live_query.filter(LiveSession.started_at <= date_to)

        live_rows = live_query.all()
        live_ids = [s.id for s in live_rows]

        live_event_counts: dict[str, int] = {}
        live_high_counts: dict[str, int] = {}

        if live_ids:
            for sid, c in (
                db.query(LiveEvent.session_id, func.count(LiveEvent.id))
                .filter(LiveEvent.session_id.in_(live_ids))
                .group_by(LiveEvent.session_id)
                .all()
            ):
                live_event_counts[sid] = int(c)

            for sid, c in (
                db.query(LiveEvent.session_id, func.count(LiveEvent.id))
                .filter(LiveEvent.session_id.in_(live_ids), LiveEvent.severity == "high")
                .group_by(LiveEvent.session_id)
                .all()
            ):
                live_high_counts[sid] = int(c)

        for s in live_rows:
            name = f"Live Camera Monitoring ({s.id[:8]})"
            if normalized_search:
                if (
                    normalized_search not in name.lower()
                    and normalized_search not in s.id.lower()
                ):
                    continue

            total_events = live_event_counts.get(s.id, s.events_discovered_count)
            high_events = live_high_counts.get(s.id, 0)

            if normalized_priority:
                if normalized_priority == "high" and high_events == 0:
                    continue
                if normalized_priority in ("medium", "low") and total_events == 0:
                    continue

            dur = _compute_live_duration(s)
            start_t = s.started_at
            end_t = s.stopped_at or s.last_frame_at

            items.append(
                MonitoringHistoryItem(
                    session_id=s.id,
                    session_type="live",
                    name=name,
                    video_id=None,
                    start_time=start_t,
                    end_time=end_t,
                    duration_seconds=dur,
                    status=s.status,
                    total_detected_objects=s.total_detections,
                    unique_tracked_objects=s.unique_tracks_count,
                    events_discovered=total_events,
                    high_priority_events=high_events,
                    created_at=s.started_at,
                )
            )

    # Sort combined sessions descending by start time / created time
    items.sort(
        key=lambda x: x.start_time or x.created_at,
        reverse=True,
    )

    total = len(items)
    page_sz = max(1, min(page_size, 100))
    total_pages = max(1, (total + page_sz - 1) // page_sz)
    current_page = max(1, min(page, total_pages)) if total > 0 else 1

    start_idx = (current_page - 1) * page_sz
    end_idx = start_idx + page_sz
    paged_items = items[start_idx:end_idx]

    return MonitoringHistoryResponse(
        items=paged_items,
        total=total,
        page=current_page,
        page_size=page_sz,
        total_pages=total_pages,
    )


def get_intelligence_analytics(
    *,
    user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session,
) -> IntelligenceAnalyticsResponse:
    """Aggregate real database intelligence metrics for the authenticated user without demo statistics."""
    # 1. Analyses stats
    analysis_q = db.query(Analysis).filter(Analysis.user_id == user_id)
    if date_from:
        analysis_q = analysis_q.filter(Analysis.created_at >= date_from)
    if date_to:
        analysis_q = analysis_q.filter(Analysis.created_at <= date_to)
    analyses = analysis_q.all()
    analysis_ids = [a.id for a in analyses]

    # 2. Live sessions stats
    live_q = db.query(LiveSession).filter(LiveSession.user_id == user_id)
    if date_from:
        live_q = live_q.filter(LiveSession.started_at >= date_from)
    if date_to:
        live_q = live_q.filter(LiveSession.started_at <= date_to)
    live_sessions = live_q.all()
    live_ids = [s.id for s in live_sessions]

    # Durations & frames
    total_duration = 0.0
    for a in analyses:
        total_duration += _compute_analysis_duration(a, a.video)
    for s in live_sessions:
        total_duration += _compute_live_duration(s)

    total_sessions_count = len(analyses) + len(live_sessions)
    avg_duration = round(total_duration / total_sessions_count, 2) if total_sessions_count > 0 else 0.0
    completed_count = sum(1 for a in analyses if a.status == "completed")
    failed_count = sum(1 for a in analyses if a.status == "failed")

    total_frames = sum(a.processed_frames for a in analyses) + sum(s.frames_processed for s in live_sessions)

    # Detections
    rec_detections = 0
    if analysis_ids:
        rec_detections = db.query(func.count(Detection.id)).filter(Detection.analysis_id.in_(analysis_ids)).scalar() or 0
    live_detections = sum(s.total_detections for s in live_sessions)
    total_detections = rec_detections + live_detections

    # Tracks
    rec_tracks = 0
    if analysis_ids:
        rec_tracks = db.query(func.count(Track.id)).filter(Track.analysis_id.in_(analysis_ids)).scalar() or 0
    live_tracks = sum(s.unique_tracks_count for s in live_sessions)
    total_unique_tracks = rec_tracks + live_tracks

    # Events from analyses
    rec_events: list[Event] = []
    if analysis_ids:
        rec_events = db.query(Event).filter(Event.analysis_id.in_(analysis_ids)).all()

    # Events from live sessions
    live_events: list[LiveEvent] = []
    if live_ids:
        live_events = db.query(LiveEvent).filter(LiveEvent.session_id.in_(live_ids)).all()

    total_events_count = len(rec_events) + len(live_events)

    # Severity & category breakdown
    severity_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()

    for e in rec_events:
        sev = e.severity.lower() if e.severity else "low"
        severity_counter[sev] += 1
        cat = e.category if e.category else "other_activities"
        category_counter[cat] += 1

    for le in live_events:
        sev = le.severity.lower() if le.severity else "low"
        severity_counter[sev] += 1
        cat = le.category if le.category else "other_activities"
        category_counter[cat] += 1

    high_pri = severity_counter.get("high", 0)
    med_pri = severity_counter.get("medium", 0)
    low_pri = severity_counter.get("low", 0)

    # Top object classes from real Track records
    top_classes: list[ObjectClassCount] = []
    if analysis_ids:
        class_rows = (
            db.query(Track.class_name, func.count(Track.id))
            .filter(Track.analysis_id.in_(analysis_ids))
            .group_by(Track.class_name)
            .order_by(func.count(Track.id).desc())
            .limit(10)
            .all()
        )
        top_classes = [ObjectClassCount(class_name=str(name), count=int(cnt)) for name, cnt in class_rows]

    # If top_classes is empty, check Detection table
    if not top_classes and analysis_ids:
        class_rows = (
            db.query(Detection.class_name, func.count(Detection.id))
            .filter(Detection.analysis_id.in_(analysis_ids))
            .group_by(Detection.class_name)
            .order_by(func.count(Detection.id).desc())
            .limit(10)
            .all()
        )
        top_classes = [ObjectClassCount(class_name=str(name), count=int(cnt)) for name, cnt in class_rows]

    # Status breakdown
    status_counter: Counter[str] = Counter()
    for a in analyses:
        status_counter[a.status] += 1
    for s in live_sessions:
        status_counter[s.status] += 1

    # Timeline trends (group by day YYYY-MM-DD)
    day_sessions: defaultdict[str, int] = defaultdict(int)
    day_events: defaultdict[str, int] = defaultdict(int)
    day_high: defaultdict[str, int] = defaultdict(int)

    for a in analyses:
        d_str = a.created_at.strftime("%Y-%m-%d")
        day_sessions[d_str] += 1

    for s in live_sessions:
        d_str = s.started_at.strftime("%Y-%m-%d")
        day_sessions[d_str] += 1

    for e in rec_events:
        d_str = e.created_at.strftime("%Y-%m-%d")
        day_events[d_str] += 1
        if e.severity == "high":
            day_high[d_str] += 1

    for le in live_events:
        d_str = le.created_at.strftime("%Y-%m-%d")
        day_events[d_str] += 1
        if le.severity == "high":
            day_high[d_str] += 1

    all_dates = sorted(set(list(day_sessions.keys()) + list(day_events.keys())))
    timeline_trends = [
        TimelineTrendPoint(
            date=d,
            sessions_count=day_sessions.get(d, 0),
            events_count=day_events.get(d, 0),
            high_priority_count=day_high.get(d, 0),
        )
        for d in all_dates
    ]

    ANOMALY_EVENT_TYPES = {
        "movement_anomaly",
        "prolonged_stationary_person",
        "restricted_zone_entry",
        "object_movement_without_person",
        "after_hours_activity",
        "possible_object_pickup",
        "possible_unattended_object",
    }
    anomaly_count = sum(1 for e in rec_events if e.event_type in ANOMALY_EVENT_TYPES) + sum(
        1 for le in live_events if le.event_type in ANOMALY_EVENT_TYPES
    )

    return IntelligenceAnalyticsResponse(
        total_sessions=total_sessions_count,
        recorded_sessions_count=len(analyses),
        live_sessions_count=len(live_sessions),
        completed_analyses_count=completed_count,
        failed_analyses_count=failed_count,
        total_duration_seconds=round(total_duration, 2),
        avg_processing_duration_seconds=avg_duration,
        total_frames_processed=total_frames,
        total_detections=total_detections,
        total_unique_tracks=total_unique_tracks,
        total_events=total_events_count,
        anomaly_events=anomaly_count,
        high_priority_events=high_pri,
        medium_priority_events=med_pri,
        low_priority_events=low_pri,
        events_by_category=dict(category_counter),
        events_by_severity=dict(severity_counter),
        top_object_classes=top_classes,
        timeline_trends=timeline_trends,
        session_status_breakdown=dict(status_counter),
    )


def get_unified_session_detail(
    *,
    session_id: str,
    user_id: int,
    session_type: str | None = None,
    db: Session,
    api_prefix: str,
) -> UnifiedSessionDetailResponse:
    """Retrieve full unified session details for recorded or live sessions."""
    # First check recorded analysis
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == session_id, Analysis.user_id == user_id)
        .first()
    )

    if analysis is not None and (session_type is None or session_type == "recorded"):
        video = analysis.video
        name = video.original_filename if video else f"Analysis {analysis.id[:8]}"
        duration = _compute_analysis_duration(analysis, video)

        # Detections
        det_count = db.query(func.count(Detection.id)).filter(Detection.analysis_id == analysis.id).scalar() or 0
        det_classes = dict(
            db.query(Detection.class_name, func.count(Detection.id))
            .filter(Detection.analysis_id == analysis.id)
            .group_by(Detection.class_name)
            .all()
        )

        # Tracks
        tracks = (
            db.query(Track)
            .filter(Track.analysis_id == analysis.id)
            .order_by(Track.track_id.asc())
            .all()
        )
        track_stats = {
            "total_tracks": len(tracks),
            "classes": dict(Counter(t.class_name for t in tracks)),
            "tracks": [
                {
                    "track_id": t.track_id,
                    "class_name": t.class_name,
                    "duration_seconds": t.duration_seconds,
                    "frame_count": t.frame_count,
                    "avg_confidence": t.avg_confidence,
                    "first_seen_timestamp": t.first_seen_timestamp,
                    "last_seen_timestamp": t.last_seen_timestamp,
                }
                for t in tracks
            ],
        }

        # Events
        events = (
            db.query(Event)
            .filter(Event.analysis_id == analysis.id)
            .order_by(Event.start_timestamp.asc())
            .all()
        )

        settings = get_settings()
        analysis_dir = settings.resolved_processed_dir / analysis.id
        metadata_path = analysis_dir / "metadata.json"
        frame_lookup: dict[int, str] = {}
        if metadata_path.exists():
            try:
                raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                for item in raw_meta.get("frames", []):
                    f_idx = int(item["frame_index"])
                    fn = str(item["filename"])
                    frame_lookup[f_idx] = f"{api_prefix}/analysis/{analysis.id}/frames/{fn}"
            except Exception:
                pass

        session_events: list[SessionEventDetail] = []
        for e in events:
            payload = e.explanation_payload or {}
            ev_urls = [frame_lookup[f] for f in (e.evidence_frame_ids or []) if f in frame_lookup]
            session_events.append(
                SessionEventDetail(
                    id=e.id,
                    event_type=e.event_type,
                    category=e.category,
                    title=e.title,
                    description=e.description,
                    start_timestamp=e.start_timestamp,
                    end_timestamp=e.end_timestamp,
                    involved_track_ids=[int(t) for t in (e.involved_track_ids or [])],
                    confidence=e.confidence,
                    severity=e.severity,
                    why_flagged=str(payload.get("why_flagged", "")),
                    observed_sequence=[str(s) for s in payload.get("observed_sequence", [])],
                    requires_human_review=bool(payload.get("requires_human_review", False)),
                    evidence_image_urls=ev_urls,
                    created_at=e.created_at,
                )
            )

        # Evidence
        evidence_items = (
            db.query(Evidence)
            .filter(Evidence.analysis_id == analysis.id, Evidence.user_id == user_id)
            .order_by(Evidence.timestamp_seconds.asc(), Evidence.frame_number.asc())
            .all()
        )
        session_evidence: list[SessionEvidenceDetail] = []
        for ev in evidence_items:
            meta = ev.metadata_json or {}
            session_evidence.append(
                SessionEvidenceDetail(
                    id=ev.id,
                    event_id=ev.event_id,
                    frame_number=ev.frame_number,
                    timestamp_seconds=ev.timestamp_seconds,
                    evidence_type=ev.evidence_type,
                    image_url=f"{api_prefix}/evidence/{ev.id}/image",
                    description=ev.description,
                    why_flagged=str(meta.get("why_flagged", "")),
                    involved_track_ids=[int(t) for t in meta.get("involved_track_ids", [])],
                    created_at=ev.created_at,
                )
            )

        ai_summary = {
            "total_events": len(events),
            "review_recommended_count": sum(1 for e in session_events if e.requires_human_review),
            "high_priority_count": sum(1 for e in session_events if e.severity == "high"),
            "most_common_category": Counter(e.category for e in session_events).most_common(1)[0][0] if session_events else "None",
            "model_architecture": "YOLOv8 + ByteTrack + Temporal Event Rules",
        }

        return UnifiedSessionDetailResponse(
            session_id=analysis.id,
            session_type="recorded",
            name=name,
            video_id=analysis.video_id,
            status=analysis.status,
            started_at=analysis.started_at or analysis.created_at,
            end_time=analysis.completed_at,
            duration_seconds=duration,
            frames_processed=analysis.processed_frames,
            total_frames=analysis.total_frames,
            frame_width=video.width if video else None,
            frame_height=video.height if video else None,
            confidence_threshold=0.40,
            detection_stats={
                "total_detections": det_count,
                "class_counts": det_classes,
            },
            track_stats=track_stats,
            events=session_events,
            evidence_count=len(session_evidence),
            evidence_items=session_evidence,
            pdf_report_url=f"{api_prefix}/reports/{analysis.id}/pdf",
            ai_explanation_summary=ai_summary,
        )

    # Next check live session
    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == user_id)
        .first()
    )

    if live_session is not None:
        duration = _compute_live_duration(live_session)
        name = f"Live Camera Monitoring ({live_session.id[:8]})"

        # Events
        live_events = (
            db.query(LiveEvent)
            .filter(LiveEvent.session_id == live_session.id)
            .order_by(LiveEvent.start_timestamp.asc())
            .all()
        )

        session_events: list[SessionEventDetail] = []
        session_evidence: list[SessionEvidenceDetail] = []

        for le in live_events:
            payload = le.explanation_payload or {}
            img_urls = []
            if le.snapshot_path:
                snap_url = f"{api_prefix}/live/{live_session.id}/events/{le.id}/snapshot"
                img_urls.append(snap_url)
                session_evidence.append(
                    SessionEvidenceDetail(
                        id=le.id,
                        event_id=le.id,
                        frame_number=le.frame_index,
                        timestamp_seconds=le.timestamp_seconds,
                        evidence_type="annotated_tracking",
                        image_url=snap_url,
                        description=le.description,
                        why_flagged=str(payload.get("why_flagged", "")),
                        involved_track_ids=[int(t) for t in (le.involved_track_ids or [])],
                        created_at=le.created_at,
                    )
                )

            session_events.append(
                SessionEventDetail(
                    id=le.id,
                    event_type=le.event_type,
                    category=le.category,
                    title=le.title,
                    description=le.description,
                    start_timestamp=le.start_timestamp,
                    end_timestamp=le.end_timestamp,
                    involved_track_ids=[int(t) for t in (le.involved_track_ids or [])],
                    confidence=le.confidence,
                    severity=le.severity,
                    why_flagged=str(payload.get("why_flagged", "")),
                    observed_sequence=[str(s) for s in payload.get("observed_sequence", [])],
                    requires_human_review=bool(payload.get("requires_human_review", False)),
                    evidence_image_urls=img_urls,
                    created_at=le.created_at,
                )
            )

        ai_summary = {
            "total_events": len(live_events),
            "review_recommended_count": sum(1 for e in session_events if e.requires_human_review),
            "high_priority_count": sum(1 for e in session_events if e.severity == "high"),
            "most_common_category": Counter(e.category for e in session_events).most_common(1)[0][0] if session_events else "None",
            "model_architecture": "YOLOv8 + ByteTrack + Real-time Stream Engine",
        }

        return UnifiedSessionDetailResponse(
            session_id=live_session.id,
            session_type="live",
            name=name,
            video_id=None,
            status=live_session.status,
            started_at=live_session.started_at,
            end_time=live_session.stopped_at or live_session.last_frame_at,
            duration_seconds=duration,
            frames_processed=live_session.frames_processed,
            total_frames=live_session.frames_processed,
            frame_width=live_session.frame_width,
            frame_height=live_session.frame_height,
            confidence_threshold=live_session.confidence_threshold,
            detection_stats={
                "total_detections": live_session.total_detections,
            },
            track_stats={
                "total_tracks": live_session.unique_tracks_count,
            },
            events=session_events,
            evidence_count=len(session_evidence),
            evidence_items=session_evidence,
            pdf_report_url=f"{api_prefix}/reports/live/{live_session.id}/pdf",
            ai_explanation_summary=ai_summary,
        )

    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Monitoring session not found.",
    )
