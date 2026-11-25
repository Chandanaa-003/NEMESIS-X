from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


settings = get_settings()
database_url = settings.resolved_database_url
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per request and close it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_safe_sqlite_migrations() -> None:
    """Safely add new nullable/defaulted columns to existing SQLite tables without data loss."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "detections" in table_names:
        existing_cols = {col["name"] for col in inspector.get_columns("detections")}
        if "track_id" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE detections ADD COLUMN track_id INTEGER"))
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_detections_track_id ON detections (track_id)")
                )

    if "analyses" in table_names:
        analysis_cols = {col["name"] for col in inspector.get_columns("analyses")}
        if "extracted_frames" not in analysis_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE analyses ADD COLUMN extracted_frames INTEGER NOT NULL DEFAULT 0"
                    )
                )


def init_db() -> None:
    """Import ORM models and create/migrate database tables safely."""
    import app.models.analysis  # noqa: F401
    import app.models.behavior  # noqa: F401
    import app.models.detection  # noqa: F401
    import app.models.event  # noqa: F401
    import app.models.evidence  # noqa: F401
    import app.models.investigation  # noqa: F401
    import app.models.identity  # noqa: F401
    import app.models.live_session  # noqa: F401
    import app.models.track  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.user_settings  # noqa: F401
    import app.models.video  # noqa: F401
    import app.models.zone  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_safe_sqlite_migrations()
