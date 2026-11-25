from pathlib import Path
import shutil
import tempfile
import unittest
from types import SimpleNamespace
import uuid

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.models.analysis import Analysis
from app.models.identity import EntityIdentity, IdentityTrackAssociation
from app.models.live_session import LiveSession
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.video import Video
from app.services.identity_engine import (
    TrackAppearanceProfile,
    associate_recorded_track_appearances,
    correct_track_identity,
    extract_appearance_descriptor,
    update_live_track_appearances,
)


def _person_frame(color: tuple[int, int, int] = (0, 0, 230)) -> np.ndarray:
    frame = np.full((240, 320, 3), 20, dtype=np.uint8)
    frame[20:220, 40:140] = color
    return frame


def _distinctive_object_frame() -> np.ndarray:
    frame = np.full((240, 320, 3), 20, dtype=np.uint8)
    region = frame[30:130, 40:140]
    region[:, :50] = (0, 0, 230)
    region[:, 50:] = (230, 0, 0)
    region[::8, :] = (0, 220, 0)
    return frame


def _profile(
    track_id: int,
    category: str,
    first: float,
    last: float,
    descriptor: dict | None,
    evidence: str | None = None,
) -> TrackAppearanceProfile:
    return TrackAppearanceProfile(
        track_id=track_id,
        category=category,
        first_seen_timestamp=first,
        last_seen_timestamp=last,
        detection_count=5,
        descriptor=descriptor,
        descriptor_sample_count=3 if descriptor else 0,
        evidence_filename=evidence,
    )


class IdentityEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="nemesis_identity_engine_"))
        self.engine = create_engine(
            f"sqlite:///{(self.tmp_dir / 'identity.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()
        self.settings = get_settings()
        self.original_live_dir = self.settings.live_dir
        self.settings.live_dir = str(self.tmp_dir / "live")
        self.user = User(
            full_name="Identity Test User",
            email=f"identity-{uuid.uuid4()}@example.com",
            hashed_password="not-used",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        video = Video(
            user_id=self.user.id,
            original_filename="identity.mp4",
            stored_filename="identity.mp4",
            file_path="storage/uploads/identity.mp4",
            file_size=1,
            mime_type="video/mp4",
            status="completed",
        )
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        self.video_id = video.id
        analysis = Analysis(video_id=video.id, user_id=self.user.id, status="completed")
        live_session = LiveSession(user_id=self.user.id, status="stopped")
        self.db.add_all([analysis, live_session])
        self.db.commit()
        self.db.refresh(analysis)
        self.db.refresh(live_session)
        self.analysis_id = analysis.id
        self.live_session_id = live_session.id

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        self.settings.live_dir = self.original_live_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_person_reappearance_links_new_tracker_id_without_losing_track_ids(self) -> None:
        descriptor = extract_appearance_descriptor(
            _person_frame(),
            (40, 20, 140, 220),
            "person",
            0.96,
        )
        self.assertIsNotNone(descriptor)
        mapping = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[
                _profile(1, "person", 0.0, 2.0, descriptor, "frame_0001.jpg"),
                _profile(8, "person", 6.0, 8.0, descriptor, "frame_0007.jpg"),
            ],
        )
        self.db.commit()

        self.assertEqual(mapping, {1: "P001", 8: "P001"})
        identity = self.db.query(EntityIdentity).filter_by(source_id=self.analysis_id).one()
        self.assertEqual(identity.appearance_count, 2)
        self.assertEqual(identity.status, "probable")
        tracks = (
            self.db.query(IdentityTrackAssociation)
            .filter_by(source_id=self.analysis_id)
            .order_by(IdentityTrackAssociation.track_id)
            .all()
        )
        self.assertEqual([row.track_id for row in tracks], [1, 8])
        self.assertEqual([row.match_status for row in tracks], ["unknown", "probable"])
        self.assertIn("frame_0001.jpg", identity.evidence_refs)

    def test_concurrent_similar_people_are_not_merged_and_ambiguous_match_stays_unknown(self) -> None:
        descriptor = extract_appearance_descriptor(
            _person_frame(),
            (40, 20, 140, 220),
            "person",
            0.96,
        )
        mapping = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[
                _profile(1, "person", 0.0, 5.0, descriptor),
                _profile(2, "person", 0.0, 5.0, descriptor),
                _profile(3, "person", 7.0, 8.0, descriptor),
            ],
        )
        self.db.commit()

        self.assertNotEqual(mapping[1], mapping[2])
        self.assertNotEqual(mapping[3], mapping[1])
        third = (
            self.db.query(EntityIdentity)
            .filter_by(source_id=self.analysis_id, identity_code=mapping[3])
            .one()
        )
        self.assertEqual(third.status, "unknown")
        self.assertEqual(third.unresolved_candidate_code, "P001")
        self.assertIn("no identity was merged", third.matching_explanation.lower())

    def test_distinctive_object_reappearance_matches_but_uniform_objects_do_not(self) -> None:
        frame = _distinctive_object_frame()
        descriptor = extract_appearance_descriptor(
            frame,
            (40, 30, 140, 130),
            "backpack",
            0.98,
        )
        self.assertGreater(descriptor["distinctiveness"], 0.12)
        matched = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[
                _profile(5, "backpack", 0.0, 1.0, descriptor),
                _profile(12, "backpack", 4.0, 5.0, descriptor),
            ],
        )
        self.assertEqual(matched[5], matched[12])

        uniform = np.full((240, 320, 3), 80, dtype=np.uint8)
        uniform[30:130, 40:140] = (0, 0, 230)
        uniform_descriptor = extract_appearance_descriptor(
            uniform,
            (40, 30, 140, 130),
            "backpack",
            0.98,
        )
        separate = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[
                _profile(20, "backpack", 0.0, 1.0, uniform_descriptor),
                _profile(21, "backpack", 4.0, 5.0, uniform_descriptor),
            ],
        )
        self.assertNotEqual(separate[20], separate[21])

    def test_small_blurry_crop_remains_unresolved_and_sources_are_isolated(self) -> None:
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        descriptor = extract_appearance_descriptor(frame, (1, 1, 10, 12), "person")
        self.assertIsNone(descriptor)

        analysis_mapping = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[_profile(1, "person", 0.0, 1.0, None)],
        )
        self.db.commit()
        live_mapping = update_live_track_appearances(
            self.db,
            user_id=self.user.id,
            session_id=self.live_session_id,
            frame_index=0,
            timestamp_seconds=0.0,
            frame=_person_frame(),
            detections=[
                SimpleNamespace(
                    track_id=1,
                    class_name="person",
                    confidence=0.96,
                    bbox=SimpleNamespace(x1=40, y1=20, x2=140, y2=220),
                )
            ],
        )
        self.db.commit()
        self.assertEqual(analysis_mapping[1], "P001")
        self.assertEqual(live_mapping[1], "P001")
        live_identity = (
            self.db.query(EntityIdentity)
            .filter_by(source_type="live_session", source_id=self.live_session_id)
            .one()
        )
        self.assertEqual(live_identity.status, "unknown")
        self.assertEqual(live_identity.appearance_count, 1)
        self.assertNotEqual(self.analysis_id, self.live_session_id)

    def test_live_fragment_reappearance_and_manual_correction_preserve_original_track_ids(self) -> None:
        frame = _person_frame()
        detection = SimpleNamespace(
            track_id=7,
            class_name="person",
            confidence=0.96,
            bbox=SimpleNamespace(x1=40, y1=20, x2=140, y2=220),
        )
        first = update_live_track_appearances(
            self.db,
            user_id=self.user.id,
            session_id=self.live_session_id,
            frame_index=0,
            timestamp_seconds=0.0,
            frame=frame,
            detections=[detection],
        )
        same_track = update_live_track_appearances(
            self.db,
            user_id=self.user.id,
            session_id=self.live_session_id,
            frame_index=1,
            timestamp_seconds=1.0,
            frame=frame,
            detections=[detection],
        )
        returned = update_live_track_appearances(
            self.db,
            user_id=self.user.id,
            session_id=self.live_session_id,
            frame_index=10,
            timestamp_seconds=8.0,
            frame=frame,
            detections=[
                SimpleNamespace(
                    track_id=12,
                    class_name="person",
                    confidence=0.96,
                    bbox=detection.bbox,
                )
            ],
        )
        self.db.commit()
        self.assertEqual(first[7], same_track[7])
        self.assertEqual(first[7], returned[12])

        left_frame = _person_frame()
        left_descriptor = extract_appearance_descriptor(
            left_frame,
            (40, 20, 140, 220),
            "person",
            0.96,
        )
        recorded = associate_recorded_track_appearances(
            self.db,
            user_id=self.user.id,
            analysis_id=self.analysis_id,
            profiles=[
                _profile(31, "person", 0.0, 4.0, left_descriptor),
                _profile(32, "person", 0.0, 4.0, left_descriptor),
            ],
        )
        self.db.flush()
        identities = (
            self.db.query(EntityIdentity)
            .filter_by(source_type="analysis", source_id=self.analysis_id)
            .order_by(EntityIdentity.identity_code)
            .all()
        )
        target = identities[0]
        source = identities[1]
        association = (
            self.db.query(IdentityTrackAssociation)
            .filter_by(source_id=self.analysis_id, track_id=32)
            .one()
        )
        corrected = correct_track_identity(
            self.db,
            identity=source,
            association=association,
            user_id=self.user.id,
            target_identity=target,
            correction_note="Reviewed against the stored clothing and shape evidence.",
        )
        self.db.commit()

        self.assertEqual(corrected.identity_code, target.identity_code)
        self.assertEqual(association.track_id, 32)
        self.assertEqual(association.match_status, "confirmed")
        self.assertTrue(association.manually_corrected)
        self.assertEqual(source.merged_into_identity_id, target.id)
        self.assertEqual(source.appearance_count, 0)

    def test_multiple_new_live_tracks_in_one_frame_get_distinct_identity_ids(self) -> None:
        detection = SimpleNamespace(
            class_name="person",
            confidence=0.96,
            bbox=SimpleNamespace(x1=40, y1=20, x2=140, y2=220),
        )
        codes = update_live_track_appearances(
            self.db,
            user_id=self.user.id,
            session_id=self.live_session_id,
            frame_index=0,
            timestamp_seconds=0.0,
            frame=_person_frame(),
            detections=[
                SimpleNamespace(track_id=41, **vars(detection)),
                SimpleNamespace(track_id=42, **vars(detection)),
            ],
        )
        self.db.commit()

        self.assertEqual(codes, {41: "P001", 42: "P002"})
        self.assertEqual(
            self.db.query(EntityIdentity)
            .filter_by(source_type="live_session", source_id=self.live_session_id)
            .count(),
            2,
        )


if __name__ == "__main__":
    unittest.main()
