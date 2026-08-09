"""SQLAlchemy ORM model for BrandSettings."""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.db import Base


class BrandSettings(Base):
    """SQLAlchemy ORM model for brand_settings table."""
    __tablename__ = "brand_settings"

    id = Column(Integer, primary_key=True, index=True)
    primary_color = Column(String, nullable=False)
    secondary_color = Column(String, nullable=False)
    accent_color = Column(String, nullable=False)
    font_family = Column(String, nullable=False, default="Inter")
    logo_url = Column(String, nullable=True)

    # --- Preview-card controls (honoured by the render engine for a user's own
    # previews). "auto" lets the AI art director decide; any other value overrides.
    preview_layout = Column(String, nullable=False, server_default="auto")   # auto | typographic | split
    preview_panel = Column(String, nullable=False, server_default="auto")    # auto | primary | secondary | dark | light
    preview_accent = Column(String, nullable=False, server_default="auto")   # auto | bar | dot | shape
    force_brand_colors = Column(Boolean, nullable=False, server_default="0")  # always use my colours, ignore extracted
    hide_watermark = Column(Boolean, nullable=False, server_default="0")      # drop the "metaview preview" footer

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    # Relationships
    user = relationship("User", back_populates="brand_settings")
    organization = relationship("Organization", back_populates="brand_settings")

