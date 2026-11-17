"""Immutable card snapshots for comparison and rollback."""
from datetime import datetime
from sqlalchemy import Column, Integer, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.db import Base

class CardHistory(Base):
    __tablename__ = 'card_history'
    id = Column(Integer, primary_key=True)
    preview_id = Column(Integer, ForeignKey('previews.id', ondelete='CASCADE'), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    preview = relationship('Preview', back_populates='history')
    __table_args__ = (UniqueConstraint('preview_id', 'revision', name='uq_card_history_revision'),)
