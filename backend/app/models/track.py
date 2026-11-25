from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class Track(Base):
    """Persistent object track and temporal memory summary across an analysis."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    max_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    analysis: Mapped["Analysis"] = relationship(back_populates="tracks")
