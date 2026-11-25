from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.services.interaction_engine import InteractionConfig, analyze_track_interactions


DEFAULT_BASELINE_CONFIG: dict[str, Any] = {
    "minimum_tracks": 3,
    "minimum_history_seconds": 30.0,
    "stationary_displacement_threshold": 0.04,
    "low_movement_speed_threshold": 0.02,
    "running_like_speed_threshold": 0.22,
    "prolonged_stationary_seconds": 8.0,
    "anomaly_weights": {
        "duration": 0.15,
        "movement_change": 0.25,
        "interaction_sequence": 0.25,
        "repeated_behavior": 0.15,
        "zone_rule": 0.20,
    },
}


def build_behavior_report(
    *,
    session_id: str,
    tracks_data: list[dict[str, Any]],
    events: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
    baseline_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build explainable behavior summaries from existing tracked histories and events."""
    config = {**DEFAULT_BASELINE_CONFIG, **(baseline_config or {})}
    track_times = [
        (float(track["first_seen_timestamp"]), float(track["last_seen_timestamp"]))
        for track in tracks_data
        if track.get("timeline_points")
    ]
    history_start = min((start for start, _ in track_times), default=0.0)
    history_end = max((end for _, end in track_times), default=0.0)
    history_seconds = max(0.0, history_end - history_start)

    frame_ts_map = {
        int(point["frame_index"]): float(point["timestamp_seconds"])
        for track in tracks_data
        for point in track.get("timeline_points", [])
    }
    interactions = analyze_track_interactions(
        tracks_data=tracks_data,
        frame_width=frame_width,
        frame_height=frame_height,
        all_frame_indices=sorted(frame_ts_map),
        config=InteractionConfig(
            running_speed_threshold=float(config["running_like_speed_threshold"]),
            stationary_displacement_norm=float(config["stationary_displacement_threshold"]),
        ),
    )

    direction_counts: Counter[str] = Counter()
    stationary_durations: list[float] = []
    movement_summaries: list[dict[str, Any]] = []
    movement_transitions = 0
    for profile in interactions.track_profiles.values():
        points = sorted(profile.points_by_frame.values(), key=lambda point: point.timestamp_seconds)
        movement_transitions += sum(
            1
            for point in points
            if point.speed >= float(config["low_movement_speed_threshold"])
        )
        direction_counts[profile.direction_label] += 1
        if profile.is_stationary:
            stationary_durations.append(profile.duration_seconds)

        if profile.is_stationary:
            movement_type = "stationary"
        elif profile.max_speed >= float(config["running_like_speed_threshold"]):
            movement_type = "running-like"
        elif profile.max_speed >= float(config["low_movement_speed_threshold"]):
            movement_type = "walking-like"
        else:
            movement_type = "low-movement"

        repeated_cells: Counter[tuple[int, int]] = Counter()
        for point in points:
            repeated_cells[(round(point.norm_x * 7), round(point.norm_y * 7))] += 1
        repeated_area_observations = sum(count - 1 for count in repeated_cells.values() if count > 1)

        movement_summaries.append(
            {
                "track_id": profile.track_id,
                "track_code": f"{'P' if profile.class_name == 'person' else 'O'}{profile.track_id:03d}",
                "class_name": profile.class_name,
                "start_timestamp": profile.first_seen_timestamp,
                "end_timestamp": profile.last_seen_timestamp,
                "duration_seconds": profile.duration_seconds,
                "movement_type": movement_type,
                "direction": profile.direction_label,
                "maximum_normalized_image_speed_per_second": profile.max_speed,
                "maximum_normalized_image_acceleration_per_second_squared": profile.max_accel,
                "speed_is_calibrated": False,
                "direction_changes": profile.direction_reversals,
                "back_and_forth": profile.direction_reversals >= 2,
                "stationary": profile.is_stationary,
                "prolonged_stationary": (
                    profile.is_stationary
                    and profile.duration_seconds >= float(config["prolonged_stationary_seconds"])
                ),
                "stationary_duration_seconds": (
                    profile.duration_seconds if profile.is_stationary else 0.0
                ),
                "repeated_area_observations": repeated_area_observations,
                "confidence": profile.avg_confidence,
                "uncertainty": (
                    "Movement uses sampled image coordinates; occlusion and tracking ID changes "
                    "can affect estimates. Speed is not a physical speed."
                ),
            }
        )

    related_tracks: dict[int, list[dict[str, Any]]] = {}
    for interaction in interactions.person_object_interactions:
        if (
            interaction.min_distance_norm > InteractionConfig().proximity_threshold_norm
            and interaction.approach_window is None
            and interaction.departure_window is None
        ):
            continue
        relationship = {
            "other_track_id": interaction.object_track_id,
            "other_class_name": interaction.object_class_name,
            "approach_observed": interaction.approach_window is not None,
            "moving_away_observed": interaction.departure_window is not None,
            "proximity_visits": len(interaction.proximity_visit_windows),
            "minimum_normalized_distance": interaction.min_distance_norm,
        }
        related_tracks.setdefault(interaction.person_track_id, []).append(relationship)
        related_tracks.setdefault(interaction.object_track_id, []).append(
            {
                **relationship,
                "other_track_id": interaction.person_track_id,
                "other_class_name": "person",
            }
        )
    for movement in movement_summaries:
        movement["related_tracks"] = related_tracks.get(movement["track_id"], [])

    normalized_events = sorted(
        events,
        key=lambda event: (
            float(event.get("start_timestamp", 0.0)),
            float(event.get("end_timestamp", 0.0)),
        ),
    )
    sequences: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for event in normalized_events:
        payload = event.get("explanation_payload") or {}
        track_ids = [int(track_id) for track_id in event.get("involved_track_ids", [])]
        evidence = event.get("evidence_references") or []
        sequence = {
            "sequence_id": str(event["id"]),
            "track_ids": track_ids,
            "start_timestamp": float(event.get("start_timestamp", 0.0)),
            "end_timestamp": float(event.get("end_timestamp", 0.0)),
            "actions_observed": [str(line) for line in payload.get("observed_sequence", [])],
            "event_type": str(event.get("event_type", "observed_sequence")),
            "confidence": float(event.get("confidence", 0.0)),
            "severity": str(event.get("severity", "low")),
            "created_at": event.get("created_at"),
            "supporting_evidence": evidence,
            "observed_facts": str(event.get("description", "")),
            "inferred_conclusion": str(payload.get("why_flagged", "")),
        }
        sequences.append(sequence)

        score = payload.get("anomaly_score")
        if not isinstance(score, dict):
            continue
        weights = config["anomaly_weights"]
        score_components = {
            "duration": float(score.get("duration_score", 0.0)),
            "movement_change": float(score.get("movement_change_score", 0.0)),
            "interaction_sequence": float(score.get("interaction_sequence_score", 0.0)),
            "repeated_behavior": float(score.get("repeated_behavior_score", 0.0)),
            "zone_rule": float(score.get("zone_rule_score", 0.0)),
        }
        has_components = any(
            key in score
            for key in (
                "duration_score",
                "movement_change_score",
                "interaction_sequence_score",
                "repeated_behavior_score",
                "zone_rule_score",
            )
        )
        total_score = (
            min(1.0, max(0.0, sum(weights[key] * score_components[key] for key in weights)))
            if has_components
            else float(score.get("total_score", 0.0))
        )
        weighted_score_breakdown = {
            **score,
            "total_score": round(total_score, 3),
            "weights": weights,
            "source_rule_explanation": score.get("explanation", ""),
            "explanation": (
                "Stored component values reweighted with this session's weights: "
                + ", ".join(f"{key}={value:.0%}" for key, value in weights.items())
                + "."
            ),
        }
        anomalies.append(
            {
                "anomaly_id": str(event["id"]),
                "track_ids": track_ids,
                "event_category": str(event.get("event_type", "behavior_rule")),
                "event_type": str(event.get("event_type", "behavior_rule")),
                "severity": str(event.get("severity", "low")),
                "confidence": float(event.get("confidence", 0.0)),
                "score": round(total_score, 3),
                "score_breakdown": weighted_score_breakdown,
                "reason": str(payload.get("why_flagged") or score.get("explanation", "")),
                "created_at": event.get("created_at"),
                "supporting_timestamps": [
                    float(timestamp) for timestamp in payload.get("evidence_timestamps", [])
                ],
                "evidence_references": evidence,
                "uncertainty": str(
                    payload.get(
                        "association_uncertainty",
                        "Rule-based visual inference; track association and occlusion may be uncertain.",
                    )
                ),
            }
        )

    correlations: list[dict[str, Any]] = []
    for previous, current in zip(normalized_events, normalized_events[1:]):
        previous_tracks = set(previous.get("involved_track_ids", []))
        shared_tracks = sorted(previous_tracks.intersection(current.get("involved_track_ids", [])))
        gap_seconds = float(current.get("start_timestamp", 0.0)) - float(
            previous.get("end_timestamp", 0.0)
        )
        if not shared_tracks or gap_seconds < 0 or gap_seconds > 60:
            continue
        person_id = next(
            (
                int(track_id)
                for track_id in shared_tracks
                if any(
                    item["track_id"] == int(track_id) and item["class_name"] == "person"
                    for item in movement_summaries
                )
            ),
            None,
        )
        object_id = next((int(track_id) for track_id in shared_tracks if track_id != person_id), None)
        person_label = f"person P{person_id:03d}" if person_id is not None else "a shared track"
        object_label = f" and object O{object_id:03d}" if object_id is not None else ""
        correlations.append(
            {
                "correlation_id": f"{previous['id']}:{current['id']}",
                "event_ids": [str(previous["id"]), str(current["id"])],
                "track_ids": shared_tracks,
                "start_timestamp": float(previous.get("start_timestamp", 0.0)),
                "end_timestamp": float(current.get("end_timestamp", 0.0)),
                "observed_facts": [
                    str(previous.get("description", "")),
                    str(current.get("description", "")),
                ],
                "explanation": (
                    f"{person_label}{object_label} appears in two observations {gap_seconds:.1f} "
                    "seconds apart. This temporal correlation does not establish causation."
                ),
            }
        )

    minimum_tracks = int(config["minimum_tracks"])
    minimum_history = float(config["minimum_history_seconds"])
    baseline_available = (
        len(movement_summaries) >= minimum_tracks and history_seconds >= minimum_history
    )
    interaction_events = sum(
        1
        for event in normalized_events
        if event.get("category") in {"object_interactions", "possible_unattended_objects"}
    )
    baseline = {
        "status": "available" if baseline_available else "insufficient_history",
        "model_trained": False,
        "scope": session_id,
        "history_seconds": round(history_seconds, 3),
        "config": config,
        "measurements": (
            {
                "typical_movement_frequency_per_minute": round(
                    movement_transitions / max(history_seconds / 60.0, 0.001), 3
                ),
                "typical_stationary_duration_seconds": round(
                    sum(stationary_durations) / len(stationary_durations), 3
                )
                if stationary_durations
                else 0.0,
                "interaction_frequency_per_minute": round(
                    interaction_events / max(history_seconds / 60.0, 0.001), 3
                ),
                "common_directions": dict(direction_counts.most_common()),
            }
            if baseline_available
            else None
        ),
        "note": (
            "Descriptive per-session rules only; no statistical model is trained."
            if baseline_available
            else (
                f"Need at least {minimum_tracks} tracks and {minimum_history:.0f} seconds of "
                "history before a descriptive baseline is available."
            )
        ),
    }
    if baseline_available:
        typical_stationary_duration = float(
            baseline["measurements"]["typical_stationary_duration_seconds"]
        )
        common_direction = next(iter(direction_counts.most_common()), ("", 0))[0]
        for movement in movement_summaries:
            movement["baseline_comparison"] = {
                "status": "descriptive_comparison",
                "stationary_duration_deviation_seconds": round(
                    float(movement["stationary_duration_seconds"])
                    - typical_stationary_duration,
                    3,
                ),
                "direction_is_most_common": movement["direction"] == common_direction,
                "note": "Compared with this session's descriptive aggregate; not a trained model.",
            }
    else:
        for movement in movement_summaries:
            movement["baseline_comparison"] = {
                "status": "insufficient_history",
                "note": baseline["note"],
            }

    return {
        "session_id": session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "track_count": len(movement_summaries),
            "sequence_count": len(sequences),
            "anomaly_count": len(anomalies),
            "correlation_count": len(correlations),
            "history_seconds": round(history_seconds, 3),
            "baseline_status": baseline["status"],
        },
        "baseline": baseline,
        "movement_summaries": movement_summaries,
        "sequences": sequences,
        "anomalies": anomalies,
        "event_correlations": correlations,
        "scoring_logic": {
            "description": (
                "Existing explainable component scores are reweighted using the configured "
                "per-session weights. No score is invented when an event has no score breakdown."
            ),
            "weights": config["anomaly_weights"],
        },
    }
