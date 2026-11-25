import json
import math
from pathlib import Path
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.analysis import Analysis
from app.models.detection import Detection
from app.models.event import Event
from app.models.track import Track
from app.schemas.analysis import (
    BoundingBoxInfo,
    DetectedObjectInfo,
    TrackDetailResponse,
    TrackFramesResponse,
    TrackMovementHistory,
    TrackMovementStep,
    TrackObservationFrameInfo,
    TrackPositionSnapshot,
    TrackRelatedEventInfo,
    TrackSummaryInfo,
    TrackTimelinePointInfo,
)

SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4}\.jpg$")
TEMPORARY_ID_NOTICE = (
    "Tracking IDs (T001, T002, ...) are temporary ByteTrack session identifiers for this "
    "analysis only and do not represent persistent real-world identities."
)


def format_track_code(track_id: int) -> str:
    """Format an integer tracker ID into a readable temporary code (e.g., T001)."""
    return f"T{track_id:03d}"


def _describe_step_direction(dx: float, dy: float, dist_px: float, norm_dist: float | None) -> str:
    """Describe relative 2D image-plane displacement between observations."""
    if norm_dist is not None and norm_dist <= 0.015:
        return "stationary"
    if norm_dist is None and dist_px <= 6.0:
        return "stationary"

    horiz = "right" if dx > 4.0 else "left" if dx < -4.0 else ""
    vert = "downward" if dy > 4.0 else "upward" if dy < -4.0 else ""
    if horiz and vert:
        return f"moving {horiz} and {vert}"
    if horiz:
        return f"moving {horiz}"
    if vert:
        return f"moving {vert}"
    return "minimal shift"


def _resolve_frame_dimensions(analysis_dir: Path) -> tuple[int | None, int | None]:
    """Resolve the extracted/detection pixel dimensions from saved JSON artifacts."""
    det_path = analysis_dir / "detections.json"
    if det_path.exists():
        try:
            raw_det = json.loads(det_path.read_text(encoding="utf-8"))
            for frame_entry in raw_det.get("frames", []):
                w = frame_entry.get("frame_width")
                h = frame_entry.get("frame_height")
                if w and h:
                    return int(w), int(h)
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    meta_path = analysis_dir / "metadata.json"
    if meta_path.exists():
        try:
            raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            orig = raw_meta.get("original_dimensions") or {}
            orig_w = int(orig.get("width") or 0)
            orig_h = int(orig.get("height") or 0)
            max_w = int(raw_meta.get("max_width_applied") or orig_w)
            if orig_w > 0 and orig_h > 0:
                if max_w > 0 and orig_w > max_w:
                    return max_w, max(1, round(orig_h * (max_w / float(orig_w))))
                return orig_w, orig_h
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    return None, None


def _build_last_position(
    points: list[TrackTimelinePointInfo],
    frame_width: int | None,
    frame_height: int | None,
) -> TrackPositionSnapshot | None:
    if not points:
        return None
    last = max(points, key=lambda p: (p.frame_index, p.timestamp_seconds))
    norm_x = (
        round(min(1.0, max(0.0, last.center_x / frame_width)), 4)
        if frame_width and frame_width > 0
        else None
    )
    norm_y = (
        round(min(1.0, max(0.0, last.center_y / frame_height)), 4)
        if frame_height and frame_height > 0
        else None
    )
    return TrackPositionSnapshot(
        frame_index=last.frame_index,
        timestamp_seconds=last.timestamp_seconds,
        center_x=last.center_x,
        center_y=last.center_y,
        norm_x=norm_x,
        norm_y=norm_y,
        bbox=last.bbox,
    )


