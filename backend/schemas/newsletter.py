"""Pydantic schemas for newsletter subscribers."""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class NewsletterSubscribeRequest(BaseModel):
    """Schema for newsletter subscription request."""
    email: EmailStr
    source: str = "demo"  # 'demo', 'blog', 'ads', etc.
    consent_given: bool = True


class NewsletterSubscriberResponse(BaseModel):
    """Schema for newsletter subscriber response."""
    id: int
    email: str
    source: str
    subscribed_at: datetime
    is_active: bool
    consent_given: bool
    unsubscribe_url: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        from_attributes = True


class NewsletterSubscriberListResponse(BaseModel):
    """Schema for paginated newsletter subscriber list."""
    items: list[NewsletterSubscriberResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

