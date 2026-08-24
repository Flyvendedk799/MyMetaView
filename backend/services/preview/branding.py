"""What the customer's *site* says its brand is.

The My Site tab (Brand & identity) is scoped per connected domain, and every
field on it is meant to reach the card: the palette, the mark, the display font,
the layout preferences, the name and the tagline. This module is the one place
that says which fields those are, so the stages that consume them and the cache
that keys off them can never drift apart.

Two things live here:

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
