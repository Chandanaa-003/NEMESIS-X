import json
from pathlib import Path
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import _apply_safe_sqlite_migrations
from app.models.identity import EntityIdentity, IdentityObservation
from app.services.identity_engine import get_identity_evidence_path
import app.models.live_session  # noqa: F401
import app.models.user_settings  # noqa: F401


def _legacy_signature() -> dict[str, object]:
    return {
        "version": 1,
        "hsv_hist": [1.0 / 48] * 48,
        "aspect_ratio": 0.5,
        "quality": 0.9,
        "distinctiveness": 0.8,
    }


class IdentitySchemaMigrationTests(unittest.TestCase):
    def test_existing_track_associations_migrate_without_losing_identity_data(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="nemesis_identity_migration_"))
        engine = create_engine(f"sqlite:///{(temp_dir / 'legacy.db').as_posix()}")
        settings = get_settings()
        original_live_dir = settings.live_dir
        legacy_live_dir = temp_dir / "live"
        settings.live_dir = str(legacy_live_dir)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE entity_identities (
                            id VARCHAR(36) PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            source_type VARCHAR(24) NOT NULL,
                            source_id VARCHAR(36) NOT NULL,
                            analysis_id VARCHAR(36),
                            live_session_id VARCHAR(36),
                            identity_code VARCHAR(16) NOT NULL,
                            entity_type VARCHAR(16) NOT NULL,
                            category VARCHAR(64) NOT NULL,
                            first_seen_timestamp FLOAT NOT NULL,
                            last_seen_timestamp FLOAT NOT NULL,
                            appearance_count INTEGER NOT NULL,
                            descriptor_sample_count INTEGER NOT NULL,
                            matching_confidence FLOAT,
                            status VARCHAR(16) NOT NULL,
                            appearance_descriptor JSON,
                            evidence_refs JSON NOT NULL,
                            matching_explanation TEXT NOT NULL,
                            unresolved_candidate_code VARCHAR(16),
                            merged_into_identity_id VARCHAR(36),
                            created_at DATETIME NOT NULL,
                            UNIQUE (source_type, source_id, identity_code),
                            CHECK (
                                (source_type = 'analysis' AND analysis_id IS NOT NULL
                                 AND source_id = analysis_id AND live_session_id IS NULL)
                                OR
                                (source_type = 'live_session' AND live_session_id IS NOT NULL
                                 AND source_id = live_session_id AND analysis_id IS NULL)
                            ),
                            CHECK (entity_type IN ('person', 'object')),
                            CHECK (status IN ('confirmed', 'probable', 'unknown'))
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE identity_track_associations (
                            id VARCHAR(36) PRIMARY KEY,
                            identity_id VARCHAR(36) NOT NULL,
                            source_type VARCHAR(24) NOT NULL,
                            source_id VARCHAR(36) NOT NULL,
                            track_id INTEGER NOT NULL,
                            category VARCHAR(64) NOT NULL,
                            first_seen_timestamp FLOAT NOT NULL,
                            last_seen_timestamp FLOAT NOT NULL,
                            detection_count INTEGER NOT NULL,
                            appearance_descriptor JSON,
                            match_confidence FLOAT,
                            matching_explanation TEXT NOT NULL,
                            evidence_reference VARCHAR(512)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO entity_identities (
                            id, user_id, source_type, source_id, live_session_id, identity_code,
                            entity_type, category, first_seen_timestamp, last_seen_timestamp,
                            appearance_count, descriptor_sample_count, matching_confidence,
                            status, appearance_descriptor, evidence_refs, matching_explanation,
                            created_at
                        ) VALUES (
                            'identity-live', 17, 'live_session', 'session-1', 'session-1', 'P001',
                            'person', 'person', 0.0, 5.0, 1, 1, 0.91, 'probable',
                            :signature, '[]', 'Possible visual match.', '2025-01-01 00:00:00'
                        )
                        """
                    ),
                    {"signature": json.dumps(_legacy_signature())},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO entity_identities (
                            id, user_id, source_type, source_id, analysis_id, identity_code,
                            entity_type, category, first_seen_timestamp, last_seen_timestamp,
                            appearance_count, descriptor_sample_count, matching_confidence,
                            status, appearance_descriptor, evidence_refs, matching_explanation,
                            created_at
                        ) VALUES (
                            'identity-1', 17, 'analysis', 'analysis-1', 'analysis-1', 'P001',
                            'person', 'person', 3.0, 7.0, 1, 1, 0.93, 'probable',
                            :signature, '[]', 'Possible visual match.', '2025-01-01 00:00:00'
                        )
                        """
                    ),
                    {"signature": json.dumps(_legacy_signature())},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO identity_track_associations (
                            id, identity_id, source_type, source_id, track_id, category,
                            first_seen_timestamp, last_seen_timestamp, detection_count,
                            appearance_descriptor, match_confidence, matching_explanation
                        ) VALUES (
                            'association-1', 'identity-1', 'analysis', 'analysis-1', 41,
                            'person', 3.0, 7.0, 5, :signature, 0.93, 'Possible visual match.'
                        )
                        """
                    ),
                    {"signature": json.dumps(_legacy_signature())},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO identity_track_associations (
                            id, identity_id, source_type, source_id, track_id, category,
                            first_seen_timestamp, last_seen_timestamp, detection_count,
                            appearance_descriptor, match_confidence, matching_explanation,
                            evidence_reference
                        ) VALUES (
                            'association-live', 'identity-live', 'live_session', 'session-1', 9,
                            'person', 0.0, 5.0, 3, :signature, 0.91, 'Possible visual match.',
                            'identity_t9_f20.jpg'
                        )
                        """
                    ),
                    {"signature": json.dumps(_legacy_signature())},
                )
            IdentityObservation.__table__.create(engine)
            legacy_evidence = (
                legacy_live_dir
                / "session-1"
                / "identity-evidence"
                / "identity_t9_f20.jpg"
            )
            legacy_evidence.parent.mkdir(parents=True)
            legacy_evidence.write_bytes(b"legacy identity crop")

            _apply_safe_sqlite_migrations(engine)

            with Session(engine) as db:
                identity = db.query(EntityIdentity).filter_by(id="identity-1").one()
                observation = db.query(IdentityObservation).filter_by(track_id=41).one()
                live_identity = db.query(EntityIdentity).filter_by(id="identity-live").one()
                live_observation = (
                    db.query(IdentityObservation).filter_by(track_id=9).one()
                )
                self.assertEqual(identity.identity_code, "P001")
                self.assertEqual(identity.class_name, "person")
                self.assertEqual(identity.associated_track_ids, [41])
                self.assertEqual(identity.analysis_id, "analysis-1")
                self.assertEqual(observation.identity_id, "identity-1")
                self.assertEqual(observation.detection_count, 5)
                self.assertEqual(observation.appearance_signature["quality"], 0.9)
                self.assertEqual(
                    len(observation.appearance_signature["histogram"]),
                    32,
                )
                self.assertEqual(live_identity.source_type, "live_session")
                self.assertEqual(
                    get_identity_evidence_path(
                        observation=live_observation,
                        identity=live_identity,
                    ),
                    legacy_evidence.resolve(),
                )
                db.add(
                    EntityIdentity(
                        id="identity-2",
                        user_id=17,
                        source_type="analysis",
                        source_id="analysis-1",
                        analysis_id="analysis-1",
                        identity_code="P002",
                        entity_type="person",
                        category="person",
                        class_name="person",
                        status="unknown",
                        first_seen_timestamp=9.0,
                        last_seen_timestamp=9.0,
                        appearance_count=1,
                        descriptor_sample_count=0,
                        associated_track_ids=[52],
                        matching_confidence=0.0,
                        matching_explanation="New identity after migration.",
                        evidence_refs=[],
                    )
                )
                db.commit()
                self.assertEqual(
                    db.query(EntityIdentity).filter_by(id="identity-2").one().category,
                    "person",
                )
                identity.associated_track_ids = [41, 52]
                identity.appearance_count = 2
                db.commit()
            _apply_safe_sqlite_migrations(engine)
            with Session(engine) as db:
                identity = db.query(EntityIdentity).filter_by(id="identity-1").one()
                self.assertEqual(identity.associated_track_ids, [41, 52])
                self.assertEqual(identity.appearance_count, 2)
        finally:
            engine.dispose()
            settings.live_dir = original_live_dir
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
