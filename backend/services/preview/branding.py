"""What the customer's *site* says its brand is.

The My Site tab (Brand & identity) is scoped per connected domain, and every
field on it is meant to reach the card: the palette, the mark, the display font,
the layout preferences, the name and the tagline. This module is the one place
that says which fields those are, so the stages that consume them and the cache
that keys off them can never drift apart.

Four things live here:

* ``engine_payload`` — the settings row turned into what the engine reads. The
  job used to hand-pick fields into a dict, and it picked six of the sixteen
  that matter: "what you do", "who it's for" and "tone of voice" were saved,
  shown back to the user, and never reached the art director.
* ``STOCK_PALETTE`` / ``STOCK_FONTS`` — the values every account starts with.
  A field still holding its stock value is not the customer's choice, and must
  not be treated as one: the stock blue is MetaView's colour, not theirs.
* ``brand_signature`` — a stable digest of the branding a generation ran with.
  The result cache is keyed by URL, so before this a card generated under one
  brand was served to the next request for that URL whatever brand it belonged
  to. A card is only reusable for a request whose branding matches, and this is
  what "matches" means.
* ``DISREGARD_KEY`` and ``disregarded`` — the per-preview escape hatch. A user
  who wants one page's card designed from the page alone sets it when they add
  the preview; the flag travels with the preview so re-rolls keep the choice.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

# Marks a brand_settings payload as "generate this one from the page alone".
DISREGARD_KEY = "disregard_site_branding"

# What a new brand row is seeded with. Kept here, next to the rules that read
# it, so "is this the customer's colour or ours?" has one answer.
STOCK_PALETTE = {
    "primary_color": "#2979ff",
    "secondary_color": "#0a1a3c",
    "accent_color": "#3fffd3",
}

# "auto" is the card's own design language (Bricolage display, Plex body).
# "Inter" was the stock value before "auto" existed, and nobody chose it: the
# picker simply opened on it. It was never drawable either — it is neither
# embedded in premium_fonts.css nor installed in the worker image, so Chromium
# fell through to Plex Sans and every app card silently lost the display face
# the demo draws with. Both mean "no font preference".
AUTO_FONT = "auto"
STOCK_FONTS = frozenset({"", AUTO_FONT, "inter"})

# Card controls that only take effect on plans with F_CARD_CONTROLS.
CARD_CONTROL_FIELDS = ("preview_layout", "preview_panel", "preview_accent")

# Everything on the My Site tab that changes the card. Ordered, so the signature
# is stable across dict orderings.
SIGNIFICANT_FIELDS = (
    "brand_name",
    "tagline",
    "brand_description",
    "audience",
    "voice",
    "primary_color",
    "secondary_color",
    "accent_color",
    "font_family",
    "logo_url",
    "preview_layout",
    "preview_panel",
    "preview_accent",
    "force_brand_colors",
    "hide_watermark",
    DISREGARD_KEY,
)


def engine_payload(
    row: Any,
    *,
    can_card_controls: bool,
    can_hide_watermark: bool,
    ignore_site_branding: bool = False,
) -> Dict[str, Any]:
    """The brand settings the engine runs with, built from a settings row.

    Every field in ``SIGNIFICANT_FIELDS`` is carried, so nothing on the My Site
    tab can be saved and then silently dropped on the way to the card again.
    Plan gating happens here too: card controls collapse to ``auto`` and the
    watermark stays without the entitlement, exactly as the sample renders.

    A preview added with branding disregarded still carries the settings — the
    stages read the flag to explain the choice in the job trace, and it is part
    of the cache signature, so a disregarded card and a branded one for the same
    URL never stand in for each other.
    """
    def text(field: str) -> Optional[str]:
        value = getattr(row, field, None) if row is not None else None
        value = str(value).strip() if value is not None else ""
        return value or None

    payload: Dict[str, Any] = {DISREGARD_KEY: bool(ignore_site_branding)}
    for field in (
        "brand_name", "tagline", "brand_description", "audience",
        "primary_color", "secondary_color", "accent_color", "logo_url",
    ):
        payload[field] = text(field)
    payload["voice"] = (text("voice") or "auto").lower()
    payload["font_family"] = text("font_family") or AUTO_FONT
    for field in CARD_CONTROL_FIELDS:
        payload[field] = (text(field) or "auto") if can_card_controls else "auto"
    payload["force_brand_colors"] = bool(getattr(row, "force_brand_colors", False))
    payload["hide_watermark"] = bool(
        can_hide_watermark and getattr(row, "hide_watermark", False)
    )
    return payload


def chosen_font(settings: Optional[Dict[str, Any]]) -> Optional[str]:
    """The font the customer actually picked, or None for the card's own type."""
    font = str((settings or {}).get("font_family") or "").strip()
    return None if font.lower() in STOCK_FONTS else font


def customised_palette(settings: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """The colours the customer set, leaving out any still at their stock value.

    Used where a palette stands in for one the page did not give us. Handing a
    page with no palette MetaView's own blue and calling it "the site's
    colours" is how an unconfigured account got somebody else's brand.
    """
    out: Dict[str, str] = {}
    for key, stock in STOCK_PALETTE.items():
        value = str((settings or {}).get(key) or "").strip()
        if value and value.lower() != stock:
            out[key] = value
    return out


def settings_of(config: Any) -> Dict[str, Any]:
    """The brand settings on an engine config, as a dict (never None)."""
    settings = getattr(config, "brand_settings", None)
    return dict(settings) if isinstance(settings, dict) else {}


def disregarded(settings: Optional[Dict[str, Any]]) -> bool:
    """Did the user ask for this preview to ignore their site branding?"""
    return bool(isinstance(settings, dict) and settings.get(DISREGARD_KEY))


def brand_signature(settings: Optional[Dict[str, Any]]) -> str:
    """A short digest of the branding a card was (or would be) generated with.

    ``None`` and an empty dict both mean "no site branding" — the demo, and any
    caller that never had settings — and share a signature, which is what keeps
    the demo's cache behaving exactly as it did.
    """
    if not isinstance(settings, dict) or not settings:
        return "none"

    material = {
        field: _normalize(settings.get(field))
        for field in SIGNIFICANT_FIELDS
        if settings.get(field) not in (None, "", False)
    }
    if not material:
        return "none"
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# The identity fields, in the order the brief reads them: who this site is, in
# the owner's own words. Colours and card controls are not here — those shape
# the picture, not the copy.
IDENTITY_FIELDS = (
    ("brand_name", "Site / brand name"),
    ("tagline", "Tagline"),
    ("brand_description", "What they do"),
    ("audience", "Who it is for"),
)


def identity_brief(settings: Optional[Dict[str, Any]]) -> str:
    """The site owner's own description of themselves, as prompt text.

    The My Site tab asks for this precisely so the card's copy is written about
    the right company, for the right reader — and until this existed it only
    reached a post-hoc rewrite of the description, never the headline. Empty
    when the user filled nothing in, which is the signal to keep inferring
    everything from the page.
    """
    if not isinstance(settings, dict) or disregarded(settings):
        return ""

    lines = []
    for field, label in IDENTITY_FIELDS:
        value = str(settings.get(field) or "").strip()
        if value:
            lines.append(f"- {label}: {value[:300]}")

    voice = str(settings.get("voice") or "auto").strip().lower()
    if voice and voice != "auto":
        lines.append(f"- Tone of voice they asked for: {voice}")

    return "\n".join(lines)


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, bool):
        return value
    return value
