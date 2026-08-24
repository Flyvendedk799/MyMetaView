"""Layered caches for the preview engine.

One cache entry per URL per lane was the whole caching story, and it had two
costs. A bulk job over 200 pages of one site re-extracted that site's brand 200
times, because the only key was the full URL. And a customer who uploaded a new
logo kept being served the old card until the TTL ran out — up to a day —
because nothing connected "brand settings changed" to "the cached previews are
now wrong".

Four layers, each keyed by what actually determines it:

    screenshot  URL              → R2 key            (hours)
    brand       domain           → logo/colors/name  (days)
    reasoning   content hash     → art director out  (days)
    result      URL + lane       → whole preview     (as before)

Invalidation follows the same shape: ``invalidate_domain`` busts brand and
result entries for one site, which is what a logo upload calls.
"""

from backend.services.preview.caching.layers import (
    BrandCache,
    CacheLayer,
    ReasoningCache,
    ScreenshotCache,
    cache_stats,
    invalidate_domain,
    invalidate_url,
    reasoning_fingerprint,
)

__all__ = [
    "BrandCache",
    "CacheLayer",
    "ReasoningCache",
    "ScreenshotCache",
    "cache_stats",
    "invalidate_domain",
    "invalidate_url",
    "reasoning_fingerprint",
]
