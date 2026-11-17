"""Durable inventory and refresh policy for connected sites."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from backend.db import Base

class SiteRefreshPolicy(Base):
    __tablename__ = 'site_refresh_policies'
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    interval_hours = Column(Integer, nullable=False, default=24)
    next_scan_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_scan_at = Column(DateTime)
    last_error = Column(String)

class SitePageCoverage(Base):
    __tablename__ = 'site_page_coverage'
    id = Column(Integer, primary_key=True)
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    url = Column(String, nullable=False)
    canonical_url = Column(String)
    fingerprint = Column(String)
    generated_fingerprint = Column(String)
    sitemap_lastmod = Column(String)
    state = Column(String, nullable=False, default='missing')
    error = Column(String)
    checked_at = Column(DateTime)
    generated_at = Column(DateTime)
    __table_args__ = (UniqueConstraint('domain_id','url', name='uq_coverage_url'),)
