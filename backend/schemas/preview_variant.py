"""Pydantic schemas for PreviewVariant."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PreviewVariantBase(BaseModel):
    """Base schema for PreviewVariant."""
    variant_key: str = Field(..., description="Variant key: 'a', 'b', or 'c'")
    title: str
    description: Optional[str] = None
    tone: Optional[str] = None
    keywords: Optional[str] = None
    image_url: Optional[str] = None
    angle: Optional[str] = Field(
        None,
        description="Which argument this variant makes: 'main' (the primary "
                    "card), 'benefit', 'proof', 'curiosity', or 'alternate'",
    )
    subtitle: Optional[str] = None


class PreviewVariantCreate(PreviewVariantBase):
    """Schema for creating a PreviewVariant."""
    preview_id: int


class PreviewVariantUpdate(BaseModel):
    """Schema for updating a PreviewVariant."""
    title: Optional[str] = None
    description: Optional[str] = None
    tone: Optional[str] = None
    keywords: Optional[str] = None
    image_url: Optional[str] = None


class PreviewVariantPublic(PreviewVariantBase):
    """Public schema for PreviewVariant."""
    id: int
    preview_id: int
    created_at: datetime

    class Config:
        from_attributes = True

