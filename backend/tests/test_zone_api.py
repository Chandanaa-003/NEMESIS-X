import json
from pathlib import Path
import shutil
import tempfile
import unittest

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.analysis import Analysis
from app.models.user import User
from app.models.video import Video


class RecordedZoneApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_zone_api_test_"))
        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'zones.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.settings = get_settings()
        self.original_dirs = {
            "processed_dir": self.settings.processed_dir,
            "evidence_dir": self.settings.evidence_dir,
            "live_dir": self.settings.live_dir,
            "reports_dir": self.settings.reports_dir,
        }
        self.processed_dir = self.tmp_dir / "processed"
        self.evidence_dir = self.tmp_dir / "evidence"
        self.settings.processed_dir = str(self.processed_dir)
        self.settings.evidence_dir = str(self.evidence_dir)
        self.settings.live_dir = str(self.tmp_dir / "live")
        self.settings.reports_dir = str(self.tmp_dir / "reports")

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
                full_name="Zone Owner",
                email="zone-owner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            other = User(
                full_name="Zone Other",
                email="zone-other@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([owner, other])
            db.commit()
            db.refresh(owner)
            db.refresh(other)
            self.owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
            self.other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

            video = Video(
                user_id=owner.id,
                original_filename="synthetic-zone.mp4",
                stored_filename="synthetic-zone.mp4",
                file_path="storage/uploads/synthetic-zone.mp4",
                file_size=1,
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
        finally:
            db.close()

        analysis_dir = self.processed_dir / self.analysis_id
        frames_dir = analysis_dir / "frames"
        frames_dir.mkdir(parents=True)
        frame_image = np.full((100, 100, 3), 110, dtype=np.uint8)
        for frame_index in range(2):
            self.assertTrue(cv2.imwrite(str(frames_dir / f"frame_{frame_index:04d}.jpg"), frame_image))

        metadata_frames = [
            {
                "frame_index": frame_index,
                "source_frame_index": frame_index,
                "timestamp_seconds": float(frame_index),
                "filename": f"frame_{frame_index:04d}.jpg",
            }
            for frame_index in range(2)
        ]
        (analysis_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "analysis_id": self.analysis_id,
                    "original_dimensions": {"width": 100, "height": 100},
                    "max_width_applied": 100,
                    "frames": metadata_frames,
                }
            ),
            encoding="utf-8",
        )
        detection = {
            "track_id": 41,
            "class_id": 0,
            "class_name": "person",
            "confidence": 0.9,
            "bbox": {"x1": 45, "y1": 30, "x2": 55, "y2": 50},
        }
        (analysis_dir / "detections.json").write_text(
            json.dumps(
                {
                    "total_detections": 2,
                    "frames": [
                        {
                            **metadata_frames[index],
                            "frame_width": 100,
                            "frame_height": 100,
                            "detections": [detection],
                        }
                        for index in range(2)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (analysis_dir / "tracks.json").write_text(
            json.dumps(
                {
                    "total_tracks": 1,
                    "tracks": [
                        {
                            "track_id": 41,
                            "class_id": 0,
                            "class_name": "person",
                            "first_seen_frame": 0,
                            "last_seen_frame": 1,
                            "first_seen_timestamp": 0.0,
                            "last_seen_timestamp": 1.0,
                            "duration_seconds": 1.0,
                            "frame_count": 2,
                            "avg_confidence": 0.9,
                            "max_confidence": 0.9,
                            "timeline_points": [
                                {
                                    "frame_index": index,
                                    "timestamp_seconds": float(index),
                                    "center_x": 50,
                                    "center_y": 40,
                                    "confidence": 0.9,
                                }
                                for index in range(2)
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.settings.processed_dir = self.original_dirs["processed_dir"]
        self.settings.evidence_dir = self.original_dirs["evidence_dir"]
        self.settings.live_dir = self.original_dirs["live_dir"]
        self.settings.reports_dir = self.original_dirs["reports_dir"]
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_recorded_zone_discovery_persists_timestamped_events_and_evidence(self) -> None:
        zone_response = self.client.post(
            "/api/v1/zones",
            json={
                "video_id": self.video_id,
                "name": "Center aisle",
                "zone_type": "monitoring",
                "polygon": [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]],
                "settings": {
                    "confirmation_frames": 2,
                    "cooldown_seconds": 0,
                    "loiter_seconds": 10,
                    "restricted_group_threshold": 2,
                    "alerts_enabled": True,
                    "voice_alerts_enabled": True,
                },
            },
            headers=self.owner_headers,
        )
        self.assertEqual(zone_response.status_code, 201)
        zone_id = zone_response.json()["id"]

        discovered = self.client.post(
            f"/api/v1/analysis/{self.analysis_id}/discover-events",
            headers=self.owner_headers,
        )
        self.assertEqual(discovered.status_code, 200, discovered.text)
        event = next(
            item
            for item in discovered.json()["events"]
            if item["event_type"] == "person_zone_entry"
        )
        self.assertEqual(event["explanation"]["zone_id"], zone_id)
        self.assertEqual(event["involved_track_ids"], [41])
        self.assertEqual(event["start_timestamp"], 0.0)
        self.assertEqual(event["evidence_frame_ids"], [0, 1])

        evidence = self.client.get(
            f"/api/v1/events/{event['id']}/evidence",
            headers=self.owner_headers,
        )
        self.assertEqual(evidence.status_code, 200)
        self.assertGreaterEqual(evidence.json()["total_evidence"], 2)
        image_response = self.client.get(
            evidence.json()["evidence"][0]["image_url"],
            headers=self.owner_headers,
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertTrue(image_response.content.startswith(b"\xff\xd8"))

        zone_events = self.client.get(
            f"/api/v1/zones/analysis/{self.analysis_id}/events",
            headers=self.owner_headers,
        )
        self.assertEqual(zone_events.status_code, 200)
        self.assertEqual(zone_events.json()[0]["zone_id"], zone_id)
        activity = self.client.get(
            f"/api/v1/zones/analysis/{self.analysis_id}/activity",
            headers=self.owner_headers,
        )
        self.assertEqual(activity.status_code, 200)
        self.assertEqual(activity.json()["total_events"], 1)
        self.assertEqual(
            self.client.post(
                f"/api/v1/analysis/{self.analysis_id}/discover-events",
                headers=self.other_headers,
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
