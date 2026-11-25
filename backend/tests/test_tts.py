from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.user import User
from app.services import tts_service


class KannadaTtsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_tts_test_"))
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
            user = User(
                full_name="Kannada Voice Tester",
                email="kn_tester@nemesis-x.test",
                hashed_password=hash_password("Password123!"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        finally:
            db.close()

        # Reset tts_service caches between tests
        tts_service._memory_cache.clear()
        tts_service._discovered_voice_cache = None

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_status_when_offline_or_package_missing(self) -> None:
        with patch.object(tts_service, "edge_tts", None):
            res = self.client.get("/api/v1/tts/kannada/status", headers=self.headers)
            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertFalse(body["available"])
            self.assertTrue(body["internet_required"])
            self.assertEqual(body["kannada_voices"], [])

    def test_synthesize_returns_503_when_offline(self) -> None:
        mock_edge = MagicMock()
        mock_edge.list_voices = AsyncMock(side_effect=OSError("Network unreachable"))

        with patch.object(tts_service, "edge_tts", mock_edge):
            res = self.client.post(
                "/api/v1/tts/kannada",
                json={"text": "ಗಮನಿಸಿ. ಚಟುವಟಿಕೆ ಪತ್ತೆಯಾಗಿದೆ."},
                headers=self.headers,
            )
            self.assertEqual(res.status_code, 503)
            self.assertIn("internet required", res.json()["detail"].lower())

    def test_dynamic_voice_discovery_and_caching(self) -> None:
        mock_edge = MagicMock()
        mock_edge.list_voices = AsyncMock(
            return_value=[
                {"ShortName": "en-US-AriaNeural", "FriendlyName": "Aria", "Locale": "en-US", "Gender": "Female"},
                {"ShortName": "kn-IN-SapnaNeural", "FriendlyName": "Sapna", "Locale": "kn-IN", "Gender": "Female"},
            ]
        )

        class FakeCommunicate:
            def __init__(self, text: str, voice: str) -> None:
                self.text = text
                self.voice = voice

            async def stream(self):
                yield {"type": "audio", "data": b"FAKE_MP3_BYTES_123"}

        mock_edge.Communicate = FakeCommunicate

        with patch.object(tts_service, "edge_tts", mock_edge), patch.object(
            tts_service, "_CACHE_DIR", self.tmp_dir / "tts_cache"
        ):
            # 1. Status check discovers kn-IN dynamically
            st = self.client.get("/api/v1/tts/kannada/status", headers=self.headers)
            self.assertEqual(st.status_code, 200)
            self.assertTrue(st.json()["available"])
            self.assertEqual(st.json()["selected_voice"], "kn-IN-SapnaNeural")

            # 2. First synthesis (cache miss)
            r1 = self.client.post(
                "/api/v1/tts/kannada",
                json={"text": "ಸಂಭಾವ್ಯ ವಸ್ತು ಎತ್ತುವಿಕೆ ಪತ್ತೆಯಾಗಿದೆ."},
                headers=self.headers,
            )
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(r1.headers["content-type"], "audio/mpeg")
            self.assertEqual(r1.headers["x-tts-voice"], "kn-IN-SapnaNeural")
            self.assertEqual(r1.headers["x-tts-cached"], "false")
            self.assertEqual(r1.content, b"FAKE_MP3_BYTES_123")

            # 3. Second synthesis of same text (cache hit)
            r2 = self.client.post(
                "/api/v1/tts/kannada",
                json={"text": "ಸಂಭಾವ್ಯ ವಸ್ತು ಎತ್ತುವಿಕೆ ಪತ್ತೆಯಾಗಿದೆ."},
                headers=self.headers,
            )
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(r2.headers["x-tts-cached"], "true")
            self.assertEqual(r2.content, b"FAKE_MP3_BYTES_123")
