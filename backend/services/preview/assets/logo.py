"""Logos: rasterize them, judge them, and keep them visible on the panel.

Three problems, all of which shipped broken cards.

**SVG was skipped.** It is the most common format for a header logo, and the
extractor dropped every one of them because PIL cannot decode it — so sites with
a perfectly good vector wordmark got the text fallback. ``rasterize_svg``
renders at 2× the slot size through whichever rasterizer is installed.

**A logo can be a smudge.** A 60×12 crop of a nav bar scaled into a 34px slot
reads as lint in the corner. ``logo_is_usable`` rejects those so the clean
wordmark shows instead.

**A white logo on a white panel is invisible.** The renderer placed the mark on
a brand-colored panel and never checked it could be seen.
``resolve_logo_contrast`` measures the logo's dominant tone against the resolved
panel and either flips the panel role, puts the mark on a plate, or gives up on
the image and returns the wordmark.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

from backend.services.preview.quality.pixel_metrics import (
    contrast_ratio,
    hex_to_rgb,
    relative_luminance,
)

logger = logging.getLogger(__name__)

# The corner mark renders at 34 CSS px, on a 2× canvas, so 68px is 1:1. We
# rasterize at 4× the CSS size to keep it crisp if the layout ever grows it.
LOGO_TARGET_PX = 136

# Below this the mark is not reliably distinguishable from the panel behind it.
# 2.0:1 is deliberately under the WCAG text floor: a logo is a shape, not
# running copy, and demanding 4.5:1 would reject marks that read perfectly well.
MIN_LOGO_PANEL_CONTRAST = 2.0


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

_SVG_SIGNATURE = re.compile(rb"<svg[\s>]", re.IGNORECASE)


def looks_like_svg(content: bytes, content_type: str = "") -> bool:
    if "svg" in (content_type or "").lower():
        return True
    head = (content or b"")[:400].lstrip()
    return bool(_SVG_SIGNATURE.search(head)) or (
        head.startswith(b"<?xml") and b"<svg" in (content or b"")[:2000]
    )


def svg_rasterizer_available() -> Optional[str]:
    """Name of the rasterizer we can use, or None.

    Both backends are optional dependencies: a deployment without either keeps
    the old behaviour (skip SVG, use the wordmark) instead of failing to boot.
    """
    try:
        import cairosvg  # noqa: F401
        return "cairosvg"
    except Exception:  # noqa: BLE001
        pass
    try:
        from resvg_py import svg_to_bytes  # noqa: F401
        return "resvg"
    except Exception:  # noqa: BLE001
        pass
    return None


def rasterize_svg(
    svg_bytes: bytes,
    *,
    target_px: int = LOGO_TARGET_PX,
) -> Optional[bytes]:
    """SVG → PNG bytes at ``target_px`` wide, or None when we cannot.

    Rasterizing at the slot's 2× size rather than the SVG's intrinsic size is
    the point: a 16×16 favicon-sized SVG scales up to a crisp mark, where
    decoding at natural size and upscaling would blur it.
    """
    if not svg_bytes:
        return None

    backend = svg_rasterizer_available()
    if backend is None:
        logger.debug("No SVG rasterizer installed; skipping SVG logo")
        return None

    try:
        if backend == "cairosvg":
            import cairosvg

            return cairosvg.svg2png(
                bytestring=svg_bytes,
                output_width=target_px,
                background_color=None,
            )
        from resvg_py import svg_to_bytes

        raw = svg_to_bytes(
            svg_string=svg_bytes.decode("utf-8", errors="replace"),
            width=target_px,
        )
        return bytes(raw) if raw else None
    except Exception as exc:  # noqa: BLE001 — a bad SVG must not fail extraction
        logger.info("SVG rasterization failed (%s): %s", backend, exc)
        return None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_logo(
    content: bytes,
    *,
    content_type: str = "",
    min_width: int = 32,
    min_height: int = 12,
) -> Optional[str]:
    """Any logo bytes → a PNG data URI the renderer can inline, or None.

    SVG goes through the rasterizer; everything else goes through PIL. Both end
    as PNG with transparency preserved, so the mark sits on the panel rather
    than in a white box.
    """
    if not content:
        return None

    if looks_like_svg(content, content_type):
        png = rasterize_svg(content)
        if not png:
            return None
        content = png

    try:
        from PIL import Image

        img = Image.open(BytesIO(content))
        img.load()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Logo decode failed: %s", exc)
        return None

    if img.width < min_width or img.height < min_height:
        return None

    img = img.convert("RGBA")
    img = _trim_transparent_padding(img)
    if img.width < min_width or img.height < min_height:
        return None

    if img.width > LOGO_TARGET_PX * 2:
        ratio = (LOGO_TARGET_PX * 2) / img.width
        img = img.resize(
            (LOGO_TARGET_PX * 2, max(1, int(img.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _trim_transparent_padding(img):
    """Crop the empty margin an exported logo usually carries.

    Without this the mark is centred inside its own whitespace and renders
    visually smaller than the slot it was given.
    """
    try:
        bbox = img.getbbox()
        if bbox:
            cropped = img.crop(bbox)
            if cropped.width >= 8 and cropped.height >= 4:
                return cropped
    except Exception:  # noqa: BLE001
        pass
    return img


def logo_is_usable(data_uri: Optional[str]) -> bool:
    """Is this crop worth showing at 34px, or is it lint?

    Rejects marks that are too small, mostly transparent, or nearly one flat
    color. Errs toward showing: a decode failure returns True, because the
    renderer will simply not draw an image it cannot load, and refusing a mark
    we merely failed to inspect would cost real logos.
    """
    if not data_uri:
        return False
    try:
        from PIL import Image

        payload = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        img = Image.open(BytesIO(base64.b64decode(payload)))
        if img.width < 44 or img.height < 14:
            return False

        small = img.convert("RGBA").resize((16, 16))
        pixels = list(small.getdata())
        if sum(1 for p in pixels if p[3] < 24) > len(pixels) * 0.82:
            return False  # mostly transparent

        def variance(values):
            mean = sum(values) / len(values)
            return sum((v - mean) ** 2 for v in values) / len(values)

        spread = sum(variance([p[channel] for p in pixels]) for channel in range(3))
        return spread >= 80
    except Exception:  # noqa: BLE001
        return True


# ---------------------------------------------------------------------------
# Contrast against the panel
# ---------------------------------------------------------------------------

def logo_dominant_tone(data_uri: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """The mark's average visible color, ignoring transparent pixels.

    Transparency is why this is not just a mean: most logos are a shape on
    nothing, and averaging the empty pixels in would report every mark as
    mid-grey.
    """
    if not data_uri:
        return None
    try:
        from PIL import Image

        payload = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        img = Image.open(BytesIO(base64.b64decode(payload))).convert("RGBA").resize((24, 24))
    except Exception:  # noqa: BLE001
        return None

    visible = [p for p in img.getdata() if p[3] >= 48]
    if not visible:
        return None
    count = len(visible)
    return (
        int(sum(p[0] for p in visible) / count),
        int(sum(p[1] for p in visible) / count),
        int(sum(p[2] for p in visible) / count),
    )


@dataclass
class LogoContrastFix:
    """What to do so the mark is actually visible.

    ``needs_plate`` asks the renderer for a subtle light/dark chip behind the
    logo; ``panel_color_role`` swaps the panel itself; ``drop_logo`` gives up on
    the image and lets the text wordmark carry the brand. In that order of
    preference — the mark is the better artefact when it can be kept.
    """

    logo_data_uri: Optional[str]
    panel_color_role: str
    needs_plate: bool = False
    plate_color: Optional[str] = None
    drop_logo: bool = False
    ratio: float = 0.0
    changed: bool = False
    detail: str = ""


def resolve_logo_contrast(
    logo_data_uri: Optional[str],
    *,
    panel_hex: str,
    panel_color_role: str = "primary",
    alternate_panel_hex: Optional[str] = None,
    alternate_role: str = "light",
) -> LogoContrastFix:
    """Make sure the mark can be seen where it is about to be drawn.

    Three moves, cheapest first: keep everything if contrast is already fine;
    move the panel to a role where the mark reads; otherwise put the mark on a
    plate tuned to it. Dropping the logo is the last resort and only happens
    when we cannot measure the mark at all.
    """
    if not logo_data_uri:
        return LogoContrastFix(None, panel_color_role, detail="no logo")

    tone = logo_dominant_tone(logo_data_uri)
    panel_rgb = hex_to_rgb(panel_hex)
    if tone is None or panel_rgb is None:
        # Unmeasurable: keep the logo and let the renderer draw it. Guessing
        # "invisible" would cost real marks on unusual formats.
        return LogoContrastFix(logo_data_uri, panel_color_role, detail="tone unmeasurable")

    ratio = contrast_ratio(tone, panel_rgb)
    if ratio >= MIN_LOGO_PANEL_CONTRAST:
        return LogoContrastFix(
            logo_data_uri, panel_color_role, ratio=round(ratio, 2),
            detail=f"logo/panel contrast {ratio:.1f}:1",
        )

    # Try the alternate panel role before touching the mark.
    alternate_rgb = hex_to_rgb(alternate_panel_hex) if alternate_panel_hex else None
    if alternate_rgb is not None:
        alternate_ratio = contrast_ratio(tone, alternate_rgb)
        if alternate_ratio >= MIN_LOGO_PANEL_CONTRAST:
            return LogoContrastFix(
                logo_data_uri, alternate_role, ratio=round(alternate_ratio, 2),
                changed=True,
                detail=(
                    f"panel {panel_color_role}→{alternate_role}: logo contrast "
                    f"{ratio:.1f}:1 → {alternate_ratio:.1f}:1"
                ),
            )

    # Keep the panel, give the mark a plate it reads against.
    plate = "#FBFBF9" if relative_luminance(tone) < 0.5 else "#0B1F18"
    return LogoContrastFix(
        logo_data_uri, panel_color_role,
        needs_plate=True, plate_color=plate,
        ratio=round(ratio, 2), changed=True,
        detail=f"logo contrast {ratio:.1f}:1 on panel — added {plate} plate",
    )


def apply_contrast_fix_to_spec(
    composition: Dict[str, Any],
    fix: LogoContrastFix,
) -> Dict[str, Any]:
    """Fold a contrast fix back into a composition spec."""
    updated = dict(composition or {})
    updated["panel_color_role"] = fix.panel_color_role
    if fix.needs_plate:
        updated["logo_plate"] = fix.plate_color
    else:
        updated.pop("logo_plate", None)
    return updated
