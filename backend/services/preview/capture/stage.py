"""The capture stage.

Input: a URL and the pipeline state. Output: a ``CaptureResult``. Nothing else
in the engine should know how a screenshot is taken.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from io import BytesIO
from typing import Any, Callable, Dict, Optional, Tuple

from backend.services.preview.budgets import StageBudget
from backend.services.preview.caching.layers import ScreenshotCache, domain_of
from backend.services.preview.net import SSRFError, guard_url
from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    Stage,
)
from backend.services.preview.stages import CaptureResult, PipelineState

logger = logging.getLogger(__name__)

# How long the local provider gets before we also start the remote one. Short
# enough that a stalled Chromium does not eat the stage, long enough that the
# common case (a page that renders in 2-4s) never pays for a second provider.
HEDGE_DELAY_S = 6.0

# A screenshot smaller than this is a blank page or an error card, not a capture.
MIN_SCREENSHOT_BYTES = 1000


def domain_breaker(domain: str):
    """Circuit breaker for one domain's captures.

    Per-domain rather than global: a single slow site must not stop the worker
    from capturing every other site in the queue, which a shared breaker would
    do.
    """
    from backend.services.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker

    return get_circuit_breaker(
        f"capture:{domain or 'unknown'}",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=120.0,
            success_threshold=1,
        ),
    )


def _placeholder_screenshot() -> bytes:
    """A neutral canvas so downstream stages have something to hold.

    Deliberately plain: any content here would look like a real capture to the
    art director, and it would author a card describing our placeholder.
    """
    try:
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (1200, 630), color="#F4F4F2").save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # noqa: BLE001
        return b""


def hedged_screenshot(
    url: str,
    *,
    local: Callable[[str], Tuple[bytes, str, Dict[str, Any]]],
    remote: Optional[Callable[[str], Tuple[bytes, str, Dict[str, Any]]]] = None,
    timeout_s: float = 20.0,
    hedge_after_s: float = HEDGE_DELAY_S,
) -> Tuple[Optional[Tuple[bytes, str, Dict[str, Any]]], str, Optional[str]]:
    """Race two capture providers, taking the first usable answer.

    Returns ``(payload, provider_name, error)``. The remote provider is only
    started if the local one has not answered by ``hedge_after_s`` — hedging
    every capture would double the bill for no benefit on the pages that work.
    """
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pv-capture")
    started = time.monotonic()
    futures: Dict[Any, str] = {}
    errors: Dict[str, str] = {}

    try:
        local_future = pool.submit(local, url)
        futures[local_future] = "local"

        while futures and (time.monotonic() - started) < timeout_s:
            remaining = timeout_s - (time.monotonic() - started)
            elapsed = time.monotonic() - started
            should_hedge = (
                remote is not None
                and "remote" not in futures.values()
                and elapsed >= hedge_after_s
            )
            slice_s = min(
                remaining,
                max(0.1, hedge_after_s - elapsed) if not should_hedge and remote else remaining,
            )

            done, _ = wait(list(futures), timeout=max(0.1, slice_s), return_when=FIRST_COMPLETED)
            for future in done:
                name = futures.pop(future)
                try:
                    payload = future.result()
                except Exception as exc:  # noqa: BLE001 — the other provider may still win
                    errors[name] = f"{type(exc).__name__}: {exc}"
                    logger.info("Capture provider %s failed for %s: %s", name, url, exc)
                    continue
                if payload and payload[0] and len(payload[0]) >= MIN_SCREENSHOT_BYTES:
                    return payload, name, None
                errors[name] = "screenshot too small"

            if should_hedge:
                logger.info("Hedging capture for %s after %.1fs", url, elapsed)
                remote_future = pool.submit(remote, url)
                futures[remote_future] = "remote"

        if not futures and errors:
            return None, "", "; ".join(f"{k}: {v}" for k, v in errors.items())
        return None, "", f"capture timed out after {timeout_s:.0f}s"
    finally:
        pool.shutdown(wait=False)


def _local_capture(url: str) -> Tuple[bytes, str, Dict[str, Any]]:
    from backend.services.playwright_screenshot import capture_screenshot_and_html

    return capture_screenshot_and_html(url)


def _remote_capture(url: str) -> Tuple[bytes, str, Dict[str, Any]]:
    """The screenshot API, wrapped to return the same triple as the local path.

    It only produces an image, so HTML comes from a plain guarded fetch — which
    is fine, because the pages that need this provider are the ones Chromium
    could not drive, not the ones that hide their markup.
    """
    from backend.services.screenshot_providers.api_provider import ApiScreenshotProvider

    screenshot = ApiScreenshotProvider().capture(url)
    html = ""
    try:
        from backend.services.preview.net import fetch

        result = fetch(url, timeout=8.0)
        html = result.text if result.ok else ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("HTML fetch alongside remote screenshot failed: %s", exc)
    return screenshot, html, {}


def _remote_available() -> bool:
    try:
        from backend.core.config import settings

        return bool(getattr(settings, "SCREENSHOT_API_KEY", ""))
    except Exception:  # noqa: BLE001
        return False


def _cloudflare_capture(url: str) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
    """Cloudflare Browser Rendering, when it is configured. Flag-gated, opt-in."""
    try:
        from backend.services.cloudflare_browser import (
            browser_rendering_available,
            cloudflare_snapshot,
        )

        if not browser_rendering_available():
            return None
        payload = cloudflare_snapshot(url)
        if payload and payload[0] and len(payload[0]) >= MIN_SCREENSHOT_BYTES:
            return payload
    except Exception as exc:  # noqa: BLE001
        logger.info("Cloudflare capture unavailable for %s: %s", url, exc)
    return None


def _html_only(url: str) -> str:
    """Last resort: the markup, without a browser."""
    try:
        from backend.services.preview.net import fetch

        result = fetch(url, timeout=10.0)
        if result.ok:
            return result.text
    except Exception as exc:  # noqa: BLE001
        logger.info("HTML-only fetch failed for %s: %s", url, exc)
    return ""


def capture_page(state: PipelineState) -> CaptureResult:
    """Capture a page. Degrades rather than raising, except on a refused URL.

    A URL the SSRF guard refuses is the one hard failure here: it is not a site
    being slow, it is a request we must not make, and pretending we merely
    failed to reach it would invite a retry.
    """
    url = state.url
    domain = domain_of(url)
    state.update_progress(0.08, "Capturing page…")

    try:
        guard_url(url)
    except SSRFError as exc:
        state.trace.degrade(
            Degradation.CAPTURE_PLACEHOLDER, Stage.CAPTURE,
            detail=str(exc), reason=FailureReason.CAPTURE_BLOCKED,
        )
        raise ValueError(f"Refusing to capture {url}: {exc}") from exc

    breaker = domain_breaker(domain)
    from backend.services.circuit_breaker import CircuitState

    if breaker.get_state() == CircuitState.OPEN:
        state.trace.degrade(
            Degradation.CAPTURE_CIRCUIT_OPEN, Stage.CAPTURE,
            detail=f"{domain} circuit open — skipping browser capture",
            reason=FailureReason.CAPTURE_BLOCKED,
        )
        html = _html_only(url)
        return _finish(state, url, html, b"", {}, provider="html-only",
                       error=None if html else "circuit open, no HTML")

    budget_s = state.budget.for_stage(Stage.CAPTURE)
    started = time.monotonic()

    cloudflare = _cloudflare_capture(url)
    if cloudflare is not None:
        state.budget.record(Stage.CAPTURE, time.monotonic() - started)
        breaker.record_success()
        return _finish(state, url, cloudflare[1], cloudflare[0], cloudflare[2],
                       provider="cloudflare")

    payload, provider, error = hedged_screenshot(
        url,
        local=_local_capture,
        remote=_remote_capture if _remote_available() else None,
        timeout_s=budget_s,
        hedge_after_s=min(HEDGE_DELAY_S, budget_s * 0.4),
    )
    state.budget.record(Stage.CAPTURE, time.monotonic() - started)

    if payload is not None:
        breaker.record_success()
        if provider == "remote":
            state.trace.degrade(
                Degradation.CAPTURE_HEDGED_TO_API, Stage.CAPTURE,
                detail="local capture was slow; screenshot API answered first",
            )
        return _finish(state, url, payload[1], payload[0], payload[2], provider=provider)

    breaker.record_failure(TimeoutError(error or "capture failed"))

    # No screenshot. HTML alone still makes a real card from the page's own
    # metadata, which is a much better outcome than failing the job.
    html = _html_only(url)
    if html:
        state.trace.degrade(
            Degradation.CAPTURE_HTML_ONLY, Stage.CAPTURE,
            detail=error or "no screenshot; using page markup",
            reason=FailureReason.CAPTURE_TIMEOUT,
        )
        return _finish(state, url, html, _placeholder_screenshot(), {},
                       provider="html-only", error=error)

    state.trace.degrade(
        Degradation.CAPTURE_PLACEHOLDER, Stage.CAPTURE,
        detail=error or "capture failed entirely",
        reason=FailureReason.CAPTURE_NETWORK_ERROR,
    )
    raise ValueError(f"Failed to capture {url}: {error or 'unknown capture failure'}")


def _finish(
    state: PipelineState,
    url: str,
    html: str,
    screenshot: bytes,
    dom_data: Dict[str, Any],
    *,
    provider: str,
    error: Optional[str] = None,
) -> CaptureResult:
    result = CaptureResult(
        url=url,
        html=html or "",
        screenshot_bytes=screenshot or b"",
        dom_data=dom_data or {},
        provider=provider,
        error=error,
    )
    if result.has_screenshot and provider not in ("html-only",):
        state.trace.degrade(
            Degradation.CAPTURE_OK, Stage.CAPTURE,
            detail=f"{provider}: {len(result.screenshot_bytes)}B screenshot, {len(result.html)}B html",
        )
    elif not result.has_screenshot:
        state.trace.degrade(
            Degradation.CAPTURE_SCREENSHOT_MISSING, Stage.CAPTURE,
            detail=f"{provider}: html only",
        )
    return result


def upload_screenshot(state: PipelineState, capture: CaptureResult) -> Optional[str]:
    """Put the raw screenshot in object storage. Best-effort by design.

    The card does not need this — it needs the crop — so a storage hiccup here
    costs the "view original" link, not the preview.
    """
    if not capture.has_screenshot:
        return None
    try:
        from uuid import uuid4

        from backend.services.r2_client import upload_file_to_r2

        folder = "demo" if state.is_demo else "saas"
        return upload_file_to_r2(
            capture.screenshot_bytes,
            f"screenshots/{folder}/{uuid4()}.png",
            "image/png",
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Screenshot upload failed (non-fatal): %s", exc)
        return None
