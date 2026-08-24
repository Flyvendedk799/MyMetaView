"""Focal crops, and refusing the ones that grabbed the wrong thing.

The art director looks at a screenshot and draws a box around the page's hero
visual. That box is a *request*: the model is reading a scaled-down image and
regularly returns a rectangle that turns out to be a nav bar, a cookie banner,
or a stretch of empty background. Cropping it anyway puts that in the card's
panel, which is worse than not using a panel at all.

``crop_focus`` does the crop and then judges it: a real hero region has visual
activity (edges, color spread) well above the page's baseline. When the crop
comes back flatter than the page around it, we reject it and say why, and the
renderer falls back to the typographic layout — a deliberate design, not a
broken one.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# A crop smaller than this cannot fill a panel without visible upscaling.
MIN_CROP_PX = 160

# Saliency floors. Both are measured against the page's own baseline rather
# than absolute values, because a minimalist page's "busy" region is quieter
# than a dense page's background.
MIN_SALIENCY_RATIO = 0.55
MIN_ABSOLUTE_SALIENCY = 0.012


@dataclass
class FocalCropResult:
    """The crop, plus whether it is worth using and why."""

    data_uri: Optional[str] = None
    accepted: bool = False
    saliency: float = 0.0
    baseline: float = 0.0
    reason: str = ""

    @property
    def ratio(self) -> float:
        return self.saliency / self.baseline if self.baseline > 0 else 0.0


def saliency_of(img) -> float:
    """How much is going on in this region, 0..1.

    Edge density plus color spread: text and product photography score high, a
    flat background or a solid nav bar score near zero. Cheap on purpose — this
    runs inside a stage with a deadline, and a saliency model would cost more
    than the crop is worth.
    """
    try:
        from PIL import ImageFilter

        gray = img.convert("L").resize((96, 96))
        edges = gray.filter(ImageFilter.FIND_EDGES).crop((2, 2, 94, 94))
        pixels = list(edges.getdata())
        if not pixels:
            return 0.0
        edge_density = sum(1 for p in pixels if p > 36) / len(pixels)

        rgb = img.convert("RGB").resize((32, 32))
        channels = list(zip(*rgb.getdata()))
        spread = 0.0
        for channel in channels[:3]:
            mean = sum(channel) / len(channel)
            spread += (sum((v - mean) ** 2 for v in channel) / len(channel)) ** 0.5
        colour_spread = min(1.0, (spread / 3.0) / 80.0)
        return round(0.7 * edge_density + 0.3 * colour_spread, 5)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Saliency measurement failed: %s", exc)
        return 0.0


def _normalize_box(
    focus: Dict[str, Any],
    width: int,
    height: int,
) -> Optional[Tuple[int, int, int, int]]:
    """Turn the director's box into pixel coordinates.

    Accepts fractional (0..1) or absolute pixel boxes and both naming
    conventions the prompts have used, because the model does not reliably pick
    one and rejecting the other spelling would silently disable the split
    layout.
    """
    if not isinstance(focus, dict):
        return None

    def pick(*names):
        for name in names:
            if name in focus and focus[name] is not None:
                try:
                    return float(focus[name])
                except (TypeError, ValueError):
                    continue
        return None

    left = pick("x", "left", "x0")
    top = pick("y", "top", "y0")
    box_w = pick("width", "w")
    box_h = pick("height", "h")
    right = pick("x1", "right")
    bottom = pick("y1", "bottom")

    if box_w is None and right is not None and left is not None:
        box_w = right - left
    if box_h is None and bottom is not None and top is not None:
        box_h = bottom - top
    if None in (left, top, box_w, box_h):
        return None

    # Fractional when everything is within 0..1 and the box is not degenerate.
    fractional = all(0.0 <= v <= 1.0 for v in (left, top, box_w, box_h)) and box_w <= 1.0
    if fractional:
        left, box_w = left * width, box_w * width
        top, box_h = top * height, box_h * height

    x0 = max(0, int(left))
    y0 = max(0, int(top))
    x1 = min(width, int(left + box_w))
    y1 = min(height, int(top + box_h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return (x0, y0, x1, y1)


def crop_focus(
    screenshot_bytes: Optional[bytes],
    focus: Optional[Dict[str, Any]],
    *,
    max_edge: int = 1400,
) -> FocalCropResult:
    """Crop the director's focus box and decide whether to trust it.

    Returns a result whose ``accepted`` flag is what the caller acts on. A
    rejected crop still carries its numbers so the trace can say *why* the panel
    went away rather than just that it did.
    """
    if not screenshot_bytes or not focus:
        return FocalCropResult(reason="no screenshot or focus box")

    try:
        from PIL import Image

        page = Image.open(BytesIO(screenshot_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        return FocalCropResult(reason=f"screenshot decode failed: {exc}")

    box = _normalize_box(focus, page.width, page.height)
    if box is None:
        return FocalCropResult(reason="focus box unusable")

    crop = page.crop(box)
    if crop.width < MIN_CROP_PX or crop.height < MIN_CROP_PX // 2:
        return FocalCropResult(
            reason=f"crop too small ({crop.width}x{crop.height})"
        )

    baseline = saliency_of(page)
    saliency = saliency_of(crop)

    # The crop must be at least as interesting as the page it came from. A nav
    # bar or a flat hero background fails this; an actual product shot does not.
    if saliency < MIN_ABSOLUTE_SALIENCY or (
        baseline > 0 and saliency / baseline < MIN_SALIENCY_RATIO
    ):
        return FocalCropResult(
            saliency=saliency,
            baseline=baseline,
            reason=(
                f"crop saliency {saliency:.4f} vs page {baseline:.4f} — "
                "looks like chrome or empty background"
            ),
        )

    if crop.width > max_edge:
        ratio = max_edge / crop.width
        crop = crop.resize(
            (max_edge, max(1, int(crop.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    buffer = BytesIO()
    crop.save(buffer, format="PNG", optimize=True)
    return FocalCropResult(
        data_uri="data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
        accepted=True,
        saliency=saliency,
        baseline=baseline,
        reason=f"crop saliency {saliency:.4f} vs page {baseline:.4f}",
    )
