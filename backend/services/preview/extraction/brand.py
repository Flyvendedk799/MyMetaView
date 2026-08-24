"""The extraction stage: who does this page belong to?

Name, mark, palette. All three are cached by *domain* rather than URL, which is
the fix that matters for bulk jobs: 200 pages of one site share one brand, and
the old cache re-derived it 200 times because its only key was the full URL.

A customer's own brand settings win over anything scraped — they typed their
name and uploaded their logo precisely so we would stop guessing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.services.preview.branding import disregarded, settings_of
from backend.services.preview.caching.layers import BrandCache, domain_of
from backend.services.preview.extraction.logo_resolver import logo_degradation, resolve_logo
from backend.services.preview.observability.reason_codes import (
    Degradation,
    PaletteSource,
    Stage,
)
from backend.services.preview.stages import BrandResult, CaptureResult, PipelineState

logger = logging.getLogger(__name__)

# The extractor substitutes these when a light page has no dominant color. They
# are a heuristic guess, not the brand, and must never outrank a real read.
SYNTHETIC_SLATE_PRIMARIES = {"#475569", "#334155", "#64748b", "#64748B"}


def extract_brand(state: PipelineState, capture: CaptureResult) -> BrandResult:
    """Resolve the page's identity, reading the domain cache first."""
    domain = domain_of(state.url)
    state.update_progress(0.22, "Reading brand identity…")

    cached = BrandCache.get(domain) if domain else None
    if cached:
        state.trace.degrade(
            Degradation.BRAND_CACHED, Stage.EXTRACTION,
            detail=f"brand for {domain} served from cache",
        )
        result = _from_payload(cached, domain)
        return _apply_brand_settings(state, result)

    result = _extract_fresh(state, capture, domain)

    if result.brand_name or result.colors:
        BrandCache.set(domain, _to_payload(result))

    return _apply_brand_settings(state, result)


def _extract_fresh(
    state: PipelineState,
    capture: CaptureResult,
    domain: str,
) -> BrandResult:
    """Read the brand off the page itself."""
    from backend.services.brand_extractor import extract_brand_colors, extract_brand_name

    result = BrandResult(domain=domain)

    try:
        result.brand_name = extract_brand_name(capture.html, state.url)
    except Exception as exc:  # noqa: BLE001
        state.trace.degrade(
            Degradation.BRAND_EXTRACTION_FAILED, Stage.EXTRACTION,
            detail=f"brand name: {exc}",
        )

    try:
        colors = extract_brand_colors(
            capture.html,
            capture.screenshot_bytes if capture.has_screenshot else None,
        ) or {}
        result.colors = colors
        primary = str(colors.get("primary_color", "")).lower()
        if not colors:
            result.palette_source = PaletteSource.DEFAULT
        elif primary in {c.lower() for c in SYNTHETIC_SLATE_PRIMARIES}:
            # A synthetic slate means the sampler found nothing dominant. Saying
            # so is what stops it being treated as the brand's real primary.
            result.palette_source = PaletteSource.DERIVED
            state.trace.degrade(
                Degradation.BRAND_COLORS_DEFAULT, Stage.EXTRACTION,
                detail=f"palette fell back to synthetic slate ({primary})",
            )
        elif capture.has_screenshot:
            result.palette_source = PaletteSource.SAMPLED
        else:
            result.palette_source = PaletteSource.DERIVED
    except Exception as exc:  # noqa: BLE001
        state.trace.degrade(
            Degradation.BRAND_COLORS_DEFAULT, Stage.EXTRACTION,
            detail=f"palette extraction failed: {exc}",
        )
        result.palette_source = PaletteSource.DEFAULT

    logo_uri, candidate, notes = resolve_logo(capture.html, state.url)
    result.logo_data_uri = logo_uri
    code, detail = logo_degradation(logo_uri, candidate, notes)
    state.trace.degrade(code, Stage.EXTRACTION, detail=detail)

    # Cropping the screenshot's top-left is the last resort, and only worth it
    # when the markup gave us nothing at all.
    if not result.logo_data_uri and capture.has_screenshot:
        cropped = _logo_from_screenshot(capture.screenshot_bytes)
        if cropped:
            result.logo_data_uri = cropped
            state.trace.degrade(
                Degradation.BRAND_LOGO_FALLBACK_SCREENSHOT, Stage.EXTRACTION,
                detail="cropped the page's top-left corner",
            )

    state.trace.palette_source = result.palette_source
    return result


def _logo_from_screenshot(screenshot_bytes: bytes) -> Optional[str]:
    try:
        from backend.services.brand_extractor import _extract_logo_from_screenshot

        raw = _extract_logo_from_screenshot(screenshot_bytes)
        if not raw:
            return None
        return raw if str(raw).startswith("data:") else f"data:image/png;base64,{raw}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("Screenshot logo crop failed: %s", exc)
        return None


