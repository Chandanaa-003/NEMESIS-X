import json
from pathlib import Path
import tempfile
import unittest

from app.services.zone_engine import (
    ZoneIntelligenceEngine,
    discover_recorded_zone_events,
    point_in_polygon,
)


def _zone(
    zone_id: str = "zone-a",
    *,
    zone_type: str = "monitoring",
    settings: dict | None = None,
    polygon: list[list[float]] | None = None,
) -> dict:
    return {
        "id": zone_id,
        "name": zone_id,
        "zone_type": zone_type,
        "polygon": polygon or [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]],
        "settings": {
            "confirmation_frames": 2,
            "cooldown_seconds": 0,
            "loiter_seconds": 30,
            "restricted_group_threshold": 2,
            **(settings or {}),
        },
    }


def _detection(
    track_id: int,
    *,
    class_name: str = "person",
    center_x: float = 50,
    bottom_y: float = 50,
    confidence: float = 0.9,
) -> dict:
    half_size = 5
    return {
        "track_id": track_id,
        "class_name": class_name,
        "confidence": confidence,
        "bbox": {
            "x1": center_x - half_size,
            "y1": bottom_y - 20 if class_name == "person" else bottom_y - half_size,
            "x2": center_x + half_size,
            "y2": bottom_y if class_name == "person" else bottom_y + half_size,
        },
    }


def _process(
    engine: ZoneIntelligenceEngine,
    *,
    zones: list[dict],
    detections: list[dict],
    frame: int,
    timestamp: float,
    width: int = 100,
    height: int = 100,
):
    return engine.process_frame(
        zones=zones,
        detections=detections,
        frame_index=frame,
        timestamp_seconds=timestamp,
        frame_width=width,
        frame_height=height,
    )


