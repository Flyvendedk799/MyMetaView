"""Extended analytics routes with real impression/click data."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.models.analytics_event import AnalyticsEvent
from backend.models.analytics_aggregate import AnalyticsDailyAggregate

router = APIRouter(prefix="/analytics", tags=["analytics"])


class TimeseriesPoint(BaseModel):
    """Single point in a timeseries."""
    date: str
    value: int


class AnalyticsOverview(BaseModel):
    """Analytics overview response."""
    total_impressions: int
    total_clicks: int
    ctr: float
    impressions_timeseries: List[TimeseriesPoint]
    clicks_timeseries: List[TimeseriesPoint]


class DomainAnalyticsItem(BaseModel):
    """Domain analytics item."""
    domain_id: int
    domain_name: str
    impressions_7d: int
    impressions_30d: int
    clicks_7d: int
    clicks_30d: int
    ctr_30d: float


class PreviewAnalyticsItem(BaseModel):
    """Preview analytics item."""
    preview_id: int
    url: str
    title: str
    domain: str
    impressions_30d: int
    clicks_30d: int
    ctr_30d: float


@router.get("/overview", response_model=AnalyticsOverview)
def get_analytics_overview(
    days: int = Query(30, description="Window in days: 7, 30, or 90"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get analytics overview for the current organization."""
    if days not in (7, 30, 90):
        days = 30
    window_start = datetime.utcnow() - timedelta(days=days)

    # Totals + daily buckets in one grouped query instead of 2 + 2*days
    # separate COUNTs.
    day_col = func.date(AnalyticsEvent.created_at)
    rows = db.query(
        day_col.label("day"),
        AnalyticsEvent.event_type,
        func.count(AnalyticsEvent.id).label("count"),
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.event_type.in_(["impression", "click"]),
        AnalyticsEvent.created_at >= window_start,
    ).group_by(day_col, AnalyticsEvent.event_type).all()

    by_day = {}
    total_impressions = 0
    total_clicks = 0
    for day, event_type, count in rows:
        day_str = str(day)[:10]
        bucket = by_day.setdefault(day_str, {"impression": 0, "click": 0})
        bucket[event_type] = int(count or 0)
        if event_type == "impression":
            total_impressions += int(count or 0)
        else:
            total_clicks += int(count or 0)

    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0

    impressions_timeseries = []
    clicks_timeseries = []
    for i in range(days):
        day_str = (datetime.utcnow() - timedelta(days=days - 1 - i)).date().isoformat()
        bucket = by_day.get(day_str, {"impression": 0, "click": 0})
        impressions_timeseries.append(TimeseriesPoint(date=day_str, value=bucket["impression"]))
        clicks_timeseries.append(TimeseriesPoint(date=day_str, value=bucket["click"]))

    return AnalyticsOverview(
        total_impressions=total_impressions,
        total_clicks=total_clicks,
        ctr=round(ctr, 2),
        impressions_timeseries=impressions_timeseries,
        clicks_timeseries=clicks_timeseries
    )


