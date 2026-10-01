"""Pydantic schemas for Brand Settings.

Every value here ends up on a card or in a prompt, so writes are validated and
normalised at the edge: a colour the renderer cannot parse used to be stored
as typed and then silently replaced by a fallback at render time, and a typo'd
layout simply did nothing.
"""
import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

# Tone presets offered on the Brand & identity page. "auto" keeps today's
# behaviour (infer the voice from the brand's colours and type).
VOICE_CHOICES = ("auto", "professional", "confident", "friendly", "technical", "playful", "luxury")

# What the renderer can actually draw (premium_card_renderer._DISPLAY_FONTS).
# "auto" is the card's own type. "Inter" is accepted for old clients and read as
# "auto": it is neither embedded nor installed, so it never rendered as Inter.
FONT_CHOICES = ("auto", "Bricolage Grotesque", "IBM Plex Sans", "System", "Inter")
LAYOUT_CHOICES = ("auto", "typographic", "split", "stat", "editorial", "product", "profile")
PANEL_CHOICES = ("auto", "primary", "secondary", "dark", "light")
ACCENT_CHOICES = ("auto", "bar", "dot", "shape")

# Lengths match the inputs on the My Site tab; the brief truncates further.
TEXT_LIMITS = {
    "brand_name": 80,
    "tagline": 120,
    "brand_description": 500,
    "audience": 200,
    "white_label_name": 60,
}

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_hex(value: Optional[str]) -> Optional[str]:
    """``#ABC`` / ``abc`` / ``#AABBCC`` → ``#aabbcc``; raise on anything else."""
    if value is None:
        return None
    match = _HEX_RE.match(str(value).strip())
    if not match:
        raise ValueError("must be a hex colour like #1a2b3c")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return f"#{digits.lower()}"


def _choice(value: Optional[str], choices: tuple, field: str) -> Optional[str]:
    if value is None:
        return None
    lookup = {c.lower(): c for c in choices}
    key = str(value).strip().lower()
    if key not in lookup:
        raise ValueError(f"{field} must be one of: {', '.join(choices)}")
    return lookup[key]


class BrandSettingsBase(BaseModel):
    """Base brand settings schema."""
    primary_color: str = Field(..., description="Primary brand color (hex)")
    secondary_color: str = Field(..., description="Secondary brand color (hex)")
    accent_color: str = Field(..., description="Accent brand color (hex)")
    font_family: str = Field(default="auto", description=" | ".join(FONT_CHOICES))
    logo_url: Optional[str] = Field(None, description="URL to logo image")
    # Identity — feeds the copy and the brand name on generated cards
    brand_name: Optional[str] = Field(None, description="Brand/site name shown on cards")
    tagline: Optional[str] = Field(None, description="One-line descriptor of the site")
    brand_description: Optional[str] = Field(None, description="What the site/company does")
    audience: Optional[str] = Field(None, description="Who the site is for")
    voice: str = Field(default="auto", description=" | ".join(VOICE_CHOICES))
    # Preview-card controls ("auto" = let the AI decide)
    preview_layout: str = Field(default="auto", description=" | ".join(LAYOUT_CHOICES))
    preview_panel: str = Field(default="auto", description=" | ".join(PANEL_CHOICES))
    preview_accent: str = Field(default="auto", description=" | ".join(ACCENT_CHOICES))
    force_brand_colors: bool = Field(default=False, description="Always use these brand colours, ignore extracted")
    hide_watermark: bool = Field(default=False, description="Drop the 'metaview preview' footer on cards")
    white_label_name: Optional[str] = Field(None, description="Product name used on install artifacts")


class BrandSettingsUpdate(BaseModel):
    """Schema for updating brand settings (and for the sample's unsaved draft).

    Validates and normalises, so what is stored is what the renderer and the
    prompt will read. Free text is trimmed and an empty string means "unset" —
    keep inferring it from the page — rather than an empty value to print.
    """
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font_family: Optional[str] = None
    logo_url: Optional[str] = None
    brand_name: Optional[str] = None
    tagline: Optional[str] = None
    brand_description: Optional[str] = None
    audience: Optional[str] = None
    voice: Optional[str] = None
    preview_layout: Optional[str] = None
    preview_panel: Optional[str] = None
    preview_accent: Optional[str] = None
    force_brand_colors: Optional[bool] = None
    hide_watermark: Optional[bool] = None
    white_label_name: Optional[str] = None

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def _hex(cls, value: Optional[str]) -> Optional[str]:
        return normalize_hex(value)

    @field_validator("font_family")
    @classmethod
    def _font(cls, value: Optional[str]) -> Optional[str]:
        font = _choice(value, FONT_CHOICES, "font_family")
        return "auto" if font == "Inter" else font

    @field_validator("voice")
    @classmethod
    def _voice(cls, value: Optional[str]) -> Optional[str]:
        return _choice(value, VOICE_CHOICES, "voice")

    @field_validator("preview_layout")
    @classmethod
    def _layout(cls, value: Optional[str]) -> Optional[str]:
        return _choice(value, LAYOUT_CHOICES, "preview_layout")

    @field_validator("preview_panel")
    @classmethod
    def _panel(cls, value: Optional[str]) -> Optional[str]:
        return _choice(value, PANEL_CHOICES, "preview_panel")

    @field_validator("preview_accent")
    @classmethod
    def _accent(cls, value: Optional[str]) -> Optional[str]:
        return _choice(value, ACCENT_CHOICES, "preview_accent")

    @field_validator("brand_name", "tagline", "brand_description", "audience", "white_label_name")
    @classmethod
    def _text(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        text = " ".join(str(value).split()) if info.field_name != "brand_description" else str(value).strip()
        if not text:
            return None
        limit = TEXT_LIMITS[info.field_name]
        if len(text) > limit:
            raise ValueError(f"{info.field_name} must be at most {limit} characters")
        return text

    @field_validator("logo_url")
    @classmethod
    def _logo_url(cls, value: Optional[str]) -> Optional[str]:
        """An http(s) URL or nothing. The engine fetches it from inside the
        infrastructure network; the fetch is guarded, but there is no reason to
        store a ``file:`` or ``data:`` value to begin with."""
        if value is None:
            return None
        url = str(value).strip()
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("logo_url must be an http(s) URL")
        if len(url) > 2048:
            raise ValueError("logo_url is too long")
        return url


class BrandSettings(BrandSettingsBase):
    """Brand settings as the My Site tab reads them."""
    # None while nothing has been saved for the account: the values are stock.
    id: Optional[int] = None
    domain_id: Optional[int] = Field(
        None, description="Domain these settings belong to; null is the organization default"
    )
    inherits_default: bool = Field(
        False,
        description=(
            "True when the requested domain has no brand of its own and is "
            "showing (and following) the organization default"
        ),
    )

    class Config:
        from_attributes = True  # Pydantic v2: allows reading from SQLAlchemy ORM models
        json_schema_extra = {
            "example": {
                "id": 1,
                "primary_color": "#2979ff",
                "secondary_color": "#0a1a3c",
                "accent_color": "#3fffd3",
                "font_family": "auto",
                "logo_url": "https://example.com/logo.png",
            }
        }


class BrandSuggestion(BaseModel):
    """What "Fill from my site" found on the domain's home page.

    Every field is optional — the form applies what was found and leaves the
    rest — and nothing here is saved until the user saves the form.
    """
    source_url: str
    brand_name: Optional[str] = None
    tagline: Optional[str] = None
    brand_description: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    palette_source: Optional[str] = None