class ZoneGeometryAndSequenceTests(unittest.TestCase):
    def test_polygon_includes_interior_and_boundary_but_not_exterior(self) -> None:
        polygon = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
        self.assertTrue(point_in_polygon(0.5, 0.5, polygon))
        self.assertTrue(point_in_polygon(0.2, 0.5, polygon))
        self.assertFalse(point_in_polygon(0.1, 0.5, polygon))

    def test_entry_exit_need_confirmed_observations_and_retain_evidence(self) -> None:
        engine = ZoneIntelligenceEngine()
        zone = _zone(zone_type="restricted")
        initial = _process(
            engine,
            zones=[zone],
            detections=[_detection(1, center_x=10)],
            frame=0,
            timestamp=0,
        )
        self.assertEqual(initial, [])

        one_inside = _process(
            engine,
            zones=[zone],
            detections=[_detection(1)],
            frame=1,
            timestamp=1,
        )
        self.assertEqual(one_inside, [])
        entered = _process(
            engine,
            zones=[zone],
            detections=[_detection(1)],
            frame=2,
            timestamp=2,
        )
        self.assertEqual([event.event_type for event in entered], ["restricted_zone_entry"])
        self.assertEqual(entered[0].involved_track_ids, [1])
        self.assertEqual(entered[0].evidence_frame_ids, [1, 2])
        self.assertEqual(entered[0].severity, "high")

        one_outside = _process(
            engine,
            zones=[zone],
            detections=[_detection(1, center_x=10)],
            frame=3,
            timestamp=3,
        )
        self.assertEqual(one_outside, [])
        exited = _process(
            engine,
            zones=[zone],
            detections=[_detection(1, center_x=10)],
            frame=4,
            timestamp=4,
        )
        self.assertEqual([event.event_type for event in exited], ["person_zone_exit"])

    def test_one_noisy_inside_observation_does_not_trigger_entry(self) -> None:
        engine = ZoneIntelligenceEngine()
        zone = _zone()
        _process(engine, zones=[zone], detections=[_detection(3, center_x=10)], frame=0, timestamp=0)
        _process(engine, zones=[zone], detections=[_detection(3)], frame=1, timestamp=1)
        events = _process(
            engine,
            zones=[zone],
            detections=[_detection(3, center_x=10)],
            frame=2,
            timestamp=2,
        )
        self.assertEqual(events, [])

    def test_objects_enter_and_exit_using_bbox_center(self) -> None:
        engine = ZoneIntelligenceEngine()
        zone = _zone(settings={"confirmation_frames": 1})
        entered = _process(
            engine,
            zones=[zone],
            detections=[_detection(8, class_name="backpack")],
            frame=0,
            timestamp=0,
        )
        self.assertEqual([event.event_type for event in entered], ["object_zone_entry"])
        exited = _process(
            engine,
            zones=[zone],
            detections=[_detection(8, class_name="backpack", center_x=10)],
            frame=1,
            timestamp=1,
        )
        self.assertEqual([event.event_type for event in exited], ["object_zone_exit"])

    def test_loitering_requires_duration_threshold_and_is_not_intent(self) -> None:
        engine = ZoneIntelligenceEngine()
        zone = _zone(settings={"confirmation_frames": 1, "loiter_seconds": 2})
        entered = _process(
            engine,
            zones=[zone],
            detections=[_detection(4)],
            frame=0,
            timestamp=1,
        )
        self.assertIn("person_zone_entry", [event.event_type for event in entered])
        before_threshold = _process(
            engine,
            zones=[zone],
            detections=[_detection(4)],
            frame=1,
            timestamp=3,
        )
        self.assertNotIn("zone_loitering", [event.event_type for event in before_threshold])
        exceeded = _process(
            engine,
            zones=[zone],
            detections=[_detection(4)],
            frame=2,
            timestamp=3.1,
        )
        loiter = next(event for event in exceeded if event.event_type == "zone_loitering")
        self.assertAlmostEqual(loiter.end_timestamp - loiter.start_timestamp, 2.1)
        self.assertIn("does not indicate intent", loiter.description)
        self.assertEqual(loiter.explanation_payload["zone_id"], zone["id"])

    def test_repeated_entry_and_zone_transition(self) -> None:
        engine = ZoneIntelligenceEngine()
        settings = {"confirmation_frames": 1}
        zone_a = _zone("a", settings=settings)
        zone_b = _zone(
            "b",
            settings=settings,
            polygon=[[0.7, 0.4], [0.9, 0.4], [0.9, 0.6], [0.7, 0.6]],
        )
        _process(engine, zones=[zone_a, zone_b], detections=[_detection(5)], frame=0, timestamp=0)
        _process(engine, zones=[zone_a, zone_b], detections=[_detection(5, center_x=10)], frame=1, timestamp=1)
        events = _process(
            engine,
            zones=[zone_a, zone_b],
            detections=[_detection(5)],
            frame=2,
            timestamp=2,
        )
        self.assertIn("repeated_zone_entry", [event.event_type for event in events])
        _process(engine, zones=[zone_a, zone_b], detections=[_detection(5, center_x=10)], frame=3, timestamp=3)
        transition = _process(
            engine,
            zones=[zone_a, zone_b],
            detections=[_detection(5, center_x=80)],
            frame=4,
            timestamp=4,
        )
        self.assertIn("zone_transition", [event.event_type for event in transition])

    def test_multiple_people_in_restricted_zone_emits_once_for_confirmed_group(self) -> None:
        engine = ZoneIntelligenceEngine()
        zone = _zone("restricted", zone_type="restricted", settings={"confirmation_frames": 1})
        events = _process(
            engine,
            zones=[zone],
            detections=[_detection(1), _detection(2, center_x=52)],
            frame=0,
            timestamp=1,
        )
        group_events = [
            event for event in events if event.event_type == "multiple_people_restricted_zone"
        ]
        self.assertEqual(len(group_events), 1)
        self.assertEqual(group_events[0].involved_track_ids, [1, 2])
        self.assertEqual(
            _process(
                engine,
                zones=[zone],
                detections=[_detection(1), _detection(2, center_x=52)],
                frame=1,
                timestamp=2,
            ),
            [],
        )

    def test_normalized_polygons_work_at_different_resolutions(self) -> None:
        for width, height in ((100, 100), (1920, 1080)):
            with self.subTest(width=width, height=height):
                engine = ZoneIntelligenceEngine()
                zone = _zone(settings={"confirmation_frames": 1})
                scale = width / 100
                y_scale = height / 100
                events = _process(
                    engine,
                    zones=[zone],
                    detections=[
                        _detection(1, center_x=50 * scale, bottom_y=50 * y_scale)
                    ],
                    frame=0,
                    timestamp=0,
                    width=width,
                    height=height,
                )
                self.assertIn("person_zone_entry", [event.event_type for event in events])

    def test_untracked_detections_do_not_fabricate_zone_events(self) -> None:
        engine = ZoneIntelligenceEngine()
        detection = _detection(1)
        detection["track_id"] = None
        self.assertEqual(
            _process(
                engine,
                zones=[_zone(settings={"confirmation_frames": 1})],
                detections=[detection],
                frame=0,
                timestamp=0,
            ),
            [],
        )

    def test_saved_recorded_detection_frames_generate_zone_events(self) -> None:
        zone = _zone(settings={"confirmation_frames": 2})
        frames = [
            {
                "frame_index": index,
                "timestamp_seconds": float(index),
                "frame_width": 100,
                "frame_height": 100,
                "detections": [_detection(17)],
            }
            for index in range(3)
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            detections_path = Path(temporary_directory) / "detections.json"
            detections_path.write_text(json.dumps({"frames": frames}), encoding="utf-8")
            events = discover_recorded_zone_events(
                detections_path=detections_path,
                zones=[zone],
            )
        entries = [event for event in events if event.event_type == "person_zone_entry"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].involved_track_ids, [17])
        self.assertEqual(entries[0].evidence_frame_ids, [0, 1])


if __name__ == "__main__":
    unittest.main()
