from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BehaviorSnapshot(Base):
    """Persisted behavior report and rule configuration for one analysis or live session."""

    __tablename__ = "behavior_snapshots"
    __table_args__ = (
        CheckConstraint(
            "(analysis_id IS NOT NULL AND live_session_id IS NULL) OR "
            "(analysis_id IS NULL AND live_session_id IS NOT NULL)",
            name="ck_behavior_snapshot_single_source",
        ),
        UniqueConstraint("analysis_id", name="uq_behavior_snapshot_analysis"),
        UniqueConstraint("live_session_id", name="uq_behavior_snapshot_live_session"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    live_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    baseline_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    track_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    report_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
