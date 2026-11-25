import json
from pathlib import Path
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from app.services.event_engine import (
    discover_events_for_analysis,
    discover_events_from_data,
)
from app.services.interaction_engine import (
    InteractionConfig,
    RestrictedZone,
    SessionTemporalMemory,
)


def _make_track(
    *,
    track_id: int,
    class_id: int,
    class_name: str,
    points: list[tuple[int, float, float, float, float]],
) -> dict:
    """Build a normalized synthetic track payload (frame_idx, ts, cx, cy, conf) for simulated tests."""
    return {
        "track_id": track_id,
        "class_id": class_id,
        "class_name": class_name,
        "first_seen_frame": points[0][0],
        "last_seen_frame": points[-1][0],
        "first_seen_timestamp": points[0][1],
        "last_seen_timestamp": points[-1][1],
        "duration_seconds": points[-1][1] - points[0][1],
        "frame_count": len(points),
        "avg_confidence": sum(p[4] for p in points) / len(points),
        "max_confidence": max(p[4] for p in points),
        "timeline_points": [
            {
                "frame_index": f,
                "timestamp_seconds": ts,
                "center_x": cx,
                "center_y": cy,
                "confidence": conf,
            }
            for f, ts, cx, cy, conf in points
        ],
    }


class InteractionAndAnomalyIntelligenceTests(unittest.TestCase):
    """Simulated test suite covering person-object interaction, pickup, placement, anomalies, and memory isolation."""

    def setUp(self) -> None:
        self.w = 1000
        self.h = 1000
        self.cfg = InteractionConfig()

    def test_01_person_approaches_object(self) -> None:
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 100, 500, 0.9),
                (2, 2.0, 250, 500, 0.9),
                (3, 3.0, 400, 500, 0.9),
                (4, 4.0, 480, 500, 0.9),
            ],
        )
        bag = _make_track(
            track_id=2,
            class_id=24,
            class_name="backpack",
            points=[
                (1, 1.0, 500, 500, 0.88),
                (2, 2.0, 500, 500, 0.88),
                (3, 3.0, 500, 500, 0.88),
                (4, 4.0, 500, 500, 0.88),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1, bag],
            frame_ts_map={1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        types = {e.event_type for e in events}
        self.assertIn("person_approaching_object", types)
        self.assertNotIn("possible_object_pickup", types)

    def test_02_person_picks_up_object(self) -> None:
        # P001 approaches Bag O001, then both move together to the right
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 200, 500, 0.92),
                (2, 2.0, 380, 500, 0.92),
                (3, 3.0, 490, 500, 0.92),
                (4, 4.0, 600, 500, 0.92),
                (5, 5.0, 720, 500, 0.92),
                (6, 6.0, 840, 500, 0.92),
            ],
        )
        bag = _make_track(
            track_id=2,
            class_id=24,
            class_name="backpack",
            points=[
                (1, 1.0, 500, 500, 0.89),
                (2, 2.0, 500, 500, 0.89),
                (3, 3.0, 500, 500, 0.89),
                (4, 4.0, 610, 500, 0.89),
                (5, 5.0, 730, 500, 0.89),
                (6, 6.0, 850, 500, 0.89),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1, bag],
            frame_ts_map={i: float(i) for i in range(1, 7)},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        pickups = [e for e in events if e.event_type == "possible_object_pickup"]
        self.assertEqual(len(pickups), 1)
        self.assertEqual(pickups[0].explanation_payload["person_track_id"], 1)
        self.assertEqual(pickups[0].explanation_payload["object_track_id"], 2)
        self.assertEqual(pickups[0].severity, "high")

    def test_03_and_04_person_places_and_leaves_object_behind(self) -> None:
        # P001 is near bag, then walks away; bag remains stationary
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 480, 500, 0.9),
                (2, 2.0, 500, 500, 0.9),
                (3, 3.0, 650, 500, 0.9),
                (4, 4.0, 800, 500, 0.9),
                (5, 5.0, 900, 500, 0.9),
            ],
        )
        bag = _make_track(
            track_id=2,
            class_id=24,
            class_name="backpack",
            points=[
                (1, 1.0, 500, 500, 0.9),
                (2, 2.0, 500, 500, 0.9),
                (3, 3.0, 500, 500, 0.9),
                (4, 4.0, 500, 500, 0.9),
                (5, 5.0, 500, 500, 0.9),
                (6, 6.0, 500, 500, 0.9),
                (7, 7.0, 500, 500, 0.9),
                (8, 8.0, 500, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1, bag],
            frame_ts_map={i: float(i) for i in range(1, 9)},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        types = {e.event_type for e in events}
        self.assertIn("possible_object_placement", types)
        self.assertIn("possible_unattended_object", types)
        unattended = next(e for e in events if e.event_type == "possible_unattended_object")
        self.assertIn("anomaly_score", unattended.explanation_payload)
        self.assertGreater(
            unattended.explanation_payload["anomaly_score"]["duration_score"],
            0,
        )

    def test_05_and_06_multiple_people_and_second_person_pickup(self) -> None:
        # P001 approaches O001 and walks away; P002 approaches O001 and moves it
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 300, 500, 0.9),
                (2, 2.0, 490, 500, 0.9),
                (3, 3.0, 300, 500, 0.9),
                (4, 4.0, 150, 500, 0.9),
            ],
        )
        p2 = _make_track(
            track_id=2,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 800, 500, 0.9),
                (2, 2.0, 700, 500, 0.9),
                (3, 3.0, 510, 500, 0.9),
                (4, 4.0, 620, 500, 0.9),
                (5, 5.0, 740, 500, 0.9),
                (6, 6.0, 860, 500, 0.9),
            ],
        )
        bag = _make_track(
            track_id=3,
            class_id=24,
            class_name="backpack",
            points=[
                (1, 1.0, 500, 500, 0.9),
                (2, 2.0, 500, 500, 0.9),
                (3, 3.0, 500, 500, 0.9),
                (4, 4.0, 620, 500, 0.9),
                (5, 5.0, 740, 500, 0.9),
                (6, 6.0, 860, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1, p2, bag],
            frame_ts_map={i: float(i) for i in range(1, 7)},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        multi = [e for e in events if e.event_type == "multi_person_object_interaction"]
        pickups = [e for e in events if e.event_type == "possible_object_pickup"]
        self.assertEqual(len(multi), 1)
        self.assertIn("anomaly_score", multi[0].explanation_payload)
        self.assertEqual(multi[0].explanation_payload["person_track_id"], 2)
        self.assertEqual(len(pickups), 1)
        self.assertEqual(pickups[0].explanation_payload["person_track_id"], 2)

    def test_07_object_moves_without_person(self) -> None:
        bag = _make_track(
            track_id=5,
            class_id=24,
            class_name="suitcase",
            points=[
                (1, 1.0, 200, 500, 0.9),
                (2, 2.0, 350, 500, 0.9),
                (3, 3.0, 500, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[bag],
            frame_ts_map={1: 1.0, 2: 2.0, 3: 3.0},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        types = {e.event_type for e in events}
        self.assertIn("object_movement_without_person", types)

    def test_08_occlusion_and_id_switch(self) -> None:
        t_prev = _make_track(
            track_id=10,
            class_id=0,
            class_name="person",
            points=[(1, 1.0, 400, 500, 0.9), (2, 2.0, 450, 500, 0.9)],
        )
        t_next = _make_track(
            track_id=11,
            class_id=0,
            class_name="person",
            points=[(4, 4.0, 470, 500, 0.9), (5, 5.0, 520, 500, 0.9)],
        )
        events = discover_events_from_data(
            tracks_data=[t_prev, t_next],
            frame_ts_map={i: float(i) for i in range(1, 6)},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        switches = [e for e in events if e.event_type == "occlusion_id_switch"]
        self.assertEqual(len(switches), 1)
        self.assertEqual(switches[0].explanation_payload["association_uncertainty"], "high")

    def test_09_normal_movement_not_anomaly(self) -> None:
        # Steady walking left-to-right at constant speed
        p_normal = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 100, 500, 0.9),
                (2, 2.0, 180, 500, 0.9),
                (3, 3.0, 260, 500, 0.9),
                (4, 4.0, 340, 500, 0.9),
                (5, 5.0, 420, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p_normal],
            frame_ts_map={i: float(i) for i in range(1, 6)},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        anomaly_types = {
            "movement_anomaly",
            "prolonged_stationary_person",
            "restricted_zone_entry",
            "object_movement_without_person",
        }
        self.assertFalse(any(e.event_type in anomaly_types for e in events))

    def test_10_restricted_zone_entry(self) -> None:
        cfg_zone = InteractionConfig(
            restricted_zones=(RestrictedZone(name="Server Vault", x1=0.6, y1=0.4, x2=0.9, y2=0.8),)
        )
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 200, 500, 0.9),
                (2, 2.0, 700, 600, 0.9),
                (3, 3.0, 750, 600, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1],
            frame_ts_map={1: 1.0, 2: 2.0, 3: 3.0},
            frame_width=self.w,
            frame_height=self.h,
            config=cfg_zone,
        )
        zone_evts = [e for e in events if e.event_type == "restricted_zone_entry"]
        self.assertEqual(len(zone_evts), 1)
        self.assertIn("anomaly_score", zone_evts[0].explanation_payload)

    def test_11_repeated_interactions(self) -> None:
        p1 = _make_track(
            track_id=1,
            class_id=0,
            class_name="person",
            points=[
                (1, 1.0, 480, 500, 0.9),  # visit 1
                (2, 2.0, 100, 500, 0.9),  # away
                (3, 3.0, 480, 500, 0.9),  # visit 2
            ],
        )
        bag = _make_track(
            track_id=2,
            class_id=24,
            class_name="backpack",
            points=[
                (1, 1.0, 500, 500, 0.9),
                (2, 2.0, 500, 500, 0.9),
                (3, 3.0, 500, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[p1, bag],
            frame_ts_map={1: 1.0, 2: 2.0, 3: 3.0},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )
        repeated = [e for e in events if e.event_type == "repeated_movement_near_object"]
        self.assertEqual(len(repeated), 1)
        anomaly_score = repeated[0].explanation_payload["anomaly_score"]
        self.assertGreater(anomaly_score["total_score"], 0)
        self.assertIn("Repeated proximity contributes", anomaly_score["explanation"])

    def test_stationary_period_followed_by_rapid_movement_is_sequenced(self) -> None:
        person = _make_track(
            track_id=7,
            class_id=0,
            class_name="person",
            points=[
                (1, 0.0, 400, 500, 0.9),
                (2, 4.0, 400, 500, 0.9),
                (3, 8.0, 400, 500, 0.9),
                (4, 12.0, 400, 500, 0.9),
                (5, 13.0, 900, 500, 0.9),
                (6, 14.0, 950, 500, 0.9),
            ],
        )
        events = discover_events_from_data(
            tracks_data=[person],
            frame_ts_map={1: 0.0, 2: 4.0, 3: 8.0, 4: 12.0, 5: 13.0, 6: 14.0},
            frame_width=self.w,
            frame_height=self.h,
            config=self.cfg,
        )

        sequence = next(
            event for event in events if event.event_type == "stationary_then_sudden_movement"
        )
        self.assertEqual(sequence.start_timestamp, 0.0)
        self.assertEqual(sequence.end_timestamp, 13.0)
        self.assertEqual(sequence.involved_track_ids, [7])
        self.assertIn("anomaly_score", sequence.explanation_payload)

    def test_12_and_13_recorded_and_live_memory_isolation(self) -> None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_rec_test_"))
        try:
            # Recorded pipeline artifacts
            (tmp_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "frames": [
                            {"frame_index": 1, "timestamp_seconds": 1.0, "filename": "frame_0001.jpg"},
                            {"frame_index": 2, "timestamp_seconds": 2.0, "filename": "frame_0002.jpg"},
                            {"frame_index": 3, "timestamp_seconds": 3.0, "filename": "frame_0003.jpg"},
                            {"frame_index": 4, "timestamp_seconds": 4.0, "filename": "frame_0004.jpg"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (tmp_dir / "detections.json").write_text(
                json.dumps({"total_detections": 8, "frames": [{"frame_width": 1000, "frame_height": 1000}]}),
                encoding="utf-8",
            )
            t1 = _make_track(
                track_id=1,
                class_id=0,
                class_name="person",
                points=[(1, 1.0, 200, 500, 0.9), (2, 2.0, 490, 500, 0.9), (3, 3.0, 620, 500, 0.9), (4, 4.0, 740, 500, 0.9)],
            )
            t2 = _make_track(
                track_id=2,
                class_id=24,
                class_name="backpack",
                points=[(1, 1.0, 500, 500, 0.9), (2, 2.0, 500, 500, 0.9), (3, 3.0, 630, 500, 0.9), (4, 4.0, 750, 500, 0.9)],
            )
            (tmp_dir / "tracks.json").write_text(
                json.dumps({"total_tracks": 2, "tracks": [t1, t2]}),
                encoding="utf-8",
            )

            output = discover_events_for_analysis(analysis_id="rec-01", analysis_dir=tmp_dir, config=self.cfg)
            self.assertTrue((tmp_dir / "events.json").is_file())
            self.assertIn("possible_object_pickup", {e.event_type for e in output.events})

            # Live isolated session memories must not leak
            mem_a = SessionTemporalMemory(session_id="live-a")
            mem_b = SessionTemporalMemory(session_id="live-b")
            discover_events_from_data(
                tracks_data=[t1, t2],
                frame_ts_map={1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0},
                frame_width=1000,
                frame_height=1000,
                memory=mem_a,
            )
            self.assertIn(1, mem_a.person_track_ids)
            self.assertNotIn(1, mem_b.person_track_ids)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