def _load_tracks_from_sqlite_fallback(
    analysis_id: str,
    db: Session,
    frame_width: int | None,
    frame_height: int | None,
) -> list[TrackSummaryInfo]:
    """Reconstruct TrackSummaryInfo from SQLite Track + Detection rows if tracks.json is absent."""
    db_tracks = (
        db.query(Track)
        .filter(Track.analysis_id == analysis_id)
        .order_by(Track.first_seen_timestamp.asc(), Track.track_id.asc())
        .all()
    )
    if not db_tracks:
        return []

    det_rows = (
        db.query(Detection)
        .filter(Detection.analysis_id == analysis_id, Detection.track_id.isnot(None))
        .order_by(Detection.frame_index.asc())
        .all()
    )
    points_by_tid: dict[int, list[TrackTimelinePointInfo]] = {}
    for det in det_rows:
        if det.track_id is None:
            continue
        cx = round((det.bbox_x1 + det.bbox_x2) / 2.0, 2)
        cy = round((det.bbox_y1 + det.bbox_y2) / 2.0, 2)
        points_by_tid.setdefault(det.track_id, []).append(
            TrackTimelinePointInfo(
                frame_index=det.frame_index,
                timestamp_seconds=det.timestamp_seconds,
                center_x=cx,
                center_y=cy,
                confidence=det.confidence,
                bbox=BoundingBoxInfo(
                    x1=det.bbox_x1,
                    y1=det.bbox_y1,
                    x2=det.bbox_x2,
                    y2=det.bbox_y2,
                ),
            )
        )

    results: list[TrackSummaryInfo] = []
    for trk in db_tracks:
        pts = points_by_tid.get(trk.track_id, [])
        results.append(
            TrackSummaryInfo(
                track_id=trk.track_id,
                track_code=format_track_code(trk.track_id),
                class_id=trk.class_id,
                class_name=trk.class_name,
                first_seen_frame=trk.first_seen_frame,
                last_seen_frame=trk.last_seen_frame,
                first_seen_timestamp=trk.first_seen_timestamp,
                last_seen_timestamp=trk.last_seen_timestamp,
                duration_seconds=trk.duration_seconds,
                frame_count=trk.frame_count,
                avg_confidence=trk.avg_confidence,
                max_confidence=trk.max_confidence,
                last_known_position=_build_last_position(pts, frame_width, frame_height),
                timeline_points=pts,
            )
        )
    return results


def load_enriched_tracks_data(
    analysis_id: str,
    db: Session | None = None,
) -> tuple[dict[str, Any], list[TrackSummaryInfo]]:
    """Load saved tracks from tracks.json (or SQLite fallback) with track codes & positions."""
    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis_id
    tracks_path = analysis_dir / "tracks.json"
    frame_w, frame_h = _resolve_frame_dimensions(analysis_dir)

    if not tracks_path.exists():
        if db is not None:
            fallback_tracks = _load_tracks_from_sqlite_fallback(analysis_id, db, frame_w, frame_h)
            if fallback_tracks:
                class_counts: dict[str, int] = {}
                for t in fallback_tracks:
                    class_counts[t.class_name] = class_counts.get(t.class_name, 0) + 1
                return (
                    {
                        "tracker_name": "bytetrack",
                        "total_tracks": len(fallback_tracks),
                        "tracks_by_class": class_counts,
                    },
                    fallback_tracks,
                )
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
        tid = int(item["track_id"])
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
                track_id=tid,
                track_code=format_track_code(tid),
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
                last_known_position=_build_last_position(timeline_points, frame_w, frame_h),
                timeline_points=timeline_points,
            )
        )

    return summary, parsed_tracks


