"""Weekly performance digest service.

Generates and delivers weekly performance digest emails for all eligible accounts.
Follows issue acceptance criteria C1-C8.
"""
from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.user import User
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.models.analytics_aggregate import AnalyticsDailyAggregate
from backend.models.weekly_digest_send import WeeklyDigestSend
from backend.services.digest_token_service import generate_digest_unsubscribe_token
from backend.services.email_service import send_weekly_digest_email

logger = logging.getLogger(__name__)


def calculate_domain_digest_metrics(
    db: Session,
    domain: DomainModel,
    start_current: date,
    end_current: date,
    start_previous: date,
    end_previous: date,
) -> Dict[str, Any]:
    """Calculate aggregate metrics for a single domain over current and preceding 7-day windows.

    Returns dict with impressions, clicks, CTR, and week-over-week deltas/percentages,
    plus top 3 previews by clicks.
    """
    # Current 7-day aggregates
    curr_row = db.query(
        func.coalesce(func.sum(AnalyticsDailyAggregate.impressions), 0).label("impressions"),
        func.coalesce(func.sum(AnalyticsDailyAggregate.clicks), 0).label("clicks"),
    ).filter(
        AnalyticsDailyAggregate.domain_id == domain.id,
        AnalyticsDailyAggregate.date >= start_current,
        AnalyticsDailyAggregate.date <= end_current,
    ).first()

    curr_impressions = int(curr_row.impressions or 0)
    curr_clicks = int(curr_row.clicks or 0)

    # Preceding 7-day aggregates
    prev_row = db.query(
        func.coalesce(func.sum(AnalyticsDailyAggregate.impressions), 0).label("impressions"),
        func.coalesce(func.sum(AnalyticsDailyAggregate.clicks), 0).label("clicks"),
    ).filter(
        AnalyticsDailyAggregate.domain_id == domain.id,
        AnalyticsDailyAggregate.date >= start_previous,
        AnalyticsDailyAggregate.date <= end_previous,
    ).first()

    prev_impressions = int(prev_row.impressions or 0)
    prev_clicks = int(prev_row.clicks or 0)

    # Calculate CTR
    curr_ctr = (curr_clicks / curr_impressions * 100.0) if curr_impressions > 0 else 0.0
    prev_ctr = (prev_clicks / prev_impressions * 100.0) if prev_impressions > 0 else 0.0

    # Week-over-week deltas
    impressions_delta = curr_impressions - prev_impressions
    clicks_delta = curr_clicks - prev_clicks
    ctr_delta = curr_ctr - prev_ctr

    # Week-over-week percentage change
    if prev_impressions > 0:
        impressions_change_pct = round((impressions_delta / prev_impressions) * 100.0, 1)
    elif curr_impressions > 0:
        impressions_change_pct = 100.0
    else:
        impressions_change_pct = 0.0

    if prev_clicks > 0:
        clicks_change_pct = round((clicks_delta / prev_clicks) * 100.0, 1)
    elif curr_clicks > 0:
        clicks_change_pct = 100.0
    else:
        clicks_change_pct = 0.0

    # Top 3 previews by clicks in the current 7-day period
    preview_rows = db.query(
        AnalyticsDailyAggregate.preview_id,
        func.sum(AnalyticsDailyAggregate.clicks).label("total_clicks"),
        func.sum(AnalyticsDailyAggregate.impressions).label("total_impressions"),
    ).filter(
        AnalyticsDailyAggregate.domain_id == domain.id,
        AnalyticsDailyAggregate.preview_id.isnot(None),
        AnalyticsDailyAggregate.date >= start_current,
        AnalyticsDailyAggregate.date <= end_current,
    ).group_by(
        AnalyticsDailyAggregate.preview_id
    ).order_by(
        func.sum(AnalyticsDailyAggregate.clicks).desc(),
        func.sum(AnalyticsDailyAggregate.impressions).desc(),
    ).limit(3).all()

    top_previews = []
    for pr in preview_rows:
        preview_id = pr.preview_id
        preview_model = db.query(PreviewModel).filter(PreviewModel.id == preview_id).first()
        title = preview_model.title if preview_model else f"Preview #{preview_id}"
        url = preview_model.url if preview_model else ""
        top_previews.append({
            "preview_id": preview_id,
            "title": title,
            "url": url,
            "clicks": int(pr.total_clicks or 0),
            "impressions": int(pr.total_impressions or 0),
        })

    return {
        "domain_id": domain.id,
        "domain_name": domain.name,
        "impressions": curr_impressions,
        "impressions_prev": prev_impressions,
        "impressions_delta": impressions_delta,
        "impressions_change_pct": impressions_change_pct,
        "clicks": curr_clicks,
        "clicks_prev": prev_clicks,
        "clicks_delta": clicks_delta,
        "clicks_change_pct": clicks_change_pct,
        "ctr": round(curr_ctr, 2),
        "ctr_prev": round(prev_ctr, 2),
        "ctr_delta": round(ctr_delta, 2),
        "top_previews": top_previews,
    }


