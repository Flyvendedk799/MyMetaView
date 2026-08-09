"""Analytics routes."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from backend.schemas.analytics import AnalyticsSummary, TopDomain
from backend.models.preview import Preview as PreviewModel
from backend.models.domain import Domain as DomainModel
from backend.models.analytics_event import AnalyticsEvent
from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_paid_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    period: str = Query("7d", description="Time period: '7d' or '30d'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_paid_user)
):
    """Get analytics summary for the current user for a given period."""
    if period not in ["7d", "30d"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Period must be '7d' or '30d'"
        )
    
    days = 30 if period == "30d" else 7
    since = datetime.utcnow() - timedelta(days=days)

    _clicks = case((AnalyticsEvent.event_type == "click", 1), else_=0)
    _imps = case((AnalyticsEvent.event_type == "impression", 1), else_=0)

    # Real clicks/impressions from tracked events (this user, in-period)
    totals = db.query(
        func.coalesce(func.sum(_clicks), 0),
        func.coalesce(func.sum(_imps), 0),
    ).filter(
        AnalyticsEvent.user_id == current_user.id,
        AnalyticsEvent.created_at >= since,
    ).first()
    total_clicks = int(totals[0] or 0)
    total_impressions = int(totals[1] or 0)
    # Fall back to the denormalised counter only if no events have been tracked yet.
    if total_clicks == 0 and total_impressions == 0:
        mc = db.query(func.sum(PreviewModel.monthly_clicks)).filter(
            PreviewModel.user_id == current_user.id
        ).scalar()
        total_clicks = int(mc) if mc else 0

    total_previews = db.query(func.count(PreviewModel.id)).filter(
        PreviewModel.user_id == current_user.id
    ).scalar() or 0

    total_domains = db.query(func.count(DomainModel.id)).filter(
        DomainModel.user_id == current_user.id
    ).scalar() or 0
    verified_domains = db.query(func.count(DomainModel.id)).filter(
        DomainModel.user_id == current_user.id,
        DomainModel.status == "active"
    ).scalar() or 0

    # Honest "brand setup" score (0-100) from real completeness signals, not a
    # fabricated baseline: has a domain, a verified domain, previews, and a
    # customised brand profile.
    brand = db.query(BrandSettingsModel).filter(
        BrandSettingsModel.user_id == current_user.id
    ).first()
    brand_customised = bool(brand and (brand.logo_url or (brand.primary_color not in (None, "", "#2979FF"))))
    brand_score = (30 if total_domains else 0) + (25 if verified_domains else 0) \
        + (25 if total_previews else 0) + (20 if brand_customised else 0)

    # Real per-domain clicks + CTR from events (in-period)
    rows = db.query(
        AnalyticsEvent.domain_id,
        func.coalesce(func.sum(_clicks), 0),
        func.coalesce(func.sum(_imps), 0),
    ).filter(
        AnalyticsEvent.user_id == current_user.id,
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.domain_id.isnot(None),
    ).group_by(AnalyticsEvent.domain_id).all()

    top_domains = []
    if rows:
        name_by_id = dict(
            db.query(DomainModel.id, DomainModel.name).filter(
                DomainModel.user_id == current_user.id
            ).all()
        )
        for domain_id, clicks, imps in rows:
            c, im = int(clicks or 0), int(imps or 0)
            ctr = round((c / im) * 100, 1) if im > 0 else 0.0
            top_domains.append(TopDomain(domain=name_by_id.get(domain_id, "—"), clicks=c, ctr=ctr))
        top_domains.sort(key=lambda t: t.clicks, reverse=True)
        top_domains = top_domains[:4]
    else:
        # No events yet: show real click counters with an honest 0% CTR (no impressions).
        for domain_name, clicks in db.query(
            PreviewModel.domain, func.sum(PreviewModel.monthly_clicks)
        ).filter(PreviewModel.user_id == current_user.id).group_by(
            PreviewModel.domain
        ).order_by(func.sum(PreviewModel.monthly_clicks).desc()).limit(4).all():
            top_domains.append(TopDomain(domain=domain_name, clicks=int(clicks or 0), ctr=0.0))

    return AnalyticsSummary(
        period=period,
        total_clicks=total_clicks,
        total_previews=total_previews,
        total_domains=total_domains,
        brand_score=int(brand_score),
        top_domains=top_domains,
    )

