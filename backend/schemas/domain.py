"""Pydantic schemas for Domain."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DomainBase(BaseModel):
    """Base domain schema."""
    name: str = Field(..., description="Domain name (e.g. 'example.com')")
    environment: str = Field(default="production", description="Environment: 'production' or 'staging'")
    status: str = Field(default="pending", description="Status: 'active', 'pending', 'verified', or 'disabled'")
    verification_method: Optional[str] = Field(None, description="Verification method: dns, html, or meta")
    verification_token: Optional[str] = Field(None, description="Verification token")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")


class DomainCreate(DomainBase):
    """Schema for creating a new domain."""
    pass


class DomainUpdate(BaseModel):
    """Schema for updating a domain."""
    name: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[str] = None
    monthly_clicks: Optional[int] = None


class Domain(DomainBase):
    """Domain schema with all fields."""
    id: int
    created_at: datetime
    monthly_clicks: int = 0
    verification_method: Optional[str] = None
    verification_token: Optional[str] = None
    verified_at: Optional[datetime] = None
    snippet_installed_at: Optional[datetime] = Field(None, description="When the embed snippet first reported in")
    snippet_last_seen_at: Optional[datetime] = Field(None, description="When the embed snippet was last seen")
    snippet_version: Optional[str] = Field(None, description="Version of the embed snippet last seen")
    verification_error: Optional[str] = Field(
        None,
        description="Why the last verification check failed (only set on check responses)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "example.com",
                "environment": "production",
                "status": "active",
                "created_at": "2024-01-15T10:00:00",
                "monthly_clicks": 1234,
            }
        }

