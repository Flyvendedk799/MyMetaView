"""Which lane does this generation run on — AI, or template?

MyMetaView's product is the AI lane: the art director looks at the captured page
and designs a card *for that page*. It costs a vision call per generation, so
each plan gets a monthly allowance (``ai_previews_month``). Past the allowance
the account keeps working, on the template lane — the page's own metadata poured
into the same premium card. Generic, near-free, and the reason to upgrade.

Usage is counted from ``activity_logs``, one row per AI generation that actually
ran, rather than from the previews table. Regenerating an existing preview
overwrites its row, so counting rows would hand out unlimited free re-rolls; and
the log survives the preview being deleted, so deleting cannot refund the spend.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, NamedTuple, Optional

from sqlalchemy.orm import Session

from backend.core.plans import plan_limit
from backend.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)

Lane = Literal["ai", "template"]

# Logged once per AI generation that reaches the engine. The month's count of
# these rows is the account's AI spend.
AI_GENERATION_ACTION = "preview.ai_generation.spent"


class LaneDecision(NamedTuple):
    lane: Lane
    used: int
    limit: Optional[int]  # None == unlimited

    @property
    def remaining(self) -> Optional[int]:
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)


def month_start(now: Optional[datetime] = None) -> datetime:
    """First instant of the current UTC month — the quota window."""
    now = now or datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def ai_previews_used(db: Session, organization_id: int) -> int:
    """AI generations this organization has spent this month."""
    try:
        return (
            db.query(ActivityLog)
            .filter(
                ActivityLog.organization_id == organization_id,
                ActivityLog.action == AI_GENERATION_ACTION,
                ActivityLog.created_at >= month_start(),
            )
            .count()
        )
    except Exception as exc:  # noqa: BLE001 — never block a generation on counting
        logger.warning("AI usage count failed for org %s: %s", organization_id, exc)
        return 0


def resolve_lane(db: Session, org) -> LaneDecision:
    """Pick the lane for the next generation on this organization."""
    limit = plan_limit(org, "ai_previews_month")
    if limit is None:
        return LaneDecision("ai", used=ai_previews_used(db, org.id), limit=None)

    used = ai_previews_used(db, org.id)
    return LaneDecision("ai" if used < limit else "template", used=used, limit=limit)


def record_ai_generation(
    db: Session,
    *,
    organization_id: int,
    user_id: Optional[int],
    url: str,
    domain: str,
) -> None:
    """Spend one AI generation.

    Written before the engine runs, not after: a generation that fails halfway
    has still cost us the vision call, and a job that could retry for free would
    let a failing URL loop through the allowance for nothing.
    """
    from backend.services.activity_logger import log_activity

    log_activity(
        db,
        user_id=user_id,
        organization_id=organization_id,
        action=AI_GENERATION_ACTION,
        metadata={"url": url, "domain": domain},
    )