@router.get("/domains", response_model=List[DomainAnalyticsItem])
def get_domain_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get analytics per domain for the current organization."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get all domains for the organization (single query)
    domains = db.query(DomainModel).filter(
        DomainModel.organization_id == current_org.id
    ).all()
    
    if not domains:
        return []
    
    domain_ids = [d.id for d in domains]
    
    # Optimize: Use single query with subqueries for each metric
    # Impressions 7d per domain
    impressions_7d_subq = db.query(
        AnalyticsEvent.domain_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.domain_id.in_(domain_ids),
        AnalyticsEvent.event_type == "impression",
        AnalyticsEvent.created_at >= seven_days_ago
    ).group_by(AnalyticsEvent.domain_id).subquery()
    
    # Impressions 30d per domain
    impressions_30d_subq = db.query(
        AnalyticsEvent.domain_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.domain_id.in_(domain_ids),
        AnalyticsEvent.event_type == "impression",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).group_by(AnalyticsEvent.domain_id).subquery()
    
    # Clicks 7d per domain
    clicks_7d_subq = db.query(
        AnalyticsEvent.domain_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.domain_id.in_(domain_ids),
        AnalyticsEvent.event_type == "click",
        AnalyticsEvent.created_at >= seven_days_ago
    ).group_by(AnalyticsEvent.domain_id).subquery()
    
    # Clicks 30d per domain
    clicks_30d_subq = db.query(
        AnalyticsEvent.domain_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.domain_id.in_(domain_ids),
        AnalyticsEvent.event_type == "click",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).group_by(AnalyticsEvent.domain_id).subquery()
    
    # Build result map
    metrics_map = {}
    for subq, key in [
        (impressions_7d_subq, 'impressions_7d'),
        (impressions_30d_subq, 'impressions_30d'),
        (clicks_7d_subq, 'clicks_7d'),
        (clicks_30d_subq, 'clicks_30d')
    ]:
        for row in db.query(subq).all():
            domain_id = row.domain_id
            if domain_id not in metrics_map:
                metrics_map[domain_id] = {'impressions_7d': 0, 'impressions_30d': 0, 'clicks_7d': 0, 'clicks_30d': 0}
            metrics_map[domain_id][key] = row.count
    
    # Build result list
    result = []
    for domain in domains:
        metrics = metrics_map.get(domain.id, {'impressions_7d': 0, 'impressions_30d': 0, 'clicks_7d': 0, 'clicks_30d': 0})
        impressions_30d = metrics['impressions_30d']
        clicks_30d = metrics['clicks_30d']
        ctr_30d = (clicks_30d / impressions_30d * 100) if impressions_30d > 0 else 0.0
        
        result.append(DomainAnalyticsItem(
            domain_id=domain.id,
            domain_name=domain.name,
            impressions_7d=metrics['impressions_7d'],
            impressions_30d=impressions_30d,
            clicks_7d=metrics['clicks_7d'],
            clicks_30d=clicks_30d,
            ctr_30d=round(ctr_30d, 2)
        ))
    
    return result


@router.get("/previews", response_model=List[PreviewAnalyticsItem])
def get_preview_analytics(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get top previews by analytics for the current organization."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get all previews for the organization (single query)
    previews = db.query(PreviewModel).filter(
        PreviewModel.organization_id == current_org.id
    ).all()
    
    if not previews:
        return []
    
    preview_ids = [p.id for p in previews]
    
    # Optimize: Use single query with aggregation for all previews at once
    # Impressions 30d per preview
    impressions_subq = db.query(
        AnalyticsEvent.preview_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.preview_id.in_(preview_ids),
        AnalyticsEvent.event_type == "impression",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).group_by(AnalyticsEvent.preview_id).subquery()
    
    # Clicks 30d per preview
    clicks_subq = db.query(
        AnalyticsEvent.preview_id,
        func.count(AnalyticsEvent.id).label('count')
    ).filter(
        AnalyticsEvent.organization_id == current_org.id,
        AnalyticsEvent.preview_id.in_(preview_ids),
        AnalyticsEvent.event_type == "click",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).group_by(AnalyticsEvent.preview_id).subquery()
    
    # Build metrics map
    metrics_map = {}
    for row in db.query(impressions_subq).all():
        metrics_map[row.preview_id] = {'impressions_30d': row.count, 'clicks_30d': 0}
    for row in db.query(clicks_subq).all():
        if row.preview_id not in metrics_map:
            metrics_map[row.preview_id] = {'impressions_30d': 0, 'clicks_30d': 0}
        metrics_map[row.preview_id]['clicks_30d'] = row.count
    
    # Build result list
    result = []
    for preview in previews:
        metrics = metrics_map.get(preview.id, {'impressions_30d': 0, 'clicks_30d': 0})
        impressions_30d = metrics['impressions_30d']
        clicks_30d = metrics['clicks_30d']
        ctr_30d = (clicks_30d / impressions_30d * 100) if impressions_30d > 0 else 0.0
        
        result.append(PreviewAnalyticsItem(
            preview_id=preview.id,
            url=preview.url,
            title=preview.title,
            domain=preview.domain,
            impressions_30d=impressions_30d,
            clicks_30d=clicks_30d,
            ctr_30d=round(ctr_30d, 2)
        ))
    
    # Sort by impressions descending and limit
    result.sort(key=lambda x: x.impressions_30d, reverse=True)
    return result[:limit]

