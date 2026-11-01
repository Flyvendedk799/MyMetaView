"""SQLAlchemy ORM model for WeeklyDigestSend."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.db import Base


class WeeklyDigestSend(Base):
    """Record of a weekly performance digest email sent to a user for an ISO week."""
    __tablename__ = "weekly_digest_sends"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    iso_week = Column(Integer, nullable=False, index=True)
    recipient_email = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "year", "iso_week", name="uq_weekly_digest_send_user_week"),
    )

    user = relationship("User", back_populates="weekly_digest_sends")
