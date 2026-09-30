"""Pydantic schemas for Organization."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from backend.models.organization_member import OrganizationRole


class OrganizationBase(BaseModel):
    """Base schema for Organization."""
    name: str


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""
    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: Optional[str] = None


class OrganizationPublic(OrganizationBase):
    """Public schema for Organization."""
    id: int
    owner_user_id: int
    created_at: datetime
    subscription_status: str
    subscription_plan: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationMemberBase(BaseModel):
    """Base schema for OrganizationMember."""
    role: OrganizationRole


class OrganizationMemberCreate(BaseModel):
    """Schema for creating an organization member."""
    user_id: int
    role: OrganizationRole = OrganizationRole.VIEWER


class OrganizationMemberPublic(BaseModel):
    """Public schema for OrganizationMember."""
    id: int
    organization_id: int
    user_id: int
    role: OrganizationRole
    created_at: datetime
    user_email: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationInviteCreate(BaseModel):
    """Schema for creating an invite."""
    role: OrganizationRole = OrganizationRole.VIEWER
    expires_in_days: int = 7
    email: Optional[str] = None


class OrganizationInviteResponse(BaseModel):
    """Response schema for invite creation."""
    invite_token: str
    invite_url: str
    expires_at: datetime


class OrganizationJoinRequest(BaseModel):
    """Schema for joining an organization."""
    invite_token: str

