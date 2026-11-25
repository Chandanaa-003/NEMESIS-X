import json
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.analysis import Analysis
from app.models.behavior import BehaviorSnapshot
from app.models.detection import Detection
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.investigation import Investigation, InvestigationNote, InvestigationSource
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.user import User
from app.models.video import Video


class InvestigationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_investigation_test_"))
        self.processed_dir = self.tmp_dir / "processed"
        self.evidence_dir = self.tmp_dir / "evidence"
        self.live_dir = self.tmp_dir / "live"
        for directory in (self.processed_dir, self.evidence_dir, self.live_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'investigation.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.settings = get_settings()
        self.original_dirs = {
            "processed_dir": self.settings.processed_dir,
            "evidence_dir": self.settings.evidence_dir,
            "live_dir": self.settings.live_dir,
        }
        self.settings.processed_dir = str(self.processed_dir)
        self.settings.evidence_dir = str(self.evidence_dir)
        self.settings.live_dir = str(self.live_dir)
        self.app = create_application()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

        db = self.SessionLocal()
        try:
            owner = User(
                full_name="Investigation Owner",
                email="investigation-owner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            other = User(
                full_name="Investigation Other",
                email="investigation-other@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([owner, other])
            db.commit()
            db.refresh(owner)
            db.refresh(other)
            self.owner_id = owner.id
            self.owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
            self.other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

            video = Video(
                user_id=owner.id,
                original_filename="actual-recording.mp4",
                stored_filename="actual-recording.mp4",
                file_path="storage/uploads/actual-recording.mp4",
                file_size=10,
                mime_type="video/mp4",
                status="completed",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            self.video_id = video.id

            analysis = Analysis(
                video_id=video.id,
                user_id=owner.id,
                status="completed",
                progress=100,
                total_frames=2,
                processed_frames=2,
                extracted_frames=2,
                sampling_interval=1,
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            self.analysis_id = analysis.id
            db.add(
                Track(
                    analysis_id=analysis.id,
                    video_id=video.id,
                    track_id=7,
                    class_id=0,
                    class_name="person",
                    first_seen_frame=0,
                    last_seen_frame=1,
                    first_seen_timestamp=0.0,
                    last_seen_timestamp=1.0,
                    duration_seconds=1.0,
                    frame_count=2,
                    avg_confidence=0.9,
                    max_confidence=0.95,
                )
            )
            for frame_index in range(2):
                db.add(
                    Detection(
                        analysis_id=analysis.id,
                        video_id=video.id,
                        frame_index=frame_index,
                        timestamp_seconds=float(frame_index),
                        track_id=7,
                        class_id=0,
                        class_name="person",
                        confidence=0.9,
                        bbox_x1=10.0 + frame_index,
                        bbox_y1=10,
                        bbox_x2=20.0 + frame_index,
                        bbox_y2=30,
                    )
                )
            event = Event(
                analysis_id=analysis.id,
                event_type="person_object_interaction",
                category="object_interactions",
                title="Possible person-object interaction",
                description="Person T007 moved near the tracked object.",
                explanation_payload={
                    "person_track_id": 7,
                    "object_track_id": 8,
                    "observed_sequence": ["Approach observed"],
                    "association_uncertainty": "Possible association based on proximity.",
                },
                start_timestamp=0.5,
                end_timestamp=1.0,
                involved_track_ids=[7],
                confidence=0.82,
                severity="medium",
                evidence_frame_ids=[0],
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            self.event_id = event.id
            db.add(
                Evidence(
                    event_id=event.id,
                    analysis_id=analysis.id,
                    user_id=owner.id,
                    frame_number=0,
                    timestamp_seconds=0.0,
                    evidence_type="original_frame",
                    file_path="storage/evidence/frame.jpg",
                    description="Original evidence frame",
                    metadata_json={"event_title": event.title},
                )
            )

            live = LiveSession(
                user_id=owner.id,
                status="stopped",
                frames_processed=2,
                total_detections=2,
                unique_tracks_count=1,
                events_discovered_count=1,
                frame_width=100,
                frame_height=100,
            )
            db.add(live)
            db.commit()
            db.refresh(live)
            self.live_session_id = live.id
            active_live = LiveSession(user_id=owner.id, status="active")
            db.add(active_live)
            db.commit()
            db.refresh(active_live)
            self.active_live_session_id = active_live.id
            db.add(
                BehaviorSnapshot(
                    user_id=owner.id,
                    live_session_id=live.id,
                    baseline_config={},
                    track_history=[
                        {
                            "track_id": 7,
                            "class_name": "person",
                            "first_seen_timestamp": 0.1,
                            "last_seen_timestamp": 0.9,
                            "frame_count": 2,
                            "timeline_points": [
                                {"frame_index": 0, "timestamp_seconds": 0.1, "center_x": 10, "center_y": 10, "confidence": 0.8},
                                {"frame_index": 1, "timestamp_seconds": 0.9, "center_x": 20, "center_y": 20, "confidence": 0.9},
                            ],
                        }
                    ],
                    report_payload={},
                )
            )
            live_event = LiveEvent(
                session_id=live.id,
                user_id=owner.id,
                event_type="person_zone_entry",
                category="people_movement",
                title="Person entered zone",
                description="Tracked person entered the configured zone.",
                explanation_payload={"zone_name": "Entry"},
                timestamp_seconds=0.9,
                start_timestamp=0.9,
                end_timestamp=0.9,
                involved_track_ids=[7],
                confidence=0.9,
                severity="low",
                frame_index=1,
            )
            db.add(live_event)
            db.commit()
            db.refresh(live_event)
            self.live_event_id = live_event.id
        finally:
            db.close()

        analysis_dir = self.processed_dir / self.analysis_id
        (analysis_dir / "frames").mkdir(parents=True)
        (analysis_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "frames": [
                        {
                            "frame_index": frame_index,
                            "source_frame_index": frame_index,
                            "timestamp_seconds": float(frame_index),
                            "filename": f"frame_{frame_index:04d}.jpg",
                        }
                        for frame_index in range(2)
                    ]
                }
            ),
            encoding="utf-8",
        )
        (analysis_dir / "tracks.json").write_text(
            json.dumps(
                {
                    "tracks": [
                        {
                            "track_id": 7,
                            "class_id": 0,
                            "class_name": "person",
                            "first_seen_frame": 0,
                            "last_seen_frame": 1,
                            "first_seen_timestamp": 0.0,
                            "last_seen_timestamp": 1.0,
                            "duration_seconds": 1.0,
                            "frame_count": 2,
                            "avg_confidence": 0.9,
                            "max_confidence": 0.95,
                            "timeline_points": [
                                {
                                    "frame_index": index,
                                    "timestamp_seconds": float(index),
                                    "center_x": 15.0 + index,
                                    "center_y": 20.0,
                                    "confidence": 0.9,
                                    "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 30},
                                }
                                for index in range(2)
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (analysis_dir / "detections.json").write_text(
            json.dumps(
                {
                    "frames": [
                        {
                            "frame_index": index,
                            "source_frame_index": index,
                            "timestamp_seconds": float(index),
                            "filename": f"frame_{index:04d}.jpg",
                            "frame_width": 100,
                            "frame_height": 100,
                            "detections": [
                                {
                                    "track_id": 7,
                                    "class_id": 0,
                                    "class_name": "person",
                                    "confidence": 0.9,
                                    "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 30},
                                }
                            ],
                        }
                        for index in range(2)
                    ]
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.settings.processed_dir = self.original_dirs["processed_dir"]
        self.settings.evidence_dir = self.original_dirs["evidence_dir"]
        self.settings.live_dir = self.original_dirs["live_dir"]
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_investigation(self) -> dict:
        response = self.client.post(
            "/api/v1/investigations",
            json={"title": "North entrance review", "description": "Review observed movement."},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_investigation_lifecycle_links_tracks_events_evidence_and_private_notes(self) -> None:
        investigation = self._create_investigation()
        investigation_id = investigation["id"]
        updated = self.client.patch(
            f"/api/v1/investigations/{investigation_id}",
            json={"status": "reviewing", "title": "North entrance follow-up"},
            headers=self.owner_headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "reviewing")

        analysis_source = self.client.post(
            f"/api/v1/investigations/{investigation_id}/sources",
            json={"analysis_id": self.analysis_id},
            headers=self.owner_headers,
        )
        self.assertEqual(analysis_source.status_code, 201, analysis_source.text)
        source_id = analysis_source.json()["id"]
        live_source = self.client.post(
            f"/api/v1/investigations/{investigation_id}/sources",
            json={"live_session_id": self.live_session_id},
            headers=self.owner_headers,
        )
        self.assertEqual(live_source.status_code, 201, live_source.text)
        self.assertNotEqual(source_id, live_source.json()["id"])
        self.assertIn("not archived", live_source.json()["data_availability"])
        self.assertEqual(
            self.client.post(
                f"/api/v1/investigations/{investigation_id}/sources",
                json={"live_session_id": self.active_live_session_id},
                headers=self.owner_headers,
            ).status_code,
            409,
        )

        tracks = self.client.get(
            f"/api/v1/investigations/{investigation_id}/tracks?q=Person",
            headers=self.owner_headers,
        )
        self.assertEqual(tracks.status_code, 200, tracks.text)
        self.assertEqual(len(tracks.json()), 2)
        self.assertEqual({track["track_label"] for track in tracks.json()}, {"T007"})
        self.assertEqual(len({track["source_id"] for track in tracks.json()}), 2)
        self.assertEqual({track["entity_label"] for track in tracks.json()}, {"Person"})

        track_detail = self.client.get(
            f"/api/v1/investigations/{investigation_id}/tracks/{source_id}/7",
            headers=self.owner_headers,
        )
        self.assertEqual(track_detail.status_code, 200, track_detail.text)
        self.assertEqual(track_detail.json()["track"]["class_name"], "person")
        self.assertTrue(track_detail.json()["temporary_id_notice"].endswith("only."))

        track_link = self.client.post(
            f"/api/v1/investigations/{investigation_id}/tracks",
            json={"source_id": source_id, "track_id": 7},
            headers=self.owner_headers,
        )
        self.assertEqual(track_link.status_code, 201, track_link.text)
        event_link = self.client.post(
            f"/api/v1/investigations/{investigation_id}/events",
            json={"source_id": source_id, "event_id": self.event_id},
            headers=self.owner_headers,
        )
        self.assertEqual(event_link.status_code, 201, event_link.text)
        live_timeline = self.client.get(
            f"/api/v1/investigations/{investigation_id}/timeline",
            params={
                "source_id": live_source.json()["id"],
                "start_date": date.today().isoformat(),
                "event_category": "people_movement",
            },
            headers=self.owner_headers,
        )
        self.assertEqual(live_timeline.status_code, 200, live_timeline.text)
        self.assertEqual(live_timeline.json()["items"][0]["event_id"], self.live_event_id)

        timeline = self.client.get(
            f"/api/v1/investigations/{investigation_id}/timeline?track_id=7&limit=2",
            headers=self.owner_headers,
        )
        self.assertEqual(timeline.status_code, 200, timeline.text)
        self.assertEqual(len(timeline.json()["items"]), 2)
        self.assertTrue(timeline.json()["has_more"])
        self.assertTrue(all(item["track_ids"] == [7] for item in timeline.json()["items"]))
        scoped_timeline = self.client.get(
            f"/api/v1/investigations/{investigation_id}/timeline",
            params={"track_id": 7, "source_id": source_id},
            headers=self.owner_headers,
        )
        self.assertEqual(scoped_timeline.status_code, 200, scoped_timeline.text)
        self.assertTrue(all(item["source_id"] == source_id for item in scoped_timeline.json()["items"]))

        graph = self.client.get(
            f"/api/v1/investigations/{investigation_id}/graph",
            headers=self.owner_headers,
        )
        self.assertEqual(graph.status_code, 200, graph.text)
        self.assertTrue(any(node["node_type"] == "person" and "T007" in node["label"] for node in graph.json()["nodes"]))
        self.assertTrue(any(edge["event_id"] == self.event_id for edge in graph.json()["edges"]))
        self.assertEqual(len(graph.json()["edges"]), 3)

        evidence = self.client.get(
            f"/api/v1/investigations/{investigation_id}/evidence?source_id={source_id}",
            headers=self.owner_headers,
        )
        self.assertEqual(evidence.status_code, 200, evidence.text)
        self.assertEqual(evidence.json()[0]["event_id"], self.event_id)
        self.assertTrue(evidence.json()[0]["image_url"].endswith("/image"))

        note = self.client.post(
            f"/api/v1/investigations/{investigation_id}/notes",
            json={
                "content": "Observed entry sequence; verify adjacent camera.",
                "source_id": source_id,
                "investigation_event_id": event_link.json()["id"],
                "timestamp_seconds": 0.5,
            },
            headers=self.owner_headers,
        )
        self.assertEqual(note.status_code, 201, note.text)
        self.assertEqual(note.json()["source"], "user")
        self.assertEqual(note.json()["timestamp_seconds"], 0.5)
        edited = self.client.patch(
            f"/api/v1/investigations/{investigation_id}/notes/{note.json()['id']}",
            json={"content": "Edited investigator note."},
            headers=self.owner_headers,
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["content"], "Edited investigator note.")
        self.assertEqual(edited.json()["source_id"], source_id)
        self.assertEqual(edited.json()["investigation_event_id"], event_link.json()["id"])
        self.assertEqual(
            self.client.delete(
                f"/api/v1/investigations/{investigation_id}/notes/{note.json()['id']}",
                headers=self.owner_headers,
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/investigations/{investigation_id}/notes",
                json={"content": "Retain only while this investigation exists.", "source_id": source_id},
                headers=self.owner_headers,
            ).status_code,
            201,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.owner_headers,
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.owner_headers,
            ).status_code,
            404,
        )

    def test_ownership_empty_state_and_cascading_delete(self) -> None:
        investigation = self._create_investigation()
        investigation_id = investigation["id"]
        empty_timeline = self.client.get(
            f"/api/v1/investigations/{investigation_id}/timeline",
            headers=self.owner_headers,
        )
        self.assertEqual(empty_timeline.status_code, 200, empty_timeline.text)
        self.assertEqual(empty_timeline.json()["items"], [])
        self.assertEqual(empty_timeline.json()["total"], 0)
        owner_source = self.client.post(
            f"/api/v1/investigations/{investigation_id}/sources",
            json={"analysis_id": self.analysis_id},
            headers=self.owner_headers,
        )
        self.assertEqual(owner_source.status_code, 201, owner_source.text)
        source_id = owner_source.json()["id"]
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/investigations/{investigation_id}",
                json={"title": "Unauthorized edit"},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}/tracks",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/investigations/{investigation_id}/tracks",
                json={"source_id": source_id, "track_id": 7},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/investigations/{investigation_id}/events",
                json={"source_id": source_id, "event_id": self.event_id},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        owner_note = self.client.post(
            f"/api/v1/investigations/{investigation_id}/notes",
            json={"content": "Private owner note."},
            headers=self.owner_headers,
        )
        self.assertEqual(owner_note.status_code, 201, owner_note.text)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/investigations/{investigation_id}/notes/{owner_note.json()['id']}",
                json={"content": "Unauthorized note edit."},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/investigations/{investigation_id}/notes/{owner_note.json()['id']}",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}/graph",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}/evidence",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/investigations/{investigation_id}/sources",
                json={"analysis_id": self.analysis_id},
                headers=self.other_headers,
            ).status_code,
            404,
        )
        source_timeline = self.client.get(
            f"/api/v1/investigations/{investigation_id}/timeline",
            headers=self.owner_headers,
        )
        self.assertEqual(source_timeline.status_code, 200, source_timeline.text)
        self.assertGreater(source_timeline.json()["total"], 0)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.owner_headers,
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/investigations/{investigation_id}",
                headers=self.owner_headers,
            ).status_code,
            404,
        )

    def test_large_detection_timeline_is_paginated(self) -> None:
        db = self.SessionLocal()
        try:
            for frame_index in range(250):
                db.add(
                    Detection(
                        analysis_id=self.analysis_id,
                        video_id=self.video_id,
                        frame_index=frame_index + 2,
                        timestamp_seconds=float(frame_index + 2),
                        track_id=7,
                        class_id=0,
                        class_name="person",
                        confidence=0.8,
                        bbox_x1=10,
                        bbox_y1=10,
                        bbox_x2=20,
                        bbox_y2=30,
                    )
                )
            db.commit()
        finally:
            db.close()
        investigation = self._create_investigation()
        source = self.client.post(
            f"/api/v1/investigations/{investigation['id']}/sources",
            json={"analysis_id": self.analysis_id},
            headers=self.owner_headers,
        )
        self.assertEqual(source.status_code, 201, source.text)
        response = self.client.get(
            f"/api/v1/investigations/{investigation['id']}/timeline",
            params={"source_id": source.json()["id"], "event_category": "detection", "limit": 50},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["items"]), 50)
        self.assertEqual(response.json()["total"], 252)
        self.assertTrue(response.json()["has_more"])


if __name__ == "__main__":
    unittest.main()
