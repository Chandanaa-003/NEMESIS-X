from datetime import datetime, timezone
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Zone(Base):
    """Normalized polygon configuration scoped to one owned video or live session."""

    __tablename__ = "zones"
    __table_args__ = (
        CheckConstraint(
            "(video_id IS NOT NULL AND live_session_id IS NULL) OR "
            "(video_id IS NULL AND live_session_id IS NOT NULL)",
            name="ck_zone_single_source",
        ),
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
    video_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    live_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#2563EB")
    polygon: Mapped[list[list[float]]] = mapped_column(JSON, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
