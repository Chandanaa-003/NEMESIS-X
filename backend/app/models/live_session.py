from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class LiveSession(Base):
    """Live webcam monitoring session metadata stored in SQLite."""

    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.40)
    image_size: Mapped[int] = mapped_column(Integer, nullable=False, default=416)
    frames_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_detections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_tracks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frame_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="live_sessions")
    events: Mapped[list["LiveEvent"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class LiveEvent(Base):
    """Discovered event produced during a real live webcam monitoring session."""

    __tablename__ = "live_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    start_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    end_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    involved_track_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session: Mapped["LiveSession"] = relationship(back_populates="events")
    user: Mapped["User"] = relationship(back_populates="live_events")
