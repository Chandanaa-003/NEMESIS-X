from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any
import uuid

import cv2
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.evidence import Evidence


def _safe_relative_evidence_path(absolute_path: Path) -> str:
    project_root = BACKEND_DIR.parent
    try:
        return absolute_path.relative_to(project_root).as_posix()
    except ValueError:
        return absolute_path.as_posix()


def _draw_detection_annotations(
    frame_img,
    detections: list[dict[str, Any]],
    timestamp_seconds: float,
):
    """Draw detection bounding boxes, class names, confidence, and timestamp."""
    canvas = frame_img.copy()
    for det in detections:
        bbox = det.get("bbox", {})
        x1 = int(round(float(bbox.get("x1", 0))))
        y1 = int(round(float(bbox.get("y1", 0))))
        x2 = int(round(float(bbox.get("x2", 0))))
        y2 = int(round(float(bbox.get("y2", 0))))
        cls_name = str(det.get("class_name", "object"))
        conf = float(det.get("confidence", 0.0))

        # BGR colors: primary blue (#2563EB -> 235,99,37) for person, violet (#7C3AED -> 237,58,124) for others
        color = (235, 99, 37) if cls_name == "person" else (237, 58, 124)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f"{cls_name} {int(round(conf * 100))}%"
        label_y = max(18, y1 - 6)
        cv2.putText(
            canvas,
            label,
            (x1, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )

    cv2.rectangle(canvas, (8, 8), (220, 32), (255, 255, 255), -1)
    cv2.putText(
        canvas,
        f"DETECTIONS | t={timestamp_seconds:.2f}s",
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (17, 24, 39),
        1,
        cv2.LINE_AA,
    )
    return canvas


def _draw_tracking_annotations(
    frame_img,
    detections: list[dict[str, Any]],
    tracks_by_id: dict[int, dict[str, Any]],
    involved_track_ids: list[int],
    frame_idx: int,
    timestamp_seconds: float,
):
    """Draw persistent tracking IDs and trajectory trails up to frame_idx."""
    canvas = frame_img.copy()
    involved_set = set(involved_track_ids)

    # Draw trajectory polylines for involved tracks up to current frame
    for tid in involved_track_ids:
        track_info = tracks_by_id.get(tid)
        if not track_info:
            continue
        pts = [
            (int(round(float(pt["center_x"]))), int(round(float(pt["center_y"]))))
            for pt in track_info.get("timeline_points", [])
            if int(pt["frame_index"]) <= frame_idx
        ]
        for i in range(1, len(pts)):
            cv2.line(canvas, pts[i - 1], pts[i], (237, 58, 124), 2, cv2.LINE_AA)
        if pts:
            cv2.circle(canvas, pts[-1], 4, (37, 99, 235), -1)

    for det in detections:
        raw_tid = det.get("track_id")
        if raw_tid is None:
            continue
        tid = int(raw_tid)
        bbox = det.get("bbox", {})
        x1 = int(round(float(bbox.get("x1", 0))))
        y1 = int(round(float(bbox.get("y1", 0))))
        x2 = int(round(float(bbox.get("x2", 0))))
        y2 = int(round(float(bbox.get("y2", 0))))
        cls_name = str(det.get("class_name", "object"))
        is_involved = tid in involved_set
        color = (37, 99, 235) if is_involved else (100, 116, 139)
        thickness = 3 if is_involved else 1

        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        label = f"T{tid:03d} {cls_name}"
        label_y = max(18, y1 - 6)
        cv2.putText(
            canvas,
            label,
            (x1, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2 if is_involved else 1,
            cv2.LINE_AA,
        )

    cv2.rectangle(canvas, (8, 8), (228, 32), (255, 255, 255), -1)
    cv2.putText(
        canvas,
        f"TRACKING | t={timestamp_seconds:.2f}s",
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (17, 24, 39),
        1,
        cv2.LINE_AA,
    )
    return canvas


def collect_evidence_for_analysis(
    *,
    analysis: Analysis,
    events: list[Event],
    db: Session,
) -> list[Evidence]:
    """Generate and persist immutable evidence artifacts for all discovered events."""
    settings = get_settings()
    processed_dir = settings.resolved_processed_dir / analysis.id
    evidence_root = settings.resolved_evidence_dir / analysis.id

    # Clean up prior evidence records and files for this analysis before regenerating
    db.query(Evidence).filter(Evidence.analysis_id == analysis.id).delete()
    if evidence_root.exists():
        shutil.rmtree(evidence_root, ignore_errors=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    if not events:
        return []

    metadata_path = processed_dir / "metadata.json"
    detections_path = processed_dir / "detections.json"
    tracks_path = processed_dir / "tracks.json"

    frame_meta_map: dict[int, dict[str, Any]] = {}
    if metadata_path.exists():
        raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        for item in raw_meta.get("frames", []):
            frame_meta_map[int(item["frame_index"])] = item

    detections_by_frame: dict[int, list[dict[str, Any]]] = {}
    if detections_path.exists():
        raw_det = json.loads(detections_path.read_text(encoding="utf-8"))
        for item in raw_det.get("frames", []):
            detections_by_frame[int(item["frame_index"])] = list(item.get("detections", []))

    tracks_by_id: dict[int, dict[str, Any]] = {}
    if tracks_path.exists():
        raw_tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
        for item in raw_tracks.get("tracks", []):
            tracks_by_id[int(item["track_id"])] = item

    frames_dir = (processed_dir / "frames").resolve()
    created_records: list[Evidence] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for event in events:
        event_dir = (evidence_root / event.id).resolve()
        event_dir.mkdir(parents=True, exist_ok=True)

        involved_ids = [int(t) for t in (event.involved_track_ids or [])]
        manifest_items: list[dict[str, Any]] = []

        for f_idx in [int(x) for x in (event.evidence_frame_ids or [])]:
            frame_info = frame_meta_map.get(f_idx)
            if not frame_info:
                continue

            filename = Path(str(frame_info["filename"])).name
            source_frame_path = (frames_dir / filename).resolve()
            if source_frame_path.parent != frames_dir or not source_frame_path.exists():
                continue

            timestamp_sec = float(frame_info["timestamp_seconds"])
            frame_detections = detections_by_frame.get(f_idx, [])
            det_summary = [
                f"{d.get('class_name', 'object')} ({int(round(float(d.get('confidence', 0.0)) * 100))}%)"
                for d in frame_detections[:6]
            ]
            base_meta = {
                "event_title": event.title,
                "event_category": event.category,
                "event_severity": event.severity,
                "event_confidence": event.confidence,
                "why_flagged": (event.explanation_payload or {}).get("why_flagged", ""),
                "involved_track_ids": involved_ids,
                "detection_count": len(frame_detections),
                "detection_summary": det_summary,
                "evidence_created_at": now_iso,
            }

            # 1. Preserve an untouched copy of the extracted original frame
            orig_name = f"{uuid.uuid4().hex[:10]}_f{f_idx:04d}_original.jpg"
            orig_dest = (event_dir / orig_name).resolve()
            shutil.copy2(source_frame_path, orig_dest)
            orig_rel = _safe_relative_evidence_path(orig_dest)

            created_records.append(
                Evidence(
                    event_id=event.id,
                    analysis_id=analysis.id,
                    user_id=analysis.user_id,
                    frame_number=f_idx,
                    timestamp_seconds=timestamp_sec,
                    evidence_type="original_frame",
                    file_path=orig_rel,
                    description=f"Original extracted frame #{f_idx} at {timestamp_sec:.2f}s for {event.title}.",
                    metadata_json=base_meta,
                )
            )
            manifest_items.append(
                {
                    "evidence_type": "original_frame",
                    "frame_number": f_idx,
                    "timestamp_seconds": timestamp_sec,
                    "filename": orig_name,
                }
            )

            frame_mat = cv2.imread(str(source_frame_path))
            if frame_mat is None:
                continue

            try:
                # 2. Annotated detection frame
                det_canvas = _draw_detection_annotations(frame_mat, frame_detections, timestamp_sec)
                det_name = f"{uuid.uuid4().hex[:10]}_f{f_idx:04d}_detection.jpg"
                det_dest = (event_dir / det_name).resolve()
                if cv2.imwrite(str(det_dest), det_canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
                    created_records.append(
                        Evidence(
                            event_id=event.id,
                            analysis_id=analysis.id,
                            user_id=analysis.user_id,
                            frame_number=f_idx,
                            timestamp_seconds=timestamp_sec,
                            evidence_type="annotated_detection",
                            file_path=_safe_relative_evidence_path(det_dest),
                            description=(
                                f"Annotated object detection frame #{f_idx} at {timestamp_sec:.2f}s "
                                f"({len(frame_detections)} detections)."
                            ),
                            metadata_json=base_meta,
                        )
                    )
                    manifest_items.append(
                        {
                            "evidence_type": "annotated_detection",
                            "frame_number": f_idx,
                            "timestamp_seconds": timestamp_sec,
                            "filename": det_name,
                        }
                    )

                # 3. Annotated tracking frame (when tracking IDs exist)
                has_track_ids = any(d.get("track_id") is not None for d in frame_detections)
                if has_track_ids or involved_ids:
                    trk_canvas = _draw_tracking_annotations(
                        frame_mat,
                        frame_detections,
                        tracks_by_id,
                        involved_ids,
                        f_idx,
                        timestamp_sec,
                    )
                    trk_name = f"{uuid.uuid4().hex[:10]}_f{f_idx:04d}_tracking.jpg"
                    trk_dest = (event_dir / trk_name).resolve()
                    if cv2.imwrite(str(trk_dest), trk_canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
                        created_records.append(
                            Evidence(
                                event_id=event.id,
                                analysis_id=analysis.id,
                                user_id=analysis.user_id,
                                frame_number=f_idx,
                                timestamp_seconds=timestamp_sec,
                                evidence_type="annotated_tracking",
                                file_path=_safe_relative_evidence_path(trk_dest),
                                description=(
                                    f"Annotated tracking frame #{f_idx} at {timestamp_sec:.2f}s "
                                    f"highlighting tracks {', '.join(f'T{t:03d}' for t in involved_ids) or 'none'}."
                                ),
                                metadata_json=base_meta,
                            )
                        )
                        manifest_items.append(
                            {
                                "evidence_type": "annotated_tracking",
                                "frame_number": f_idx,
                                "timestamp_seconds": timestamp_sec,
                                "filename": trk_name,
                            }
                        )
            finally:
                del frame_mat

        manifest_path = event_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "event_id": event.id,
                    "analysis_id": analysis.id,
                    "title": event.title,
                    "description": event.description,
                    "start_timestamp": event.start_timestamp,
                    "end_timestamp": event.end_timestamp,
                    "involved_track_ids": involved_ids,
                    "evidence_created_at": now_iso,
                    "artifacts": manifest_items,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if created_records:
        db.add_all(created_records)
    return created_records
