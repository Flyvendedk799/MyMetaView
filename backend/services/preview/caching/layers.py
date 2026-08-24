"""The four cache layers and their invalidation.

Every layer is the same small object — a namespace, a TTL, and JSON in Redis —
differing only in what it keys off. That is the point: the layers exist because
the *keys* are different, not because the storage is.

Redis being unavailable is a normal condition (local dev, a degraded worker),
so every operation no-ops rather than raising. A cache that fails closed would
turn a Redis blip into a total outage of a feature that is meant to be an
optimisation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _redis():
    """The shared client, or None. Imported lazily to keep this importable."""
    try:
        from backend.services.preview_cache import get_redis_client
        return get_redis_client()
    except Exception as exc:  # noqa: BLE001 — Redis is optional infrastructure
        logger.debug("Redis unavailable for layered cache: %s", exc)
        return None


def domain_of(url: str) -> str:
    """Registrable-ish host for brand keying: ``www.`` dropped, port dropped."""
    try:
        parsed = urlparse(url if "://" in str(url) else f"https://{url}")
        host = (parsed.hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return str(url or "").lower()


@dataclass
class CacheLayer:
    """A namespaced, TTL'd JSON store.

    ``version`` is part of every key, so changing the shape of what a layer
    stores is a one-character change that orphans the old entries instead of
    deserializing them into the new code.
    """

    namespace: str
    ttl_seconds: int
    version: str = "v1"

    def key(self, identity: str) -> str:
        digest = hashlib.sha256(f"{self.version}:{identity}".encode()).hexdigest()[:32]
        return f"pv:{self.namespace}:{self.version}:{digest}"

    def get(self, identity: str) -> Optional[Dict[str, Any]]:
        client = _redis()
        if client is None:
            return None
        try:
            raw = client.get(self.key(identity))
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s cache read failed: %s", self.namespace, exc)
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None

    def set(self, identity: str, payload: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        client = _redis()
        if client is None or not isinstance(payload, dict):
            return False
        body = {**payload, "_cached_at": time.time()}
        try:
            client.setex(
                self.key(identity),
                int(ttl_seconds or self.ttl_seconds),
                json.dumps(body, default=str),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s cache write failed: %s", self.namespace, exc)
            return False

    def delete(self, identity: str) -> bool:
        client = _redis()
        if client is None:
            return False
        try:
            return bool(client.delete(self.key(identity)))
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s cache delete failed: %s", self.namespace, exc)
            return False

    def get_or_compute(
        self,
        identity: str,
        compute: Callable[[], Optional[Dict[str, Any]]],
        *,
        on_hit: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Read-through. ``on_hit`` is where callers record the degradation."""
        hit = self.get(identity)
        if hit is not None:
            if on_hit is not None:
                on_hit(hit)
            return hit
        value = compute()
        if isinstance(value, dict) and value:
            self.set(identity, value)
        return value


# ---------------------------------------------------------------------------
# The layers
# ---------------------------------------------------------------------------

# Screenshots go stale as a page is redesigned, but not within a working day —
# and re-capturing is the single most expensive thing the engine does.
ScreenshotCache = CacheLayer(namespace="screenshot", ttl_seconds=6 * 3600)

# Brand identity is the slowest-moving thing about a site: a logo and a palette
# change on the order of a rebrand. Keyed by domain, which is what makes a bulk
# job over one site extract the brand once instead of once per URL.
BrandCache = CacheLayer(namespace="brand", ttl_seconds=7 * 24 * 3600)

# The art director's output is a pure function of what it saw, so the key is a
# hash of exactly that. Doubles as a regression fixture store: every entry is an
# (input, output) pair a prompt change can be replayed against.
ReasoningCache = CacheLayer(namespace="reasoning", ttl_seconds=14 * 24 * 3600)


def reasoning_fingerprint(
    *,
    url: str,
    title: str = "",
    text: str = "",
    screenshot_phash: str = "",
    model: str = "",
    prompt_version: str = "",
) -> str:
    """Identity of one art-director call.

    Everything that changes the answer goes in: the copy it read, a perceptual
    hash of what it saw, and the model plus prompt version that produced it. A
    prompt edit therefore misses cache rather than serving output authored by
    the previous prompt.
    """
    parts = [
        domain_of(url),
        (title or "").strip()[:200],
        hashlib.sha256((text or "").encode()).hexdigest()[:16],
        screenshot_phash or "",
        model or "",
        prompt_version or "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def screenshot_phash(image_bytes: Optional[bytes]) -> str:
    """Cheap perceptual hash — a 8x8 mean-threshold aHash as 16 hex chars.

    Not a real pHash: we want "is this visually the same page" for cache
    identity, and a DCT would be precision nobody consumes here. Same reason it
    tolerates a missing PIL rather than making the cache a hard dependency on it.
    """
    if not image_bytes:
        return ""
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(image_bytes)).convert("L").resize((8, 8))
        pixels = list(img.getdata())
        mean = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= mean else "0" for p in pixels)
        return f"{int(bits, 2):016x}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("phash failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

# Every result-cache namespace a preview can land in. Kept beside the layers so
# adding a lane means editing one list, not hunting for the string.
RESULT_PREFIXES: List[str] = [
    "preview:focus:",
    "preview:analysis:",
    "demo:preview:",
    "demo:preview:v2:",
    "demo:preview:v3:fast:",
    "demo:preview:v3:balanced:",
    "demo:preview:v3:ultra:",
    "demo:preview:v3:template:",
    "preview:engine:",
    "preview:enhanced:",
    "saas:preview:",
    "saas:preview:ai:",
    "saas:preview:template:",
]


def invalidate_url(url: str) -> int:
    """Drop every cached artefact for one URL. Returns entries removed."""
    client = _redis()
    if client is None or not url:
        return 0

    removed = 0
    try:
        from backend.services.preview_cache import generate_cache_key

        keys = [generate_cache_key(url, prefix) for prefix in RESULT_PREFIXES]
        keys.append(ScreenshotCache.key(url))
        removed = int(client.delete(*keys) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("URL cache invalidation failed for %s: %s", str(url)[:80], exc)
    return removed


def invalidate_domain(domain_or_url: str, *, urls: Optional[List[str]] = None) -> int:
    """Bust a site's brand cache and any result caches we can name.

    Called when brand settings are saved or a logo is uploaded. The brand entry
    is keyed by domain so it always goes; result entries are keyed by URL, so
    the caller passes the URLs it knows about (the org's previews) and we clear
    those. Anything not passed expires on its own TTL — bounded staleness, not
    the day-long staleness of doing nothing.
    """
    domain = domain_of(domain_or_url)
    if not domain:
        return 0

    removed = 1 if BrandCache.delete(domain) else 0
    for url in urls or []:
        removed += invalidate_url(url)
    logger.info("Invalidated brand cache for %s (%d entries total)", domain, removed)
    return removed


def cache_stats() -> Dict[str, Any]:
    """Per-layer entry counts for the ops dashboard."""
    client = _redis()
    if client is None:
        return {"enabled": False}

    stats: Dict[str, Any] = {"enabled": True}
    for layer in (ScreenshotCache, BrandCache, ReasoningCache):
        try:
            pattern = f"pv:{layer.namespace}:{layer.version}:*"
            stats[layer.namespace] = sum(1 for _ in client.scan_iter(pattern, count=500))
        except Exception as exc:  # noqa: BLE001
            stats[layer.namespace] = f"error: {exc}"
    return stats
