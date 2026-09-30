"""Organization API keys for the agency API-access feature."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from backend.db import Base


class ApiKey(Base):
    """A bearer key. The secret is stored only as a hash; ``prefix`` is safe to list."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    prefix = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, unique=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
