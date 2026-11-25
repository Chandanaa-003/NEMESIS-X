from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'reviewing', 'closed')",
            name="ck_investigation_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sources: Mapped[list["InvestigationSource"]] = relationship(
        cascade="all, delete-orphan", back_populates="investigation"
    )
    events: Mapped[list["InvestigationEvent"]] = relationship(
        cascade="all, delete-orphan", back_populates="investigation"
    )
    tracks: Mapped[list["InvestigationTrack"]] = relationship(
        cascade="all, delete-orphan", back_populates="investigation"
    )
    notes: Mapped[list["InvestigationNote"]] = relationship(
        cascade="all, delete-orphan", back_populates="investigation"
    )


class InvestigationSource(Base):
    """One explicitly linked analysis or live session; track IDs are scoped to this row."""

    __tablename__ = "investigation_sources"
    __table_args__ = (
        CheckConstraint(
            "(analysis_id IS NOT NULL AND live_session_id IS NULL) OR "
            "(analysis_id IS NULL AND live_session_id IS NOT NULL)",
            name="ck_investigation_source_single_source",
        ),
        UniqueConstraint("investigation_id", "analysis_id", name="uq_investigation_analysis"),
        UniqueConstraint("investigation_id", "live_session_id", name="uq_investigation_live_session"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    live_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="sources")
    event_links: Mapped[list["InvestigationEvent"]] = relationship(
        cascade="all, delete-orphan", back_populates="source"
    )
    track_links: Mapped[list["InvestigationTrack"]] = relationship(
        cascade="all, delete-orphan", back_populates="source"
    )
    notes: Mapped[list["InvestigationNote"]] = relationship(back_populates="source")


class InvestigationEvent(Base):
    __tablename__ = "investigation_events"
    __table_args__ = (
        CheckConstraint(
            "(event_id IS NOT NULL AND live_event_id IS NULL) OR "
            "(event_id IS NULL AND live_event_id IS NOT NULL)",
            name="ck_investigation_event_single_event",
        ),
        UniqueConstraint("source_id", "event_id", name="uq_investigation_source_event"),
        UniqueConstraint("source_id", "live_event_id", name="uq_investigation_source_live_event"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigation_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    live_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("live_events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="events")
    source: Mapped[InvestigationSource] = relationship(back_populates="event_links")
    notes: Mapped[list["InvestigationNote"]] = relationship(back_populates="event_link")


class InvestigationTrack(Base):
    __tablename__ = "investigation_tracks"
    __table_args__ = (
        UniqueConstraint("investigation_id", "source_id", "track_id", name="uq_investigation_source_track"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigation_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="tracks")
    source: Mapped[InvestigationSource] = relationship(back_populates="track_links")


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("investigation_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    investigation_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("investigation_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp_seconds: Mapped[float | None] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    investigation: Mapped[Investigation] = relationship(back_populates="notes")
    source: Mapped[InvestigationSource | None] = relationship(back_populates="notes")
    event_link: Mapped[InvestigationEvent | None] = relationship(back_populates="notes")
