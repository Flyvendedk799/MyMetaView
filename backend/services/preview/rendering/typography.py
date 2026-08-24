"""Text metrics and truncation, in one place.

The renderer sized headlines and clipped copy by counting characters. That
works for English and fails everywhere else, in two opposite directions:

  * A CJK glyph is roughly twice as wide as a Latin one, so "本気で速く出荷する"
    at 9 characters was given the 82px size meant for a short English phrase
    and ran off the card.
  * Truncation cut at a character index, so a long German compound —
    ``Rechtsschutzversicherungsgesellschaft`` — was clipped mid-word into
    something that looks like a rendering bug rather than an ellipsis.

Both are the same mistake: character count is not visual width. Everything here
measures in *em units* instead, so one rule covers every script the corpus
contains.

RTL is the other half. Arabic and Hebrew copy laid out LTR reads as
punctuation-in-the-wrong-place to anyone who reads it, and the fix is a ``dir``
attribute the renderer has to be told to emit.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

# Advance width per character, in em. Real shaping needs the font, which is in
# Chromium rather than here — but these are measured against Liberation Sans
# Bold as a metric proxy for Bricolage Grotesque 600 (lowercase averages 0.539,
# uppercase 0.688, space 0.278; sentence-case copy lands near 0.50), and the
# ratios between scripts are what the sizing decision actually turns on.
_WIDE_SCRIPT_EM = 1.0    # CJK ideographs, kana, hangul: full-width by design
_LATIN_EM = 0.52
_NARROW_EM = 0.28        # i, l, j, punctuation, spaces

_NARROW_CHARS = set(" .,:;!|'\"`ilj()[]{}/\\-")

# Unicode blocks that render full-width.
_WIDE_RANGES = (
    (0x1100, 0x115F),    # Hangul Jamo
    (0x2E80, 0x303E),    # CJK radicals, punctuation
    (0x3041, 0x33FF),    # Kana, CJK compatibility
    (0x3400, 0x4DBF),    # CJK Ext A
    (0x4E00, 0x9FFF),    # CJK Unified
    (0xA000, 0xA4CF),    # Yi
    (0xAC00, 0xD7A3),    # Hangul syllables
    (0xF900, 0xFAFF),    # CJK compatibility ideographs
    (0xFF00, 0xFF60),    # Fullwidth forms
    (0xFFE0, 0xFFE6),
    (0x20000, 0x2FFFD),  # CJK Ext B+
)

# Scripts written right to left.
_RTL_RANGES = (
    (0x0590, 0x05FF),    # Hebrew
    (0x0600, 0x06FF),    # Arabic
    (0x0700, 0x074F),    # Syriac
    (0x0750, 0x077F),    # Arabic supplement
    (0x08A0, 0x08FF),    # Arabic extended-A
    (0xFB1D, 0xFDFF),    # Hebrew/Arabic presentation forms
    (0xFE70, 0xFEFF),    # Arabic presentation forms-B
)


def _in_ranges(code: int, ranges) -> bool:
    return any(low <= code <= high for low, high in ranges)


def is_wide(char: str) -> bool:
    """Does this glyph occupy a full em?"""
    if unicodedata.east_asian_width(char) in ("W", "F"):
        return True
    return _in_ranges(ord(char), _WIDE_RANGES)


def is_rtl_text(text: Optional[str]) -> bool:
    """Is this string predominantly right-to-left?

    Predominantly, not "contains": a Hebrew brand name inside an English
    headline should not flip the whole card.
    """
    if not text:
        return False
    strong = [c for c in text if c.isalpha()]
    if not strong:
        return False
    rtl = sum(1 for c in strong if _in_ranges(ord(c), _RTL_RANGES))
    return rtl > len(strong) * 0.4


def text_direction(text: Optional[str]) -> str:
    """``rtl`` or ``ltr`` — what to put in the element's ``dir`` attribute."""
    return "rtl" if is_rtl_text(text) else "ltr"


def em_width(text: Optional[str]) -> float:
    """Visual width of ``text`` in em units.

    This is the number every sizing and truncation decision here is made
    against, and the reason one rule can cover Latin, CJK and everything
    between: ``len()`` says nine characters either way, this says 9.0 em for
    CJK and 4.7 em for English.
    """
    if not text:
        return 0.0
    total = 0.0
    for char in text:
        if is_wide(char):
            total += _WIDE_SCRIPT_EM
        elif char in _NARROW_CHARS:
            total += _NARROW_EM
        else:
            total += _LATIN_EM
    return total


@dataclass(frozen=True)
class HeadlineFit:
    """A headline sized to the space it has."""

    text: str
    font_size_px: int
    lines: int
    direction: str
    truncated: bool


# The text column's usable width, as a fraction of card width, per layout. These
# track the renderer's CSS padding; if that changes, these change with it.
COLUMN_FRACTION = {
    "typographic": 0.86,
    "editorial": 0.86,
    "stat": 0.80,
    "profile": 0.78,
    "split": 0.48,
    "product": 0.48,
}

# How many lines a headline may occupy before it stops being a headline.
MAX_HEADLINE_LINES = 3
MIN_HEADLINE_PX = 30
MAX_HEADLINE_PX = 82

