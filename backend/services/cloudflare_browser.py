"""Optional Cloudflare Browser Rendering offload for screenshot capture.

When enabled (BROWSER_RENDERING_ENABLED + credentials), the worker fetches the
page screenshot and rendered HTML from Cloudflare's Browser Rendering REST API
instead of launching a local Chromium via Playwright. This relieves the VPS.

Everything here is best-effort and self-contained: a Redis failure never blocks
a screenshot, and any remote failure lets the caller fall back to local capture.
"""
import base64
import logging
import time
from datetime import datetime

import requests

from backend.core.config import settings
from backend.queue.queue_connection import get_redis_connection

logger = logging.getLogger(__name__)

# 40 days keeps the current month's counter alive well past month-end while
# ensuring stale months eventually self-expire.
_USAGE_TTL_SECONDS = 40 * 24 * 60 * 60

# Injected into the page before the screenshot so cookie/consent banners don't
# pollute the capture. Local Playwright actively dismisses these; the remote path
# can't, so we hide the common CMP surfaces + undo any scroll-lock they set.
# Best-effort and heuristic — covers OneTrust, Cookiebot, Osano, Termly, Iubenda,
# Quantcast, Usercentrics, TrustArc, Google Funding Choices, and generic classes.
_COOKIE_HIDE_CSS = (
    '[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],'
    '[id*="gdpr" i],[class*="gdpr" i],[class*="cmp-" i],[aria-label*="cookie" i],'
    '[aria-label*="consent" i],#onetrust-banner-sdk,#onetrust-consent-sdk,#onetrust-pc-sdk,'
    '.onetrust-pc-dark-filter,#CybotCookiebotDialog,.cc-window,.cookie-banner,.cookie-notice,'
    '.osano-cm-window,.termly-consent-banner,#iubenda-cs-banner,.qc-cmp2-container,'
    '#usercentrics-root,.fc-consent-root,.truste_overlay,.truste_box_overlay'
    '{display:none!important}html,body{overflow:auto!important}'
)


def _usage_key() -> str:
    """Redis key for the current UTC month's browser-seconds counter."""
    return f"cf:browser:seconds:{datetime.utcnow().strftime('%Y%m')}"


def _usage_seconds() -> int:
    """Current month's recorded browser-seconds (0 if missing or on any error)."""
    try:
        redis_client = get_redis_connection()
        value = redis_client.get(_usage_key())
        if value is None:
            return 0
        return int(float(value))
    except Exception:
        return 0


def _record_seconds(n: float) -> None:
    """Add measured seconds to the monthly counter; never raise."""
    try:
        redis_client = get_redis_connection()
        key = _usage_key()
        redis_client.incrbyfloat(key, n)
        redis_client.expire(key, _USAGE_TTL_SECONDS)
    except Exception:
        pass


def browser_rendering_available() -> bool:
    """True only if remote rendering is enabled, credentialed, and under cap.

    A Redis failure while reading the usage counter is treated as available so a
    transient counter problem never blocks a screenshot; only an explicit
    at/over-cap reading returns False (so we fall back locally and avoid overage).
    """
    if not settings.BROWSER_RENDERING_ENABLED:
        return False
    if not settings.CF_ACCOUNT_ID or not settings.CF_BROWSER_RENDERING_TOKEN:
        return False
    if _usage_seconds() >= settings.BROWSER_RENDERING_MONTHLY_SECONDS_CAP:
        return False
    return True


def cloudflare_snapshot(url: str, timeout: int = 45) -> tuple:
    """Capture a page via Cloudflare Browser Rendering.

    Returns (screenshot_bytes, html_content, dom_data) where dom_data is always
    an empty dict (the pipeline tolerates it, matching the local HTML-only path).
    Raises RuntimeError on any non-200 / unsuccessful response so the caller can
    fall back to local Playwright capture.
    """
    api_url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.CF_ACCOUNT_ID}/browser-rendering/snapshot"
    )
    headers = {
        "Authorization": f"Bearer {settings.CF_BROWSER_RENDERING_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "viewport": {"width": 1200, "height": 630, "deviceScaleFactor": 2},
        "gotoOptions": {"waitUntil": "networkidle0", "timeout": 30000},
        "addStyleTag": [{"content": _COOKIE_HIDE_CSS}],
    }

    started = time.monotonic()
    response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
    elapsed = time.monotonic() - started

    if response.status_code != 200:
        raise RuntimeError(f"Cloudflare snapshot HTTP {response.status_code}")

    data = response.json()
    if not data.get("success"):
        raise RuntimeError("Cloudflare snapshot returned success=false")

    result = data.get("result") or {}
    screenshot_b64 = result.get("screenshot")
    if not screenshot_b64:
        raise RuntimeError("Cloudflare snapshot missing screenshot")

    screenshot_bytes = base64.b64decode(screenshot_b64)
    html_content = result.get("content") or ""

    _record_seconds(elapsed)
    logger.info(
        "Cloudflare Browser Rendering snapshot: url=%s elapsed=%.2fs "
        "monthly_usage=%ss/%ss",
        url,
        elapsed,
        _usage_seconds(),
        settings.BROWSER_RENDERING_MONTHLY_SECONDS_CAP,
    )

    return screenshot_bytes, html_content, {}
