"""Re-render a card from its stored spec — no page capture, no vision call.

Generating a preview is expensive: a headless browser visits the page, a vision
model reads the screenshot, and a quality loop grades the result. But almost
everything a *second* render of the same page needs is already decided by then.
``PreviewEngineResult.render_spec`` captures it — composition, palette, copy,
proof, and R2 URLs for the two crops — so re-rendering is just the rasterizer.

That makes three things cheap enough to ship:

  * an alternative hook rendered as its own card (A/B variants),
  * the same card composed at another aspect ratio (per-platform sizes),
  * a re-roll where the user changes the layout, panel or accent.

None of them spend an AI generation, because none of them call the model.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from backend.services.premium_card_renderer import (
    CARD_SIZES,
    LAYOUTS,
    render_premium_card_detailed,
)
from backend.services.r2_client import upload_file_to_r2

logger = logging.getLogger(__name__)

# What a user may steer on a re-roll. Copy is deliberately absent: rewriting the
# hook needs the model, which is what the AI allowance meters.
DIRECTABLE_LAYOUTS = tuple(LAYOUTS)
DIRECTABLE_PANELS = ("primary", "secondary", "dark", "light")
DIRECTABLE_ACCENTS = ("bar", "dot", "shape")

_FETCH_TIMEOUT = 10


def _as_data_uri(url: Optional[str]) -> Optional[str]:
    """Pull a stored crop back down as a data URI the renderer can inline."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code != 200 or not resp.content:
            return None
        return "data:image/png;base64," + base64.b64encode(resp.content).decode()
    except Exception as e:
        logger.warning("Could not fetch crop %s for re-render: %s", url, e)
        return None


def spec_is_renderable(render_spec: Optional[Dict[str, Any]]) -> bool:
    """Can this preview be re-rendered without regenerating it?

    Previews made before the spec existed — and any that fell through to the
    legacy image generator — have nothing to re-render from.
    """
    return bool(render_spec and isinstance(render_spec, dict) and render_spec.get("composition"))


def apply_direction(
    render_spec: Dict[str, Any],
    *,
    layout: Optional[str] = None,
    panel: Optional[str] = None,
    accent: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a copy of the spec with the user's overrides applied.

    Unknown or unsupported values are ignored rather than rejected: a direction
    is a preference, and the worst outcome of a bad one should be the card the
    user already had.
    """
    spec = {**render_spec, "composition": {**(render_spec.get("composition") or {})}}
    composition = spec["composition"]

    if layout and layout in DIRECTABLE_LAYOUTS:
        composition["layout"] = layout
        # Only the panel layouts consume a visual. Asking for one elsewhere
        # would reserve a panel the renderer never fills.
        composition["use_visual"] = layout in ("split", "product")
    if panel and panel in DIRECTABLE_PANELS:
        composition["panel_color_role"] = panel
    if accent and accent in DIRECTABLE_ACCENTS:
        composition["accent_moment"] = accent

    return spec


def rerender_card(
    render_spec: Dict[str, Any],
    *,
    url: str,
    title: str,
    subtitle: Optional[str] = None,
    size: str = "wide",
    is_demo: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """Render one card from a stored spec and upload it.

    Returns ``(image_url, rendered_layout)``; ``(None, None)`` when the render or
    the upload failed. Callers treat that as "keep what you had" — a failed
    re-render must never blank an existing card.
    """
    if not spec_is_renderable(render_spec):
        return None, None

    composition = render_spec.get("composition") or {}
    try:
        png, rendered_layout = render_premium_card_detailed(
            title=title,
            subtitle=subtitle if subtitle is not None else render_spec.get("subtitle"),
            url=url,
            brand_name=render_spec.get("brand_name"),
            colors=render_spec.get("colors") or {},
            composition=composition,
            logo_data_uri=_as_data_uri(render_spec.get("logo_url")),
            visual_data_uri=_as_data_uri(render_spec.get("visual_url")),
            hide_watermark=bool(render_spec.get("hide_watermark")),
            proof=render_spec.get("proof"),
            cta_text=render_spec.get("cta_text"),
            size=size,
        )
    except Exception as e:
        logger.warning("Card re-render failed (%s, size=%s): %s", url, size, e)
        return None, None

    if not png:
        return None, None

    try:
        folder = "demo" if is_demo else "saas"
        suffix = "" if size == "wide" else f"-{size}"
        image_url = upload_file_to_r2(
            png, f"previews/{folder}/{uuid4()}{suffix}.png", "image/png"
        )
    except Exception as e:
        logger.warning("Re-rendered card upload failed (%s): %s", url, e)
        return None, None

    return image_url, rendered_layout


def render_platform_sizes(
    render_spec: Dict[str, Any],
    *,
    url: str,
    title: str,
    subtitle: Optional[str] = None,
    sizes: Optional[list] = None,
    is_demo: bool = False,
) -> Dict[str, str]:
    """Render the same card at several aspects. Missing sizes are simply absent.

    Each size is composed at its own dimensions rather than cropped out of the
    wide card, so a square is laid out as a square — stacked, with the type
    resized — instead of being a chopped-up link preview.
    """
    wanted = [s for s in (sizes or list(CARD_SIZES)) if s in CARD_SIZES]
    out: Dict[str, str] = {}
    for size in wanted:
        image_url, _ = rerender_card(
            render_spec, url=url, title=title, subtitle=subtitle,
            size=size, is_demo=is_demo,
        )
        if image_url:
            out[size] = image_url
        else:
            logger.info("Skipping %s card for %s — render unavailable", size, url)
    return out
