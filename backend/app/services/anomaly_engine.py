from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.interaction_engine import (
    InteractionAnalysisResult,
    InteractionConfig,
    SessionTemporalMemory,
)


@dataclass(frozen=True)
class AnomalyScoreBreakdown:
    """Explainable rule-based anomaly score decomposition (0.0 to 1.0)."""

    duration_score: float = 0.0
    movement_change_score: float = 0.0
    interaction_sequence_score: float = 0.0
    track_association_confidence: float = 0.0
    repeated_behavior_score: float = 0.0
    zone_rule_score: float = 0.0
    total_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_score": round(self.duration_score, 3),
            "movement_change_score": round(self.movement_change_score, 3),
            "interaction_sequence_score": round(self.interaction_sequence_score, 3),
            "track_association_confidence": round(self.track_association_confidence, 3),
            "repeated_behavior_score": round(self.repeated_behavior_score, 3),
            "zone_rule_score": round(self.zone_rule_score, 3),
            "total_score": round(self.total_score, 3),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class DetectedAnomaly:
    """Structured anomaly finding with explicit observed facts vs rule inference."""

    event_type: str
    category: str
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int]
    person_track_id: int | None
    object_track_id: int | None
    confidence: float
    severity: str
    frame_ids: list[int]
    observed_actions: list[str]
    inference_explanation: str
    association_uncertainty: str
    score_breakdown: AnomalyScoreBreakdown
    requires_human_review: bool


def compute_explainable_anomaly_score(
    *,
    duration_factor: float = 0.0,
    movement_factor: float = 0.0,
    interaction_factor: float = 0.0,
    association_conf: float = 0.8,
    repeated_factor: float = 0.0,
    zone_factor: float = 0.0,
    explanation: str = "",
) -> AnomalyScoreBreakdown:
    """Compute weighted, transparent rule-based anomaly score."""
    total = min(
        1.0,
        max(
            0.0,
            0.15 * duration_factor
            + 0.25 * movement_factor
            + 0.25 * interaction_factor
            + 0.15 * repeated_factor
            + 0.20 * zone_factor,
        ),
    )
    return AnomalyScoreBreakdown(
        duration_score=min(1.0, max(0.0, duration_factor)),
        movement_change_score=min(1.0, max(0.0, movement_factor)),
        interaction_sequence_score=min(1.0, max(0.0, interaction_factor)),
        track_association_confidence=min(1.0, max(0.0, association_conf)),
        repeated_behavior_score=min(1.0, max(0.0, repeated_factor)),
        zone_rule_score=min(1.0, max(0.0, zone_factor)),
        total_score=round(total, 3),
        explanation=explanation,
    )


