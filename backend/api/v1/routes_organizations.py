"""Organization management routes."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from secrets import token_urlsafe
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, get_org_member_role, role_required, get_org_from_path
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationPublic,
    OrganizationMemberCreate,
    OrganizationMemberPublic,
    OrganizationInviteCreate,
    OrganizationInviteResponse,
    OrganizationJoinRequest,
)
from backend.services.activity_logger import log_activity
from backend.services.email_service import send_org_invite_email
from backend.core.config import settings

router = APIRouter(prefix="/organizations", tags=["organizations"])

# In-memory invite store (in production, use Redis or database)
INVITE_TOKENS = {}  # token -> {org_id, role, expires_at, created_by}


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
def create_organization(
    org_in: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Create a new organization."""
    # Create organization
    org = Organization(
        name=org_in.name,
        owner_user_id=current_user.id
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    
    # Create owner membership
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role=OrganizationRole.OWNER
    )
    db.add(membership)
    db.commit()
    
    # Log activity
    log_activity(
        db,
        user_id=current_user.id,
        action="organization.created",
        metadata={"organization_id": org.id, "organization_name": org.name},
        request=request
    )
    
    return org


@router.get("", response_model=List[OrganizationPublic])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all organizations the user belongs to."""
    # Get organizations where user is owner or member
    owned_orgs = db.query(Organization).filter(
        Organization.owner_user_id == current_user.id
    ).all()
    
    member_orgs = db.query(Organization).join(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).all()
    
    # Combine and deduplicate
    all_orgs = {org.id: org for org in owned_orgs + member_orgs}
    return list(all_orgs.values())


@router.get("/{org_id}", response_model=OrganizationPublic)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path)
):
    """Get organization details."""
    return current_org


@router.put("/{org_id}", response_model=OrganizationPublic)
def update_organization(
    org_id: int,
    org_update: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
    request: Request = None
):
    """Update organization (owner/admin only)."""
    
    if org_update.name:
        current_org.name = org_update.name
        db.commit()
        db.refresh(current_org)
        
        log_activity(
            db,
            user_id=current_user.id,
            action="organization.updated",
            metadata={"organization_id": current_org.id, "organization_name": current_org.name},
            request=request
        )
    
    return current_org


@router.post("/{org_id}/invite", response_model=OrganizationInviteResponse)
def create_invite(
    org_id: int,
    invite_in: OrganizationInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
    request: Request = None
):
    """Create an invite link for the organization (owner/admin only)."""
    
    # Generate invite token
    invite_token = token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=invite_in.expires_in_days)
    
    # Store invite (in production, use database)
    INVITE_TOKENS[invite_token] = {
        "organization_id": org_id,
        "role": invite_in.role.value,
        "expires_at": expires_at,
        "created_by": current_user.id
    }
    
    # Build invite URL
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    invite_url = f"{base_url}/join?token={invite_token}"

    # Send invite email if the payload carried a recipient address. The current
    # invite is a shareable link (no email field on OrganizationInviteCreate),
    # so this only fires when an email is present. Fire-and-forget; must never
    # fail invite creation.
    try:
        invitee_email = (
            getattr(invite_in, 'email', None)
            or getattr(invite_in, 'invitee_email', None)
        )
        if invitee_email:
            send_org_invite_email(
                to_email=invitee_email,
                org_name=current_org.name,
                invite_url=invite_url,
                inviter_email=getattr(current_user, 'email', None),
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to enqueue org invite email")

    log_activity(
        db,
        user_id=current_user.id,
        action="organization.invite.created",
        metadata={"organization_id": org_id, "role": invite_in.role.value},
        request=request
    )
    
    return OrganizationInviteResponse(
        invite_token=invite_token,
        invite_url=invite_url,
        expires_at=expires_at
    )


@router.post("/join", response_model=OrganizationPublic)
def join_organization(
    join_request: OrganizationJoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Join an organization using an invite token."""
    invite_data = INVITE_TOKENS.get(join_request.invite_token)
    
    if not invite_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite token"
        )
    
    if datetime.utcnow() > invite_data["expires_at"]:
        del INVITE_TOKENS[join_request.invite_token]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite token has expired"
        )
    
    org_id = invite_data["organization_id"]
    role = OrganizationRole(invite_data["role"])
    
    # Check if user is already a member
    existing = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this organization"
        )
    
    # Create membership
    membership = OrganizationMember(
        organization_id=org_id,
        user_id=current_user.id,
        role=role
    )
    db.add(membership)
    db.commit()
    
    # Get organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    
    log_activity(
        db,
        user_id=current_user.id,
        action="organization.joined",
        metadata={"organization_id": org_id, "organization_name": org.name},
        request=request
    )
    
    return org


@router.get("/{org_id}/members", response_model=List[OrganizationMemberPublic])
def list_members(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path)
):
    """List all members of an organization."""
    
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id
    ).all()
    
    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        result.append(OrganizationMemberPublic(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role=member.role,
            created_at=member.created_at,
            user_email=user.email if user else None
        ))
    
    return result


@router.put("/{org_id}/members/{member_id}/role", response_model=OrganizationMemberPublic)
def update_member_role(
    org_id: int,
    member_id: int,
    new_role: OrganizationRole = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
    request: Request = None
):
    """Update a member's role (owner/admin only)."""
    
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.id == member_id,
        OrganizationMember.organization_id == org_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Prevent changing owner role
    if membership.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change owner role"
        )
    
    # Prevent non-owners from assigning admin role
    if current_role != OrganizationRole.OWNER and new_role == OrganizationRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can assign admin role"
        )
    
    old_role = membership.role
    membership.role = new_role
    db.commit()
    db.refresh(membership)
    
    user = db.query(User).filter(User.id == membership.user_id).first()
    
    log_activity(
        db,
        user_id=current_user.id,
        action="organization.member.role_updated",
        metadata={
            "organization_id": org_id,
            "member_id": member_id,
            "member_email": user.email if user else None,
            "old_role": old_role.value,
            "new_role": new_role.value
        },
        request=request
    )
    
    return OrganizationMemberPublic(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        role=membership.role,
        created_at=membership.created_at,
        user_email=user.email if user else None
    )


@router.delete("/{org_id}/members/{member_id}")
def remove_member(
    org_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_org_from_path),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
    request: Request = None
):
    """Remove a member from the organization (owner/admin only)."""
    
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.id == member_id,
        OrganizationMember.organization_id == org_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Prevent removing owner
    if membership.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove owner"
        )
    
    # Prevent removing yourself
    if membership.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself. Transfer ownership first."
        )
    
    user = db.query(User).filter(User.id == membership.user_id).first()
    
    db.delete(membership)
    db.commit()
    
    log_activity(
        db,
        user_id=current_user.id,
        action="organization.member.removed",
        metadata={
            "organization_id": org_id,
            "member_id": member_id,
            "member_email": user.email if user else None
        },
        request=request
    )
    
    return {"success": True}

