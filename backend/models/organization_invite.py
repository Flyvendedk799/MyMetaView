"""Durable organization invite tokens."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from backend.db import Base


class OrganizationInvite(Base):
    """An invite that survives process restarts and multiple workers.

    The raw token is shown once. Only its hash is stored.
    """
    __tablename__ = "organization_invites"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
