"""SQLAlchemy ORM model for Organization."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.db import Base


class Organization(Base):
    """SQLAlchemy ORM model for organizations table."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Stripe subscription fields (migrated from User)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, default="inactive", nullable=False)
    subscription_plan = Column(String, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_organizations")
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    domains = relationship("Domain", back_populates="organization")
    previews = relationship("Preview", back_populates="organization")
    # One row per connected domain, plus the domain_id=NULL organization default.
    brand_settings = relationship("BrandSettings", back_populates="organization")
    analytics_events = relationship("AnalyticsEvent", back_populates="organization")
    analytics_aggregates = relationship("AnalyticsDailyAggregate", back_populates="organization")

