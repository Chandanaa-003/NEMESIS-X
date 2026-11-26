from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any
import uuid

import cv2
import numpy as np
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models.behavior import BehaviorSnapshot
from app.models.live_session import LiveEvent, LiveSession
from app.models.zone import Zone
from app.schemas.analysis import (
    BoundingBoxInfo,
    TrackPositionSnapshot,
    TrackSummaryInfo,
    TrackTimelinePointInfo,
)
from app.schemas.live import (
    LiveDetectionInfo,
    LiveEventInfo,
    LiveFrameProcessResponse,
    LiveSessionStartResponse,
    LiveSessionStatusResponse,
)
from app.services.detector import get_detection_model
from app.services.behavior_engine import DEFAULT_BASELINE_CONFIG
from app.services.event_engine import discover_events_from_data
from app.services.identity_engine import (
    IdentityMatcher,
    identify_live_detections,
    initialize_live_identity_matcher,
)
from app.services.interaction_engine import SessionTemporalMemory
from app.services.track_explorer import format_track_code
from app.services.tracker import TrackTimelinePoint, _TrackAccumulator
from app.services.zone_engine import ZoneIntelligenceEngine

MAX_LIVE_FRAME_BYTES = 10 * 1024 * 1024  # 10 MB per captured JPEG frame

_live_registry_lock = threading.Lock()
_model_predict_lock = threading.Lock()


@dataclass
class _LiveSessionRuntime:
    session_id: str
    user_id: int
    tracker: Any
    confidence_threshold: float
    image_size: int
    started_monotonic: float
    next_frame_index: int = 0
    frame_width: int = 0
    frame_height: int = 0
    total_detections: int = 0
    frame_ts_map: dict[int, float] = field(default_factory=dict)
    track_map: dict[int, _TrackAccumulator] = field(default_factory=dict)
    emitted_event_keys: set[tuple[str, tuple[int, ...]]] = field(default_factory=set)
    memory: SessionTemporalMemory | None = None
    identity_matcher: IdentityMatcher | None = None
    zone_engine: ZoneIntelligenceEngine = field(default_factory=ZoneIntelligenceEngine)
    session_lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = SessionTemporalMemory(session_id=self.session_id)


_active_live_sessions: dict[str, _LiveSessionRuntime] = {}


def refresh_live_identity_matcher(
    *, session_id: str, user_id: int, db: Session
) -> None:
    """Reload corrected owner-scoped track assignments into an active live session."""
    with _live_registry_lock:
        runtime = _active_live_sessions.get(session_id)
    if runtime is None or runtime.user_id != user_id:
        return
    with runtime.session_lock:
        if runtime.identity_matcher is not None:
            runtime.identity_matcher = initialize_live_identity_matcher(
                db=db,
                session_id=session_id,
                user_id=user_id,
            )


def _create_isolated_bytetracker(tracker_config: str) -> Any:
    """Create a dedicated Ultralytics BYTETracker instance for one live session."""
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import IterableSimpleNamespace, YAML
    from ultralytics.utils.checks import check_yaml

    cfg_dict = YAML.load(check_yaml(tracker_config))
    cfg_dict["device"] = "cpu"
    cfg = IterableSimpleNamespace(**cfg_dict)
    return BYTETracker(args=cfg)


def _safe_relative_live_path(absolute_path: Path) -> str:
    project_root = BACKEND_DIR.parent
    try:
        return absolute_path.relative_to(project_root).as_posix()
    except ValueError:
        return absolute_path.as_posix()


