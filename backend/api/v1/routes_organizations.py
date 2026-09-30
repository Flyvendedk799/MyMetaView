"""Organization management routes."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from secrets import token_urlsafe
import hashlib
from backend.models.organization_invite import OrganizationInvite
from backend.core.plans import plan_limit
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


def _hash_invite(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    seat_limit = plan_limit(current_org, "team_seats")
    if seat_limit is not None:
        member_count = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org_id
        ).count()
        if member_count >= seat_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This plan includes {seat_limit} team seat{'s' if seat_limit != 1 else ''}.",
            )

    invite_token = token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=invite_in.expires_in_days)
    db.add(OrganizationInvite(
        organization_id=org_id,
        role=invite_in.role.value,
        token_hash=_hash_invite(invite_token),
        created_by=current_user.id,
        expires_at=expires_at,
    ))
    db.commit()
    
    # Build invite URL
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    invite_url = f"{base_url}/join?token={invite_token}"

    # Send invite email if the payload carried a recipient address. The current
    # invite is a shareable link (no email field on OrganizationInviteCreate),
    # so this only fires when an email is present. Fire-and-forget; must never
    # fail invite creation.
    try:
        invitee_email = invite_in.email
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
    invite = db.query(OrganizationInvite).filter(
        OrganizationInvite.token_hash == _hash_invite(join_request.invite_token),
        OrganizationInvite.accepted_at.is_(None),
    ).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite token"
        )

    if datetime.utcnow() > invite.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite token has expired"
        )

    org_id = invite.organization_id
    role = OrganizationRole(invite.role)
    
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
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    seat_limit = plan_limit(org, "team_seats") if org else None
    if seat_limit is not None:
        member_count = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org_id
        ).count()
        if member_count >= seat_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This plan includes {seat_limit} team seats.",
            )

    membership = OrganizationMember(
        organization_id=org_id,
        user_id=current_user.id,
        role=role
    )
    db.add(membership)
    invite.accepted_at = datetime.utcnow()
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


@router.post("/{org_id}/leave")
def leave_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    """Leave an organization. Owners transfer or delete the org instead."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if org.owner_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners cannot leave. Transfer ownership by deleting the account, or delete the organization.",
        )
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == current_user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a member of this organization")
    db.delete(membership)
    db.commit()
    log_activity(
        db,
        user_id=current_user.id,
        action="organization.left",
        metadata={"organization_id": org_id},
        request=request,
    )
    return {"success": True}

