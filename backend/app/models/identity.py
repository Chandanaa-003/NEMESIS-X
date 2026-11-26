from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EntityIdentity(Base):
    """Anonymous, source-local visual identity assembled from tracked appearances."""

    __tablename__ = "entity_identities"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "identity_code", name="uq_identity_source_code"),
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
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    analysis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    live_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    identity_code: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="object")
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", index=True)
    first_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    appearance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    descriptor_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    associated_track_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    appearance_descriptor: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    appearance_signature: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_position: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    feature_reference: Mapped[str] = mapped_column(String(64), nullable=False, default="hsv_color_shape_v1")
    matching_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matching_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unresolved_candidate_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    merged_into_identity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entity_identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    observations: Mapped[list["IdentityObservation"]] = relationship(
        back_populates="identity", cascade="all, delete-orphan"
    )


class IdentityObservation(Base):
    """One ByteTrack fragment associated with a source-local anonymous identity."""

    __tablename__ = "identity_observations"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "track_id", name="uq_identity_source_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entity_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    match_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feature_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matching_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bbox: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    last_position: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    appearance_signature: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    identity: Mapped[EntityIdentity] = relationship(back_populates="observations")