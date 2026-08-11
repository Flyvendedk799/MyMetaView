"""SQLAlchemy ORM model for Domain."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.db import Base


class Domain(Base):
    """SQLAlchemy ORM model for domains table."""
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    environment = Column(String, nullable=False, default="production")
    status = Column(String, nullable=False, default="pending")
    verification_method = Column(String, nullable=True)
    verification_token = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    monthly_clicks = Column(Integer, default=0, nullable=False)
    # Snippet install tracking, reported by the embed script's heartbeat.
    snippet_installed_at = Column(DateTime, nullable=True)
    snippet_last_seen_at = Column(DateTime, nullable=True)
    snippet_version = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)
    site_id = Column(Integer, ForeignKey("published_sites.id"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="domains")
    organization = relationship("Organization", back_populates="domains")
    analytics_events = relationship("AnalyticsEvent", back_populates="domain")
    analytics_aggregates = relationship("AnalyticsDailyAggregate", back_populates="domain")

