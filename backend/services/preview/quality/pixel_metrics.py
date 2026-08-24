"""Mechanical scoring of a rendered card.

Every score here is computed from the PNG a human will see on Slack or X. That
is deliberate and it is the difference between this module and the quality
scoring that came before it: the old critics graded intermediate dicts, so a
card could score 0.9 while shipping a headline clipped mid-word on a panel with
no contrast.

Six measurements, each answering a failure we have actually shipped:

    contrast          white-on-white headline (WCAG ratio against real pixels)
    truncation        copy clipped at the safe-area edge
    logo occupancy    a 12px smudge in the corner where a logo should be
    palette match     a card whose colors have nothing to do with the site
    gradient-only     the 6.5 regression class: a pretty gradient, no content
    balance           everything crammed in one corner

The functions take bytes and return floats in [0, 1] where 1 is good, except
``contrast_ratio`` which returns a WCAG ratio (1–21) because that number is
meaningful on its own and clamping it would throw away information.

PIL is the only dependency and it is imported lazily: a scoring failure must
degrade to "unscored", never to "generation failed".
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

RGB = Tuple[int, int, int]


# ---------------------------------------------------------------------------
# Color math
# ---------------------------------------------------------------------------

def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Sequence[int]) -> float:
    """WCAG relative luminance."""
    r, g, b = (_srgb_to_linear(float(c)) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: Sequence[int], bg: Sequence[int]) -> float:
    """WCAG contrast ratio between two colors: 1.0 (identical) … 21.0 (black/white)."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def hex_to_rgb(value: Optional[str]) -> Optional[RGB]:
    if not value:
        return None
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return None


def _rgb_to_lab(rgb: Sequence[int]) -> Tuple[float, float, float]:
    """sRGB → CIELAB (D65). Written out rather than pulled from a color library
    because it is twenty lines and the dependency would be the heavier cost."""
    r, g, b = (_srgb_to_linear(float(c)) for c in rgb[:3])
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    # D65 white point
    x, y, z = x / 0.95047, y / 1.00000, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(rgb_a: Sequence[int], rgb_b: Sequence[int]) -> float:
    """CIE76 ΔE. Under ~2.3 is imperceptible; over ~30 is a different color."""
    la, aa, ba = _rgb_to_lab(rgb_a)
    lb, ab, bb = _rgb_to_lab(rgb_b)
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _open(image_bytes: bytes):
    from PIL import Image

    return Image.open(BytesIO(image_bytes)).convert("RGB")


