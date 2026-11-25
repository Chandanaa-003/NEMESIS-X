from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.user import User
from app.services import live_monitor


class _FakeBoxes:
    def __init__(self, rows: list[list[float]]) -> None:
        self._arr = np.array(rows, dtype=np.float32) if rows else np.empty((0, 6), dtype=np.float32)
        self.xyxy = self
        self.conf = self
        self.cls = self

    def __len__(self) -> int:
        return len(self._arr)

    def cpu(self):
        return self

    def numpy(self):
        return self._arr

    def tolist(self):
        return []


class _FakeYoloResult:
    def __init__(self, rows: list[list[float]]) -> None:
        self.names = {0: "person", 24: "backpack"}
        self.boxes = _FakeBoxes(rows)


class _FakeYoloModel:
    def __init__(self) -> None:
        self.calls = 0

    def predict(self, source=None, **_kwargs):
        self.calls += 1
        # Solid grayscale brightness distinguishes JPEG-encoded synthetic frames cleanly:
        # mean ~100 -> 1 person at initial location
        # mean ~200 -> 1 person shifted later
        # mean ~20  -> empty frame (0 detections)
        mean_val = float(np.mean(source)) if source is not None else 0.0
        if 75.0 <= mean_val <= 135.0:
            return [_FakeYoloResult([[10.0, 20.0, 110.0, 220.0, 0.91, 0.0]])]
        if mean_val >= 165.0:
            return [_FakeYoloResult([[80.0, 25.0, 180.0, 225.0, 0.93, 0.0]])]
        return [_FakeYoloResult([])]


class _FakeByteTracker:
    def __init__(self) -> None:
        self.updates = 0

    def update(self, det_np: np.ndarray, _img=None):
        self.updates += 1
        if det_np is None or len(det_np) == 0:
            return np.empty((0, 8), dtype=np.float32)
        out = []
        for idx, row in enumerate(det_np):
            x1, y1, x2, y2, conf, cls_id = row[:6]
            out.append([x1, y1, x2, y2, 1.0, conf, cls_id, float(idx)])
        return np.array(out, dtype=np.float32)


