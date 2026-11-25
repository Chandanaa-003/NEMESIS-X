import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.user import User
from app.models.video import Video
from app.services.video_playback import (
    FfmpegUnavailableError,
    VideoPlaybackJobManager,
    convert_to_browser_mp4,
    inspect_video,
    is_browser_compatible,
    _ffmpeg_executable,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_video(path: Path, codec: str) -> None:
    ffmpeg = _ffmpeg_executable()
    encoder = "libx265" if codec == "hevc" else "libx264"
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x180:rate=12",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:sample_rate=48000",
        "-t",
        "0.8",
        "-shortest",
        "-c:v",
        encoder,
        "-threads",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-movflags",
        "+faststart",
    ]
    if codec == "hevc":
        command.extend(["-x265-params", "pools=1:frame-threads=1:log-level=error"])
    command.append(str(path))
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise AssertionError(f"Could not create synthetic {codec} test video: {result.stderr}")


class VideoPlaybackServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_dir = Path(tempfile.mkdtemp(prefix="nemesis_playback_fixtures_"))
        cls.h264_path = cls.fixture_dir / "browser-compatible.mp4"
        cls.hevc_path = cls.fixture_dir / "hevc-input.mp4"
        _make_video(cls.h264_path, "h264")
        _make_video(cls.hevc_path, "hevc")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.fixture_dir, ignore_errors=True)

    def test_h264_mp4_is_reused_without_modifying_original(self) -> None:
        before = _sha256(self.h264_path)
        metadata = inspect_video(self.h264_path)
        self.assertEqual(metadata.container, "mp4")
        self.assertEqual(metadata.video_codec, "h264")
        self.assertEqual(metadata.pixel_format, "yuv420p")
        self.assertEqual(metadata.audio_codec, "aac")
        self.assertTrue(is_browser_compatible(self.h264_path, metadata))

        manager = VideoPlaybackJobManager()
        state = manager.prepare(str(uuid.uuid4()), self.h264_path, self.fixture_dir / "playback")
        self.assertEqual(state.status, "ready")
        self.assertEqual(state.path, self.h264_path)
        self.assertEqual(_sha256(self.h264_path), before)

    def test_hevc_input_converts_to_faststart_h264_aac_copy(self) -> None:
        before = _sha256(self.hevc_path)
        source_metadata = inspect_video(self.hevc_path)
        self.assertIn(source_metadata.video_codec, {"hevc", "h265"})
        output = convert_to_browser_mp4(
            self.hevc_path,
            self.fixture_dir / "playback" / "converted.mp4",
        )
        output_metadata = inspect_video(output)
        self.assertEqual(output_metadata.container, "mp4")
        self.assertEqual(output_metadata.video_codec, "h264")
        self.assertEqual(output_metadata.pixel_format, "yuv420p")
        self.assertEqual(output_metadata.audio_codec, "aac")
        self.assertTrue(is_browser_compatible(output, output_metadata))
        self.assertEqual(_sha256(self.hevc_path), before)

    def test_missing_ffmpeg_and_invalid_input_report_frame_fallback(self) -> None:
        manager = VideoPlaybackJobManager()
        with patch(
            "app.services.video_playback._ffmpeg_executable",
            side_effect=FfmpegUnavailableError("FFmpeg is missing."),
        ):
            state = manager.prepare(
                str(uuid.uuid4()),
                self.h264_path,
                self.fixture_dir / "missing-ffmpeg",
            )
        self.assertEqual(state.status, "failed")
        self.assertIn("Annotated frame navigation remains available", state.message)

        invalid_path = self.fixture_dir / "not-a-video.mp4"
        invalid_path.write_bytes(b"not an mp4")
        state = manager.prepare(
            str(uuid.uuid4()),
            invalid_path,
            self.fixture_dir / "invalid-input",
        )
        self.assertEqual(state.status, "failed")
        self.assertIn("Annotated frame navigation remains available", state.message)


class VideoPlaybackApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_dir = Path(tempfile.mkdtemp(prefix="nemesis_playback_api_fixture_"))
        cls.h264_path = cls.fixture_dir / "owned-source.mp4"
        _make_video(cls.h264_path, "h264")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.fixture_dir, ignore_errors=True)

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_playback_api_"))
        self.upload_dir = self.tmp_dir / "uploads"
        self.playback_dir = self.tmp_dir / "playback"
        self.upload_dir.mkdir()
        self.playback_dir.mkdir()
        self.source_path = self.upload_dir / "owned-source.mp4"
        shutil.copy2(self.h264_path, self.source_path)
        self.source_hash = _sha256(self.source_path)
        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'playback.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.settings = get_settings()
        self.original_dirs = (self.settings.upload_dir, self.settings.playback_dir)
        self.settings.upload_dir = str(self.upload_dir)
        self.settings.playback_dir = str(self.playback_dir)
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
                full_name="Playback Owner",
                email=f"playback-{uuid.uuid4()}@example.com",
                hashed_password=hash_password("Password123!"),
            )
            other = User(
                full_name="Other Playback User",
                email=f"other-playback-{uuid.uuid4()}@example.com",
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
                original_filename="owned-source.mp4",
                stored_filename=self.source_path.name,
                file_path=str(self.source_path),
                file_size=self.source_path.stat().st_size,
                mime_type="video/mp4",
                status="completed",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            self.video_id = video.id
        finally:
            db.close()

    def tearDown(self) -> None:
        self.settings.upload_dir, self.settings.playback_dir = self.original_dirs
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_owned_h264_stream_is_prepared_and_other_users_are_denied(self) -> None:
        response = self.client.post(
            f"/api/v1/videos/{self.video_id}/playback/prepare",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        playback = self.client.get(
            f"/api/v1/videos/{self.video_id}/playback",
            headers=self.owner_headers,
        )
        self.assertEqual(playback.status_code, 200)
        self.assertEqual(playback.headers["content-type"], "video/mp4")
        self.assertEqual(hashlib.sha256(playback.content).hexdigest(), self.source_hash)

        denied = self.client.post(
            f"/api/v1/videos/{self.video_id}/playback/prepare",
            headers=self.other_headers,
        )
        self.assertEqual(denied.status_code, 404)