def _dominant_colors(img, count: int = 5, sample: int = 64) -> List[RGB]:
    """The card's main colors, by quantized frequency."""
    small = img.resize((sample, sample))
    quantized = small.quantize(colors=max(2, count * 3), method=2).convert("RGB")
    counts: Dict[RGB, int] = {}
    for pixel in quantized.getdata():
        counts[pixel] = counts.get(pixel, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [color for color, _ in ranked[:count]]


def _region(img, box: Tuple[float, float, float, float]):
    """Crop by fractional box (l, t, r, b) in 0..1."""
    w, h = img.size
    left, top, right, bottom = box
    return img.crop((int(left * w), int(top * h), int(right * w), int(bottom * h)))


def _mean_color(img) -> RGB:
    pixels = list(img.resize((16, 16)).getdata())
    n = max(1, len(pixels))
    return (
        int(sum(p[0] for p in pixels) / n),
        int(sum(p[1] for p in pixels) / n),
        int(sum(p[2] for p in pixels) / n),
    )


def _variance(img) -> float:
    """Mean per-channel variance, normalized to roughly 0..1."""
    pixels = list(img.resize((48, 48)).getdata())
    n = max(1, len(pixels))
    out = 0.0
    for channel in range(3):
        values = [p[channel] for p in pixels]
        mean = sum(values) / n
        out += sum((v - mean) ** 2 for v in values) / n
    return min(1.0, (out / 3.0) / (128.0 ** 2))


def _edge_density(img) -> float:
    """Fraction of pixels that sit on an edge. Text is edges; a gradient is not.

    The outermost ring is dropped before counting: ``FIND_EDGES`` treats the
    image boundary itself as an edge, and on a 160px crop that frame is ~2.5%
    of the pixels — more than the signal we are trying to measure, which is why
    an early version of this scored a flat rectangle the same as a card full of
    type.
    """
    from PIL import ImageFilter

    gray = img.convert("L").resize((160, 160))
    edges = gray.filter(ImageFilter.FIND_EDGES).crop((2, 2, 158, 158))
    pixels = list(edges.getdata())
    if not pixels:
        return 0.0
    return sum(1 for p in pixels if p > 40) / len(pixels)


# ---------------------------------------------------------------------------
# The measurements
# ---------------------------------------------------------------------------

# Where the renderer puts things. The card is laid out in HTML with fixed
# padding, so these fractional boxes track the real safe area; if the renderer's
# geometry moves, these move with it.
#
# The horizontal extent is deliberately the *full* safe width rather than the
# left column: an RTL card mirrors its text to the right, and a left-column
# sampler measured empty panel on those — reporting a perfectly legible Arabic
# headline as barely-passing 3.0:1. The vertical band is where the headline sits
# in either direction, and sampling by luminance decile within the band finds
# the glyphs wherever they are.
TEXT_BOX = (0.055, 0.24, 0.945, 0.82)    # headline + subtitle band
EYEBROW_BOX = (0.055, 0.09, 0.945, 0.20)  # brand mark / mono label row
CONTENT_BOX = (0.04, 0.06, 0.96, 0.94)   # everything inside the bleed

# The corner mark slot. Unlike the text, this genuinely has a side — but which
# side flips with direction, so both are checked and the fuller one wins.
LOGO_BOX = (0.05, 0.07, 0.28, 0.18)
LOGO_BOX_RTL = (0.72, 0.07, 0.95, 0.18)


def text_contrast(image_bytes: bytes) -> Dict[str, float]:
    """Contrast of the text areas against the pixels actually behind them.

    Sampling the darkest and lightest deciles inside the text box, rather than
    its mean, is what makes this meaningful: a headline is a small fraction of
    the box's pixels, and averaging would report the panel's contrast with
    itself (1.0) on every card.
    """
    try:
        img = _open(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.debug("contrast scoring failed to open image: %s", exc)
        return {"title_contrast": 0.0, "eyebrow_contrast": 0.0}

    out: Dict[str, float] = {}
    for name, box in (("title_contrast", TEXT_BOX), ("eyebrow_contrast", EYEBROW_BOX)):
        pixels = _sample_pixels(_region(img, box))
        out[name] = _ink_contrast(pixels)
    return out


def _ink_contrast(pixels: List[RGB]) -> float:
    """Contrast between a region's background and the type drawn on it.

    Finding the ink is the hard part, and a fixed decile does not do it. The
    headline fills a good share of its band, but the eyebrow is a 19px mono
    label crossing maybe 1% of its band's pixels — so a 10%-decile "foreground"
    was 90% background, and every card reported its eyebrow at ~1.4:1 no matter
    what colour it actually was.

    Instead: the background is the region's dominant luminance, and the ink is
    the pixels furthest from it. Sparse type and dense type both work, because
    nothing here assumes how much of the region the type covers.
    """
    if not pixels:
        return 0.0

    lumas = [relative_luminance(p) for p in pixels]
    # Dominant luminance via a coarse histogram — the panel, whatever it is.
    buckets: Dict[int, int] = {}
    for luma in lumas:
        key = int(luma * 32)
        buckets[key] = buckets.get(key, 0) + 1
    dominant = max(buckets.items(), key=lambda kv: kv[1])[0] / 32.0

    # Ink = the pixels furthest from the background, capped so a handful of
    # anti-aliasing outliers cannot invent contrast that is not there.
    ranked = sorted(zip(lumas, pixels), key=lambda item: abs(item[0] - dominant), reverse=True)
    take = max(1, min(len(ranked) // 50, 400))
    ink_pixels = [p for _, p in ranked[:take]]
    if not ink_pixels:
        return 0.0

    count = len(ink_pixels)
    ink = (
        int(sum(p[0] for p in ink_pixels) / count),
        int(sum(p[1] for p in ink_pixels) / count),
        int(sum(p[2] for p in ink_pixels) / count),
    )
    background_pixels = [p for luma, p in ranked[-take:]] or ink_pixels
    background = (
        int(sum(p[0] for p in background_pixels) / len(background_pixels)),
        int(sum(p[1] for p in background_pixels) / len(background_pixels)),
        int(sum(p[2] for p in background_pixels) / len(background_pixels)),
    )
    return round(contrast_ratio(ink, background), 2)


# How many pixels to sample from a text region. Enough to be representative,
# few enough to stay fast on a 2400x1260 card.
_SAMPLE_TARGET = 12000


def _sample_pixels(region) -> List[RGB]:
    """Sample a region by striding, never by resizing.

    Resizing was the bug: a 19px mono eyebrow on a 1200px-wide card downscaled
    to 64px has its strokes averaged into the background, so every card reported
    its eyebrow at ~1.4:1 whatever it actually was. Striding keeps real pixel
    values, which is the whole point of measuring the artefact.
    """
    width, height = region.size
    if width < 2 or height < 2:
        return []
    total = width * height
    stride = max(1, int((total / _SAMPLE_TARGET) ** 0.5))
    pixels = region.load()
    return [
        pixels[x, y]
        for y in range(0, height, stride)
        for x in range(0, width, stride)
    ]


def text_overflow_risk(image_bytes: bytes) -> float:
    """0 = copy sits inside the safe area, 1 = ink is running off the edge.

    Ink in the last 2% of the card on any side means the layout overflowed —
    the renderer's padding guarantees a margin, so pixels there are a bug.
    """
    try:
        img = _open(image_bytes)
    except Exception:  # noqa: BLE001
        return 0.0

    w, h = img.size
    margin_w = max(2, int(w * 0.02))
    margin_h = max(2, int(h * 0.02))
    interior_mean = _mean_color(_region(img, CONTENT_BOX))

    strips = [
        img.crop((0, 0, w, margin_h)),
        img.crop((0, h - margin_h, w, h)),
        img.crop((0, 0, margin_w, h)),
        img.crop((w - margin_w, 0, w, h)),
    ]
    worst = 0.0
    for strip in strips:
        pixels = list(strip.resize((32, 8)).getdata())
        if not pixels:
            continue
        # "Ink" = a pixel far from both the strip's own background and the card
        # interior. A colored panel bleeding to the edge is by design; a glyph
        # is not, and a glyph is a high-contrast outlier within its strip.
        strip_bg = _mean_color(strip)
        outliers = sum(
            1 for p in pixels
            if delta_e(p, strip_bg) > 28 and delta_e(p, interior_mean) > 20
        )
        worst = max(worst, outliers / len(pixels))
    return round(min(1.0, worst * 4.0), 3)


def logo_slot_occupancy(image_bytes: bytes) -> float:
    """How much of the corner-mark slot carries actual mark, 0..1.

    Checked on the *final crop* rather than the input asset, which is the whole
    point: an SVG that decoded fine and a logo that scaled down to a smudge look
    identical upstream and completely different here.
    """
    try:
        img = _open(image_bytes)
    except Exception:  # noqa: BLE001
        return 0.0

    # Check both corners: RTL cards mirror the mark to the opposite side, and
    # scoring only one would report every RTL card as having no logo.
    best = 0.0
    for box in (LOGO_BOX, LOGO_BOX_RTL):
        slot = _region(img, box)
        pixels = list(slot.resize((40, 20)).getdata())
        if not pixels:
            continue
        background = _mean_color(slot)
        marked = sum(1 for p in pixels if delta_e(p, background) > 18)
        best = max(best, marked / len(pixels))
    return round(best, 3)


def palette_delta_e(
    image_bytes: bytes,
    expected_colors: Optional[Sequence[str]] = None,
) -> float:
    """Smallest ΔE between the card's dominant colors and the brand's.

    Answers "does this card look like it belongs to that site?". Returns a large
    number when there is nothing to compare against, so a caller that scores it
    treats "unknown" as "unmatched" rather than silently passing.
    """
    expected = [c for c in (hex_to_rgb(v) for v in (expected_colors or [])) if c]
    if not expected:
        return 100.0
    try:
        dominants = _dominant_colors(_open(image_bytes))
    except Exception:  # noqa: BLE001
        return 100.0
    if not dominants:
        return 100.0
    return round(min(delta_e(d, e) for d in dominants for e in expected), 2)


# Calibrated against rendered cards: a smooth gradient and a flat fill both
# score 0.0 edge density, the sparsest real card (one 64px word, nothing else)
# scores ~0.005, and an ordinary headline-plus-deck card scores ~0.03. The
# threshold sits below the sparsest real card on purpose — a false positive here
# rejects a good card, which is worse than missing a bad one.
_GRADIENT_EDGE_FLOOR = 0.0035
_GRADIENT_INK_FLOOR = 0.02


def detect_gradient_only(image_bytes: bytes) -> bool:
    """True when the card is a pretty gradient with no content on it.

    This is the 6.5 regression class, and it earns a dedicated detector because
    it passes every dict-level check: the copy exists, the palette is on-brand,
    the render "succeeded" — the type just never made it onto the canvas.

    Two signals have to agree. Edge density over the whole content region says
    "there is no structure here", and ink coverage in the headline box says "and
    in particular there are no glyphs where the headline goes". Requiring both
    is what keeps a deliberately spare card — one word, huge, on a flat panel —
    from being called broken.
    """
    try:
        img = _open(image_bytes)
    except Exception:  # noqa: BLE001
        return False

    if _edge_density(_region(img, CONTENT_BOX)) >= _GRADIENT_EDGE_FLOOR:
        return False

    text_area = _region(img, TEXT_BOX)
    pixels = list(text_area.resize((48, 48)).getdata())
    if not pixels:
        return True
    background = _mean_color(text_area)
    ink = sum(1 for p in pixels if delta_e(p, background) > 12) / len(pixels)
    return ink < _GRADIENT_INK_FLOOR


def visual_balance(image_bytes: bytes) -> float:
    """1.0 when ink is distributed across the card, 0 when it is all in one corner."""
    try:
        img = _open(image_bytes).convert("L").resize((64, 64))
    except Exception:  # noqa: BLE001
        return 0.5
    pixels = list(img.getdata())
    quadrants = [0.0, 0.0, 0.0, 0.0]
    for index, value in enumerate(pixels):
        x, y = index % 64, index // 64
        quadrants[(0 if x < 32 else 1) + (0 if y < 32 else 2)] += value
    total = sum(quadrants) or 1.0
    shares = [q / total for q in quadrants]
    # Perfectly even is 0.25 each; report how far the worst quadrant strays.
    spread = max(abs(share - 0.25) for share in shares)
    return round(max(0.0, 1.0 - spread * 3.0), 3)


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

# WCAG AA for large text is 3.0:1; headlines on these cards are 46px and up, so
# 3.0 is the floor and 4.5 is where we stop worrying.
MIN_TITLE_CONTRAST = 3.0
GOOD_TITLE_CONTRAST = 4.5
MIN_LOGO_OCCUPANCY = 0.06
MAX_PALETTE_DELTA_E = 45.0


@dataclass
class CardScore:
    """Every mechanical measurement of one rendered card, plus a verdict.

    ``passed`` is the CI gate's question; ``overall`` is the trend line's. The
    individual fields are what tell you *which* thing regressed, which is the
    reason they are all kept rather than collapsed into the single number.
    """

    title_contrast: float = 0.0
    eyebrow_contrast: float = 0.0
    overflow_risk: float = 0.0
    logo_occupancy: float = 0.0
    palette_delta_e: float = 100.0
    gradient_only: bool = False
    balance: float = 0.0
    width: int = 0
    height: int = 0
    bytes_len: int = 0
    issues: List[str] = field(default_factory=list)
    scored: bool = True

    @property
    def overall(self) -> float:
        """Weighted 0..1 summary. Contrast and gradient-only dominate because
        they are the two failures that make a card unusable rather than weak."""
        if not self.scored:
            return 0.0
        contrast_score = min(1.0, self.title_contrast / GOOD_TITLE_CONTRAST)
        overflow_score = 1.0 - min(1.0, self.overflow_risk)
        logo_score = min(1.0, self.logo_occupancy / 0.18)
        palette_score = max(0.0, 1.0 - (self.palette_delta_e / MAX_PALETTE_DELTA_E))
        gradient_penalty = 0.0 if self.gradient_only else 1.0
        return round(
            0.32 * contrast_score
            + 0.20 * overflow_score
            + 0.12 * logo_score
            + 0.16 * palette_score
            + 0.12 * self.balance
            + 0.08 * gradient_penalty,
            4,
        )

    @property
    def passed(self) -> bool:
        """Hard floor. A card that trips any of these is not shippable."""
        return (
            self.scored
            and not self.gradient_only
            and self.title_contrast >= MIN_TITLE_CONTRAST
            and self.overflow_risk < 0.25
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["overall"] = self.overall
        payload["passed"] = self.passed
        return payload


def score_card(
    image_bytes: Optional[bytes],
    *,
    expected_colors: Optional[Sequence[str]] = None,
    expect_logo: bool = True,
) -> CardScore:
    """Score a rendered card. Never raises — an unscorable card scores 0.

    ``expect_logo`` exists because a card whose brand has no logo renders the
    text wordmark by design, and penalising the empty logo slot there would
    report a defect where there is a deliberate choice.
    """
    if not image_bytes:
        return CardScore(scored=False, issues=["no image bytes"])

    try:
        img = _open(image_bytes)
        width, height = img.size
    except Exception as exc:  # noqa: BLE001
        return CardScore(scored=False, issues=[f"decode failed: {exc}"])

    contrasts = text_contrast(image_bytes)
    score = CardScore(
        title_contrast=contrasts.get("title_contrast", 0.0),
        eyebrow_contrast=contrasts.get("eyebrow_contrast", 0.0),
        overflow_risk=text_overflow_risk(image_bytes),
        logo_occupancy=logo_slot_occupancy(image_bytes),
        palette_delta_e=palette_delta_e(image_bytes, expected_colors),
        gradient_only=detect_gradient_only(image_bytes),
        balance=visual_balance(image_bytes),
        width=width,
        height=height,
        bytes_len=len(image_bytes),
    )

    if score.gradient_only:
        score.issues.append("gradient-only: no readable content detected")
    if score.title_contrast < MIN_TITLE_CONTRAST:
        score.issues.append(
            f"title contrast {score.title_contrast:.1f}:1 below {MIN_TITLE_CONTRAST}:1"
        )
    if score.overflow_risk >= 0.25:
        score.issues.append(f"text overflow risk {score.overflow_risk:.2f}")
    if expect_logo and score.logo_occupancy < MIN_LOGO_OCCUPANCY:
        score.issues.append(f"logo slot nearly empty ({score.logo_occupancy:.2f})")
    if expected_colors and score.palette_delta_e > MAX_PALETTE_DELTA_E:
        score.issues.append(f"palette ΔE {score.palette_delta_e:.0f} off brand")
    return score
