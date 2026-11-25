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
from app.models.identity import EntityIdentity, IdentityTrackAssociation
from app.models.live_session import LiveSession
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.video import Video


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
        self.original_live_dir = self.settings.live_dir
        self.settings.live_dir = str(self.tmp_dir / "live")
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
            self.owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
            self.other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}
            video = Video(
                user_id=owner.id,
                original_filename="identity-source.mp4",
                stored_filename="identity-source.mp4",
                file_path="storage/uploads/identity-source.mp4",
                file_size=1,
                mime_type="video/mp4",
                status="completed",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            self.analysis = Analysis(
                video_id=video.id,
                user_id=owner.id,
                status="completed",
                progress=100,
                total_frames=2,
                processed_frames=2,
                extracted_frames=2,
            )
            self.live_session = LiveSession(user_id=owner.id, status="stopped")
            db.add_all([self.analysis, self.live_session])
            db.commit()
            db.refresh(self.analysis)
            db.refresh(self.live_session)
            self.analysis_id = self.analysis.id
            first = EntityIdentity(
                user_id=owner.id,
                source_type="analysis",
                source_id=self.analysis_id,
                analysis_id=self.analysis_id,
                identity_code="P001",
                entity_type="person",
                category="person",
                first_seen_timestamp=0,
                last_seen_timestamp=4,
                appearance_count=1,
                descriptor_sample_count=0,
                status="unknown",
                appearance_descriptor=None,
                evidence_refs=[],
                matching_explanation="First track in the source.",
            )
            second = EntityIdentity(
                user_id=owner.id,
                source_type="analysis",
                source_id=self.analysis_id,
                analysis_id=self.analysis_id,
                identity_code="P002",
                entity_type="person",
                category="person",
                first_seen_timestamp=8,
                last_seen_timestamp=10,
                appearance_count=1,
                descriptor_sample_count=0,
                status="unknown",
                appearance_descriptor=None,
                evidence_refs=[],
                matching_explanation="No automatic match was made.",
            )
            db.add_all([first, second])
            db.flush()
            self.first_identity_id = first.id
            self.second_identity_id = second.id
            db.add_all(
                [
                    self._association(first, 1, 0, 4),
                    self._association(second, 2, 8, 10),
                ]
            )
            db.commit()
        finally:
            db.close()

    def _association(
        self,
        identity: EntityIdentity,
        track_id: int,
        first_seen: float,
        last_seen: float,
    ) -> IdentityTrackAssociation:
        return IdentityTrackAssociation(
            identity_id=identity.id,
            source_type="analysis",
            source_id=self.analysis_id,
            track_id=track_id,
            category="person",
            first_seen_timestamp=first_seen,
            last_seen_timestamp=last_seen,
            detection_count=3,
            descriptor_sample_count=0,
            appearance_descriptor=None,
            match_status="unknown",
            matching_explanation="No appearance descriptor was available.",
        )

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        self.settings.live_dir = self.original_live_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_search_counts_and_manual_track_correction_are_source_scoped(self) -> None:
        params = {"source_type": "analysis", "source_id": self.analysis_id}
        response = self.client.get(
            "/api/v1/identities",
            params={**params, "query": "T002"},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["identity_code"], "P002")

        counts = self.client.get(
            "/api/v1/identities/counts",
            params=params,
            headers=self.owner_headers,
        )
        self.assertEqual(counts.status_code, 200)
        self.assertEqual(counts.json()["unique_people"], 2)

        correction = self.client.patch(
            f"/api/v1/identities/{self.second_identity_id}/tracks/2",
            headers=self.owner_headers,
            json={
                "target_identity_id": self.first_identity_id,
                "correction_note": "Reviewed source evidence.",
            },
        )
        self.assertEqual(correction.status_code, 200)
        corrected = correction.json()
        self.assertEqual(corrected["identity_code"], "P001")
        corrected_track = next(
            item for item in corrected["track_appearances"] if item["track_code"] == "T002"
        )
        self.assertTrue(corrected_track["manually_corrected"])

        foreign = self.client.get(
            f"/api/v1/identities/{self.first_identity_id}",
            headers=self.other_headers,
        )
        self.assertEqual(foreign.status_code, 404)


if __name__ == "__main__":
    unittest.main()
