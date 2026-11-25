import unittest

from app.services.behavior_engine import build_behavior_report


def _track(track_id: int, class_name: str, offset: float = 0.0) -> dict:
    points = [
        (0, 0.0, 100.0 + offset, 200.0),
        (1, 10.0, 900.0 + offset, 200.0),
        (2, 20.0, 100.0 + offset, 200.0),
        (3, 40.0, 900.0 + offset, 200.0),
    ]
    return {
        "track_id": track_id,
        "class_name": class_name,
        "first_seen_frame": 0,
        "last_seen_frame": 3,
        "first_seen_timestamp": 0.0,
        "last_seen_timestamp": 40.0,
        "duration_seconds": 40.0,
        "frame_count": len(points),
        "avg_confidence": 0.9,
        "timeline_points": [
            {
                "frame_index": frame,
                "timestamp_seconds": timestamp,
                "center_x": center_x,
                "center_y": center_y,
                "confidence": 0.9,
            }
            for frame, timestamp, center_x, center_y in points
        ],
    }


class BehaviorEngineTests(unittest.TestCase):
    def test_builds_movement_baseline_sequences_and_scored_anomalies(self) -> None:
        repeated_event = {
            "id": "event-1",
            "event_type": "repeated_movement_near_object",
            "category": "object_interactions",
            "description": "Person approached the object repeatedly.",
            "start_timestamp": 10.0,
            "end_timestamp": 20.0,
            "involved_track_ids": [1, 2],
            "confidence": 0.82,
            "severity": "medium",
            "created_at": "2026-01-01T10:00:00+00:00",
            "explanation_payload": {
                "observed_sequence": ["Approach", "Departure", "Return"],
                "why_flagged": "Repeated proximity visits.",
                "evidence_timestamps": [10.0, 20.0],
                "anomaly_score": {
                    "total_score": 0.3,
                    "duration_score": 0.4,
                    "movement_change_score": 0.2,
                    "interaction_sequence_score": 0.6,
                    "repeated_behavior_score": 0.8,
                    "zone_rule_score": 0.1,
                    "explanation": "Repeat and interaction rule weights.",
                },
            },
            "evidence_references": [{"timestamp_seconds": 10.0, "url": "/frame.jpg"}],
        }
        followup_event = {
            **repeated_event,
            "id": "event-2",
            "event_type": "possible_unattended_object",
            "description": "The object remained after the person left.",
            "start_timestamp": 25.0,
            "end_timestamp": 35.0,
            "explanation_payload": {"observed_sequence": ["Person left."]},
        }

        report = build_behavior_report(
            session_id="session-a",
            tracks_data=[
                _track(1, "person"),
                _track(2, "backpack", 10),
                _track(3, "chair", 20),
            ],
            events=[repeated_event, followup_event],
            frame_width=1000,
            frame_height=1000,
        )

        self.assertEqual(report["baseline"]["status"], "available")
        self.assertFalse(report["baseline"]["model_trained"])
        self.assertEqual(report["summary"]["sequence_count"], 2)
        self.assertEqual(report["summary"]["anomaly_count"], 1)
        self.assertEqual(report["summary"]["correlation_count"], 1)
        self.assertEqual(report["sequences"][0]["actions_observed"], ["Approach", "Departure", "Return"])
        self.assertEqual(report["anomalies"][0]["score"], 0.4)
        self.assertEqual(report["anomalies"][0]["score_breakdown"]["weights"]["duration"], 0.15)
        self.assertFalse(report["movement_summaries"][0]["speed_is_calibrated"])

        custom_weights = build_behavior_report(
            session_id="session-b",
            tracks_data=[_track(1, "person")],
            events=[repeated_event],
            frame_width=1000,
            frame_height=1000,
            baseline_config={
                "anomaly_weights": {
                    "duration": 0.0,
                    "movement_change": 0.0,
                    "interaction_sequence": 0.0,
                    "repeated_behavior": 1.0,
                    "zone_rule": 0.0,
                }
            },
        )
        self.assertEqual(custom_weights["anomalies"][0]["score"], 0.8)

    def test_insufficient_history_is_explicit(self) -> None:
        track = _track(1, "person")
        track["last_seen_timestamp"] = 5.0
        track["duration_seconds"] = 5.0
        for index, point in enumerate(track["timeline_points"]):
            point["timestamp_seconds"] = float(index)

        report = build_behavior_report(
            session_id="short-session",
            tracks_data=[track],
            events=[],
            frame_width=1000,
            frame_height=1000,
        )

        self.assertEqual(report["baseline"]["status"], "insufficient_history")
        self.assertIsNone(report["baseline"]["measurements"])
        self.assertIn("Need at least", report["baseline"]["note"])


if __name__ == "__main__":
    unittest.main()
