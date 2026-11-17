"""SQLAlchemy ORM model for AnalyticsEvent."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.db import Base


class AnalyticsEvent(Base):
    """SQLAlchemy ORM model for analytics_events table."""
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=True, index=True)
    preview_id = Column(Integer, ForeignKey("previews.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)  # "impression" or "click"
    event_source = Column(String, nullable=True)
    campaign = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    referrer = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="analytics_events")
    domain = relationship("Domain", back_populates="analytics_events")
    preview = relationship("Preview", back_populates="analytics_events")
    organization = relationship("Organization", back_populates="analytics_events")

