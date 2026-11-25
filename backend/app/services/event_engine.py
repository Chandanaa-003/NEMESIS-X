from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import uuid

from app.services.anomaly_engine import analyze_anomalies, compute_explainable_anomaly_score
from app.services.interaction_engine import (
    InteractionConfig,
    SessionTemporalMemory,
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
    memory: SessionTemporalMemory | None = None,
    session_timestamp_utc: datetime | None = None,
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
        memory=memory,
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
        person_track_id: int | None = None,
        object_track_id: int | None = None,
        association_uncertainty: str | None = None,
        anomaly_score: dict[str, Any] | None = None,
    ) -> DiscoveredEventDraft:
        selected_frames = _select_evidence_frames(frame_ids)
        evidence_timestamps = [
            round(frame_ts_map.get(fid, start_ts), 3) for fid in selected_frames
        ]
        payload: dict[str, Any] = {
            "observed_sequence": observed_sequence,
            "why_flagged": why_flagged,
            "evidence_timestamps": evidence_timestamps,
            "confidence_note": (
                "Combined rule-based temporal confidence and YOLO/ByteTrack observation "
                "confidence. Visual inference only; human verification recommended."
            ),
            "requires_human_review": requires_human_review,
        }
        if person_track_id is not None:
            payload["person_track_id"] = person_track_id
        if object_track_id is not None:
            payload["object_track_id"] = object_track_id
        if association_uncertainty is not None:
            payload["association_uncertainty"] = association_uncertainty
        if anomaly_score is not None:
            payload["anomaly_score"] = anomaly_score

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
            explanation_payload=payload,
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
                        object_track_id=prof.track_id,
                        anomaly_score=compute_explainable_anomaly_score(
                            duration_factor=min(
                                1.0,
                                prof.duration_seconds / max(cfg.stationary_min_seconds * 2.0, 0.1),
                            ),
                            association_conf=prof.avg_confidence,
                            explanation=(
                                "Weighted rule score: duration 15%, interaction sequence 25%, "
                                "movement change 25%, repeated behavior 15%, configured zone 20%. "
                                "This rule contributes duration evidence only."
                            ),
                        ).to_dict(),
                    )
                )

    # Rule: prolonged stationary interval followed by sudden movement
    for prof in interactions.track_profiles.values():
        if prof.class_name != "person":
            continue
        points = sorted(prof.points_by_frame.values(), key=lambda point: point.timestamp_seconds)
        stationary_start = 0
        pending_stationary: tuple[int, int, float] | None = None
        for burst_index in range(1, len(points)):
            burst = points[burst_index]
            if pending_stationary is not None:
                pending_end = points[pending_stationary[1]]
                if burst.timestamp_seconds - pending_end.timestamp_seconds > cfg.burst_window_seconds:
                    pending_stationary = None

            anchor = points[stationary_start]
            displacement = math.hypot(burst.norm_x - anchor.norm_x, burst.norm_y - anchor.norm_y)
            if displacement > cfg.stationary_displacement_norm:
                stationary_end = burst_index - 1
                stationary_duration = (
                    points[stationary_end].timestamp_seconds - anchor.timestamp_seconds
                )
                if stationary_duration >= cfg.prolonged_person_stationary_seconds:
                    pending_stationary = (
                        stationary_start,
                        stationary_end,
                        stationary_duration,
                    )
                stationary_start = burst_index

            has_sudden_movement = (
                burst.speed >= cfg.running_speed_threshold
                or burst.accel >= cfg.sudden_accel_threshold
            )
            if (
                pending_stationary is None
                or burst_index <= pending_stationary[1]
                or not has_sudden_movement
            ):
                continue

            stationary_start, stationary_end, stationary_duration = pending_stationary
            anchor = points[stationary_start]
            prior_moving = next(
                (point for point in reversed(points[:stationary_start]) if point.speed > 0.03),
                None,
            )
            direction_changed = False
            if prior_moving is not None and burst.speed > 0.03:
                prior_mag = math.hypot(prior_moving.vx, prior_moving.vy)
                burst_mag = math.hypot(burst.vx, burst.vy)
                if prior_mag > 0 and burst_mag > 0:
                    cosine = (
                        prior_moving.vx * burst.vx + prior_moving.vy * burst.vy
                    ) / (prior_mag * burst_mag)
                    direction_changed = cosine <= cfg.direction_reversal_cos_threshold

            actions = [
                (
                    f"Person P{prof.track_id:03d} stayed within "
                    f"{cfg.stationary_displacement_norm:.3f} normalized image units for "
                    f"{stationary_duration:.1f}s."
                ),
                (
                    f"At {burst.timestamp_seconds:.1f}s, movement reached "
                    f"{burst.speed:.3f} normalized image units/s with acceleration "
                    f"{burst.accel:.3f} normalized image units/s²."
                ),
            ]
            if direction_changed:
                actions.append("The post-stationary direction opposed the prior moving direction.")

            score = compute_explainable_anomaly_score(
                duration_factor=min(
                    1.0,
                    stationary_duration / max(cfg.prolonged_person_stationary_seconds * 2.0, 0.1),
                ),
                movement_factor=min(
                    1.0,
                    max(
                        burst.speed / max(cfg.running_speed_threshold, 0.01),
                        burst.accel / max(cfg.sudden_accel_threshold, 0.01),
                    ),
                ),
                association_conf=prof.avg_confidence,
                explanation=(
                    "Weighted rule score: duration 15%, interaction sequence 25%, "
                    "movement change 25%, repeated behavior 15%, configured zone 20%. "
                    "This rule contributes stationary-duration and post-stationary motion evidence."
                ),
            )
            discovered.append(
                build_event(
                    event_type="stationary_then_sudden_movement",
                    category="people_movement",
                    title=f"Stationary period followed by sudden movement (P{prof.track_id:03d})",
                    description=(
                        f"Person P{prof.track_id:03d} remained within a small image-plane area, then "
                        f"accelerated or moved rapidly at {burst.timestamp_seconds:.1f}s."
                    ),
                    start_ts=anchor.timestamp_seconds,
                    end_ts=burst.timestamp_seconds,
                    track_ids=[prof.track_id],
                    confidence=prof.avg_confidence * 0.88,
                    severity="medium",
                    frame_ids=[
                        anchor.frame_index,
                        points[stationary_end].frame_index,
                        burst.frame_index,
                    ],
                    observed_sequence=actions,
                    why_flagged=(
                        "A configured prolonged-stationary interval was followed by rapid image-plane "
                        "movement or a sudden acceleration. This is a movement pattern, not evidence "
                        "of intent."
                    ),
                    requires_human_review=True,
                    person_track_id=prof.track_id,
                    anomaly_score=score.to_dict(),
                )
            )
            break

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
                    person_track_id=inter.person_track_id,
                    object_track_id=inter.object_track_id,
                    anomaly_score=compute_explainable_anomaly_score(
                        duration_factor=min(
                            1.0,
                            remaining_after_depart / max(cfg.unattended_min_seconds * 2.0, 0.1),
                        ),
                        interaction_factor=0.6,
                        association_conf=pair_conf,
                        explanation=(
                            "Weighted rule score: duration 15%, interaction sequence 25%, "
                            "movement change 25%, repeated behavior 15%, configured zone 20%. "
                            "This rule contributes duration and interaction evidence only."
                        ),
                    ).to_dict(),
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
                    person_track_id=inter.person_track_id,
                    object_track_id=inter.object_track_id,
                    anomaly_score=compute_explainable_anomaly_score(
                        interaction_factor=0.5,
                        repeated_factor=min(1.0, len(inter.proximity_visit_windows) / 4.0),
                        association_conf=pair_conf,
                        explanation=(
                            "Weighted rule score: duration 15%, interaction sequence 25%, "
                            "movement change 25%, repeated behavior 15%, configured zone 20%. "
                            "Repeated proximity contributes interaction and repeat-count evidence."
                        ),
                    ).to_dict(),
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

    # Rule 10: Possible Object Pickup & Possible Object Placement
    multi_assoc_by_obj = {m.object_track_id: m for m in interactions.multi_person_object_associations}
    for inter in interactions.person_object_interactions:
        p_code = f"P{inter.person_track_id:03d}"
        o_code = f"O{inter.object_track_id:03d}"
        p_prof = interactions.track_profiles[inter.person_track_id]
        o_prof = interactions.track_profiles[inter.object_track_id]
        obj_label = inter.object_class_name
        pair_conf = (p_prof.avg_confidence + o_prof.avg_confidence) / 2.0

        multi_info = multi_assoc_by_obj.get(inter.object_track_id)
        uncertainty = "low"
        if multi_info is not None:
            uncertainty = multi_info.association_uncertainty
            # Only attribute pickup to primary person if identified, or mark uncertain
            if multi_info.primary_person_id is not None and multi_info.primary_person_id != inter.person_track_id:
                continue

        if inter.is_possible_pickup and inter.pickup_window is not None:
            f_s, f_e, ts_s, ts_e = inter.pickup_window
            seq = [
                f"Person {p_code} approached {obj_label} {o_code} around {_fmt_hms(ts_s)}.",
                f"Possible interaction observed at {_fmt_hms(inter.min_distance_timestamp)} (min distance {inter.min_distance_norm:.2f}).",
                f"{obj_label.capitalize()} {o_code} displaced by {inter.object_displacement_norm:.2f} normalized units.",
                f"{obj_label.capitalize()} {o_code} moved consistently with {p_code} across {len(inter.co_movement_frames)} frames (score {inter.co_movement_score:.2f}).",
            ]
            discovered.append(
                build_event(
                    event_type="possible_object_pickup",
                    category="object_interactions",
                    title=f"Possible pickup: {p_code} & {obj_label} {o_code}",
                    description=(
                        f"Possible pickup: {p_code} appears to interact with and move {obj_label} {o_code} "
                        f"between {_fmt_hms(ts_s)} and {_fmt_hms(ts_e)}."
                    ),
                    start_ts=ts_s,
                    end_ts=ts_e,
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * (0.75 + 0.2 * inter.co_movement_score),
                    severity="high",
                    frame_ids=[f_s, inter.min_distance_frame, f_e] + inter.co_movement_frames[:2],
                    observed_sequence=seq,
                    why_flagged=(
                        "Object pickup heuristic triggered: person approached object, followed by object "
                        "displacement aligned with person trajectory."
                    ),
                    requires_human_review=True,
                    person_track_id=inter.person_track_id,
                    object_track_id=inter.object_track_id,
                    association_uncertainty=uncertainty,
                    anomaly_score=compute_explainable_anomaly_score(
                        movement_factor=0.4,
                        interaction_factor=0.8,
                        association_conf=pair_conf,
                        explanation=(
                            "Weighted rule score: duration 15%, interaction sequence 25%, "
                            "movement change 25%, repeated behavior 15%, configured zone 20%. "
                            "Possible pickup contributes co-movement and proximity evidence."
                        ),
                    ).to_dict(),
                )
            )

        if inter.is_possible_placement and inter.placement_window is not None:
            f_s, f_e, ts_s, ts_e = inter.placement_window
            seq = [
                f"Person {p_code} and {obj_label} {o_code} co-located at {_fmt_hms(ts_s)}.",
                f"Person {p_code} separated from {obj_label} {o_code}.",
                f"{obj_label.capitalize()} {o_code} remained stationary until {_fmt_hms(ts_e)}.",
            ]
            discovered.append(
                build_event(
                    event_type="possible_object_placement",
                    category="object_interactions",
                    title=f"Possible placement: {p_code} & {obj_label} {o_code}",
                    description=(
                        f"Possible object placement: {p_code} separated from {obj_label} {o_code}, "
                        f"which remained stationary from {_fmt_hms(ts_s)} to {_fmt_hms(ts_e)}."
                    ),
                    start_ts=ts_s,
                    end_ts=ts_e,
                    track_ids=[inter.person_track_id, inter.object_track_id],
                    confidence=pair_conf * 0.85,
                    severity="medium",
                    frame_ids=[f_s, f_e],
                    observed_sequence=seq,
                    why_flagged=(
                        "Object placement heuristic triggered: object remained stationary after nearby person departed."
                    ),
                    requires_human_review=False,
                    person_track_id=inter.person_track_id,
                    object_track_id=inter.object_track_id,
                    association_uncertainty=uncertainty,
                )
            )

    # Rule 11: Multi-person object association
    for ma in interactions.multi_person_object_associations:
        o_code = f"O{ma.object_track_id:03d}"
        cand_codes = [f"P{p:03d}" for p in ma.candidate_person_ids]
        discovered.append(
            build_event(
                event_type="multi_person_object_interaction",
                category="object_interactions",
                title=f"Multiple people near {ma.object_class_name} {o_code}",
                description=ma.reason,
                start_ts=ma.start_timestamp,
                end_ts=ma.end_timestamp,
                track_ids=ma.candidate_person_ids + [ma.object_track_id],
                confidence=0.80 if ma.association_uncertainty != "high" else 0.60,
                severity="medium",
                frame_ids=ma.frame_ids,
                observed_sequence=[
                    f"Candidates {', '.join(cand_codes)} entered proximity of {ma.object_class_name} {o_code}.",
                    ma.reason,
                ],
                why_flagged=(
                    "Multi-person object association rule triggered: multiple distinct person tracks approached the same object."
                ),
                requires_human_review=ma.association_uncertainty == "high",
                person_track_id=ma.primary_person_id,
                object_track_id=ma.object_track_id,
                association_uncertainty=ma.association_uncertainty,
                anomaly_score=compute_explainable_anomaly_score(
                    interaction_factor=0.5,
                    repeated_factor=min(1.0, len(ma.candidate_person_ids) / 4.0),
                    association_conf=0.8 if ma.association_uncertainty != "high" else 0.6,
                    explanation=(
                        "Weighted rule score: duration 15%, interaction sequence 25%, "
                        "movement change 25%, repeated behavior 15%, configured zone 20%. "
                        "This rule contributes shared-object interaction and candidate-count evidence."
                    ),
                ).to_dict(),
            )
        )

    # Rule 12: Occlusion & Track ID Switching awareness
    for sw in interactions.possible_id_switches:
        discovered.append(
            build_event(
                event_type="occlusion_id_switch",
                category="other_activities",
                title=f"Possible occlusion/ID switch ({sw.class_name} T{sw.prev_track_id:03d} → T{sw.next_track_id:03d})",
                description=(
                    f"Track T{sw.prev_track_id:03d} ({sw.class_name}) ended at {_fmt_hms(sw.prev_end_timestamp)} and "
                    f"T{sw.next_track_id:03d} appeared {sw.gap_frames} frame(s) later within {sw.spatial_distance_norm:.2f} norm distance."
                ),
                start_ts=sw.prev_end_timestamp,
                end_ts=sw.next_start_timestamp,
                track_ids=[sw.prev_track_id, sw.next_track_id],
                confidence=0.68,
                severity="low",
                frame_ids=[min_f, max_f],
                observed_sequence=[
                    f"Track T{sw.prev_track_id:03d} last seen at {_fmt_hms(sw.prev_end_timestamp)}.",
                    f"Track T{sw.next_track_id:03d} appeared at {_fmt_hms(sw.next_start_timestamp)} nearby (dist {sw.spatial_distance_norm:.2f}).",
                ],
                why_flagged="Short temporal gap and spatial proximity suggest possible occlusion or tracker ID switch.",
                requires_human_review=False,
                association_uncertainty="high",
            )
        )

    # Rule 13: Configurable Anomaly Engine + Explainable Scoring
    anomalies = analyze_anomalies(
        interactions=interactions,
        config=cfg,
        memory=memory,
        session_timestamp_utc=session_timestamp_utc,
    )
    for anom in anomalies:
        discovered.append(
            build_event(
                event_type=anom.event_type,
                category=anom.category,
                title=anom.title,
                description=anom.description,
                start_ts=anom.start_timestamp,
                end_ts=anom.end_timestamp,
                track_ids=anom.involved_track_ids,
                confidence=anom.confidence,
                severity=anom.severity,
                frame_ids=anom.frame_ids,
                observed_sequence=anom.observed_actions,
                why_flagged=anom.inference_explanation,
                requires_human_review=anom.requires_human_review,
                person_track_id=anom.person_track_id,
                object_track_id=anom.object_track_id,
                association_uncertainty=anom.association_uncertainty,
                anomaly_score=anom.score_breakdown.to_dict(),
            )
        )

    discovered.sort(key=lambda evt: (evt.start_timestamp, evt.end_timestamp, evt.event_type))

    if memory is not None:
        memory.previous_event_sequences = [
            {
                "event_type": e.event_type,
                "start_timestamp": e.start_timestamp,
                "end_timestamp": e.end_timestamp,
                "track_ids": e.involved_track_ids,
            }
            for e in discovered
        ]

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
