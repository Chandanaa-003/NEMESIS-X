from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.detection import Detection
    from app.models.track import Track
    from app.models.user import User
    from app.models.video import Video


class Analysis(Base):
    """Video preprocessing and frame extraction job metadata."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        nullable=False,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_frames: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_frames: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_frames: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sampling_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    video: Mapped["Video"] = relationship(back_populates="analyses")
    user: Mapped["User"] = relationship(back_populates="analyses")
    detections: Mapped[list["Detection"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    tracks: Mapped[list["Track"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