def build_track_observation_frames(
    *,
    analysis: Analysis,
    track: TrackSummaryInfo,
    api_prefix: str,
) -> list[TrackObservationFrameInfo]:
    """Build chronologically ordered observation frames for a single track."""
    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id
    frames_dir = (analysis_dir / "frames").resolve()
    detections_path = analysis_dir / "detections.json"
    metadata_path = analysis_dir / "metadata.json"

    meta_by_index: dict[int, dict[str, Any]] = {}
    if metadata_path.exists():
        try:
            raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            for item in raw_meta.get("frames", []):
                meta_by_index[int(item["frame_index"])] = item
        except (OSError, json.JSONDecodeError, ValueError):
            meta_by_index = {}

    observations: list[TrackObservationFrameInfo] = []
    seen_frames: set[int] = set()
    prev_cx: float | None = None
    prev_cy: float | None = None

    if detections_path.exists():
        try:
            raw_det = json.loads(detections_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read detection records for track frames.",
            ) from exc

        det_frames = sorted(
            raw_det.get("frames", []),
            key=lambda f: int(f.get("frame_index", 0)),
        )
        for frame_entry in det_frames:
            f_idx = int(frame_entry.get("frame_index", 0))
            raw_dets = frame_entry.get("detections", [])
            matching: list[DetectedObjectInfo] = []
            others: list[DetectedObjectInfo] = []

            for det in raw_dets:
                bbox = det.get("bbox", {})
                raw_tid = det.get("track_id")
                tid = int(raw_tid) if raw_tid is not None else None
                parsed_det = DetectedObjectInfo(
                    track_id=tid,
                    track_code=format_track_code(tid) if tid is not None else None,
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
                if tid == track.track_id:
                    matching.append(parsed_det)
                else:
                    others.append(parsed_det)

            if not matching:
                continue

            selected = max(matching, key=lambda d: d.confidence)
            filename = str(frame_entry.get("filename", ""))
            if not SAFE_FRAME_FILENAME_RE.match(filename):
                filename = f"frame_{f_idx:04d}.jpg"

            target_path = (frames_dir / Path(filename).name).resolve()
            frame_available = target_path.parent == frames_dir and target_path.is_file()

            cx = round((selected.bbox.x1 + selected.bbox.x2) / 2.0, 2)
            cy = round((selected.bbox.y1 + selected.bbox.y2) / 2.0, 2)
            dx = round(cx - prev_cx, 2) if prev_cx is not None else 0.0
            dy = round(cy - prev_cy, 2) if prev_cy is not None else 0.0
            prev_cx, prev_cy = cx, cy
            seen_frames.add(f_idx)

            observations.append(
                TrackObservationFrameInfo(
                    frame_index=f_idx,
                    source_frame_index=int(frame_entry.get("source_frame_index", f_idx)),
                    timestamp_seconds=float(frame_entry.get("timestamp_seconds", 0.0)),
                    filename=filename,
                    frame_url=f"{api_prefix}/analysis/{analysis.id}/frames/{filename}",
                    frame_available=frame_available,
                    frame_width=frame_entry.get("frame_width"),
                    frame_height=frame_entry.get("frame_height"),
                    selected_detection=selected,
                    center_x=cx,
                    center_y=cy,
                    position_delta_x=dx,
                    position_delta_y=dy,
                    other_detections=others,
                )
            )

    # Fallback: fill any timeline points missing from detections.json (without inventing boxes)
    if not observations and track.timeline_points:
        frame_w, frame_h = _resolve_frame_dimensions(analysis_dir)
        for pt in sorted(track.timeline_points, key=lambda p: p.frame_index):
            if pt.frame_index in seen_frames:
                continue
            meta_entry = meta_by_index.get(pt.frame_index, {})
            filename = str(meta_entry.get("filename") or f"frame_{pt.frame_index:04d}.jpg")
            if not SAFE_FRAME_FILENAME_RE.match(filename):
                filename = f"frame_{pt.frame_index:04d}.jpg"
            target_path = (frames_dir / Path(filename).name).resolve()
            frame_available = target_path.parent == frames_dir and target_path.is_file()

            dx = round(pt.center_x - prev_cx, 2) if prev_cx is not None else 0.0
            dy = round(pt.center_y - prev_cy, 2) if prev_cy is not None else 0.0
            prev_cx, prev_cy = pt.center_x, pt.center_y

            observations.append(
                TrackObservationFrameInfo(
                    frame_index=pt.frame_index,
                    source_frame_index=int(meta_entry.get("source_frame_index", pt.frame_index)),
                    timestamp_seconds=pt.timestamp_seconds,
                    filename=filename,
                    frame_url=f"{api_prefix}/analysis/{analysis.id}/frames/{filename}",
                    frame_available=frame_available,
                    frame_width=frame_w,
                    frame_height=frame_h,
                    selected_detection=DetectedObjectInfo(
                        track_id=track.track_id,
                        track_code=format_track_code(track.track_id),
                        class_id=track.class_id,
                        class_name=track.class_name,
                        confidence=pt.confidence,
                        bbox=pt.bbox,
                    ),
                    center_x=pt.center_x,
                    center_y=pt.center_y,
                    position_delta_x=dx,
                    position_delta_y=dy,
                    other_detections=[],
                )
            )

    return observations


def _compute_movement_history(
    track: TrackSummaryInfo,
    frame_width: int | None,
    frame_height: int | None,
) -> TrackMovementHistory:
    pts = sorted(track.timeline_points, key=lambda p: (p.frame_index, p.timestamp_seconds))
    if len(pts) < 2:
        return TrackMovementHistory(
            total_path_distance_px=0.0,
            net_displacement_px=0.0,
            net_displacement_norm=0.0 if (frame_width and frame_height) else None,
            dominant_direction="single observation" if len(pts) == 1 else "unavailable",
            steps=[],
        )

    steps: list[TrackMovementStep] = []
    total_dist_px = 0.0

    for prev_pt, curr_pt in zip(pts, pts[1:]):
        dx = round(curr_pt.center_x - prev_pt.center_x, 2)
        dy = round(curr_pt.center_y - prev_pt.center_y, 2)
        dist_px = round(math.hypot(dx, dy), 2)
        total_dist_px += dist_px

        norm_dist: float | None = None
        if frame_width and frame_width > 0 and frame_height and frame_height > 0:
            norm_dist = round(
                math.hypot(dx / frame_width, dy / frame_height),
                4,
            )

        steps.append(
            TrackMovementStep(
                from_frame_index=prev_pt.frame_index,
                to_frame_index=curr_pt.frame_index,
                from_timestamp=prev_pt.timestamp_seconds,
                to_timestamp=curr_pt.timestamp_seconds,
                from_center_x=prev_pt.center_x,
                from_center_y=prev_pt.center_y,
                to_center_x=curr_pt.center_x,
                to_center_y=curr_pt.center_y,
                delta_x=dx,
                delta_y=dy,
                displacement_px=dist_px,
                displacement_norm=norm_dist,
                direction=_describe_step_direction(dx, dy, dist_px, norm_dist),
            )
        )

    net_dx = pts[-1].center_x - pts[0].center_x
    net_dy = pts[-1].center_y - pts[0].center_y
    net_px = round(math.hypot(net_dx, net_dy), 2)
    net_norm: float | None = None
    if frame_width and frame_width > 0 and frame_height and frame_height > 0:
        net_norm = round(math.hypot(net_dx / frame_width, net_dy / frame_height), 4)

    return TrackMovementHistory(
        total_path_distance_px=round(total_dist_px, 2),
        net_displacement_px=net_px,
        net_displacement_norm=net_norm,
        dominant_direction=_describe_step_direction(net_dx, net_dy, net_px, net_norm),
        steps=steps,
    )


def get_track_detail_payload(
    *,
    analysis: Analysis,
    track_id: int,
    db: Session,
    api_prefix: str,
) -> TrackDetailResponse:
    """Assemble full detail payload (movement, positions, frames, events) for an owned track."""
    settings = get_settings()
    analysis_dir = settings.resolved_processed_dir / analysis.id
    frame_w, frame_h = _resolve_frame_dimensions(analysis_dir)

    _, tracks = load_enriched_tracks_data(analysis.id, db=db)
    target = next((t for t in tracks if t.track_id == track_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track #{track_id} was not found for this analysis.",
        )

    observations = build_track_observation_frames(
        analysis=analysis,
        track=target,
        api_prefix=api_prefix,
    )
    movement_history = _compute_movement_history(target, frame_w, frame_h)

    all_events = (
        db.query(Event)
        .filter(Event.analysis_id == analysis.id)
        .order_by(Event.start_timestamp.asc(), Event.end_timestamp.asc())
        .all()
    )
    related_events = [
        TrackRelatedEventInfo(
            id=ev.id,
            event_type=ev.event_type,
            category=ev.category,
            title=ev.title,
            description=ev.description,
            start_timestamp=ev.start_timestamp,
            end_timestamp=ev.end_timestamp,
            severity=ev.severity,
            confidence=ev.confidence,
            involved_track_ids=[int(t) for t in (ev.involved_track_ids or [])],
        )
        for ev in all_events
        if track_id in [int(t) for t in (ev.involved_track_ids or [])]
    ]

    return TrackDetailResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        track_code=format_track_code(track_id),
        temporary_id_notice=TEMPORARY_ID_NOTICE,
        frame_width=frame_w,
        frame_height=frame_h,
        track=target,
        last_known_position=target.last_known_position,
        movement_history=movement_history,
        related_events=related_events,
        frames=observations,
    )


def get_track_frames_payload(
    *,
    analysis: Analysis,
    track_id: int,
    db: Session,
    api_prefix: str,
) -> TrackFramesResponse:
    """Return all available observation frames containing the specified track ID."""
    _, tracks = load_enriched_tracks_data(analysis.id, db=db)
    target = next((t for t in tracks if t.track_id == track_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track #{track_id} was not found for this analysis.",
        )

    observations = build_track_observation_frames(
        analysis=analysis,
        track=target,
        api_prefix=api_prefix,
    )
    return TrackFramesResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        track_id=target.track_id,
        track_code=format_track_code(target.track_id),
        class_name=target.class_name,
        total_observations=len(observations),
        frames=observations,
    )
