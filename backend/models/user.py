"""SQLAlchemy ORM model for User."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.db import Base


class User(Base):
    """SQLAlchemy ORM model for users table."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Stripe subscription fields
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, default="inactive", nullable=False)
    subscription_plan = Column(String, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)

    # Relationships
    domains = relationship("Domain", back_populates="user", cascade="all, delete-orphan")
    # Brands are scoped per domain now, so a user can be the author of several.
    brand_settings = relationship("BrandSettings", back_populates="user")
    previews = relationship("Preview", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user")
    analytics_events = relationship("AnalyticsEvent", back_populates="user")
    analytics_aggregates = relationship("AnalyticsDailyAggregate", back_populates="user")
    owned_organizations = relationship("Organization", foreign_keys="Organization.owner_user_id", back_populates="owner")
    organization_memberships = relationship("OrganizationMember", back_populates="user")

