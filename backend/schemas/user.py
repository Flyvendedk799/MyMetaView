"""Pydantic schemas for User."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    """Base user schema."""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class User(UserBase):
    """User schema with all fields."""
    id: int
    is_active: bool
    is_admin: bool = False
    created_at: datetime
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: str = "inactive"
    subscription_plan: Optional[str] = None
    trial_ends_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 syntax (was orm_mode in v1)


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data schema."""
    email: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = None
    bio: Optional[str] = None
