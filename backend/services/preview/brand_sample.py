"""The My Site tab's sample card.

The sample is the only feedback a customer gets on their brand settings before
real cards are generated, so it has to be drawn the way real cards are: the
same plan gating (``branding.engine_payload``), the same card-preference rules,
the same font rule, and the same logo treatment — usability check and
panel-contrast fix included. It used to compose its own spec beside the engine,
fetch the logo with a bare ``requests.get`` (no SSRF guard), and draw marks the
engine would have dropped or plated.

It renders the *draft* the user is editing, not only what is saved, so every
control answers immediately instead of after a save round-trip.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from backend.services.preview.branding import chosen_font
from backend.services.preview.composition.builder import (
    DEFAULT_COMPOSITION,
    apply_card_preferences,
    fit_logo,
)
from backend.services.preview.extraction.brand import uploaded_logo

SAMPLE_TITLE = "Plans that scale with your team"
SAMPLE_SUBTITLE = "Usage-based pricing that grows only when you do."
SAMPLE_PATH = "/pricing"


def sample_spec(
    settings: Dict[str, Any],
    *,
    host: str,
    fallback_name: Optional[str] = None,
    logo_data_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Keyword arguments for ``render_premium_card`` from engine-shaped settings.

    ``settings`` is what ``engine_payload`` returns, so gating has already been
    applied. ``logo_data_uri`` lets a caller pass a mark it already holds;
    otherwise the saved/draft ``logo_url`` is loaded the way the engine does.
    """
    colors = {
        key: settings.get(key)
        for key in ("primary_color", "secondary_color", "accent_color")
        if settings.get(key)
    }

    composition = dict(DEFAULT_COMPOSITION)
    composition, _ = apply_card_preferences(composition, settings)
    # The sample has no page screenshot, so a panel layout shows its
    # typographic fallback — which is also what a real card does when the
    # page gives the art director nothing worth cropping.
    composition["use_visual"] = False
    composition["visual_source"] = "none"

    logo = logo_data_uri or uploaded_logo(settings.get("logo_url"))
    composition, logo = fit_logo(composition, colors, logo)

    brand_name = (settings.get("brand_name") or fallback_name or "").strip() or None
    return {
        "title": SAMPLE_TITLE,
        "subtitle": settings.get("tagline") or SAMPLE_SUBTITLE,
        "url": f"{host}{SAMPLE_PATH}",
        "brand_name": brand_name,
        "colors": colors,
        "composition": composition,
        "logo_data_uri": logo,
        "hide_watermark": bool(settings.get("hide_watermark")),
        "font_family": chosen_font(settings),
    }


def render_sample_data_uri(
    settings: Dict[str, Any],
    *,
    host: str,
    fallback_name: Optional[str] = None,
) -> str:
    """Render the sample and return it inline as a PNG data URI.

    Inline rather than uploaded: the sample is redrawn as the user edits, and
    each redraw used to leave another orphaned PNG in the public bucket.
    """
    from backend.services.premium_card_renderer import render_premium_card

    png = render_premium_card(
        **sample_spec(settings, host=host, fallback_name=fallback_name)
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


def sample_host(brand_name: Optional[str], domain_name: Optional[str]) -> str:
    """The hostname printed on the sample: the real one when we know it."""
    if domain_name:
        return domain_name
    slug = "".join(ch for ch in (brand_name or "yourdomain").lower() if ch.isalnum())
    return f"{slug or 'yourdomain'}.com"
