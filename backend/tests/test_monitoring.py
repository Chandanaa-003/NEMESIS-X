from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.user import User
from app.models.video import Video


class MonitoringHistoryAndAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_monitoring_test_"))
        self.db_path = self.tmp_dir / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

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
            self.user = User(
                full_name="Monitoring Analyst",
                email="analyst@nemesis-x.test",
                hashed_password=hash_password("Password123!"),
            )
            db.add(self.user)
            db.commit()
            db.refresh(self.user)
            self.headers = {"Authorization": f"Bearer {create_access_token(str(self.user.id))}"}

            # Seed a video
            vid = Video(
                id="vid-test-01",
                user_id=self.user.id,
                original_filename="gate_monitoring_cam1.mp4",
                stored_filename="gate_monitoring_cam1_stored.mp4",
                file_path="/tmp/gate_monitoring_cam1.mp4",
                file_size=1024000,
                mime_type="video/mp4",
                duration_seconds=120.0,
                width=1920,
                height=1080,
                status="completed",
            )
            db.add(vid)

            # Seed a recorded analysis
            self.analysis_id = "an-test-01"
            self.analysis = Analysis(
                id=self.analysis_id,
                video_id=vid.id,
                user_id=self.user.id,
                status="completed",
                progress=100,
                total_frames=120,
                processed_frames=120,
                extracted_frames=120,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(self.analysis)

            # Add tracks to analysis
            t1 = Track(
                analysis_id=self.analysis_id,
                video_id=vid.id,
                track_id=1,
                class_id=0,
                class_name="person",
                first_seen_frame=1,
                last_seen_frame=50,
                first_seen_timestamp=1.0,
                last_seen_timestamp=50.0,
                duration_seconds=49.0,
                frame_count=50,
                avg_confidence=0.88,
                max_confidence=0.95,
            )
            t2 = Track(
                analysis_id=self.analysis_id,
                video_id=vid.id,
                track_id=2,
                class_id=2,
                class_name="car",
                first_seen_frame=10,
                last_seen_frame=60,
                first_seen_timestamp=10.0,
                last_seen_timestamp=60.0,
                duration_seconds=50.0,
                frame_count=50,
                avg_confidence=0.91,
                max_confidence=0.97,
            )
            db.add_all([t1, t2])

            # Add an event to analysis
            evt = Event(
                id="evt-test-01",
                analysis_id=self.analysis_id,
                event_type="person_loitering",
                category="people_movement",
                title="Loitering Person at Gate",
                description="Person remained stationary near gate entrance.",
                explanation_payload={
                    "why_flagged": "Dwell time exceeded 30 seconds threshold.",
                    "observed_sequence": ["Person entered at 1s", "Stationary until 45s"],
                    "requires_human_review": True,
                },
                start_timestamp=1.0,
                end_timestamp=45.0,
                involved_track_ids=[1],
                confidence=0.89,
                severity="high",
                evidence_frame_ids=[],
            )
            db.add(evt)

            # Seed a live monitoring session
            self.live_session_id = "live-test-01"
            self.live_session = LiveSession(
                id=self.live_session_id,
                user_id=self.user.id,
                status="stopped",
                confidence_threshold=0.45,
                image_size=416,
                frames_processed=300,
                total_detections=15,
                unique_tracks_count=4,
                events_discovered_count=1,
                started_at=datetime.now(timezone.utc),
                stopped_at=datetime.now(timezone.utc),
            )
            db.add(self.live_session)

            # Add a live event
            live_evt = LiveEvent(
                id="live-evt-01",
                session_id=self.live_session_id,
                user_id=self.user.id,
                event_type="rapid_motion",
                category="people_movement",
                title="Rapid Motion Detected",
                description="Fast movement observed in live stream.",
                explanation_payload={
                    "why_flagged": "Velocity vector exceeded standard threshold.",
                    "observed_sequence": ["Velocity spike detected at frame 150"],
                },
                timestamp_seconds=15.0,
                start_timestamp=14.0,
                end_timestamp=16.0,
                involved_track_ids=[3],
                confidence=0.82,
                severity="medium",
                frame_index=150,
            )
            db.add(live_evt)

            db.commit()
        finally:
            db.close()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_list_unified_monitoring_history(self) -> None:
        res = self.client.get("/api/v1/monitoring/history", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        session_types = {item["session_type"] for item in data["items"]}
        self.assertEqual(session_types, {"recorded", "live"})

    def test_filter_by_session_type(self) -> None:
        # Recorded only
        res_rec = self.client.get(
            "/api/v1/monitoring/history?session_type=recorded",
            headers=self.headers,
        )
        self.assertEqual(res_rec.status_code, 200)
        data_rec = res_rec.json()
        self.assertEqual(data_rec["total"], 1)
        self.assertEqual(data_rec["items"][0]["session_type"], "recorded")
        self.assertEqual(data_rec["items"][0]["name"], "gate_monitoring_cam1.mp4")

        # Live only
        res_live = self.client.get(
            "/api/v1/monitoring/history?session_type=live",
            headers=self.headers,
        )
        self.assertEqual(res_live.status_code, 200)
        data_live = res_live.json()
        self.assertEqual(data_live["total"], 1)
        self.assertEqual(data_live["items"][0]["session_type"], "live")

    def test_filter_by_priority(self) -> None:
        # High priority only: recorded analysis has 1 high priority event, live has medium
        res_high = self.client.get(
            "/api/v1/monitoring/history?priority=high",
            headers=self.headers,
        )
        self.assertEqual(res_high.status_code, 200)
        data_high = res_high.json()
        self.assertEqual(data_high["total"], 1)
        self.assertEqual(data_high["items"][0]["session_id"], self.analysis_id)

    def test_filter_by_search(self) -> None:
        res_search = self.client.get(
            "/api/v1/monitoring/history?search=gate_monitoring",
            headers=self.headers,
        )
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.json()
        self.assertEqual(data_search["total"], 1)
        self.assertEqual(data_search["items"][0]["session_id"], self.analysis_id)

    def test_pagination(self) -> None:
        res = self.client.get(
            "/api/v1/monitoring/history?page=1&page_size=1",
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["total_pages"], 2)
        self.assertEqual(data["page"], 1)
        self.assertEqual(len(data["items"]), 1)

    def test_intelligence_analytics(self) -> None:
        res = self.client.get("/api/v1/monitoring/analytics", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        analytics = res.json()
        self.assertEqual(analytics["total_sessions"], 2)
        self.assertEqual(analytics["recorded_sessions_count"], 1)
        self.assertEqual(analytics["live_sessions_count"], 1)
        self.assertEqual(analytics["completed_analyses_count"], 1)
        self.assertEqual(analytics["failed_analyses_count"], 0)
        self.assertEqual(analytics["total_events"], 2)
        self.assertEqual(analytics["high_priority_events"], 1)
        self.assertEqual(analytics["medium_priority_events"], 1)
        self.assertIn("people_movement", analytics["events_by_category"])
        self.assertTrue(len(analytics["top_object_classes"]) > 0)
        class_names = [c["class_name"] for c in analytics["top_object_classes"]]
        self.assertIn("person", class_names)
        self.assertTrue(len(analytics["timeline_trends"]) > 0)

    def test_analytics_invalid_date_range(self) -> None:
        res = self.client.get(
            "/api/v1/monitoring/analytics?date_from=2026-12-31T00:00:00Z&date_to=2026-01-01T00:00:00Z",
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 400)

    def test_analytics_user_isolation_and_empty_state(self) -> None:
        db = self.SessionLocal()
        try:
            other = User(
                full_name="Other Analyst",
                email="other@nemesis-x.test",
                hashed_password=hash_password("Password123!"),
            )
            db.add(other)
            db.commit()
            db.refresh(other)
            other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}
        finally:
            db.close()

        res = self.client.get("/api/v1/monitoring/analytics", headers=other_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_sessions"], 0)
        self.assertEqual(data["recorded_sessions_count"], 0)
        self.assertEqual(data["live_sessions_count"], 0)
        self.assertEqual(data["total_events"], 0)
        self.assertEqual(data["avg_processing_duration_seconds"], 0.0)

    def test_unified_session_detail_recorded(self) -> None:
        res = self.client.get(
            f"/api/v1/monitoring/sessions/{self.analysis_id}",
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        detail = res.json()
        self.assertEqual(detail["session_id"], self.analysis_id)
        self.assertEqual(detail["session_type"], "recorded")
        self.assertEqual(detail["name"], "gate_monitoring_cam1.mp4")
        self.assertEqual(len(detail["events"]), 1)
        self.assertEqual(detail["events"][0]["title"], "Loitering Person at Gate")
        self.assertEqual(detail["events"][0]["involved_track_ids"], [1])
        self.assertTrue("pdf_report_url" in detail)
        self.assertTrue("ai_explanation_summary" in detail)

    def test_unified_session_detail_live(self) -> None:
        res = self.client.get(
            f"/api/v1/monitoring/sessions/{self.live_session_id}",
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        detail = res.json()
        self.assertEqual(detail["session_id"], self.live_session_id)
        self.assertEqual(detail["session_type"], "live")
        self.assertEqual(len(detail["events"]), 1)
        self.assertEqual(detail["events"][0]["title"], "Rapid Motion Detected")
        self.assertTrue("pdf_report_url" in detail)