def analyze_anomalies(
    *,
    interactions: InteractionAnalysisResult,
    config: InteractionConfig,
    memory: SessionTemporalMemory | None = None,
    session_timestamp_utc: datetime | None = None,
) -> list[DetectedAnomaly]:
    """Evaluate movement, interaction, area-based, and temporal anomalies using transparent rules."""
    anomalies: list[DetectedAnomaly] = []

    # A. Movement Anomalies (for person tracks)
    for prof in interactions.track_profiles.values():
        if prof.class_name != "person":
            continue

        p_code = f"P{prof.track_id:03d}"

        # 1. Sudden acceleration or erratic direction reversals
        if prof.max_accel >= config.sudden_accel_threshold or prof.direction_reversals >= config.min_reversals_for_anomaly:
            reasons: list[str] = []
            mov_factor = 0.0
            if prof.max_accel >= config.sudden_accel_threshold:
                reasons.append(f"sudden acceleration ({prof.max_accel:.2f} norm/s²)")
                mov_factor += 0.5
            if prof.direction_reversals >= config.min_reversals_for_anomaly:
                reasons.append(f"{prof.direction_reversals} sharp direction reversals")
                mov_factor += 0.5

            score = compute_explainable_anomaly_score(
                movement_factor=min(1.0, mov_factor),
                association_conf=prof.avg_confidence,
                explanation=f"Rule triggered by {' and '.join(reasons)}.",
            )
            anomalies.append(
                DetectedAnomaly(
                    event_type="movement_anomaly",
                    category="people_movement",
                    title=f"Unusual movement pattern by {p_code}",
                    description=f"Observed {p_code} exhibiting {' and '.join(reasons)}.",
                    start_timestamp=prof.first_seen_timestamp,
                    end_timestamp=prof.last_seen_timestamp,
                    involved_track_ids=[prof.track_id],
                    person_track_id=prof.track_id,
                    object_track_id=None,
                    confidence=round(min(0.92, prof.avg_confidence * 0.9), 3),
                    severity="medium",
                    frame_ids=[prof.first_seen_frame, prof.last_seen_frame],
                    observed_actions=[
                        f"Person {p_code} tracked from {prof.first_seen_timestamp:.1f}s to {prof.last_seen_timestamp:.1f}s.",
                        f"Measured peak acceleration {prof.max_accel:.2f} norm/s² and {prof.direction_reversals} direction reversals.",
                    ],
                    inference_explanation=(
                        f"Movement anomaly rule triggered ({', '.join(reasons)}). "
                        "Rapid velocity changes or pacing do not prove malicious intent; human verification advised."
                    ),
                    association_uncertainty="low",
                    score_breakdown=score,
                    requires_human_review=True,
                )
            )

        # 2. Prolonged stationary person behavior
        if prof.is_stationary and prof.duration_seconds >= config.prolonged_person_stationary_seconds:
            dur_factor = min(1.0, prof.duration_seconds / (config.prolonged_person_stationary_seconds * 2.0))
            score = compute_explainable_anomaly_score(
                duration_factor=dur_factor,
                association_conf=prof.avg_confidence,
                explanation=f"Person remained within {prof.max_displacement_norm:.3f} norm units for {prof.duration_seconds:.1f}s.",
            )
            anomalies.append(
                DetectedAnomaly(
                    event_type="prolonged_stationary_person",
                    category="people_movement",
                    title=f"Prolonged stationary presence ({p_code})",
                    description=(
                        f"Observed {p_code} remaining stationary for {prof.duration_seconds:.1f}s "
                        f"(threshold: {config.prolonged_person_stationary_seconds:.1f}s)."
                    ),
                    start_timestamp=prof.first_seen_timestamp,
                    end_timestamp=prof.last_seen_timestamp,
                    involved_track_ids=[prof.track_id],
                    person_track_id=prof.track_id,
                    object_track_id=None,
                    confidence=round(min(0.90, prof.avg_confidence * 0.88), 3),
                    severity="low",
                    frame_ids=[prof.first_seen_frame, prof.last_seen_frame],
                    observed_actions=[
                        f"Person {p_code} stayed within {prof.max_displacement_norm:.3f} normalized displacement over {prof.duration_seconds:.1f}s."
                    ],
                    inference_explanation=(
                        "Prolonged stationary rule triggered. May reflect waiting, resting, or loitering."
                    ),
                    association_uncertainty="low",
                    score_breakdown=score,
                    requires_human_review=False,
                )
            )

        # C. Area-based anomalies (if restricted zones are configured)
        if config.restricted_zones:
            sorted_pts = sorted(prof.points_by_frame.values(), key=lambda pt: pt.frame_index)
            for zone in config.restricted_zones:
                inside_pts = [pt for pt in sorted_pts if zone.contains(pt.norm_x, pt.norm_y)]
                if not inside_pts:
                    continue

                # Count zone entries
                entries = 0
                was_inside = False
                running_in_zone = False
                for pt in sorted_pts:
                    now_inside = zone.contains(pt.norm_x, pt.norm_y)
                    if now_inside and not was_inside:
                        entries += 1
                    if now_inside and pt.speed >= config.running_speed_threshold:
                        running_in_zone = True
                    was_inside = now_inside

                if memory is not None:
                    memory.area_history.setdefault(prof.track_id, []).append(
                        {"zone": zone.name, "entries": entries, "frames": len(inside_pts)}
                    )

                zone_sev = "high" if (running_in_zone or entries >= 2) else "medium"
                score = compute_explainable_anomaly_score(
                    movement_factor=0.8 if running_in_zone else 0.2,
                    repeated_factor=0.8 if entries >= 2 else 0.0,
                    zone_factor=1.0,
                    association_conf=prof.avg_confidence,
                    explanation=f"Restricted zone '{zone.name}' entered {entries} time(s)" + (" with fast movement." if running_in_zone else "."),
                )
                anomalies.append(
                    DetectedAnomaly(
                        event_type="restricted_zone_entry",
                        category="people_movement",
                        title=f"Restricted zone entry: {p_code} in {zone.name}",
                        description=(
                            f"Observed {p_code} inside configured restricted zone '{zone.name}' "
                            f"({entries} entry cycle(s), {len(inside_pts)} frame(s))"
                            + (" with high-speed movement." if running_in_zone else ".")
                        ),
                        start_timestamp=inside_pts[0].timestamp_seconds,
                        end_timestamp=inside_pts[-1].timestamp_seconds,
                        involved_track_ids=[prof.track_id],
                        person_track_id=prof.track_id,
                        object_track_id=None,
                        confidence=round(min(0.95, prof.avg_confidence * 0.92), 3),
                        severity=zone_sev,
                        frame_ids=[inside_pts[0].frame_index, inside_pts[-1].frame_index],
                        observed_actions=[
                            f"Person {p_code} entered '{zone.name}' at {inside_pts[0].timestamp_seconds:.1f}s.",
                            f"Detected {entries} zone entry transition(s) across {len(inside_pts)} sampled frames.",
                        ],
                        inference_explanation=(
                            f"Area rule triggered for configured zone '{zone.name}'. "
                            + ("Fast movement exceeded running speed threshold inside zone." if running_in_zone else "Presence detected inside restricted bounds.")
                        ),
                        association_uncertainty="low",
                        score_breakdown=score,
                        requires_human_review=True,
                    )
                )

    # B. Interaction anomaly: Object moved without a clearly associated person
    objects_with_person_assoc: set[int] = {
        inter.object_track_id
        for inter in interactions.person_object_interactions
        if inter.min_distance_norm <= config.co_movement_max_dist_norm
    }

    for prof in interactions.track_profiles.values():
        if prof.class_name == "person":
            continue
        if prof.max_displacement_norm >= config.object_move_disp_norm and prof.track_id not in objects_with_person_assoc:
            o_code = f"O{prof.track_id:03d}"
            score = compute_explainable_anomaly_score(
                movement_factor=0.7,
                interaction_factor=0.8,
                association_conf=prof.avg_confidence,
                explanation="Object displaced significantly without any nearby person track.",
            )
            anomalies.append(
                DetectedAnomaly(
                    event_type="object_movement_without_person",
                    category="object_interactions",
                    title=f"{prof.class_name.capitalize()} {o_code} moved without associated person",
                    description=(
                        f"Observed {prof.class_name} {o_code} shifting {prof.max_displacement_norm:.3f} "
                        f"normalized units with no tracked person within proximity."
                    ),
                    start_timestamp=prof.first_seen_timestamp,
                    end_timestamp=prof.last_seen_timestamp,
                    involved_track_ids=[prof.track_id],
                    person_track_id=None,
                    object_track_id=prof.track_id,
                    confidence=round(min(0.88, prof.avg_confidence * 0.85), 3),
                    severity="medium",
                    frame_ids=[prof.first_seen_frame, prof.last_seen_frame],
                    observed_actions=[
                        f"Object {o_code} ({prof.class_name}) displaced by {prof.max_displacement_norm:.3f} norm units.",
                        "No person track was detected within proximity during the displacement.",
                    ],
                    inference_explanation=(
                        "Unassociated object movement rule triggered. Could be self-propelled, pushed from off-camera, "
                        "or caused by an occluded/untracked person."
                    ),
                    association_uncertainty="high",
                    score_breakdown=score,
                    requires_human_review=True,
                )
            )

    # D. Temporal Anomaly: Activity outside configured operating hours
    if config.operating_hours_utc is not None and interactions.track_profiles:
        ts_now = session_timestamp_utc or datetime.now(timezone.utc)
        start_hr, end_hr = config.operating_hours_utc
        cur_hr = ts_now.hour
        in_hours = (start_hr <= cur_hr < end_hr) if start_hr <= end_hr else (cur_hr >= start_hr or cur_hr < end_hr)
        if not in_hours:
            all_tids = sorted(interactions.track_profiles.keys())
            first_f = interactions.min_frame_index
            last_f = interactions.max_frame_index
            score = compute_explainable_anomaly_score(
                zone_factor=0.8,
                duration_factor=0.5,
                association_conf=0.9,
                explanation=f"Activity observed at {cur_hr:02d}:00 UTC outside configured operating hours ({start_hr:02d}:00-{end_hr:02d}:00 UTC).",
            )
            anomalies.append(
                DetectedAnomaly(
                    event_type="after_hours_activity",
                    category="other_activities",
                    title="Activity outside configured operating hours",
                    description=(
                        f"Detected {len(all_tids)} tracked entity/entities during off-hours "
                        f"({cur_hr:02d}:00 UTC; permitted: {start_hr:02d}:00–{end_hr:02d}:00 UTC)."
                    ),
                    start_timestamp=min(p.first_seen_timestamp for p in interactions.track_profiles.values()),
                    end_timestamp=max(p.last_seen_timestamp for p in interactions.track_profiles.values()),
                    involved_track_ids=all_tids,
                    person_track_id=None,
                    object_track_id=None,
                    confidence=0.9,
                    severity="high",
                    frame_ids=[first_f, last_f],
                    observed_actions=[
                        f"Observed {len(all_tids)} track(s) active at {cur_hr:02d}:00 UTC."
                    ],
                    inference_explanation=(
                        "Temporal operating-hours rule triggered based on system clock vs configured schedule."
                    ),
                    association_uncertainty="low",
                    score_breakdown=score,
                    requires_human_review=True,
                )
            )

    return anomalies
