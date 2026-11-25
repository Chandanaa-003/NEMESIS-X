from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class EntityIdentity(Base):
    """Anonymous, source-scoped visual identity inferred from tracked appearances."""

    __tablename__ = "entity_identities"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "identity_code"),
        CheckConstraint(
            "(source_type = 'analysis' AND analysis_id IS NOT NULL "
            "AND source_id = analysis_id AND live_session_id IS NULL) "
            "OR (source_type = 'live_session' AND live_session_id IS NOT NULL "
            "AND source_id = live_session_id AND analysis_id IS NULL)",
            name="ck_entity_identity_single_source",
        ),
        CheckConstraint("entity_type IN ('person', 'object')", name="ck_entity_identity_type"),
        CheckConstraint(
            "status IN ('confirmed', 'probable', 'unknown')",
            name="ck_entity_identity_status",
        ),
        Index("ix_entity_identity_owner_source", "user_id", "source_type", "source_id"),
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
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
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
    identity_code: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    appearance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    descriptor_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matching_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    appearance_descriptor: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matching_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    unresolved_candidate_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    merged_into_identity_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("entity_identities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tracks: Mapped[list["IdentityTrackAssociation"]] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
    )


class IdentityTrackAssociation(Base):
    """Audit-preserving mapping from one original tracker ID to an anonymous identity."""

    __tablename__ = "identity_track_associations"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "track_id"),
        CheckConstraint(
            "match_status IN ('confirmed', 'probable', 'unknown')",
            name="ck_identity_track_match_status",
        ),
        Index("ix_identity_track_identity", "identity_id"),
        Index("ix_identity_track_source", "source_type", "source_id", "track_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    identity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("entity_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    descriptor_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    appearance_descriptor: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    matching_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    unresolved_candidate_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    manually_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corrected_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    correction_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    identity: Mapped["EntityIdentity"] = relationship(back_populates="tracks")
