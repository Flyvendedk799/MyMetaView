"""Plan / tier info routes (single source of truth is backend.core.plans)."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.core.plans import public_plans, get_plan
from backend.services.generation_lane import ai_previews_used as ai_previews_used_this_month

router = APIRouter(tags=["plans"])


@router.get("/plans")
def list_plans():
    """Public tier list for the pricing page."""
    return {"plans": public_plans()}


@router.get("/plans/me")
def my_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """The current org's effective plan, limits, features and this-month usage."""
    plan = get_plan(current_org)
    domains_used = db.query(DomainModel).filter(
        DomainModel.organization_id == current_org.id
    ).count()
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previews_used = db.query(PreviewModel).filter(
        PreviewModel.organization_id == current_org.id,
        PreviewModel.created_at >= month_start,
    ).count()
    ai_previews_used = ai_previews_used_this_month(db, current_org.id)
    trial_ends = getattr(current_org, "trial_ends_at", None)
    return {
        "key": plan["key"],
        "name": plan["name"],
        "price": plan["price"],
        "status": getattr(current_org, "subscription_status", None),
        "trial_ends_at": trial_ends.isoformat() if trial_ends else None,
        "limits": {
            "domains": plan["domains"],
            "previews_month": plan["previews_month"],
            "ai_previews_month": plan["ai_previews_month"],
            "team_seats": plan["team_seats"],
        },
        "features": sorted(plan["features"]),
        "usage": {
            "domains": domains_used,
            "previews_month": previews_used,
            "ai_previews_month": ai_previews_used,
        },
    }
