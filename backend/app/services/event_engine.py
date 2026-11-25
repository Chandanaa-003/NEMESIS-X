from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import uuid

from app.services.interaction_engine import (
    InteractionConfig,
    analyze_track_interactions,
)


@dataclass(frozen=True)
class DiscoveredEventDraft:
    """In-memory discovered event ready to persist to SQLite and JSON."""

    id: str
    event_type: str
    category: str
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int]
    confidence: float
    severity: str
    evidence_frame_ids: list[int]
    explanation_payload: dict[str, Any]


@dataclass(frozen=True)
class EventDiscoveryOutput:
    """Complete output of rule-based event discovery for one analysis."""

    total_detected_objects: int
    total_unique_tracks: int
    events: list[DiscoveredEventDraft]
    events_path: Path


def _fmt_track(track_id: int) -> str:
    return f"T{track_id:03d}"


def _fmt_hms(seconds: float) -> str:
    total_sec = max(0, int(round(seconds)))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def _select_evidence_frames(frame_ids: list[int], limit: int = 4) -> list[int]:
    """Deduplicate and pick up to `limit` representative frame indices."""
    unique_sorted = sorted(set(frame_ids))
    if len(unique_sorted) <= limit:
        return unique_sorted
    if limit <= 2:
        return [unique_sorted[0], unique_sorted[-1]]
    step = (len(unique_sorted) - 1) / float(limit - 1)
    picked = [unique_sorted[round(i * step)] for i in range(limit)]
    return sorted(set(picked))


def _clamp_confidence(value: float) -> float:
    return round(min(0.95, max(0.35, value)), 3)


