"""Shared dependencies for FastAPI routes."""
from contextvars import ContextVar
from fastapi import Depends, HTTPException, status, Query, Header, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, List
from backend.db.session import get_db
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Set when the bearer token is an org API key, so get_current_org pins that org.
_api_key_org_id: ContextVar[Optional[int]] = ContextVar("api_key_org_id", default=None)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    _api_key_org_id.set(None)
    if token.startswith("mv_"):
        from backend.api.v1.routes_api_keys import hash_api_key
        from backend.core.plans import F_API, has_feature
        from backend.models.api_key import ApiKey

        row = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == hash_api_key(token), ApiKey.revoked_at.is_(None))
            .first()
        )
        if row is None:
            raise credentials_exception
        org = db.query(Organization).filter(Organization.id == row.organization_id).first()
        if org is None or not has_feature(org, F_API):
            raise credentials_exception
        user = db.query(User).filter(User.id == row.created_by).first()
        if user is None or not user.is_active:
            raise credentials_exception
        _api_key_org_id.set(org.id)
        return user

    email = decode_access_token(token)
    if email is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


def get_current_org(
    current_user: User = Depends(get_current_user),
    org_id_query: Optional[int] = Query(None, description="Organization ID (optional, defaults to user's first org)"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: Session = Depends(get_db)
) -> Organization:
    """
    Get the current organization context.
    
    Priority:
    1. org_id query parameter
    2. X-Organization-ID header
    3. User's first organization membership
    4. User's owned organization
    
    Note: When org_id is a path parameter, it should be passed explicitly to this function.
    
    Raises 404 if no organization found or user is not a member.
    """
    # An API key always acts as the organization it was issued for.
    pinned = _api_key_org_id.get()
    if pinned is not None:
        target_org_id = pinned
    else:
        target_org_id = org_id_query
    
    # Try header if no query param
    if target_org_id is None and x_organization_id:
        try:
            target_org_id = int(x_organization_id)
        except ValueError:
            pass
    
    # If still no org_id, get user's first org membership
    if target_org_id is None:
        membership = db.query(OrganizationMember).join(Organization).filter(
            OrganizationMember.user_id == current_user.id
        ).first()
        
        if membership:
            target_org_id = membership.organization_id
        else:
            # Fallback to owned organization
            owned_org = db.query(Organization).filter(
                Organization.owner_user_id == current_user.id
            ).first()
            if owned_org:
                target_org_id = owned_org.id
    
    if target_org_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization found. Please create or join an organization."
        )
    
    # Verify organization exists
    org = db.query(Organization).filter(
        Organization.id == target_org_id
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Verify user is a member (or owner)
    is_owner = org.owner_user_id == current_user.id
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == current_user.id
    ).first()
    
    if not is_owner and not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    
    return org


def get_paid_user(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
) -> User:
    """
    Require organization to have an active paid subscription.
    
    Raises 403 if organization doesn't have active subscription or trial.
    """
    # Check organization subscription status (subscriptions are org-level)
    if current_org.subscription_status in ['active', 'trialing']:
        return current_user
    
    # Check if organization is within trial period
    if current_org.trial_ends_at:
        from datetime import datetime
        if datetime.utcnow() < current_org.trial_ends_at:
            return current_user
    
    # Organization doesn't have active subscription
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Active subscription required. Please upgrade your plan."
    )


def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be an admin.
    
    Raises 403 if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

# Alias for backwards compatibility
get_current_admin = get_admin_user


def get_org_from_path(
    org_id: int = Path(..., description="Organization ID from path"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Organization:
    """
    Get organization by path parameter org_id and verify user access.
    
    Usage:
        @router.put("/{org_id}")
        def update_org(
            org_id: int,
            current_org: Organization = Depends(get_org_from_path)
        ):
            ...
    """
    # Verify organization exists
    org = db.query(Organization).filter(
        Organization.id == org_id
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Verify user is a member (or owner)
    is_owner = org.owner_user_id == current_user.id
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == current_user.id
    ).first()
    
    if not is_owner and not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    
    return org


def get_org_member_role(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db)
) -> OrganizationRole:
    """
    Get the current user's role in the organization.
    
    Returns OrganizationRole.OWNER if user is the owner, otherwise returns their membership role.
    """
    # Owner has highest privileges
    if current_org.owner_user_id == current_user.id:
        return OrganizationRole.OWNER
    
    # Get membership role
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == current_org.id,
        OrganizationMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    
    return membership.role


def role_required(required_roles: List[OrganizationRole]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))):
            ...
    """
    def role_checker(
        current_role: OrganizationRole = Depends(get_org_member_role)
    ) -> OrganizationRole:
        if current_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join([r.value for r in required_roles])}"
            )
        return current_role
    
    return role_checker