def _make_jpeg(marker_b: int) -> bytes:
    img = np.full((240, 320, 3), marker_b, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


class LiveMonitoringApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_live_test_"))
        self.live_dir = self.tmp_dir / "live"
        self.live_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.tmp_dir / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.settings = get_settings()
        self._orig_live_dir = self.settings.live_dir
        self._orig_reports_dir = self.settings.reports_dir
        self.settings.live_dir = str(self.live_dir)
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
            u1 = User(
                full_name="Live Owner",
                email="liveowner@example.com",
                hashed_password=hash_password("Password123!"),
            )
            u2 = User(
                full_name="Live Other",
                email="liveother@example.com",
                hashed_password=hash_password("Password123!"),
            )
            db.add_all([u1, u2])
            db.commit()
            db.refresh(u1)
            db.refresh(u2)
            self.owner_headers = {"Authorization": f"Bearer {create_access_token(str(u1.id))}"}
            self.other_headers = {"Authorization": f"Bearer {create_access_token(str(u2.id))}"}
        finally:
            db.close()

        live_monitor._active_live_sessions.clear()

    def tearDown(self) -> None:
        live_monitor._active_live_sessions.clear()
        self.settings.live_dir = self._orig_live_dir
        self.settings.reports_dir = self._orig_reports_dir
        self.engine.dispose()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("app.services.live_monitor._create_isolated_bytetracker", side_effect=lambda _cfg: _FakeByteTracker())
    @patch("app.services.live_monitor.get_detection_model", return_value=_FakeYoloModel())
    def test_live_session_lifecycle_tracking_events_and_cleanup(self, _mock_model, _mock_tracker) -> None:
        # Unauthenticated start is rejected
        self.assertEqual(self.client.post("/api/v1/live/start").status_code, 401)

        # Start owned session
        start_resp = self.client.post(
            "/api/v1/live/start",
            json={"confidence_threshold": 0.4, "image_size": 416},
            headers=self.owner_headers,
        )
        self.assertEqual(start_resp.status_code, 201)
        sid = start_resp.json()["session_id"]
        self.assertIn(sid, live_monitor._active_live_sessions)

        # Frame 0: Empty scene -> 0 detections, 0 tracks, 0 events (no fabrication)
        f0 = self.client.post(
            f"/api/v1/live/{sid}/frame",
            files={"file": ("f0.jpg", _make_jpeg(20), "image/jpeg")},
            data={"timestamp_seconds": "0.0"},
            headers=self.owner_headers,
        )
        self.assertEqual(f0.status_code, 200)
        d0 = f0.json()
        self.assertEqual(d0["detections"], [])
        self.assertEqual(d0["active_tracks"], [])
        self.assertEqual(d0["new_events"], [])

        # Frame 1: Person enters after frame 0 -> track T001 + person_entering event
        f1 = self.client.post(
            f"/api/v1/live/{sid}/frame",
            files={"file": ("f1.jpg", _make_jpeg(100), "image/jpeg")},
            data={"timestamp_seconds": "1.0"},
            headers=self.owner_headers,
        )
        self.assertEqual(f1.status_code, 200)
        d1 = f1.json()
        self.assertEqual(len(d1["detections"]), 1)
        self.assertEqual(d1["detections"][0]["track_code"], "T001")
        self.assertEqual(d1["unique_tracks_count"], 1)
        self.assertEqual(len(d1["new_events"]), 1)
        evt = d1["new_events"][0]
        self.assertEqual(evt["event_type"], "person_entering")
        self.assertIsNotNone(evt["snapshot_url"])

        # Snapshot endpoint works for owner and rejects other user
        snap_ok = self.client.get(evt["snapshot_url"], headers=self.owner_headers)
        self.assertEqual(snap_ok.status_code, 200)
        self.assertEqual(
            self.client.get(evt["snapshot_url"], headers=self.other_headers).status_code,
            404,
        )

        # Frame 2: Track T001 persists across frames; duplicate event is NOT re-emitted
        f2 = self.client.post(
            f"/api/v1/live/{sid}/frame",
            files={"file": ("f2.jpg", _make_jpeg(200), "image/jpeg")},
            data={"timestamp_seconds": "2.0"},
            headers=self.owner_headers,
        )
        self.assertEqual(f2.status_code, 200)
        d2 = f2.json()
        self.assertEqual(d2["frames_processed"], 3)
        self.assertEqual(d2["active_tracks"][0]["frame_count"], 2)
        self.assertEqual(d2["new_events"], [])

        # Ownership & validation checks
        self.assertEqual(
            self.client.get(f"/api/v1/live/{sid}/status", headers=self.other_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/live/{sid}/frame",
                files={"file": ("bad.jpg", b"not-a-jpeg", "image/jpeg")},
                headers=self.owner_headers,
            ).status_code,
            400,
        )

        # Status check
        status_resp = self.client.get(f"/api/v1/live/{sid}/status", headers=self.owner_headers)
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()["events_discovered_count"], 1)

        # Live Evidence Center & Live PDF Report integration checks
        sessions_resp = self.client.get("/api/v1/live/sessions", headers=self.owner_headers)
        self.assertEqual(sessions_resp.status_code, 200)
        self.assertEqual(len(sessions_resp.json()), 1)

        ev_resp = self.client.get(f"/api/v1/live/{sid}/evidence", headers=self.owner_headers)
        self.assertEqual(ev_resp.status_code, 200)
        ev_payload = ev_resp.json()
        self.assertEqual(ev_payload["total_evidence"], 1)
        self.assertEqual(ev_payload["evidence"][0]["event_id"], evt["id"])
        self.assertEqual(self.client.get(f"/api/v1/live/{sid}/evidence", headers=self.other_headers).status_code, 404)

        pdf_resp = self.client.get(f"/api/v1/reports/live/{sid}/pdf", headers=self.owner_headers)
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertTrue(pdf_resp.content.startswith(b"%PDF-"))
        self.assertEqual(self.client.get(f"/api/v1/reports/live/{sid}/pdf", headers=self.other_headers).status_code, 404)

        # Second concurrent session keeps independent tracker/event state
        start_b = self.client.post("/api/v1/live/start", headers=self.owner_headers)
        self.assertEqual(start_b.status_code, 201)
        sid_b = start_b.json()["session_id"]
        self.assertNotEqual(sid, sid_b)
        self.assertIn(sid, live_monitor._active_live_sessions)
        self.assertIn(sid_b, live_monitor._active_live_sessions)
        self.assertIsNot(
            live_monitor._active_live_sessions[sid].tracker,
            live_monitor._active_live_sessions[sid_b].tracker,
        )
        self.client.post(f"/api/v1/live/{sid_b}/stop", headers=self.owner_headers)

        # Stop monitoring cleans up runtime tracker and prevents further frames
        stop_resp = self.client.post(f"/api/v1/live/{sid}/stop", headers=self.owner_headers)
        self.assertEqual(stop_resp.status_code, 200)
        self.assertEqual(stop_resp.json()["status"], "stopped")
        self.assertNotIn(sid, live_monitor._active_live_sessions)

        after_stop = self.client.post(
            f"/api/v1/live/{sid}/frame",
            files={"file": ("f3.jpg", _make_jpeg(100), "image/jpeg")},
            headers=self.owner_headers,
        )
        self.assertEqual(after_stop.status_code, 409)


if __name__ == "__main__":
    unittest.main()
