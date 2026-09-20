"""SQLAlchemy ORM model for AI credentials (OAuth tokens and API keys, encrypted at rest)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.db import Base

class AiCredential(Base):
    """Encrypted AI credential storage — OAuth tokens and API keys.
    
    Values arrive sealed (AES-256-GCM) and leave sealed. The store never
    holds a plaintext token, and the meta column carries only non-secret
    facts (plan name, expiry, masked hint) so a status page costs no
    decryption.
    """
    __tablename__ = "ai_credentials"

    id = Column(Integer, primary_key=True, index=True)
    # Scoped to either an organization or a user (or both for user override within org)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # The logical key, e.g. 'claude:42', 'Antigravity:42', 'key:anthropic'
    credential_key = Column(String, nullable=False, index=True)
    # The sealed payload: iv:tag:ciphertext
    encrypted_payload = Column(Text, nullable=False)
    # JSON string of non-secret metadata (plan, expiresAt, hint, email, projectId)
    meta_json = Column(Text, nullable=False, default='{}')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization", backref="ai_credentials")
    user = relationship("User", backref="ai_credentials")

    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id', 'credential_key', name='uq_ai_credential_scope_key'),
    )