def discover_events_from_data(
    *,
    tracks_data: list[dict[str, Any]],
    frame_ts_map: dict[int, float],
    frame_width: int,
    frame_height: int,
    config: InteractionConfig | None = None,
    exit_grace_frames: int = 0,
) -> list[DiscoveredEventDraft]:
    """Run rule-based event discovery in-memory over normalized tracks and timestamps.

    Shared by both offline video analyses and live webcam monitoring sessions.
    """
    cfg = config or InteractionConfig()
    all_frame_indices = sorted(frame_ts_map.keys())
    if not tracks_data:
        return []

    interactions = analyze_track_interactions(
        tracks_data=tracks_data,
        frame_width=frame_width,
        frame_height=frame_height,
        all_frame_indices=all_frame_indices,
        config=cfg,
    )

    discovered: list[DiscoveredEventDraft] = []
    min_f = interactions.min_frame_index
    max_f = interactions.max_frame_index

    def build_event(
        *,
        event_type: str,
        category: str,
        title: str,
        description: str,
        start_ts: float,
        end_ts: float,
        track_ids: list[int],
        confidence: float,
        severity: str,
        frame_ids: list[int],
        observed_sequence: list[str],
        why_flagged: str,
        requires_human_review: bool,
    ) -> DiscoveredEventDraft:
        selected_frames = _select_evidence_frames(frame_ids)
        evidence_timestamps = [
            round(frame_ts_map.get(fid, start_ts), 3) for fid in selected_frames
        ]
        return DiscoveredEventDraft(
            id=str(uuid.uuid4()),
            event_type=event_type,
            category=category,
            title=title,
            description=description,
            start_timestamp=round(start_ts, 3),
            end_timestamp=round(max(start_ts, end_ts), 3),
            involved_track_ids=sorted(set(track_ids)),
            confidence=_clamp_confidence(confidence),
            severity=severity,
            evidence_frame_ids=selected_frames,
            explanation_payload={
                "observed_sequence": observed_sequence,
                "why_flagged": why_flagged,
                "evidence_timestamps": evidence_timestamps,
                "confidence_note": (
                    "Combined rule-based temporal confidence and YOLO/ByteTrack observation "
                    "confidence. Visual inference only; human verification recommended."
                ),
                "requires_human_review": requires_human_review,
            },
        )

    # Rules 1, 2, 6, 7: Single-track entry, exit, disappearance, extended stationary state
    for prof in interactions.track_profiles.values():
        t_code = _fmt_track(prof.track_id)

        if prof.class_name == "person":
            # 1. Person entering the camera view
            if prof.first_seen_frame > min_f or (
                prof.started_near_edge and prof.frame_count >= 2
            ):
                edge_note = " near the frame boundary" if prof.started_near_edge else ""
                discovered.append(
                    build_event(
                        event_type="person_entering",
                        category="people_movement",
                        title=f"Person {t_code} entered camera view",
                        description=(
                            f"Observed tracked person {t_code} appearing{edge_note} at "
                            f"{_fmt_hms(prof.first_seen_timestamp)} ({prof.direction_label})."
                        ),
                        start_ts=prof.first_seen_timestamp,
                        end_ts=prof.first_seen_timestamp,
                        track_ids=[prof.track_id],
                        confidence=prof.avg_confidence * 0.9,
                        severity="low",
                        frame_ids=[prof.first_seen_frame],
                        observed_sequence=[
                            f"Person {t_code} first appears at {_fmt_hms(prof.first_seen_timestamp)}.",
                            f"Track {t_code} remains visible for {prof.duration_seconds:.1f}s ({prof.direction_label}).",
                        ],
                        why_flagged=(
                            "Track appearance rule triggered because the person track began after "
                            "the initial frame or entered near a frame boundary."
                        ),
                        requires_human_review=False,
                    )
                )

            # 2. Person leaving the camera view
            if prof.last_seen_frame < max_f - exit_grace_frames:
                edge_note = " near the frame boundary" if prof.ended_near_edge else ""
                discovered.append(
                    build_event(
                        event_type="person_leaving",
                        category="people_movement",
                        title=f"Person {t_code} left camera view",
                        description=(
                            f"Observed tracked person {t_code} no longer visible after "
                            f"{_fmt_hms(prof.last_seen_timestamp)}{edge_note}."
                        ),
                        start_ts=prof.last_seen_timestamp,
                        end_ts=prof.last_seen_timestamp,
                        track_ids=[prof.track_id],
                        confidence=prof.avg_confidence * 0.88,
                        severity="low",
                        frame_ids=[prof.last_seen_frame],
                        observed_sequence=[
                            f"Person {t_code} tracked from {_fmt_hms(prof.first_seen_timestamp)}.",
                            f"Person {t_code} last observed at {_fmt_hms(prof.last_seen_timestamp)} ({prof.direction_label}).",
                        ],
                        why_flagged=(
                            "Track exit rule triggered because the person track ended before the "
                            "final sampled frame."
                        ),
                        requires_human_review=False,
                    )
                )
        else:
            obj_label = prof.class_name

            # 6. Object disappearing from view
            if prof.frame_count >= 2 and prof.last_seen_frame < max_f - exit_grace_frames:
                discovered.append(
                    build_event(
                        event_type="object_disappearing",
                        category="other_activities",
                        title=f"Tracked {obj_label} {t_code} disappeared from view",
                        description=(
                            f"Observed {obj_label} {t_code} from {_fmt_hms(prof.first_seen_timestamp)} "
                            f"until {_fmt_hms(prof.last_seen_timestamp)}, after which it was no longer detected. "
                            "Cause cannot be determined from visual tracking alone."
                        ),
                        start_ts=prof.first_seen_timestamp,
                        end_ts=prof.last_seen_timestamp,
                        track_ids=[prof.track_id],
                        confidence=prof.avg_confidence * 0.82,
                        severity="medium",
                        frame_ids=[prof.first_seen_frame, prof.last_seen_frame],
                        observed_sequence=[
                            f"Object ({obj_label}) {t_code} observed starting at {_fmt_hms(prof.first_seen_timestamp)}.",
                            f"Object ({obj_label}) {t_code} last detected at {_fmt_hms(prof.last_seen_timestamp)}.",
                            "No subsequent detections matched this track in remaining frames.",
                        ],
                        why_flagged=(
                            "Object disappearance rule triggered because a multi-frame object track "
                            "ended before the end of the analyzed sequence (may reflect occlusion, "
                            "movement out of frame, or removal)."
                        ),
                        requires_human_review=True,
                    )
                )

            # 7. Object remaining stationary for an extended period
            if (
                prof.is_stationary
                and prof.frame_count >= cfg.stationary_min_frames
                and prof.duration_seconds >= cfg.stationary_min_seconds
            ):
                discovered.append(
                    build_event(
                        event_type="stationary_object_extended",
                        category="other_activities",
                        title=f"Stationary {obj_label} {t_code} observed",
                        description=(
                            f"Observed {obj_label} {t_code} remaining stationary (max normalized "
                            f"shift {prof.max_displacement_norm:.3f}) from "
                            f"{_fmt_hms(prof.first_seen_timestamp)} to {_fmt_hms(prof.last_seen_timestamp)}."
                        ),
                        start_ts=prof.first_seen_timestamp,
                        end_ts=prof.last_seen_timestamp,
                        track_ids=[prof.track_id],
                        confidence=prof.avg_confidence * 0.9,
                        severity="low",
                        frame_ids=[prof.first_seen_frame, prof.last_seen_frame],
                        observed_sequence=[
                            f"Object ({obj_label}) {t_code} first seen at {_fmt_hms(prof.first_seen_timestamp)}.",
                            f"Object ({obj_label}) {t_code} stayed within {prof.max_displacement_norm:.3f} normalized frame units until {_fmt_hms(prof.last_seen_timestamp)}.",
                        ],
                        why_flagged=(
                            f"Extended stationary rule triggered (duration {prof.duration_seconds:.1f}s "
                            f">= {cfg.stationary_min_seconds:.1f}s threshold)."
                        ),
                        requires_human_review=False,
                    )
                )

    # Rules 3, 4, 5, 8: Person-object proximity & interaction rules
    for inter in interactions.person_object_interactions:
        p_code = _fmt_track(inter.person_track_id)
        o_code = _fmt_track(inter.object_track_id)
        p_prof = interactions.track_profiles[inter.person_track_id]
        o_prof = interactions.track_profiles[inter.object_track_id]
        obj_label = inter.object_class_name
        pair_conf = (p_prof.avg_confidence + o_prof.avg_confidence) / 2.0

        # 3. Person approaching an object
        if inter.approach_window is not None:
            f_start, f_end, ts_start, ts_end, d_start, d_end = inter.approach_window
            discovered.append(
                build_event(
                    event_type="person_approaching_object",
                    category="object_interactions",
                    title=f"Person {p_code} approached {obj_label} {o_code}",
                    description=(
                        f"Observed person {p_code} moving closer to {obj_label} {o_code} between "
                        f"{_fmt_hms(ts_start)} and {_fmt_hms(ts_end)} (normalized center distance "
                        f"decreased from {d_start:.2f} to {d_end:.2f})."
                    ),
                    start_ts=ts_start,
                    end_ts=ts_end,
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * 0.88,
                    severity="low",
                    frame_ids=[f_start, f_end],
                    observed_sequence=[
                        f"Person {p_code} and {obj_label} {o_code} co-observed at {_fmt_hms(ts_start)} (normalized distance {d_start:.2f}).",
                        f"Person {p_code} moved closer to {obj_label} {o_code} by {_fmt_hms(ts_end)} (normalized distance {d_end:.2f}).",
                    ],
                    why_flagged=(
                        "Proximity approach rule triggered because normalized image-plane distance "
                        "decreased into the configured proximity threshold."
                    ),
                    requires_human_review=False,
                )
            )

        # 4. Person moving away from an object
        if inter.departure_window is not None:
            f_start, f_end, ts_start, ts_end, d_start, d_end = inter.departure_window
            discovered.append(
                build_event(
                    event_type="person_moving_away_from_object",
                    category="object_interactions",
                    title=f"Person {p_code} moved away from {obj_label} {o_code}",
                    description=(
                        f"Observed person {p_code} separating from {obj_label} {o_code} between "
                        f"{_fmt_hms(ts_start)} and {_fmt_hms(ts_end)} (normalized center distance "
                        f"increased from {d_start:.2f} to {d_end:.2f})."
                    ),
                    start_ts=ts_start,
                    end_ts=ts_end,
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * 0.88,
                    severity="low",
                    frame_ids=[f_start, f_end],
                    observed_sequence=[
                        f"Person {p_code} was in proximity of {obj_label} {o_code} at {_fmt_hms(ts_start)} (normalized distance {d_start:.2f}).",
                        f"Person {p_code} moved away by {_fmt_hms(ts_end)} (normalized distance {d_end:.2f}).",
                    ],
                    why_flagged=(
                        "Proximity separation rule triggered because normalized distance increased "
                        "significantly after close co-presence."
                    ),
                    requires_human_review=False,
                )
            )

        # 5. Object placed or possibly left behind (unattended after nearby person departed)
        person_left_object_behind = False
        depart_ts = inter.min_distance_timestamp
        depart_frame = inter.min_distance_frame

        if inter.departure_window is not None:
            person_left_object_behind = True
            depart_frame = inter.departure_window[1]
            depart_ts = inter.departure_window[3]
        elif (
            inter.min_distance_norm <= cfg.proximity_threshold_norm
            and p_prof.last_seen_frame < o_prof.last_seen_frame
        ):
            person_left_object_behind = True
            depart_frame = p_prof.last_seen_frame
            depart_ts = p_prof.last_seen_timestamp

        remaining_after_depart = round(max(0.0, o_prof.last_seen_timestamp - depart_ts), 3)
        remaining_frames = max(0, o_prof.last_seen_frame - depart_frame)

        if (
            person_left_object_behind
            and o_prof.is_stationary
            and (
                remaining_after_depart >= cfg.unattended_min_seconds
                or remaining_frames >= cfg.unattended_min_frames
            )
        ):
            seq_lines = [
                f"Person {p_code} first seen at {_fmt_hms(p_prof.first_seen_timestamp)}.",
            ]
            if inter.approach_window is not None:
                seq_lines.append(
                    f"Person {p_code} approached {obj_label} {o_code} around {_fmt_hms(inter.approach_window[3])}."
                )
            else:
                seq_lines.append(
                    f"Person {p_code} observed near {obj_label} {o_code} at {_fmt_hms(inter.min_distance_timestamp)}."
                )
            seq_lines.append(
                f"Person {p_code} moved away or exited proximity at {_fmt_hms(depart_ts)}."
            )
            seq_lines.append(
                f"Object ({obj_label}) {o_code} remained visible and stationary until {_fmt_hms(o_prof.last_seen_timestamp)}."
            )

            discovered.append(
                build_event(
                    event_type="possible_unattended_object",
                    category="possible_unattended_objects",
                    title="Possible unattended object",
                    description=(
                        f"The system observed {obj_label} {o_code} remaining stationary for "
                        f"{remaining_after_depart:.1f}s after nearby person {p_code} moved away. "
                        "Ownership or intent cannot be inferred visually; this may require human review."
                    ),
                    start_ts=min(p_prof.first_seen_timestamp, inter.min_distance_timestamp),
                    end_ts=o_prof.last_seen_timestamp,
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * 0.84,
                    severity="high",
                    frame_ids=[
                        inter.min_distance_frame,
                        depart_frame,
                        o_prof.last_seen_frame,
                    ],
                    observed_sequence=seq_lines,
                    why_flagged=(
                        "Unattended-object heuristic triggered: a stationary object remained visible "
                        "after a nearby person track separated or left the area. Requires human review."
                    ),
                    requires_human_review=True,
                )
            )

        # 8. Repeated movement near an object
        if len(inter.proximity_visit_windows) >= cfg.repeated_visit_min_cycles:
            first_visit = inter.proximity_visit_windows[0]
            last_visit = inter.proximity_visit_windows[-1]
            visit_frames = [
                w[0] for w in inter.proximity_visit_windows
            ] + [w[1] for w in inter.proximity_visit_windows]

            discovered.append(
                build_event(
                    event_type="repeated_movement_near_object",
                    category="object_interactions",
                    title=f"Repeated movement near {obj_label} {o_code}",
                    description=(
                        f"Observed person {p_code} entering proximity of {obj_label} {o_code} "
                        f"{len(inter.proximity_visit_windows)} separate times between "
                        f"{_fmt_hms(first_visit[2])} and {_fmt_hms(last_visit[3])}."
                    ),
                    start_ts=first_visit[2],
                    end_ts=last_visit[3],
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * 0.85,
                    severity="medium",
                    frame_ids=visit_frames,
                    observed_sequence=[
                        f"Person {p_code} visited proximity of {obj_label} {o_code} {len(inter.proximity_visit_windows)} times.",
                        f"First proximity window: {_fmt_hms(first_visit[2])}–{_fmt_hms(first_visit[3])}.",
                        f"Latest proximity window: {_fmt_hms(last_visit[2])}–{_fmt_hms(last_visit[3])}.",
                    ],
                    why_flagged=(
                        f"Repeated proximity rule triggered ({len(inter.proximity_visit_windows)} "
                        f"distinct visits >= {cfg.repeated_visit_min_cycles})."
                    ),
                    requires_human_review=True,
                )
            )

    # Rule 9: Multiple people interacting in the same area
    for pp in interactions.person_person_interactions:
        code_a = _fmt_track(pp.track_id_a)
        code_b = _fmt_track(pp.track_id_b)
        prof_a = interactions.track_profiles[pp.track_id_a]
        prof_b = interactions.track_profiles[pp.track_id_b]
        avg_conf = (prof_a.avg_confidence + prof_b.avg_confidence) / 2.0

        discovered.append(
            build_event(
                event_type="multiple_people_interacting",
                category="people_movement",
                title=f"Multiple people in shared area ({code_a} & {code_b})",
                description=(
                    f"Observed person {code_a} and person {code_b} within normalized image "
                    f"proximity ({pp.min_distance_norm:.2f}) across "
                    f"{len(pp.shared_proximity_frames)} frames from {_fmt_hms(pp.start_timestamp)} "
                    f"to {_fmt_hms(pp.end_timestamp)}."
                ),
                start_ts=pp.start_timestamp,
                end_ts=pp.end_timestamp,
                track_ids=[pp.track_id_a, pp.track_id_b],
                confidence=avg_conf * 0.87,
                severity="low",
                frame_ids=pp.shared_proximity_frames,
                observed_sequence=[
                    f"Person {code_a} and person {code_b} co-located within normalized distance {pp.min_distance_norm:.2f} at {_fmt_hms(pp.start_timestamp)}.",
                    f"Co-presence continued across {len(pp.shared_proximity_frames)} sampled frames until {_fmt_hms(pp.end_timestamp)}.",
                ],
                why_flagged=(
                    "Multi-person proximity rule triggered based on sustained close normalized "
                    "bounding-box positions in the same region."
                ),
                requires_human_review=False,
            )
        )

    discovered.sort(key=lambda evt: (evt.start_timestamp, evt.end_timestamp, evt.event_type))
    return discovered