def _save_live_latest_frame(session_id: str, frame_img: np.ndarray) -> None:
    """Keep one small current-frame preview for authorized zone editing and overlays."""
    settings = get_settings()
    session_dir = (settings.resolved_live_dir / session_id).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    target_path = (session_dir / "latest.jpg").resolve()
    if target_path.parent != session_dir:
        raise ValueError("Invalid live preview storage path.")
    height, width = frame_img.shape[:2]
    preview = frame_img
    if width > 640:
        preview = cv2.resize(
            frame_img,
            (640, max(1, round(height * (640 / float(width))))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not ok:
        raise OSError("Unable to encode live preview frame.")
    temporary_path = target_path.with_suffix(".tmp")
    temporary_path.write_bytes(encoded.tobytes())
    temporary_path.replace(target_path)


def _build_track_summaries(runtime: _LiveSessionRuntime) -> list[TrackSummaryInfo]:
    summaries: list[TrackSummaryInfo] = []
    for acc in sorted(
        runtime.track_map.values(),
        key=lambda item: (item.first_seen_timestamp, item.track_id),
    ):
        if not acc.class_votes:
            continue
        (dominant_cls_id, dominant_cls_name), _ = acc.class_votes.most_common(1)[0]
        duration = round(max(0.0, acc.last_seen_timestamp - acc.first_seen_timestamp), 3)
        avg_conf = round(sum(acc.confidences) / max(len(acc.confidences), 1), 4)
        max_conf = round(max(acc.confidences), 4)

        pts = [
            TrackTimelinePointInfo(
                frame_index=pt.frame_index,
                timestamp_seconds=pt.timestamp_seconds,
                center_x=pt.center_x,
                center_y=pt.center_y,
                confidence=pt.confidence,
                bbox=BoundingBoxInfo(
                    x1=pt.bbox_x1,
                    y1=pt.bbox_y1,
                    x2=pt.bbox_x2,
                    y2=pt.bbox_y2,
                ),
            )
            for pt in acc.timeline_points[-60:]
        ]

        last_pos: TrackPositionSnapshot | None = None
        if pts:
            last_pt = pts[-1]
            norm_x = (
                round(min(1.0, max(0.0, last_pt.center_x / runtime.frame_width)), 4)
                if runtime.frame_width > 0
                else None
            )
            norm_y = (
                round(min(1.0, max(0.0, last_pt.center_y / runtime.frame_height)), 4)
                if runtime.frame_height > 0
                else None
            )
            last_pos = TrackPositionSnapshot(
                frame_index=last_pt.frame_index,
                timestamp_seconds=last_pt.timestamp_seconds,
                center_x=last_pt.center_x,
                center_y=last_pt.center_y,
                norm_x=norm_x,
                norm_y=norm_y,
                bbox=last_pt.bbox,
            )

        summaries.append(
            TrackSummaryInfo(
                track_id=acc.track_id,
                track_code=format_track_code(acc.track_id),
                class_id=dominant_cls_id,
                class_name=dominant_cls_name,
                first_seen_frame=acc.first_seen_frame,
                last_seen_frame=acc.last_seen_frame,
                first_seen_timestamp=acc.first_seen_timestamp,
                last_seen_timestamp=acc.last_seen_timestamp,
                duration_seconds=duration,
                frame_count=len(acc.timeline_points),
                avg_confidence=avg_conf,
                max_confidence=max_conf,
                last_known_position=last_pos,
                timeline_points=pts,
            )
        )
    return summaries


def _serialize_tracks_for_events(tracks: list[TrackSummaryInfo]) -> list[dict[str, Any]]:
    return [
        {
            "track_id": t.track_id,
            "class_id": t.class_id,
            "class_name": t.class_name,
            "first_seen_frame": t.first_seen_frame,
            "last_seen_frame": t.last_seen_frame,
            "first_seen_timestamp": t.first_seen_timestamp,
            "last_seen_timestamp": t.last_seen_timestamp,
            "duration_seconds": t.duration_seconds,
            "frame_count": t.frame_count,
            "avg_confidence": t.avg_confidence,
            "max_confidence": t.max_confidence,
            "timeline_points": [
                {
                    "frame_index": pt.frame_index,
                    "timestamp_seconds": pt.timestamp_seconds,
                    "center_x": pt.center_x,
                    "center_y": pt.center_y,
                    "confidence": pt.confidence,
                }
                for pt in t.timeline_points
            ],
        }
        for t in tracks
    ]


def _save_live_event_snapshot(
    *,
    session_id: str,
    event_id: str,
    frame_img: np.ndarray,
    detections: list[LiveDetectionInfo],
    involved_track_ids: list[int],
    timestamp_seconds: float,
    zones: list[dict[str, Any]] | None = None,
) -> str | None:
    """Save an annotated JPEG snapshot for a newly discovered live event."""
    settings = get_settings()
    session_dir = (settings.resolved_live_dir / session_id).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    target_path = (session_dir / f"{event_id}.jpg").resolve()
    if target_path.parent != session_dir:
        return None

    canvas = frame_img.copy()
    for zone in zones or []:
        points = [
            (
                int(round(float(point[0]) * canvas.shape[1])),
                int(round(float(point[1]) * canvas.shape[0])),
            )
            for point in zone["polygon"]
        ]
        rgb = str(zone.get("color", "#2563EB")).lstrip("#")
        try:
            color = tuple(int(rgb[index : index + 2], 16) for index in (4, 2, 0))
        except ValueError:
            color = (235, 99, 37)
        if points:
            cv2.polylines(
                canvas,
                [np.array(points, dtype=np.int32)],
                True,
                color,
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                canvas,
                str(zone["name"])[:28],
                points[0],
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )
    involved_set = set(involved_track_ids)
    for det in detections:
        x1 = int(round(det.bbox.x1))
        y1 = int(round(det.bbox.y1))
        x2 = int(round(det.bbox.x2))
        y2 = int(round(det.bbox.y2))
        is_involved = det.track_id is not None and det.track_id in involved_set
        color = (235, 99, 37) if is_involved else (148, 163, 184)
        thickness = 3 if is_involved else 1
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        prefix = f"{det.track_code} " if det.track_code else ""
        label = f"{prefix}{det.class_name} {int(round(det.confidence * 100))}%"
        cv2.putText(
            canvas,
            label,
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2 if is_involved else 1,
            cv2.LINE_AA,
        )

    cv2.rectangle(canvas, (8, 8), (245, 32), (255, 255, 255), -1)
    cv2.putText(
        canvas,
        f"LIVE EVENT | t={timestamp_seconds:.2f}s",
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (17, 24, 39),
        1,
        cv2.LINE_AA,
    )

    ok, encoded = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None
    target_path.write_bytes(encoded.tobytes())
    return _safe_relative_live_path(target_path)


def _to_live_event_info(ev: LiveEvent, api_prefix: str) -> LiveEventInfo:
    payload = ev.explanation_payload or {}
    snap_url = (
        f"{api_prefix}/live/{ev.session_id}/events/{ev.id}/snapshot"
        if ev.snapshot_path
        else None
    )
    return LiveEventInfo(
        id=ev.id,
        session_id=ev.session_id,
        event_type=ev.event_type,
        category=ev.category,
        title=ev.title,
        description=ev.description,
        timestamp_seconds=ev.timestamp_seconds,
        start_timestamp=ev.start_timestamp,
        end_timestamp=ev.end_timestamp,
        involved_track_ids=[int(t) for t in (ev.involved_track_ids or [])],
        confidence=ev.confidence,
        severity=ev.severity,
        frame_index=ev.frame_index,
        requires_human_review=bool(payload.get("requires_human_review", False)),
        alerts_enabled=bool(payload.get("alerts_enabled", True)),
        voice_alerts_enabled=bool(payload.get("voice_alerts_enabled", True)),
        zone_id=payload.get("zone_id"),
        zone_name=payload.get("zone_name"),
        why_flagged=str(payload.get("why_flagged", "")),
        observed_sequence=[str(s) for s in payload.get("observed_sequence", [])],
        snapshot_url=snap_url,
        created_at=ev.created_at,
    )


def start_live_session(
    *,
    user_id: int,
    confidence_threshold: float,
    image_size: int,
    db: Session,
) -> LiveSessionStartResponse:
    """Create a SQLite LiveSession record and allocate isolated ByteTrack state."""
    settings = get_settings()
    # Ensure cached singleton YOLO model and Ultralytics runtime are ready
    get_detection_model(settings.yolo_model_name)
    tracker = _create_isolated_bytetracker(settings.tracker_config)

    session_id = str(uuid.uuid4())
    db_session = LiveSession(
        id=session_id,
        user_id=user_id,
        status="active",
        confidence_threshold=confidence_threshold,
        image_size=image_size,
    )
    try:
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError("Database error while starting live monitoring session.") from exc

    runtime = _LiveSessionRuntime(
        session_id=session_id,
        user_id=user_id,
        tracker=tracker,
        confidence_threshold=confidence_threshold,
        image_size=image_size,
        started_monotonic=time.monotonic(),
    )
    with _live_registry_lock:
        _active_live_sessions[session_id] = runtime

    return LiveSessionStartResponse(
        session_id=db_session.id,
        status="active",
        confidence_threshold=db_session.confidence_threshold,
        image_size=db_session.image_size,
        started_at=db_session.started_at,
    )


def process_live_frame(
    *,
    session_row: LiveSession,
    frame_bytes: bytes,
    timestamp_seconds: float | None,
    db: Session,
) -> LiveFrameProcessResponse:
    """Decode one captured JPEG frame, run YOLO + session ByteTrack, and discover events."""
    if len(frame_bytes) == 0 or len(frame_bytes) > MAX_LIVE_FRAME_BYTES:
        raise ValueError("Captured frame payload is empty or exceeds size limit.")

    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame_img is None or frame_img.size == 0:
        raise ValueError("Uploaded payload is not a valid image frame.")
    _save_live_latest_frame(session_row.id, frame_img)

    with _live_registry_lock:
        runtime = _active_live_sessions.get(session_row.id)

    if runtime is None:
        settings = get_settings()
        runtime = _LiveSessionRuntime(
            session_id=session_row.id,
            user_id=session_row.user_id,
            tracker=_create_isolated_bytetracker(settings.tracker_config),
            confidence_threshold=session_row.confidence_threshold,
            image_size=session_row.image_size,
            started_monotonic=time.monotonic(),
            next_frame_index=session_row.frames_processed,
        )
        with _live_registry_lock:
            _active_live_sessions[session_row.id] = runtime

    settings = get_settings()
    model = get_detection_model(settings.yolo_model_name)

    t0 = time.perf_counter()
    with runtime.session_lock:
        frame_h, frame_w = frame_img.shape[:2]
        runtime.frame_width = frame_w
        runtime.frame_height = frame_h

        frame_index = runtime.next_frame_index
        runtime.next_frame_index += 1

        ts = (
            round(max(0.0, float(timestamp_seconds)), 3)
            if timestamp_seconds is not None
            else round(max(0.0, time.monotonic() - runtime.started_monotonic), 3)
        )
        runtime.frame_ts_map[frame_index] = ts

        with _model_predict_lock:
            results = model.predict(
                source=frame_img,
                imgsz=runtime.image_size,
                conf=runtime.confidence_threshold,
                device="cpu",
                verbose=False,
            )

        frame_detections: list[LiveDetectionInfo] = []
        if results:
            result = results[0]
            names_map = result.names or {}
            boxes = result.boxes
            if boxes is not None:
                det_np = boxes.cpu().numpy()
                tracks_out = runtime.tracker.update(det_np, frame_img)

                tracked_indices: set[int] = set()
                if tracks_out is not None and len(tracks_out) > 0:
                    for row in tracks_out:
                        x1, y1, x2, y2 = (round(float(v), 2) for v in row[:4])
                        tid = int(row[4])
                        conf_val = round(float(row[5]), 4)
                        cls_id = int(row[6])
                        det_idx = int(row[7]) if len(row) > 7 else -1
                        if det_idx >= 0:
                            tracked_indices.add(det_idx)
                        cls_name = str(names_map.get(cls_id, f"class_{cls_id}"))
                        t_code = format_track_code(tid)

                        frame_detections.append(
                            LiveDetectionInfo(
                                track_id=tid,
                                track_code=t_code,
                                class_id=cls_id,
                                class_name=cls_name,
                                confidence=conf_val,
                                bbox=BoundingBoxInfo(x1=x1, y1=y1, x2=x2, y2=y2),
                            )
                        )

                        cx = round((x1 + x2) / 2.0, 2)
                        cy = round((y1 + y2) / 2.0, 2)
                        acc = runtime.track_map.get(tid)
                        if acc is None:
                            acc = _TrackAccumulator(
                                track_id=tid,
                                first_seen_frame=frame_index,
                                last_seen_frame=frame_index,
                                first_seen_timestamp=ts,
                                last_seen_timestamp=ts,
                            )
                            runtime.track_map[tid] = acc
                        else:
                            acc.last_seen_frame = max(acc.last_seen_frame, frame_index)
                            acc.last_seen_timestamp = max(acc.last_seen_timestamp, ts)

                        acc.class_votes[(cls_id, cls_name)] += 1
                        acc.confidences.append(conf_val)
                        acc.timeline_points.append(
                            TrackTimelinePoint(
                                frame_index=frame_index,
                                timestamp_seconds=ts,
                                center_x=cx,
                                center_y=cy,
                                confidence=conf_val,
                                bbox_x1=x1,
                                bbox_y1=y1,
                                bbox_x2=x2,
                                bbox_y2=y2,
                            )
                        )

                # Also expose raw detections not yet assigned an active ByteTrack ID
                if len(boxes) > 0:
                    xyxy_all = boxes.xyxy.tolist()
                    conf_all = boxes.conf.tolist()
                    cls_all = boxes.cls.tolist()
                    for idx, (coords, score, cls_raw) in enumerate(
                        zip(xyxy_all, conf_all, cls_all)
                    ):
                        if idx in tracked_indices:
                            continue
                        cls_id = int(cls_raw)
                        cls_name = str(names_map.get(cls_id, f"class_{cls_id}"))
                        x1, y1, x2, y2 = (round(float(v), 2) for v in coords[:4])
                        frame_detections.append(
                            LiveDetectionInfo(
                                track_id=None,
                                track_code=None,
                                class_id=cls_id,
                                class_name=cls_name,
                                confidence=round(float(score), 4),
                                bbox=BoundingBoxInfo(x1=x1, y1=y1, x2=x2, y2=y2),
                            )
                        )

        if runtime.identity_matcher is None:
            runtime.identity_matcher = initialize_live_identity_matcher(
                db=db,
                session_id=session_row.id,
                user_id=session_row.user_id,
            )
        identify_live_detections(
            db=db,
            matcher=runtime.identity_matcher,
            session_id=session_row.id,
            user_id=session_row.user_id,
            frame=frame_img,
            frame_index=frame_index,
            timestamp=ts,
            detections=frame_detections,
        )

        runtime.total_detections += len(frame_detections)
        active_tracks = _build_track_summaries(runtime)

        drafts = discover_events_from_data(
            tracks_data=_serialize_tracks_for_events(active_tracks),
            frame_ts_map=runtime.frame_ts_map,
            frame_width=frame_w,
            frame_height=frame_h,
            exit_grace_frames=1,
            memory=runtime.memory,
        )
        zone_rows = (
            db.query(Zone)
            .filter(
                Zone.live_session_id == session_row.id,
                Zone.user_id == session_row.user_id,
            )
            .order_by(Zone.created_at.asc())
            .all()
        )
        zone_configs = [
            {
                "id": zone.id,
                "name": zone.name,
                "zone_type": zone.zone_type,
                "color": zone.color,
                "polygon": zone.polygon,
                "settings": zone.settings,
            }
            for zone in zone_rows
        ]
        drafts.extend(
            runtime.zone_engine.process_frame(
                zones=zone_configs,
                detections=[
                    {
                        "track_id": detection.track_id,
                        "class_name": detection.class_name,
                        "confidence": detection.confidence,
                        "bbox": detection.bbox.model_dump(),
                    }
                    for detection in frame_detections
                ],
                frame_index=frame_index,
                timestamp_seconds=ts,
                frame_width=frame_w,
                frame_height=frame_h,
            )
        )

        detection_summary_lines = [
            f"{(d.identity_code + ' · ') if d.identity_code else ''}"
            f"{(d.track_code + ' ') if d.track_code else ''}"
            f"{d.class_name} ({int(round(d.confidence * 100))}%)"
            for d in frame_detections
        ]

        new_db_events: list[LiveEvent] = []
        for draft in drafts:
            zone_id = draft.explanation_payload.get("zone_id")
            if zone_id is None:
                key = (draft.event_type, tuple(draft.involved_track_ids))
                if key in runtime.emitted_event_keys:
                    continue
                runtime.emitted_event_keys.add(key)

            snap_rel = _save_live_event_snapshot(
                session_id=session_row.id,
                event_id=draft.id,
                frame_img=frame_img,
                detections=frame_detections,
                involved_track_ids=draft.involved_track_ids,
                timestamp_seconds=ts,
                zones=zone_configs if zone_id is not None else None,
            )
            payload = dict(draft.explanation_payload)
            payload.update(
                {
                    "session_id": session_row.id,
                    "event_id": draft.id,
                    "detection_count": len(frame_detections),
                    "detection_summary": detection_summary_lines,
                    "evidence_image_reference": snap_rel,
                }
            )
            new_db_events.append(
                LiveEvent(
                    id=draft.id,
                    session_id=session_row.id,
                    user_id=session_row.user_id,
                    event_type=draft.event_type,
                    category=draft.category,
                    title=draft.title,
                    description=draft.description,
                    explanation_payload=payload,
                    timestamp_seconds=ts,
                    start_timestamp=draft.start_timestamp,
                    end_timestamp=draft.end_timestamp,
                    involved_track_ids=draft.involved_track_ids,
                    confidence=draft.confidence,
                    severity=draft.severity,
                    frame_index=frame_index,
                    snapshot_path=snap_rel,
                )
            )

        session_row.frames_processed = runtime.next_frame_index
        session_row.total_detections = runtime.total_detections
        session_row.unique_tracks_count = len(active_tracks)
        session_row.events_discovered_count += len(new_db_events)
        session_row.frame_width = frame_w
        session_row.frame_height = frame_h
        session_row.last_frame_at = datetime.now(timezone.utc)

        behavior_snapshot = (
            db.query(BehaviorSnapshot)
            .filter(
                BehaviorSnapshot.live_session_id == session_row.id,
                BehaviorSnapshot.user_id == session_row.user_id,
            )
            .first()
        )
        if behavior_snapshot is None:
            behavior_snapshot = BehaviorSnapshot(
                user_id=session_row.user_id,
                live_session_id=session_row.id,
                baseline_config=dict(DEFAULT_BASELINE_CONFIG),
                track_history=[],
                report_payload={},
            )
            db.add(behavior_snapshot)

        behavior_snapshot.track_history = _serialize_tracks_for_events(active_tracks)
        if new_db_events:
            db.add_all(new_db_events)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        for ev in new_db_events:
            db.refresh(ev)

    processing_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    api_prefix = settings.api_v1_prefix
    return LiveFrameProcessResponse(
        session_id=session_row.id,
        status=session_row.status,  # type: ignore[arg-type]
        frame_index=frame_index,
        timestamp_seconds=ts,
        frame_width=frame_w,
        frame_height=frame_h,
        frames_processed=session_row.frames_processed,
        total_detections=session_row.total_detections,
        unique_tracks_count=session_row.unique_tracks_count,
        events_discovered_count=session_row.events_discovered_count,
        processing_ms=processing_ms,
        detections=frame_detections,
        active_tracks=active_tracks,
        new_events=[_to_live_event_info(ev, api_prefix) for ev in new_db_events],
    )


def get_live_session_status_payload(
    *,
    session_row: LiveSession,
    db: Session,
) -> LiveSessionStatusResponse:
    """Return persisted metrics plus active runtime trajectories for a live session."""
    settings = get_settings()
    with _live_registry_lock:
        runtime = _active_live_sessions.get(session_row.id)

    active_tracks = _build_track_summaries(runtime) if runtime is not None else []
    events = (
        db.query(LiveEvent)
        .filter(LiveEvent.session_id == session_row.id, LiveEvent.user_id == session_row.user_id)
        .order_by(LiveEvent.created_at.desc())
        .limit(50)
        .all()
    )

    end_ref = session_row.stopped_at or session_row.last_frame_at or datetime.now(timezone.utc)
    started = session_row.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if end_ref.tzinfo is None:
        end_ref = end_ref.replace(tzinfo=timezone.utc)
    duration = round(max(0.0, (end_ref - started).total_seconds()), 1)

    return LiveSessionStatusResponse(
        session_id=session_row.id,
        status=session_row.status,  # type: ignore[arg-type]
        confidence_threshold=session_row.confidence_threshold,
        image_size=session_row.image_size,
        frames_processed=session_row.frames_processed,
        total_detections=session_row.total_detections,
        unique_tracks_count=session_row.unique_tracks_count,
        events_discovered_count=session_row.events_discovered_count,
        duration_seconds=duration,
        frame_width=session_row.frame_width,
        frame_height=session_row.frame_height,
        started_at=session_row.started_at,
        last_frame_at=session_row.last_frame_at,
        stopped_at=session_row.stopped_at,
        active_tracks=active_tracks,
        events=[_to_live_event_info(ev, settings.api_v1_prefix) for ev in events],
    )


def stop_live_session(
    *,
    session_row: LiveSession,
    db: Session,
) -> LiveSessionStatusResponse:
    """Stop monitoring session, release in-memory ByteTrack state, and persist stop timestamp."""
    with _live_registry_lock:
        runtime = _active_live_sessions.pop(session_row.id, None)

    if runtime is not None:
        with runtime.session_lock:
            runtime.track_map.clear()
            runtime.frame_ts_map.clear()
            runtime.emitted_event_keys.clear()
            runtime.identity_matcher = None
            runtime.zone_engine.reset()
            runtime.tracker = None
    latest_frame = (get_settings().resolved_live_dir / session_row.id / "latest.jpg").resolve()
    if latest_frame.parent == (get_settings().resolved_live_dir / session_row.id).resolve():
        latest_frame.unlink(missing_ok=True)

    if session_row.status != "stopped":
        session_row.status = "stopped"
        session_row.stopped_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session_row)

    return get_live_session_status_payload(session_row=session_row, db=db)


def list_user_live_sessions(*, user_id: int, db: Session) -> list[LiveSessionStatusResponse]:
    """List live monitoring sessions belonging to the authenticated user, newest first."""
    sessions = (
        db.query(LiveSession)
        .filter(LiveSession.user_id == user_id)
        .order_by(LiveSession.started_at.desc())
        .limit(30)
        .all()
    )
    return [get_live_session_status_payload(session_row=s, db=db) for s in sessions]
