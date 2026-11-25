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
from app.models.detection import Detection
from app.models.event import Event
from app.models.track import Track
from app.models.user import User
from app.models.video import Video
from app.services.intelligence_search import parse_search_query


class IntelligenceSearchParserTests(unittest.TestCase):
    def test_supported_query_examples_are_parsed_deterministically(self) -> None:
        cases = {
            "Find when a person approached a backpack": (None, "person", "object_interactions"),
            "Show possible pickup events": (None, None, "object_interactions"),
            "Find objects left stationary": (None, None, "possible_unattended_objects"),
            "When did P001 enter the restricted zone?": ("person", None, "people_movement"),
            "Show all interactions involving O001": ("object", None, "object_interactions"),
            "Find unusual movement sequences": (None, None, "people_movement"),
        }
        for query, (role, class_name, category) in cases.items():
            with self.subTest(query=query):
                parsed = parse_search_query(query)
                self.assertTrue(parsed.supported)
                if role:
                    self.assertEqual(parsed.track_role, role)
                if class_name:
                    self.assertIn(class_name, parsed.class_terms)
                if category:
                    self.assertIn(category, parsed.event_categories)
                if query == "Find when a person approached a backpack":
                    self.assertIn("backpack", parsed.class_terms)

    def test_time_range_and_unknown_query(self) -> None:
        parsed = parse_search_query("Show events between 00:01:00 and 00:02:00")
        self.assertEqual(parsed.start_seconds, 60)
        self.assertEqual(parsed.end_seconds, 120)
        self.assertIn("traffic light", parse_search_query("Find traffic lights").class_terms)
        self.assertFalse(parse_search_query("explain the meaning of life").supported)


class IntelligenceSearchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_search_test_"))
        self.processed_dir = self.tmp_dir / "processed"
        self.processed_dir.mkdir()
        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'search.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.settings = get_settings()
        self.original_processed_dir = self.settings.processed_dir
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
            owner = User(
                full_name="Search Owner",
                email="search-owner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            other = User(
                full_name="Search Other",
                email="search-other@example.com",
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
                original_filename="search-source.mp4",
                stored_filename="search-source.mp4",
                file_path="storage/uploads/search-source.mp4",
                file_size=20,
                mime_type="video/mp4",
                status="completed",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            analysis = Analysis(
                video_id=video.id,
                user_id=owner.id,
                status="completed",
                progress=100,
                total_frames=1,
                processed_frames=1,
                extracted_frames=1,
                sampling_interval=1,
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            self.analysis_id = analysis.id

            for track_id, class_id, class_name in ((7, 0, "person"), (8, 24, "backpack")):
                db.add(
                    Track(
                        analysis_id=analysis.id,
                        video_id=video.id,
                        track_id=track_id,
                        class_id=class_id,
                        class_name=class_name,
                        first_seen_frame=0,
                        last_seen_frame=0,
                        first_seen_timestamp=1.0,
                        last_seen_timestamp=1.0,
                        duration_seconds=0.0,
                        frame_count=1,
                        avg_confidence=0.9,
                        max_confidence=0.9,
                    )
                )
                db.add(
                    Detection(
                        analysis_id=analysis.id,
                        video_id=video.id,
                        frame_index=0,
                        timestamp_seconds=1.0,
                        track_id=track_id,
                        class_id=class_id,
                        class_name=class_name,
                        confidence=0.9,
                        bbox_x1=10.0,
                        bbox_y1=10.0,
                        bbox_x2=20.0,
                        bbox_y2=30.0,
                    )
                )
            db.add(
                Event(
                    analysis_id=analysis.id,
                    event_type="person_object_interaction",
                    category="object_interactions",
                    title="Possible person-object interaction",
                    description="Person T007 approached backpack O008.",
                    explanation_payload={"person_track_id": 7, "object_track_id": 8},
                    start_timestamp=1.0,
                    end_timestamp=2.0,
                    involved_track_ids=[7],
                    confidence=0.85,
                    severity="medium",
                    evidence_frame_ids=[0],
                )
            )
            db.add(
                Event(
                    analysis_id=analysis.id,
                    event_type="person_zone_entry",
                    category="people_movement",
                    title="Person entered zone",
                    description="Person T007 entered the configured zone.",
                    explanation_payload={"person_track_id": 7},
                    start_timestamp=3.0,
                    end_timestamp=3.0,
                    involved_track_ids=[7],
                    confidence=0.8,
                    severity="low",
                    evidence_frame_ids=[],
                )
            )
            db.commit()
        finally:
            db.close()

        analysis_dir = self.processed_dir / self.analysis_id
        analysis_dir.mkdir()
        (analysis_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "original_dimensions": {"width": 100, "height": 80},
                    "max_width_applied": 100,
                    "frames": [
                        {
                            "frame_index": 0,
                            "timestamp_seconds": 1.0,
                            "filename": "frame_0000.jpg",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.settings.processed_dir = self.original_processed_dir
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_search_returns_stored_results_with_owned_video_context(self) -> None:
        response = self.client.get(
            "/api/v1/search/intelligence",
            params={"q": "P007 approached backpack"},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["event_id"] for item in payload["results"]))
        self.assertTrue(all(item["analysis_id"] == self.analysis_id for item in payload["results"]))
        event_result = next(item for item in payload["results"] if item["event_id"])
        self.assertIn("/analysis/", event_result["evidence"][0]["image_url"])

    def test_track_search_is_owner_scoped_and_source_local(self) -> None:
        owner_response = self.client.get(
            "/api/v1/search/tracks",
            params={"q": "P007"},
            headers=self.owner_headers,
        )
        other_response = self.client.get(
            "/api/v1/search/tracks",
            params={"q": "P007"},
            headers=self.other_headers,
        )
        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(owner_response.json()["results"][0]["track_code"], "T007")
        object_response = self.client.get(
            "/api/v1/search/tracks",
            params={"q": "O008"},
            headers=self.owner_headers,
        )
        self.assertEqual(object_response.json()["results"][0]["track_code"], "T008")
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.json()["results"], [])

    def test_source_type_mismatch_is_rejected(self) -> None:
        response = self.client.get(
            "/api/v1/search/intelligence",
            params={"analysis_id": self.analysis_id, "source_type": "live_session"},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_event_intent_does_not_return_unrelated_category_matches(self) -> None:
        for query in ("Show possible pickup events", "Find unusual movement sequences"):
            with self.subTest(query=query):
                response = self.client.get(
                    "/api/v1/search/intelligence",
                    params={"q": query},
                    headers=self.owner_headers,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["results"], [])

