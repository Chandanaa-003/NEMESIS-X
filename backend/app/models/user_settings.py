from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserSettings(Base):
    """Per-user alert language, voice intelligence, and priority preferences."""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    voice_language: Mapped[str] = mapped_column(String(24), nullable=False, default="english")
    voice_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    announce_high_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    announce_medium_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    announce_low_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="settings")
