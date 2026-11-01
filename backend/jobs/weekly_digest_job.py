"""RQ job for the weekly performance digest.

The HTTP trigger only enqueues this. Database queries and SMTP stay on the
worker, which is not bound by the web process timeout.
"""
import logging
from datetime import datetime
from typing import Optional

from backend.db.session import SessionLocal
from backend.services.weekly_digest_service import process_weekly_digest

logger = logging.getLogger(__name__)


def run_weekly_digest(as_of_date: Optional[str] = None) -> dict:
    """Send the weekly digest. ``as_of_date`` is YYYY-MM-DD or omitted for today."""
    parsed = datetime.strptime(as_of_date, "%Y-%m-%d").date() if as_of_date else None
    db = SessionLocal()
    try:
        result = process_weekly_digest(db=db, as_of_date=parsed, dry_run=False)
        logger.info(
            "Weekly digest job finished: sent=%s failed=%s skipped=%s",
            result.get("sent_count"),
            result.get("failed_count"),
            result.get("skipped_count"),
        )
        return result
    finally:
        db.close()
