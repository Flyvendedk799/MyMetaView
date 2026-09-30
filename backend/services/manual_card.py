"""Template-lane card for a preview created by hand.

Manual create does not spend an art-director generation. It still has to leave
a real premium card in the library — the same renderer the engine uses, fed
only the title, description, and brand colours the user already provided.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.services.brand_resolver import DEFAULT_BRAND
from backend.services.card_rerender import rerender_card

logger = logging.getLogger(__name__)


def template_render_spec(
    *,
    title: str,
    description: Optional[str],
    domain: str,
    brand: Any = None,
    hide_watermark: bool = False,
) -> dict:
    """A render spec the restyle / platform-size paths can re-render from."""
    colors = {
        "primary_color": getattr(brand, "primary_color", None) or DEFAULT_BRAND["primary_color"],
        "secondary_color": getattr(brand, "secondary_color", None) or DEFAULT_BRAND["secondary_color"],
        "accent_color": getattr(brand, "accent_color", None) or DEFAULT_BRAND["accent_color"],
    }
    return {
        "composition": {
            "layout": "typographic",
            "panel_color_role": "primary",
            "accent_moment": "bar",
            "use_visual": False,
            "mood": "confident",
            "logo_plate": "wordmark",
        },
        "colors": colors,
        "brand_name": getattr(brand, "brand_name", None) or domain,
        "subtitle": description or "",
        "hide_watermark": bool(hide_watermark),
        "font_family": getattr(brand, "font_family", None) or DEFAULT_BRAND["font_family"],
        "proof": None,
        "cta_text": None,
        "logo_url": None,
        "visual_url": None,
        "rendered_layout": "typographic",
        "minimal": True,
        "title": title,
    }


def stamp_template_card(preview, brand: Any = None, *, hide_watermark: bool = False) -> None:
    """Render a typographic card onto ``preview`` in place.

    Raises RuntimeError when the renderer or the upload fails, so the caller
    can refuse to store a title-only row.
    """
    spec = template_render_spec(
        title=preview.title,
        description=preview.description,
        domain=preview.domain,
        brand=brand,
        hide_watermark=hide_watermark,
    )
    image_url, layout = rerender_card(
        spec,
        url=preview.url,
        title=preview.title,
        subtitle=preview.description,
    )
    if not image_url:
        raise RuntimeError("template card render produced no image")
    preview.image_url = image_url
    preview.composited_image_url = image_url
    preview.render_spec = spec
    preview.layout = layout or "typographic"
    preview.generation_mode = "template"
    logger.info("Stamped template card for %s", preview.url)