def process_weekly_digest(
    db: Session,
    as_of_date: Optional[date] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Process and send weekly performance digest emails for all accounts.

    Args:
        db: Database session.
        as_of_date: Execution date (defaults to today UTC).
        dry_run: If True, returns what would be sent without sending emails
                 or recording sends in weekly_digest_sends.

    Returns:
        Summary dict containing sent, would_send, skipped, and failed accounts.
    """
    if as_of_date is None:
        as_of_date = datetime.utcnow().date()

    iso_year, iso_week, _ = as_of_date.isocalendar()

    # Define the two 7-day windows
    end_current = as_of_date - timedelta(days=1)
    start_current = as_of_date - timedelta(days=7)

    end_previous = as_of_date - timedelta(days=8)
    start_previous = as_of_date - timedelta(days=14)

    analytics_url = f"{settings.APP_PUBLIC_URL.rstrip('/')}/app/analytics"

    users = db.query(User).filter(
        User.is_active == True,  # noqa: E712
        User.deleted_at.is_(None),
    ).all()

    sent: List[Dict[str, Any]] = []
    would_send: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for user in users:
        # C3: Opt-out handling
        if not user.weekly_digest_enabled:
            skipped.append({
                "user_id": user.id,
                "email": user.email,
                "reason": "opted_out",
            })
            continue

        # C6: Duplicate-send guard
        already_sent = db.query(WeeklyDigestSend).filter(
            WeeklyDigestSend.user_id == user.id,
            WeeklyDigestSend.year == iso_year,
            WeeklyDigestSend.iso_week == iso_week,
        ).first()

        if already_sent:
            skipped.append({
                "user_id": user.id,
                "email": user.email,
                "reason": "already_sent_this_week",
                "sent_at": already_sent.sent_at.isoformat(),
            })
            continue

        # Find verified domains for this user
        owned_org_ids = [org.id for org in user.owned_organizations if org.deleted_at is None]
        domain_query = db.query(DomainModel).filter(
            DomainModel.status == "verified",
        )
        if owned_org_ids:
            domain_query = domain_query.filter(
                or_(
                    DomainModel.user_id == user.id,
                    DomainModel.organization_id.in_(owned_org_ids),
                )
            )
        else:
            domain_query = domain_query.filter(DomainModel.user_id == user.id)

        verified_domains = domain_query.order_by(DomainModel.name.asc()).all()

        # C1: Account must have at least one verified domain
        if not verified_domains:
            skipped.append({
                "user_id": user.id,
                "email": user.email,
                "reason": "no_verified_domains",
            })
            continue

        # Calculate metrics for each verified domain
        domain_summaries: List[Dict[str, Any]] = []
        total_curr_impressions = 0
        total_prev_impressions = 0

        for domain in verified_domains:
            summary = calculate_domain_digest_metrics(
                db=db,
                domain=domain,
                start_current=start_current,
                end_current=end_current,
                start_previous=start_previous,
                end_previous=end_previous,
            )
            total_curr_impressions += summary["impressions"]
            total_prev_impressions += summary["impressions_prev"]
            domain_summaries.append(summary)

        # C1 & C2: No empty emails - accounts with zero impressions across both 7-day periods get no email
        if total_curr_impressions == 0 and total_prev_impressions == 0:
            skipped.append({
                "user_id": user.id,
                "email": user.email,
                "reason": "zero_impressions",
            })
            continue

        # C4: Generate signed expiring unsubscribe token
        unsub_token = generate_digest_unsubscribe_token(user.email)
        unsubscribe_url = f"{settings.APP_PUBLIC_URL.rstrip('/')}/unsubscribe?token={unsub_token}"

        digest_payload = {
            "user_id": user.id,
            "email": user.email,
            "iso_year": iso_year,
            "iso_week": iso_week,
            "domains": domain_summaries,
            "unsubscribe_url": unsubscribe_url,
            "analytics_url": analytics_url,
        }

        if dry_run:
            would_send.append(digest_payload)
            continue

        # C7: Email delivery with logging and non-aborting batch loop
        try:
            send_weekly_digest_email(
                to_email=user.email,
                domain_summaries=domain_summaries,
                unsubscribe_url=unsubscribe_url,
                analytics_url=analytics_url,
            )
            # Record send to enforce duplicate-send guard (C6)
            send_record = WeeklyDigestSend(
                user_id=user.id,
                year=iso_year,
                iso_week=iso_week,
                recipient_email=user.email,
                sent_at=datetime.utcnow(),
            )
            db.add(send_record)
            db.commit()
            sent.append({
                "user_id": user.id,
                "email": user.email,
                "domains_count": len(domain_summaries),
            })
            logger.info("Sent weekly digest to %s (ISO week %s-%s)", user.email, iso_year, iso_week)
        except Exception as exc:
            db.rollback()
            logger.error("Failed sending weekly digest to %s: %s", user.email, exc, exc_info=True)
            failed.append({
                "user_id": user.id,
                "email": user.email,
                "error": str(exc),
            })

    return {
        "as_of_date": as_of_date.isoformat(),
        "iso_year": iso_year,
        "iso_week": iso_week,
        "dry_run": dry_run,
        "period": {
            "current_7d": f"{start_current.isoformat()} to {end_current.isoformat()}",
            "previous_7d": f"{start_previous.isoformat()} to {end_previous.isoformat()}",
        },
        "total_users_checked": len(users),
        "sent_count": len(sent),
        "would_send_count": len(would_send),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "sent": sent,
        "would_send": would_send,
        "skipped": skipped,
        "failed": failed,
    }
