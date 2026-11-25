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
from app.models.user import User


class UserSettingsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_settings_test_"))
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
            u1 = User(
                full_name="Voice Tester One",
                email="voice1@example.com",
                hashed_password=hash_password("Password123!"),
            )
            u2 = User(
                full_name="Voice Tester Two",
                email="voice2@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([u1, u2])
            db.commit()
            db.refresh(u1)
            db.refresh(u2)
            self.u1_headers = {"Authorization": f"Bearer {create_access_token(str(u1.id))}"}
            self.u2_headers = {"Authorization": f"Bearer {create_access_token(str(u2.id))}"}
        finally:
            db.close()

    def tearDown(self) -> None:
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_requires_authentication(self) -> None:
        self.assertEqual(self.client.get("/api/v1/settings").status_code, 401)
        self.assertEqual(
            self.client.put(
                "/api/v1/settings",
                json={
                    "voice_language": "english",
                    "voice_alerts_enabled": True,
                    "alert_volume": 0.8,
                },
            ).status_code,
            401,
        )

    def test_get_defaults_and_persist_updates(self) -> None:
        default_resp = self.client.get("/api/v1/settings", headers=self.u1_headers)
        self.assertEqual(default_resp.status_code, 200)
        defaults = default_resp.json()
        self.assertEqual(defaults["voice_language"], "english")
        self.assertTrue(defaults["voice_alerts_enabled"])
        self.assertAlmostEqual(defaults["alert_volume"], 0.85, places=2)

        update_payload = {
            "voice_language": "bilingual",
            "voice_alerts_enabled": False,
            "alert_volume": 0.55,
            "announce_high_priority": True,
            "announce_medium_priority": True,
            "announce_low_priority": False,
            "cooldown_seconds": 45,
        }
        put_resp = self.client.put("/api/v1/settings", json=update_payload, headers=self.u1_headers)
        self.assertEqual(put_resp.status_code, 200)
        updated = put_resp.json()
        self.assertEqual(updated["voice_language"], "bilingual")
        self.assertFalse(updated["voice_alerts_enabled"])
        self.assertAlmostEqual(updated["alert_volume"], 0.55, places=2)
        self.assertFalse(updated["announce_low_priority"])
        self.assertEqual(updated["cooldown_seconds"], 45)

        # Re-read persists and isolates per user
        get_u1 = self.client.get("/api/v1/settings", headers=self.u1_headers).json()
        self.assertEqual(get_u1["voice_language"], "bilingual")
        self.assertFalse(get_u1["voice_alerts_enabled"])

        get_u2 = self.client.get("/api/v1/settings", headers=self.u2_headers).json()
        self.assertEqual(get_u2["voice_language"], "english")
        self.assertTrue(get_u2["voice_alerts_enabled"])

    def test_validation_rejects_invalid_values(self) -> None:
        bad = self.client.put(
            "/api/v1/settings",
            json={
                "voice_language": "french",
                "voice_alerts_enabled": True,
                "alert_volume": 1.5,
            },
            headers=self.u1_headers,
        )
        self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
