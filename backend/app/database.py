from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


settings = get_settings()
database_url = settings.resolved_database_url
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _normalize_identity_signature(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None

    histogram = value.get("histogram")
    if isinstance(histogram, list) and len(histogram) == 32:
        try:
            normalized = [max(0.0, float(item)) for item in histogram]
        except (TypeError, ValueError):
            return None
    else:
        legacy_histogram = value.get("hsv_hist")
        if not isinstance(legacy_histogram, list) or len(legacy_histogram) != 48:
            return None
        try:
            old_values = [max(0.0, float(item)) for item in legacy_histogram]
        except (TypeError, ValueError):
            return None
        normalized = [0.0] * 32
        old_width = 1.0 / 12.0
        new_width = 1.0 / 8.0
        for old_hue in range(12):
            old_start = old_hue * old_width
            old_end = old_start + old_width
            for new_hue in range(8):
                new_start = new_hue * new_width
                new_end = new_start + new_width
                overlap = max(0.0, min(old_end, new_end) - max(old_start, new_start))
                if overlap == 0:
                    continue
                for saturation in range(4):
                    normalized[new_hue * 4 + saturation] += (
                        old_values[old_hue * 4 + saturation] * overlap / old_width
                    )

    total = sum(normalized)
    if total <= 0:
        return None
    return {
        "histogram": [round(item / total, 6) for item in normalized],
        "aspect_ratio": float(value.get("aspect_ratio", 0.0)),
        "quality": float(value.get("quality", 0.0)),
        "distinctiveness": float(value.get("distinctiveness", 0.0)),
    }


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per request and close it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_safe_sqlite_migrations(target_engine: Engine = engine) -> None:
    """Safely add new nullable/defaulted columns to existing SQLite tables without data loss."""
    if target_engine.dialect.name != "sqlite":
        return
    inspector = inspect(target_engine)
    table_names = set(inspector.get_table_names())

    if "detections" in table_names:
        existing_cols = {col["name"] for col in inspector.get_columns("detections")}
        if "track_id" not in existing_cols:
            with target_engine.begin() as conn:
                conn.execute(text("ALTER TABLE detections ADD COLUMN track_id INTEGER"))
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_detections_track_id ON detections (track_id)")
                )

    if "analyses" in table_names:
        analysis_cols = {col["name"] for col in inspector.get_columns("analyses")}
        if "extracted_frames" not in analysis_cols:
            with target_engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE analyses ADD COLUMN extracted_frames INTEGER NOT NULL DEFAULT 0"
                    )
                )

    if "entity_identities" in table_names:
        identity_cols = {col["name"] for col in inspector.get_columns("entity_identities")}
        identity_additions = {
            "analysis_id": "VARCHAR(36)",
            "live_session_id": "VARCHAR(36)",
            "category": "VARCHAR(64) NOT NULL DEFAULT 'object'",
            "class_name": "VARCHAR(64) NOT NULL DEFAULT 'object'",
            "descriptor_sample_count": "INTEGER NOT NULL DEFAULT 0",
            "associated_track_ids": "JSON NOT NULL DEFAULT '[]'",
            "appearance_descriptor": "JSON",
            "appearance_signature": "JSON",
            "last_position": "JSON",
            "feature_reference": "VARCHAR(64) NOT NULL DEFAULT 'hsv_color_shape_v1'",
            "unresolved_candidate_code": "VARCHAR(16)",
            "merged_into_identity_id": "VARCHAR(36)",
            "updated_at": "DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'",
        }
        with target_engine.begin() as conn:
            for column, definition in identity_additions.items():
                if column not in identity_cols:
                    conn.execute(
                        text(f"ALTER TABLE entity_identities ADD COLUMN {column} {definition}")
                    )
            if "category" in identity_cols:
                conn.execute(
                    text(
                        "UPDATE entity_identities SET class_name = category "
                        "WHERE class_name = 'object' OR class_name IS NULL"
                    )
                )
            conn.execute(
                text(
                    """
                    UPDATE entity_identities
                    SET category = class_name,
                        analysis_id = CASE
                            WHEN source_type = 'analysis' THEN source_id ELSE NULL END,
                        live_session_id = CASE
                            WHEN source_type = 'live_session' THEN source_id ELSE NULL END
                    """
                )
            )
            if "appearance_descriptor" in identity_cols:
                descriptors = conn.execute(
                    text(
                        "SELECT id, appearance_descriptor, appearance_signature "
                        "FROM entity_identities"
                    )
                ).mappings()
                for identity in descriptors:
                    if identity["appearance_signature"] is not None:
                        continue
                    signature = _normalize_identity_signature(
                        identity["appearance_descriptor"]
                    )
                    if signature is not None:
                        conn.execute(
                            text(
                                "UPDATE entity_identities SET appearance_signature = :signature "
                                "WHERE id = :identity_id"
                            ),
                            {
                                "identity_id": identity["id"],
                                "signature": json.dumps(signature),
                            },
                        )
            conn.execute(
                text(
                    "UPDATE entity_identities SET descriptor_sample_count = 1 "
                    "WHERE appearance_signature IS NOT NULL AND descriptor_sample_count = 0"
                )
            )
            if "created_at" in identity_cols:
                conn.execute(
                    text(
                        "UPDATE entity_identities SET updated_at = created_at "
                        "WHERE updated_at = '1970-01-01 00:00:00'"
                    )
                )
            if "matching_confidence" in identity_cols:
                conn.execute(
                    text("UPDATE entity_identities SET matching_confidence = 0 WHERE matching_confidence IS NULL")
                )

        if "identity_track_associations" in table_names:
            association_cols = {
                col["name"] for col in inspector.get_columns("identity_track_associations")
            }
            required_association_cols = {
                "identity_id",
                "source_type",
                "source_id",
                "track_id",
                "category",
                "first_seen_timestamp",
                "last_seen_timestamp",
                "detection_count",
            }
            if required_association_cols.issubset(association_cols):
                with target_engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS app_schema_migrations (
                                migration_key VARCHAR(100) PRIMARY KEY,
                                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            )
                            """
                        )
                    )
                    migration_key = "identity_associations_to_observations_v1"
                    migration_applied = (
                        conn.execute(
                            text(
                                "SELECT 1 FROM app_schema_migrations WHERE migration_key = :key"
                            ),
                            {"key": migration_key},
                        ).first()
                        is not None
                    )
                    legacy_rows = (
                        []
                        if migration_applied
                        else conn.execute(
                            text("SELECT * FROM identity_track_associations")
                        ).mappings()
                    )
                    tracks_by_identity: dict[str, set[int]] = {}
                    for row in legacy_rows:
                        signature = _normalize_identity_signature(
                            row.get("appearance_descriptor")
                        )
                        quality = (
                            float(signature.get("quality", 0.0))
                            if isinstance(signature, dict)
                            else 0.0
                        )
                        evidence_path = row.get("evidence_reference")
                        if (
                            evidence_path
                            and row["source_type"] == "live_session"
                            and Path(str(evidence_path)).name == str(evidence_path)
                        ):
                            evidence_path = str(
                                (
                                    settings.resolved_live_dir
                                    / str(row["source_id"])
                                    / "identity-evidence"
                                    / str(evidence_path)
                                ).resolve()
                            )
                        conn.execute(
                            text(
                                """
                                INSERT OR IGNORE INTO identity_observations (
                                    identity_id, user_id, source_type, source_id, track_id,
                                    class_name, first_seen_timestamp, last_seen_timestamp,
                                    detection_count, match_confidence, feature_quality,
                                    matching_explanation, evidence_path, appearance_signature
                                )
                                SELECT
                                    :identity_id, identity.user_id, :source_type, :source_id, :track_id,
                                    :class_name, :first_seen, :last_seen, :detection_count,
                                    :match_confidence, :feature_quality, :explanation,
                                    :evidence_path, :signature
                                FROM entity_identities AS identity
                                WHERE identity.id = :identity_id
                                """
                            ),
                            {
                                "identity_id": row["identity_id"],
                                "source_type": row["source_type"],
                                "source_id": row["source_id"],
                                "track_id": row["track_id"],
                                "class_name": row["category"],
                                "first_seen": row["first_seen_timestamp"],
                                "last_seen": row["last_seen_timestamp"],
                                "detection_count": row["detection_count"],
                                "match_confidence": row.get("match_confidence") or 0.0,
                                "feature_quality": quality,
                                "explanation": row.get("matching_explanation") or "",
                                "evidence_path": evidence_path,
                                "signature": json.dumps(signature) if signature is not None else None,
                            },
                        )
                        tracks_by_identity.setdefault(str(row["identity_id"]), set()).add(
                            int(row["track_id"])
                        )
                    for identity_id, track_ids in tracks_by_identity.items():
                        conn.execute(
                            text(
                                "UPDATE entity_identities SET associated_track_ids = :track_ids, "
                                "appearance_count = :appearance_count WHERE id = :identity_id"
                            ),
                            {
                                "identity_id": identity_id,
                                "track_ids": json.dumps(sorted(track_ids)),
                                "appearance_count": len(track_ids),
                            },
                        )
                    conn.execute(
                        text(
                            """
                            UPDATE entity_identities
                            SET associated_track_ids = COALESCE(associated_track_ids, '[]')
                            """
                        )
                    )
                    if not migration_applied:
                        conn.execute(
                            text(
                                "INSERT INTO app_schema_migrations (migration_key) "
                                "VALUES (:key)"
                            ),
                            {"key": migration_key},
                        )


def init_db() -> None:
    """Import ORM models and create/migrate database tables safely."""
    import app.models.analysis  # noqa: F401
    import app.models.behavior  # noqa: F401
    import app.models.detection  # noqa: F401
    import app.models.event  # noqa: F401
    import app.models.evidence  # noqa: F401
    import app.models.identity  # noqa: F401
    import app.models.investigation  # noqa: F401
    import app.models.live_session  # noqa: F401
    import app.models.track  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.user_settings  # noqa: F401
    import app.models.video  # noqa: F401
    import app.models.zone  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_safe_sqlite_migrations()
