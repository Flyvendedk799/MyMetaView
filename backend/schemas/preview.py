"""Pydantic schemas for Preview."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PreviewBase(BaseModel):
    """Base preview schema."""
    url: str = Field(..., description="Full URL of the preview")
    domain: str = Field(..., description="Domain name")
    title: str = Field(..., description="Preview title")
    type: str = Field(..., description="Preview type: 'product', 'blog', or 'landing'")
    image_url: str = Field(..., description="URL to preview image")
    description: Optional[str] = Field(None, description="Preview description")
    keywords: Optional[str] = Field(None, description="Comma-separated keywords")
    tone: Optional[str] = Field(None, description="Content tone")
    ai_reasoning: Optional[str] = Field(None, description="AI reasoning (internal use)")


class PreviewCreate(BaseModel):
    """Schema for creating a new preview."""
    url: str = Field(..., description="Full URL of the preview")
    domain: str = Field(..., description="Domain name")
    title: str = Field(..., description="Preview title")
    type: str = Field(..., description="Preview type: 'product', 'blog', or 'landing'")
    image_url: Optional[str] = Field(None, description="URL to preview image")
    description: Optional[str] = Field(None, description="Preview description")
    keywords: Optional[str] = Field(None, description="Comma-separated keywords")
    tone: Optional[str] = Field(None, description="Content tone")
    ai_reasoning: Optional[str] = Field(None, description="AI reasoning (internal use)")


class PreviewUpdate(BaseModel):
    """Schema for updating an existing preview."""
    title: Optional[str] = Field(None, description="Preview title")
    type: Optional[str] = Field(None, description="Preview type: 'product', 'blog', or 'landing'")
    image_url: Optional[str] = Field(None, description="URL to preview image")
    description: Optional[str] = Field(None, description="Preview description")
    keywords: Optional[str] = Field(None, description="Comma-separated keywords")
    tone: Optional[str] = Field(None, description="Content tone")


class Preview(PreviewBase):
    """Preview schema with all fields."""
    id: int
    created_at: datetime
    monthly_clicks: int = 0
    description: Optional[str] = None
    keywords: Optional[str] = None
    tone: Optional[str] = None
    ai_reasoning: Optional[str] = None
    generation_mode: str = Field(
        "ai",
        description="Lane that produced this card: 'ai' (designed for this page) "
                    "or 'template' (built from the page's metadata, past the "
                    "plan's monthly AI allowance)",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "url": "https://example.com/product",
                "domain": "example.com",
                "title": "Product Page",
                "type": "product",
                "image_url": "https://example.com/image.jpg",
                "description": "A beautiful product page showcasing our latest offering.",
                "keywords": "product, ecommerce, shopping",
                "tone": "professional",
                "ai_reasoning": "Detected product page based on metadata signals",
                "generation_mode": "ai",
                "created_at": "2024-01-15T10:00:00",
                "monthly_clicks": 1234,
            }
        }

