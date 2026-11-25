import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.user import User
from app.models.video import Video


class TrackExplorerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_track_explorer_test_"))
        self.upload_dir = self.tmp_dir / "uploads"
        self.processed_dir = self.tmp_dir / "processed"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.tmp_dir / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.settings = get_settings()
        self._orig_upload_dir = self.settings.upload_dir
        self._orig_processed_dir = self.settings.processed_dir
        self.settings.upload_dir = str(self.upload_dir)
        self.settings.processed_dir = str(self.processed_dir)

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
            self.owner = User(
                full_name="Owner User",
                email="owner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            self.other = User(
                full_name="Other User",
                email="other@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([self.owner, self.other])
            db.commit()
            db.refresh(self.owner)
            db.refresh(self.other)
            self.owner_id = self.owner.id
            self.other_id = self.other.id

            self.video_id = "vid-track-test-001"
            self.analysis_id = "ana-track-test-001"
            self.empty_analysis_id = "ana-track-empty-002"

            sample_mp4 = self.upload_dir / "sample_test.mp4"
            sample_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

            video = Video(
                id=self.video_id,
                user_id=self.owner.id,
                original_filename="sample_test.mp4",
                stored_filename="sample_test.mp4",
                file_path="storage/uploads/sample_test.mp4",
                file_size=sample_mp4.stat().st_size,
                mime_type="video/mp4",
                duration_seconds=10.0,
                width=640,
                height=360,
                status="completed",
            )
            db.add(video)

            analysis = Analysis(
                id=self.analysis_id,
                video_id=self.video_id,
                user_id=self.owner.id,
                status="completed",
                progress=100,
                total_frames=300,
                processed_frames=300,
                extracted_frames=3,
                sampling_interval=30,
            )
            empty_analysis = Analysis(
                id=self.empty_analysis_id,
                video_id=self.video_id,
                user_id=self.owner.id,
                status="completed",
                progress=100,
                total_frames=60,
                processed_frames=60,
                extracted_frames=2,
                sampling_interval=30,
            )
            db.add_all([analysis, empty_analysis])

            evt = Event(
                id="evt-track-001",
                analysis_id=self.analysis_id,
                event_type="person_entering",
                category="people_movement",
                title="Person T001 entered camera view",
                description="Observed tracked person T001 appearing at 00:00:01.",
                explanation_payload={"observed_sequence": ["Entered"], "why_flagged": "Rule 1"},
                start_timestamp=1.0,
                end_timestamp=1.0,
                involved_track_ids=[1],
                confidence=0.85,
                severity="low",
                evidence_frame_ids=[0],
            )
            db.add(evt)
            db.commit()
        finally:
            db.close()

        # Populate processed JSON and leave frame_0001.jpg missing to verify graceful handling
        a_dir = self.processed_dir / self.analysis_id
        frames_dir = a_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        (frames_dir / "frame_0000.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        (frames_dir / "frame_0002.jpg").write_bytes(b"\xff\xd8\xff\xd9")

        (a_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "analysis_id": self.analysis_id,
                    "frames": [
                        {"frame_index": 0, "source_frame_index": 0, "timestamp_seconds": 1.0, "filename": "frame_0000.jpg"},
                        {"frame_index": 1, "source_frame_index": 30, "timestamp_seconds": 2.5, "filename": "frame_0001.jpg"},
                        {"frame_index": 2, "source_frame_index": 60, "timestamp_seconds": 4.0, "filename": "frame_0002.jpg"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (a_dir / "detections.json").write_text(
            json.dumps(
                {
                    "analysis_id": self.analysis_id,
                    "total_detections": 4,
                    "frames": [
                        {
                            "frame_index": 0,
                            "source_frame_index": 0,
                            "timestamp_seconds": 1.0,
                            "filename": "frame_0000.jpg",
                            "frame_width": 640,
                            "frame_height": 360,
                            "detections": [
                                {"track_id": 1, "class_id": 0, "class_name": "person", "confidence": 0.91, "bbox": {"x1": 100, "y1": 50, "x2": 180, "y2": 250}},
                                {"track_id": 2, "class_id": 24, "class_name": "backpack", "confidence": 0.78, "bbox": {"x1": 300, "y1": 180, "x2": 360, "y2": 260}},
                            ],
                        },
                        {
                            "frame_index": 1,
                            "source_frame_index": 30,
                            "timestamp_seconds": 2.5,
                            "filename": "frame_0001.jpg",
                            "frame_width": 640,
                            "frame_height": 360,
                            "detections": [
                                {"track_id": 1, "class_id": 0, "class_name": "person", "confidence": 0.89, "bbox": {"x1": 160, "y1": 55, "x2": 240, "y2": 255}},
                            ],
                        },
                        {
                            "frame_index": 2,
                            "source_frame_index": 60,
                            "timestamp_seconds": 4.0,
                            "filename": "frame_0002.jpg",
                            "frame_width": 640,
                            "frame_height": 360,
                            "detections": [
                                {"track_id": 1, "class_id": 0, "class_name": "person", "confidence": 0.93, "bbox": {"x1": 220, "y1": 60, "x2": 300, "y2": 260}},
                            ],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (a_dir / "tracks.json").write_text(
            json.dumps(
                {
                    "analysis_id": self.analysis_id,
                    "total_tracks": 2,
                    "tracks_by_class": {"person": 1, "backpack": 1},
                    "tracks": [
                        {
                            "track_id": 1,
                            "class_id": 0,
                            "class_name": "person",
                            "first_seen_frame": 0,
                            "last_seen_frame": 2,
                            "first_seen_timestamp": 1.0,
                            "last_seen_timestamp": 4.0,
                            "duration_seconds": 3.0,
                            "frame_count": 3,
                            "avg_confidence": 0.91,
                            "max_confidence": 0.93,
                            "timeline_points": [
                                {"frame_index": 0, "timestamp_seconds": 1.0, "center_x": 140.0, "center_y": 150.0, "confidence": 0.91, "bbox": {"x1": 100, "y1": 50, "x2": 180, "y2": 250}},
                                {"frame_index": 1, "timestamp_seconds": 2.5, "center_x": 200.0, "center_y": 155.0, "confidence": 0.89, "bbox": {"x1": 160, "y1": 55, "x2": 240, "y2": 255}},
                                {"frame_index": 2, "timestamp_seconds": 4.0, "center_x": 260.0, "center_y": 160.0, "confidence": 0.93, "bbox": {"x1": 220, "y1": 60, "x2": 300, "y2": 260}},
                            ],
                        },
                        {
                            "track_id": 2,
                            "class_id": 24,
                            "class_name": "backpack",
                            "first_seen_frame": 0,
                            "last_seen_frame": 0,
                            "first_seen_timestamp": 1.0,
                            "last_seen_timestamp": 1.0,
                            "duration_seconds": 0.0,
                            "frame_count": 1,
                            "avg_confidence": 0.78,
                            "max_confidence": 0.78,
                            "timeline_points": [
                                {"frame_index": 0, "timestamp_seconds": 1.0, "center_x": 330.0, "center_y": 220.0, "confidence": 0.78, "bbox": {"x1": 300, "y1": 180, "x2": 360, "y2": 260}},
                            ],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        self.owner_headers = {"Authorization": f"Bearer {create_access_token(str(self.owner_id))}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token(str(self.other_id))}"}

    def tearDown(self) -> None:
        self.settings.upload_dir = self._orig_upload_dir
        self.settings.processed_dir = self._orig_processed_dir
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_multiple_tracks_listed(self) -> None:
        resp = self.client.get(f"/api/v1/analysis/{self.analysis_id}/tracks", headers=self.owner_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["tracks"]), 2)
        self.assertEqual(data["tracks"][0]["track_code"], "T001")
        self.assertEqual(data["tracks"][1]["track_code"], "T002")
        self.assertEqual(data["tracks"][0]["last_known_position"]["center_x"], 260.0)

    def test_track_detail_and_frames_accuracy(self) -> None:
        detail_resp = self.client.get(
            f"/api/v1/analysis/{self.analysis_id}/tracks/1",
            headers=self.owner_headers,
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.json()
        self.assertEqual(detail["track_code"], "T001")
        self.assertEqual(len(detail["movement_history"]["steps"]), 2)
        self.assertEqual(detail["movement_history"]["steps"][0]["delta_x"], 60.0)
        self.assertEqual(len(detail["related_events"]), 1)
        self.assertEqual(detail["related_events"][0]["id"], "evt-track-001")

        frames_resp = self.client.get(
            f"/api/v1/analysis/{self.analysis_id}/tracks/1/frames",
            headers=self.owner_headers,
        )
        self.assertEqual(frames_resp.status_code, 200)
        frames_payload = frames_resp.json()
        self.assertEqual(frames_payload["total_observations"], 3)
        frames = frames_payload["frames"]
        self.assertEqual([f["timestamp_seconds"] for f in frames], [1.0, 2.5, 4.0])
        self.assertEqual(frames[0]["selected_detection"]["track_id"], 1)
        self.assertEqual(frames[0]["selected_detection"]["bbox"], {"x1": 100.0, "y1": 50.0, "x2": 180.0, "y2": 250.0})
        self.assertEqual(len(frames[0]["other_detections"]), 1)
        self.assertEqual(frames[0]["other_detections"][0]["track_id"], 2)
        # Missing JPEG handled gracefully
        self.assertTrue(frames[0]["frame_available"])
        self.assertFalse(frames[1]["frame_available"])
        self.assertTrue(frames[2]["frame_available"])

    def test_video_stream_and_empty_states(self) -> None:
        stream_resp = self.client.get(f"/api/v1/videos/{self.video_id}/stream", headers=self.owner_headers)
        self.assertEqual(stream_resp.status_code, 200)
        self.assertTrue(stream_resp.content.startswith(b"\x00\x00\x00\x18ftypmp42"))

        empty_resp = self.client.get(
            f"/api/v1/analysis/{self.empty_analysis_id}/tracks",
            headers=self.owner_headers,
        )
        self.assertEqual(empty_resp.status_code, 200)
        self.assertEqual(empty_resp.json()["tracks"], [])

        missing_track = self.client.get(
            f"/api/v1/analysis/{self.analysis_id}/tracks/999",
            headers=self.owner_headers,
        )
        self.assertEqual(missing_track.status_code, 404)

    def test_unauthorized_access_rejected(self) -> None:
        endpoints = [
            f"/api/v1/analysis/{self.analysis_id}/tracks",
            f"/api/v1/analysis/{self.analysis_id}/tracks/1",
            f"/api/v1/analysis/{self.analysis_id}/tracks/1/frames",
            f"/api/v1/videos/{self.video_id}/stream",
        ]
        for ep in endpoints:
            unauth = self.client.get(ep)
            self.assertEqual(unauth.status_code, 401, msg=f"Expected 401 for {ep}")
            other_user = self.client.get(ep, headers=self.other_headers)
            self.assertEqual(other_user.status_code, 404, msg=f"Expected 404 for {ep}")


if __name__ == "__main__":
    unittest.main()