def discover_events_for_analysis(
    *,
    analysis_id: str,
    analysis_dir: Path,
    config: InteractionConfig | None = None,
) -> EventDiscoveryOutput:
    """Analyze saved detection and tracking outputs to discover rule-based events."""
    cfg = config or InteractionConfig()

    metadata_path = analysis_dir / "metadata.json"
    detections_path = analysis_dir / "detections.json"
    tracks_path = analysis_dir / "tracks.json"

    if not metadata_path.exists() or not detections_path.exists() or not tracks_path.exists():
        raise FileNotFoundError(
            "Detection and tracking prerequisites (metadata.json, detections.json, tracks.json) "
            "are missing for this analysis. Run video processing before discovering events."
        )

    raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw_det = json.loads(detections_path.read_text(encoding="utf-8"))
    raw_tracks = json.loads(tracks_path.read_text(encoding="utf-8"))

    frame_entries = raw_meta.get("frames", [])
    det_frames = raw_det.get("frames", [])
    tracks_data = raw_tracks.get("tracks", [])

    total_detected_objects = int(raw_det.get("total_detections", 0))
    total_unique_tracks = int(raw_tracks.get("total_tracks", len(tracks_data)))

    frame_ts_map: dict[int, float] = {
        int(item["frame_index"]): float(item["timestamp_seconds"]) for item in frame_entries
    }

    # Resolve frame dimensions matching detections/tracks coordinate space
    frame_width = 640
    frame_height = 360
    if det_frames:
        frame_width = int(det_frames[0].get("frame_width") or 640)
        frame_height = int(det_frames[0].get("frame_height") or 360)
    elif raw_meta.get("original_dimensions"):
        orig_w = int(raw_meta["original_dimensions"].get("width") or 640)
        orig_h = int(raw_meta["original_dimensions"].get("height") or 360)
        max_w = int(raw_meta.get("max_width_applied") or orig_w)
        if orig_w > max_w > 0:
            frame_width = max_w
            frame_height = max(1, round(orig_h * (max_w / float(orig_w))))
        else:
            frame_width, frame_height = orig_w, orig_h

    if total_detected_objects == 0 or total_unique_tracks == 0:
        events_path = analysis_dir / "events.json"
        events_path.write_text(
            json.dumps(
                {
                    "analysis_id": analysis_id,
                    "total_detected_objects": total_detected_objects,
                    "total_unique_tracks": total_unique_tracks,
                    "events": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return EventDiscoveryOutput(
            total_detected_objects=total_detected_objects,
            total_unique_tracks=total_unique_tracks,
            events=[],
            events_path=events_path,
        )

    discovered = discover_events_from_data(
        tracks_data=tracks_data,
        frame_ts_map=frame_ts_map,
        frame_width=frame_width,
        frame_height=frame_height,
        config=cfg,
        exit_grace_frames=0,
    )

    category_counts = Counter(evt.category for evt in discovered)
    events_path = analysis_dir / "events.json"
    events_path.write_text(
        json.dumps(
            {
                "analysis_id": analysis_id,
                "total_detected_objects": total_detected_objects,
                "total_unique_tracks": total_unique_tracks,
                "total_discovered_events": len(discovered),
                "category_counts": dict(category_counts),
                "events": [
                    {
                        "id": evt.id,
                        "event_type": evt.event_type,
                        "category": evt.category,
                        "title": evt.title,
                        "description": evt.description,
                        "start_timestamp": evt.start_timestamp,
                        "end_timestamp": evt.end_timestamp,
                        "involved_track_ids": evt.involved_track_ids,
                        "confidence": evt.confidence,
                        "severity": evt.severity,
                        "evidence_frame_ids": evt.evidence_frame_ids,
                        "explanation": evt.explanation_payload,
                    }
                    for evt in discovered
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return EventDiscoveryOutput(
        total_detected_objects=total_detected_objects,
        total_unique_tracks=total_unique_tracks,
        events=discovered,
        events_path=events_path,
    )
