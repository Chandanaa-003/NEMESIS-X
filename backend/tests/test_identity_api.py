import json
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

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
from app.models.identity import EntityIdentity, IdentityObservation
from app.models.live_session import LiveSession
from app.models.user import User
from app.models.video import Video
from app.schemas.analysis import BoundingBoxInfo
from app.schemas.live import LiveDetectionInfo
from app.services.identity_engine import (
    IdentityMatcher,
    identify_live_detections,
    recognize_recorded_analysis,
)


def _synthetic_person_frame() -> np.ndarray:
    frame = np.full((240, 320, 3), 35, dtype=np.uint8)
    colors = [(0, 0, 220), (220, 0, 0), (0, 210, 0), (0, 210, 210)]
    for row, y in enumerate(range(64, 210, 18)):
        for column, x in enumerate(range(52, 128, 18)):
            frame[y : y + 18, x : x + 18] = colors[(row + column) % len(colors)]
    return frame


def _live_detection(track_id: int) -> LiveDetectionInfo:
    return LiveDetectionInfo(
        track_id=track_id,
        track_code=f"T{track_id:03d}",
        class_id=0,
        class_name="person",
        confidence=0.94,
        bbox=BoundingBoxInfo(x1=40, y1=20, x2=140, y2=220),
    )


class IdentityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_identity_api_"))
        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'identities.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.settings = get_settings()
        self.original_dirs = {
            "identity_evidence_dir": self.settings.identity_evidence_dir,
            "processed_dir": self.settings.processed_dir,
        }
        self.evidence_dir = self.tmp_dir / "identities"
        self.processed_dir = self.tmp_dir / "processed"
        self.settings.identity_evidence_dir = str(self.evidence_dir)
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
                full_name="Identity Owner",
                email="identity-owner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            other = User(
                full_name="Identity Other",
                email="identity-other@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([owner, other])
            db.commit()
            db.refresh(owner)
            db.refresh(other)
            self.owner_id = owner.id
            self.owner_headers = {
                "Authorization": f"Bearer {create_access_token(str(owner.id))}"
            }
            self.other_headers = {
                "Authorization": f"Bearer {create_access_token(str(other.id))}"
            }

            video = Video(
                user_id=owner.id,
                original_filename="identity-test.mp4",
                stored_filename="identity-test.mp4",
                file_path="storage/uploads/identity-test.mp4",
                file_size=1,
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
                total_frames=2,
                processed_frames=2,
                extracted_frames=2,
                sampling_interval=1,
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            self.analysis_id = analysis.id

            self.identity_ids = []
            for identity_number, track_id in ((1, 7), (2, 8)):
                identity_id = str(uuid.uuid4())
                identity = EntityIdentity(
                    id=identity_id,
                    user_id=owner.id,
                    source_type="analysis",
                    source_id=analysis.id,
                    analysis_id=analysis.id,
                    identity_code=f"P{identity_number:03d}",
                    entity_type="person",
                    category="person",
                    class_name="person",
                    status="probable",
                    first_seen_timestamp=float(track_id),
                    last_seen_timestamp=float(track_id + 1),
                    appearance_count=1,
                    descriptor_sample_count=1,
                    associated_track_ids=[track_id],
                    appearance_signature={
                        "histogram": [1.0] + [0.0] * 31,
                        "quality": 0.9,
                        "distinctiveness": 0.8,
                        "aspect_ratio": 0.4,
                    },
                    appearance_descriptor={
                        "histogram": [1.0] + [0.0] * 31,
                        "quality": 0.9,
                        "distinctiveness": 0.8,
                        "aspect_ratio": 0.4,
                    },
                    feature_reference="hsv_color_shape_v1",
                    matching_confidence=0.9,
                    matching_explanation="Synthetic test fixture.",
                    evidence_refs=[],
                )
                db.add(identity)
                db.add(
                    IdentityObservation(
                        identity_id=identity_id,
                        user_id=owner.id,
                        source_type="analysis",
                        source_id=analysis.id,
                        track_id=track_id,
                        class_name="person",
                        first_seen_timestamp=float(track_id),
                        last_seen_timestamp=float(track_id + 1),
                        detection_count=2,
                        match_confidence=0.9,
                        feature_quality=0.9,
                        matching_explanation="Synthetic test fixture.",
                        bbox={"x1": 1.0, "y1": 1.0, "x2": 20.0, "y2": 40.0},
                    )
                )
                self.identity_ids.append(identity_id)
            db.commit()
        finally:
            db.close()

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.engine.dispose()
        for key, value in self.original_dirs.items():
            setattr(self.settings, key, value)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_owner_can_search_source_and_get_counts(self) -> None:
        search = self.client.get(
            "/api/v1/identities",
            params={"source_type": "analysis", "source_id": self.analysis_id},
            headers=self.owner_headers,
        )
        counts = self.client.get(
            "/api/v1/identities/counts",
            params={"source_type": "analysis", "source_id": self.analysis_id},
            headers=self.owner_headers,
        )

        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["total_unique_people"], 2)
        self.assertEqual(search.json()["total_unique_objects"], 0)
        self.assertEqual(counts.status_code, 200)
        self.assertEqual(counts.json()["unique_people"], 2)

    def test_identity_source_and_evidence_are_owner_scoped(self) -> None:
        foreign_search = self.client.get(
            "/api/v1/identities",
            params={"source_type": "analysis", "source_id": self.analysis_id},
            headers=self.other_headers,
        )
        evidence_file = (
            self.evidence_dir
            / "analysis"
            / self.analysis_id
            / "track_7.jpg"
        )
        evidence_file.parent.mkdir(parents=True)
        evidence_file.write_bytes(b"synthetic evidence")
        db = self.SessionLocal()
        try:
            observation = (
                db.query(IdentityObservation)
                .filter(IdentityObservation.track_id == 7)
                .one()
            )
            observation.evidence_path = str(evidence_file)
            db.commit()
        finally:
            db.close()

        owner_evidence = self.client.get(
            f"/api/v1/identities/{self.identity_ids[0]}/tracks/7/evidence",
            headers=self.owner_headers,
        )
        foreign_evidence = self.client.get(
            f"/api/v1/identities/{self.identity_ids[0]}/tracks/7/evidence",
            headers=self.other_headers,
        )

        self.assertEqual(foreign_search.status_code, 404)
        self.assertEqual(owner_evidence.status_code, 200)
        self.assertEqual(owner_evidence.content, b"synthetic evidence")
        self.assertEqual(foreign_evidence.status_code, 404)

    def test_legacy_correction_can_split_a_track_into_a_new_identity(self) -> None:
        response = self.client.patch(
            f"/api/v1/identities/{self.identity_ids[0]}/tracks/7",
            headers=self.owner_headers,
            json={
                "create_new_identity": True,
                "correction_note": "Reviewed separately by the operator.",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["corrected_track_id"], 7)
        self.assertEqual(response.json()["identity"]["identity_code"], "P003")
        self.assertEqual(response.json()["identity"]["status"], "confirmed", response.text)
        counts = self.client.get(
            "/api/v1/identities/counts",
            params={"source_type": "analysis", "source_id": self.analysis_id},
            headers=self.owner_headers,
        )
        self.assertEqual(counts.json()["unique_people"], 2)

    def test_owner_can_reassign_track_to_existing_identity(self) -> None:
        response = self.client.patch(
            f"/api/v1/identities/{self.identity_ids[0]}/observations/7",
            headers=self.owner_headers,
            json={"target_identity_id": self.identity_ids[1]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["identity"]["identity_code"], "P002")
        self.assertEqual(response.json()["identity"]["associated_track_ids"], [7, 8])
        counts = self.client.get(
            "/api/v1/identities/counts",
            params={"source_type": "analysis", "source_id": self.analysis_id},
            headers=self.owner_headers,
        )
        self.assertEqual(counts.json()["unique_people"], 1)

    def test_recorded_analysis_links_separate_track_fragments(self) -> None:
        analysis_dir = self.processed_dir / self.analysis_id
        frames_dir = analysis_dir / "frames"
        frames_dir.mkdir(parents=True)
        frame = _synthetic_person_frame()
        frame_records = []
        for index, (track_id, timestamp) in enumerate(((1, 0.0), (8, 10.0))):
            filename = f"frame_{index:04d}.jpg"
            self.assertTrue(cv2.imwrite(str(frames_dir / filename), frame))
            frame_records.append(
                {
                    "frame_index": index,
                    "timestamp_seconds": timestamp,
                    "filename": filename,
                    "frame_width": 320,
                    "frame_height": 240,
                    "detections": [
                        {
                            "track_id": track_id,
                            "class_name": "person",
                            "bbox": {"x1": 40, "y1": 20, "x2": 140, "y2": 220},
                        }
                    ],
                }
            )
        analysis_dir.mkdir(parents=True, exist_ok=True)
        detections_path = analysis_dir / "detections.json"
        tracks_path = analysis_dir / "tracks.json"
        detections_path.write_text(json.dumps({"frames": frame_records}), encoding="utf-8")
        tracks_path.write_text(
            json.dumps({"tracks": [{"track_id": 1}, {"track_id": 8}]}),
            encoding="utf-8",
        )

        db = self.SessionLocal()
        try:
            summary = recognize_recorded_analysis(
                db=db,
                analysis_id=self.analysis_id,
                user_id=self.owner_id,
                analysis_dir=analysis_dir,
            )
            updated_detections = json.loads(detections_path.read_text(encoding="utf-8"))
            identities = db.query(EntityIdentity).filter_by(source_id=self.analysis_id).all()
            observations = (
                db.query(IdentityObservation)
                .filter_by(source_id=self.analysis_id)
                .order_by(IdentityObservation.track_id)
                .all()
            )

            self.assertEqual(summary["total_unique_people"], 1)
            self.assertEqual(len(identities), 1)
            self.assertEqual(identities[0].identity_code, "P001")
            self.assertEqual([row.track_id for row in observations], [1, 8])
            self.assertEqual(
                updated_detections["frames"][1]["detections"][0]["identity_code"],
                "P001",
            )
        finally:
            db.close()

    def test_live_session_links_returning_track_and_persists_identity(self) -> None:
        db = self.SessionLocal()
        try:
            live_session = LiveSession(user_id=self.owner_id, status="active")
            db.add(live_session)
            db.commit()
            db.refresh(live_session)
            matcher = IdentityMatcher("live_session", live_session.id)
            frame = _synthetic_person_frame()
            first = _live_detection(3)
            identify_live_detections(
                db=db,
                matcher=matcher,
                session_id=live_session.id,
                user_id=self.owner_id,
                frame=frame,
                frame_index=0,
                timestamp=0.0,
                detections=[first],
            )
            db.commit()
            returning = _live_detection(9)
            identify_live_detections(
                db=db,
                matcher=matcher,
                session_id=live_session.id,
                user_id=self.owner_id,
                frame=frame,
                frame_index=10,
                timestamp=10.0,
                detections=[returning],
            )
            db.commit()
            observations = (
                db.query(IdentityObservation)
                .filter_by(source_id=live_session.id)
                .order_by(IdentityObservation.track_id)
                .all()
            )

            self.assertEqual(first.identity_code, "P001")
            self.assertEqual(returning.identity_code, "P001")
            self.assertEqual([row.track_id for row in observations], [3, 9])
            self.assertEqual(len(matcher.profiles), 1)
        finally:
            db.close()

    def test_simultaneous_live_people_receive_distinct_identity_ids(self) -> None:
        db = self.SessionLocal()
        try:
            live_session = LiveSession(user_id=self.owner_id, status="active")
            db.add(live_session)
            db.commit()
            db.refresh(live_session)
            matcher = IdentityMatcher("live_session", live_session.id)
            detections = [_live_detection(3), _live_detection(4)]
            identify_live_detections(
                db=db,
                matcher=matcher,
                session_id=live_session.id,
                user_id=self.owner_id,
                frame=_synthetic_person_frame(),
                frame_index=0,
                timestamp=0.0,
                detections=detections,
            )

            self.assertEqual([item.identity_code for item in detections], ["P001", "P002"])
            self.assertEqual(len(matcher.profiles), 2)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()