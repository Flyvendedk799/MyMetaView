"""Busting preview caches when the brand behind them changes.

``invalidate_brand_settings`` cleared one Redis key: the settings row. It did
not touch the preview caches, which is why a customer who uploaded a new logo
kept seeing the old card — for up to 24 hours on the app and 48 on the demo —
and reasonably concluded the upload had not worked.

The gap was structural. Settings are keyed by ``(org, domain)``; previews are
keyed by URL and by domain. Nothing connected the two, so nothing could know
which previews a settings change invalidated.

``invalidate_org_previews`` closes it: it looks up which URLs the org actually
has previews for and clears exactly those, plus the domain's brand cache. That
is a database query on a rare, user-initiated action — the right place to spend
a query, since the alternative is a day of serving a card the customer believes
they replaced.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.services.preview.caching.layers import (
    BrandCache,
    domain_of,
    invalidate_url,
)

logger = logging.getLogger(__name__)

# Clearing every preview for a very large account would be a long synchronous
# loop on a web request. Past this we clear the brand cache (which is what makes
# the *next* generation correct) and let the rest expire on their own TTL.
MAX_URLS_PER_INVALIDATION = 500


def invalidate_org_previews(
    db: Any,
    organization_id: int,
    *,
    domain_id: Optional[int] = None,
    reason: str = "brand settings changed",
) -> int:
    """Drop cached previews and brand data for an org, optionally one domain.

    Returns the number of cache entries removed. Never raises: a caching
    problem must not fail the settings save the user just made.
    """
    try:
        from backend.models.domain import Domain as DomainModel
        from backend.models.preview import Preview as PreviewModel
    except Exception as exc:  # noqa: BLE001
        logger.debug("Models unavailable for preview invalidation: %s", exc)
        return 0

    removed = 0
    try:
        domain_query = db.query(DomainModel).filter(
            DomainModel.organization_id == organization_id
        )
        if domain_id is not None:
            domain_query = domain_query.filter(DomainModel.id == domain_id)
        domains = domain_query.all()

        for domain in domains:
            if BrandCache.delete(domain_of(domain.name)):
                removed += 1

        preview_query = db.query(PreviewModel.url).filter(
            PreviewModel.organization_id == organization_id
        )
        if domain_id is not None:
            names = [d.name for d in domains]
            if names:
                preview_query = preview_query.filter(PreviewModel.domain.in_(names))

        urls: List[str] = [
            row[0] for row in preview_query.limit(MAX_URLS_PER_INVALIDATION).all()
            if row and row[0]
        ]
        for url in urls:
            removed += invalidate_url(url)

        logger.info(
            "Invalidated %d cache entries for org %s (%s): %d domains, %d previews",
            removed, organization_id, reason, len(domains), len(urls),
        )
    except Exception as exc:  # noqa: BLE001 — never fail the user's save
        logger.warning(
            "Preview cache invalidation failed for org %s: %s", organization_id, exc
        )
    return removed


def invalidate_domain_previews(db: Any, domain_name: str) -> int:
    """Drop cached previews for one site by name. Used by the regenerate action."""
    try:
        from backend.models.preview import Preview as PreviewModel
    except Exception:  # noqa: BLE001
        return 0

    removed = 1 if BrandCache.delete(domain_of(domain_name)) else 0
    try:
        rows = (
            db.query(PreviewModel.url)
            .filter(PreviewModel.domain == domain_name)
            .limit(MAX_URLS_PER_INVALIDATION)
            .all()
        )
        for row in rows:
            if row and row[0]:
                removed += invalidate_url(row[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Domain cache invalidation failed for %s: %s", domain_name, exc)
    return removed