def _apply_brand_settings(state: PipelineState, result: BrandResult) -> BrandResult:
    """A customer's typed-in identity beats anything we scraped.

    They filled these in so we would stop inferring. Blank fields still mean
    "keep inferring", which is why this only overrides what is actually set.

    Colours follow a three-step rule rather than the old all-or-nothing one:
    forced settings win outright; otherwise a real read off the page wins; and
    when the page gave us nothing real — no palette at all, or the sampler's
    synthetic slate — the site's own colours are used instead of a grey we
    invented. "Take the branding into account" has to mean something in exactly
    the case where the page had no branding to find.
    """
    settings = settings_of(state.config)
    if not settings:
        return result

    if disregarded(settings):
        state.trace.degrade(
            Degradation.BRAND_SETTINGS_DISREGARDED, Stage.EXTRACTION,
            detail="this preview was added with site branding disregarded",
        )
        return result

    name = (settings.get("brand_name") or "").strip()
    if name:
        result.brand_name = name

    if settings.get("force_brand_colors"):
        result.colors = {
            "primary_color": settings.get("primary_color") or result.colors.get("primary_color"),
            "secondary_color": settings.get("secondary_color") or result.colors.get("secondary_color"),
            "accent_color": settings.get("accent_color") or result.colors.get("accent_color"),
        }
        result.palette_source = PaletteSource.BRAND_SETTINGS
        state.trace.palette_source = result.palette_source
        state.trace.degrade(
            Degradation.COMPOSITION_BRAND_OVERRIDES_APPLIED, Stage.EXTRACTION,
            detail="org forced its own brand colors",
        )
    elif _palette_is_guesswork(result) and _has_colors(settings):
        result.colors = {
            "primary_color": settings.get("primary_color") or result.colors.get("primary_color"),
            "secondary_color": settings.get("secondary_color") or result.colors.get("secondary_color"),
            "accent_color": settings.get("accent_color") or result.colors.get("accent_color"),
        }
        result.palette_source = PaletteSource.BRAND_SETTINGS
        state.trace.palette_source = result.palette_source
        state.trace.degrade(
            Degradation.BRAND_COLORS_FROM_SETTINGS, Stage.EXTRACTION,
            detail="page had no usable palette; using the site's own colours",
        )

    uploaded = _uploaded_logo(settings.get("logo_url"))
    if uploaded:
        result.logo_data_uri = uploaded
    return result


def _palette_is_guesswork(result: BrandResult) -> bool:
    """True when nothing on the page told us what this brand's colours are."""
    if not result.colors:
        return True
    if result.palette_source is PaletteSource.DEFAULT:
        return True
    primary = str(result.colors.get("primary_color", "")).lower()
    return primary in {c.lower() for c in SYNTHETIC_SLATE_PRIMARIES}


def _has_colors(settings: Dict[str, Any]) -> bool:
    return any(
        settings.get(key)
        for key in ("primary_color", "secondary_color", "accent_color")
    )


def _uploaded_logo(logo_url: Optional[str]) -> Optional[str]:
    """The customer's uploaded mark, as a data URI Chromium can draw.

    SVG passes straight through: the renderer is a browser, so a vector mark is
    drawn crisply at any size and rasterizing it here would only lose fidelity.
    """
    if not logo_url:
        return None
    try:
        from backend.services.preview.net import fetch

        result = fetch(str(logo_url), timeout=8.0)
        if not result.ok:
            logger.info("Uploaded logo unreachable (%s): %s", logo_url, result.error)
            return None

        content_type = (result.content_type or "").lower()
        if "svg" in content_type or result.content[:200].lstrip().startswith(b"<svg"):
            import base64

            return "data:image/svg+xml;base64," + base64.b64encode(result.content).decode()

        from backend.services.preview.assets.logo import normalize_logo

        return normalize_logo(result.content, content_type=content_type)
    except Exception as exc:  # noqa: BLE001
        logger.info("Uploaded logo fetch failed: %s", exc)
        return None


def _to_payload(result: BrandResult) -> Dict[str, Any]:
    return {
        "brand_name": result.brand_name,
        "logo_data_uri": result.logo_data_uri,
        "colors": dict(result.colors or {}),
        "palette_source": result.palette_source.value,
    }


def _from_payload(payload: Dict[str, Any], domain: str) -> BrandResult:
    try:
        source = PaletteSource(payload.get("palette_source", "default"))
    except ValueError:
        source = PaletteSource.DEFAULT
    return BrandResult(
        brand_name=payload.get("brand_name"),
        logo_data_uri=payload.get("logo_data_uri"),
        colors=dict(payload.get("colors") or {}),
        palette_source=source,
        from_cache=True,
        domain=domain,
    )


def to_legacy_dict(result: BrandResult) -> Dict[str, Any]:
    """The ``brand_elements`` shape the rest of the app still passes around."""
    logo_b64 = None
    if result.logo_data_uri and "," in result.logo_data_uri:
        logo_b64 = result.logo_data_uri.split(",", 1)[1]
    return {
        "brand_name": result.brand_name,
        "logo_base64": logo_b64,
        "logo_data_uri": result.logo_data_uri,
        "hero_image_base64": None,
        "colors": dict(result.colors or {}),
    }