# Preferred size by measured width. This is the card's existing type scale —
# short headlines get to be big and confident — restated in em rather than
# character count. The thresholds are the old character thresholds converted at
# the measured ~0.5 em/char, so English cards size exactly as they did before;
# CJK now lands in the right bucket instead of being handed the size meant for a
# phrase half its visual width.
_SIZE_LADDER = (
    (11.0, 82),
    (17.0, 72),
    (24.0, 62),
    (32.0, 54),
    (float("inf"), 46),
)

# Vertical room the headline block has, as a fraction of card height, once the
# eyebrow row, subtitle and footer have taken theirs.
_HEADLINE_HEIGHT_FRACTION = 0.48
_LINE_HEIGHT = 1.06


def _preferred_size(width_em: float) -> int:
    for threshold, size in _SIZE_LADDER:
        if width_em <= threshold:
            return size
    return MIN_HEADLINE_PX


def fit_headline(
    text: Optional[str],
    *,
    card_width: int = 1200,
    card_height: int = 630,
    layout: str = "typographic",
    stacked: bool = False,
    max_lines: int = MAX_HEADLINE_LINES,
) -> HeadlineFit:
    """Size a headline to the space it actually has.

    Starts from the card's type scale, then shrinks while the measured text
    would need more lines than fit — or more vertical room than the block has.
    Measuring rather than counting characters is the whole point: one rule that
    holds for Latin, CJK and RTL instead of a table per language.
    """
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return HeadlineFit("", MAX_HEADLINE_PX, 0, "ltr", False)

    fraction = COLUMN_FRACTION.get(layout, 0.86)
    if stacked and layout in ("split", "product"):
        fraction = 0.86  # stacked layouts get the full width back
    column_px = card_width * fraction
    width_em = em_width(cleaned)
    height_px = card_height * _HEADLINE_HEIGHT_FRACTION
    direction = text_direction(cleaned)

    size = _preferred_size(width_em)
    while size >= MIN_HEADLINE_PX:
        lines = max(1, math.ceil(width_em / (column_px / size)))
        if lines <= max_lines and lines * size * _LINE_HEIGHT <= height_px:
            return HeadlineFit(cleaned, size, lines, direction, False)
        size -= 2

    # Even at the floor it does not fit: truncate to what does, breaking where a
    # reader would, so the result reads as an edited headline rather than a bug.
    truncated = truncate_to_em(cleaned, (column_px / MIN_HEADLINE_PX) * max_lines)
    return HeadlineFit(truncated, MIN_HEADLINE_PX, max_lines, direction,
                       truncated != cleaned)


def normalize_whitespace(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


# Characters a truncation should not end on.
_TRAILING_JUNK = " ,.;:-–—·|/\\、。，"


def truncate_to_em(text: Optional[str], max_em: float) -> str:
    """Trim ``text`` to ``max_em`` visual width, breaking where a reader would.

    Word boundaries where the script has them; character boundaries where it
    does not (CJK does not use spaces, so word-breaking there would return the
    whole string or nothing). A very long single token — the German compound
    case — is broken mid-word because there is nowhere else to break it, and an
    ellipsis is a clearer signal there than an overflowing line.
    """
    cleaned = normalize_whitespace(text)
    if not cleaned or em_width(cleaned) <= max_em:
        return cleaned

    budget = max_em - _LATIN_EM  # room for the ellipsis
    kept: List[str] = []
    used = 0.0
    for char in cleaned:
        char_width = _WIDE_SCRIPT_EM if is_wide(char) else (
            _NARROW_EM if char in _NARROW_CHARS else _LATIN_EM
        )
        if used + char_width > budget:
            break
        kept.append(char)
        used += char_width

    candidate = "".join(kept)
    # Prefer a word boundary, but only if it does not throw away most of the
    # line — on a single long token the last space may be at index 0.
    if " " in candidate:
        head = candidate.rsplit(" ", 1)[0]
        if em_width(head) >= budget * 0.6:
            candidate = head

    return candidate.rstrip(_TRAILING_JUNK) + "…"


def clamp(text: Optional[str], max_em: float) -> str:
    """Public truncation entry point — one rule, used everywhere."""
    return truncate_to_em(text, max_em)


def available_fonts() -> List[str]:
    """Font families fontconfig can actually see in this container.

    The renderer's CSS names Noto fallbacks for CJK and Arabic, but naming a
    family does not install it: a container missing ``fonts-noto-cjk`` renders
    Japanese copy as tofu while every check upstream reports success. This makes
    that a fact the corpus can assert instead of an assumption.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return []
        families = set()
        for line in out.stdout.splitlines():
            for name in line.split(","):
                cleaned = name.strip()
                if cleaned:
                    families.add(cleaned)
        return sorted(families)
    except Exception:  # noqa: BLE001
        return []


def missing_script_fonts() -> List[str]:
    """Scripts the render container cannot draw. Empty is the healthy answer."""
    families = " ".join(available_fonts()).lower()
    if not families:
        return []  # fc-list unavailable; do not claim a problem we cannot see

    missing = []
    if "cjk" not in families and "noto sans jp" not in families:
        missing.append("CJK")
    if "arabic" not in families and "noto naskh" not in families:
        missing.append("Arabic")
    if "hebrew" not in families:
        missing.append("Hebrew")
    return missing
