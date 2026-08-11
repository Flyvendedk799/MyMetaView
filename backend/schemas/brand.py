"""Pydantic schemas for Brand Settings."""
from typing import Optional
from pydantic import BaseModel, Field

# Tone presets offered on the Brand & identity page. "auto" keeps today's
# behaviour (infer the voice from the brand's colours and type).
VOICE_CHOICES = ("auto", "professional", "confident", "friendly", "technical", "playful", "luxury")


class BrandSettingsBase(BaseModel):
    """Base brand settings schema."""
    primary_color: str = Field(..., description="Primary brand color (hex)")
    secondary_color: str = Field(..., description="Secondary brand color (hex)")
    accent_color: str = Field(..., description="Accent brand color (hex)")
    font_family: str = Field(default="Inter", description="Font family name")
    logo_url: Optional[str] = Field(None, description="URL to logo image")
    # Identity — feeds the copy and the brand name on generated cards
    brand_name: Optional[str] = Field(None, description="Brand/site name shown on cards")
    tagline: Optional[str] = Field(None, description="One-line descriptor of the site")
    brand_description: Optional[str] = Field(None, description="What the site/company does")
    audience: Optional[str] = Field(None, description="Who the site is for")
    voice: str = Field(default="auto", description=" | ".join(VOICE_CHOICES))
    # Preview-card controls ("auto" = let the AI decide)
    preview_layout: str = Field(
        default="auto",
        description="auto | typographic | split | stat | editorial | product | profile",
    )
    preview_panel: str = Field(default="auto", description="auto | primary | secondary | dark | light")
    preview_accent: str = Field(default="auto", description="auto | bar | dot | shape")
    force_brand_colors: bool = Field(default=False, description="Always use these brand colours, ignore extracted")
    hide_watermark: bool = Field(default=False, description="Drop the 'metaview preview' footer on cards")


class BrandSettingsUpdate(BaseModel):
    """Schema for updating brand settings."""
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


class BrandSettings(BrandSettingsBase):
    """Brand settings schema with all fields."""
    id: int
    domain_id: Optional[int] = Field(
        None, description="Domain these settings belong to; null is the organization default"
    )

    class Config:
        from_attributes = True  # Pydantic v2: allows reading from SQLAlchemy ORM models
        json_schema_extra = {
            "example": {
                "id": 1,
                "primary_color": "#2979FF",
                "secondary_color": "#0A1A3C",
                "accent_color": "#3FFFD3",
                "font_family": "Inter",
                "logo_url": "https://example.com/logo.png",
            }
        }

