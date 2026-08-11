"""Account management routes (data export, deletion)."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
from backend.db.session import get_db
from backend.core.deps import get_current_user
from backend.models.user import User as UserModel
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.models.preview_variant import PreviewVariant as PreviewVariantModel
from backend.models.activity_log import ActivityLog
from backend.models.brand import BrandSettings as BrandSettingsModel

router = APIRouter(prefix="/account", tags=["account"])


from pydantic import BaseModel


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    request: Request = None,
):
    """Change the current user's password (requires the current one)."""
    from backend.core.security import verify_password, get_password_hash
    from backend.services.activity_logger import log_activity

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    log_activity(db, user_id=current_user.id, action="user.password_changed", request=request)
    return {"status": "ok", "message": "Password updated."}


@router.get("/export")
def export_user_data(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    request: Request = None
) -> Dict[str, Any]:
    """
    Export all user data in JSON format (GDPR-style data export).
    
    Returns:
        JSON object containing:
        - User profile
        - Organizations (owned and memberships)
        - Domains (for owned orgs)
        - Previews + variants
        - Activity logs
        - Billing status (non-sensitive)
    """
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "organizations": [],
        "domains": [],
        "previews": [],
        "activity_logs": [],
        "billing_status": {}
    }
    
    # Get organizations user owns
    owned_orgs = db.query(Organization).filter(
        Organization.owner_user_id == current_user.id
    ).all()
    
    # Get organizations user is member of
    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).all()
    
    org_ids = set()
    for org in owned_orgs:
        org_ids.add(org.id)
        export_data["organizations"].append({
            "id": org.id,
            "name": org.name,
            "role": "OWNER",
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "subscription_status": org.subscription_status,
            "subscription_plan": org.subscription_plan,
        })
    
    for membership in memberships:
        if membership.organization_id not in org_ids:
            org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
            if org:
                export_data["organizations"].append({
                    "id": org.id,
                    "name": org.name,
                    "role": membership.role.value,
                    "created_at": org.created_at.isoformat() if org.created_at else None,
                    "subscription_status": org.subscription_status,
                    "subscription_plan": org.subscription_plan,
                })
                org_ids.add(org.id)
    
    # Get domains for owned organizations
    for org_id in org_ids:
        domains = db.query(DomainModel).filter(DomainModel.organization_id == org_id).all()
        for domain in domains:
            export_data["domains"].append({
                "id": domain.id,
                "name": domain.name,
                "environment": domain.environment,
                "status": domain.status,
                "created_at": domain.created_at.isoformat() if domain.created_at else None,
                "organization_id": domain.organization_id,
            })
    
    # Get previews for owned organizations
    for org_id in org_ids:
        previews = db.query(PreviewModel).filter(PreviewModel.organization_id == org_id).all()
        for preview in previews:
            variants = db.query(PreviewVariantModel).filter(
                PreviewVariantModel.preview_id == preview.id
            ).all()
            
            export_data["previews"].append({
                "id": preview.id,
                "url": preview.url,
                "domain": preview.domain,
                "title": preview.title,
                "description": preview.description,
                "type": preview.type,
                "image_url": preview.image_url,
                "highlight_image_url": preview.highlight_image_url,
                "keywords": preview.keywords,
                "tone": preview.tone,
                "created_at": preview.created_at.isoformat() if preview.created_at else None,
                "organization_id": preview.organization_id,
                "variants": [
                    {
                        "id": v.id,
                        "variant_key": v.variant_key,
                        "title": v.title,
                        "description": v.description,
                        "tone": v.tone,
                        "keywords": v.keywords,
                    }
                    for v in variants
                ]
            })
    
    # Get activity logs
    activity_logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == current_user.id
    ).order_by(ActivityLog.created_at.desc()).limit(1000).all()  # Limit to last 1000
    
    for log in activity_logs:
        export_data["activity_logs"].append({
            "action": log.action,
            "metadata": log.extra_metadata,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "ip_address": log.ip_address,  # Include for user transparency
        })
    
    # Billing status (non-sensitive, no Stripe secrets)
    # Get billing info from owned organizations
    for org_data in export_data["organizations"]:
        if org_data["role"] == "OWNER":
            export_data["billing_status"][str(org_data["id"])] = {
                "subscription_status": org_data["subscription_status"],
                "subscription_plan": org_data["subscription_plan"],
            }
    
    return export_data


@router.delete("")
def delete_user_account(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    request: Request = None
):
    """
    Delete user account (soft delete, GDPR-style).
    
    Behavior:
    - Soft delete user (mark as inactive, set deleted_at if field exists)
    - Keep organizations but mark owner as deleted (NOTE: needs product decision for transfer)
    - Anonymize PII where appropriate
    """
    from backend.services.activity_logger import log_activity
    
    # Soft delete user
    current_user.is_active = False
    # Note: If you add a deleted_at field later, set it here:
    # current_user.deleted_at = datetime.utcnow()
    
    # Anonymize email (keep for uniqueness but mark as deleted)
    original_email = current_user.email
    current_user.email = f"deleted_{current_user.id}_{datetime.utcnow().timestamp()}@deleted.local"
    
    # For organizations owned by this user:
    # Keep org but mark owner as deleted (product decision needed for transfer)
    owned_orgs = db.query(Organization).filter(
        Organization.owner_user_id == current_user.id
    ).all()
    
    # TODO: Product decision needed - should we:
    # 1. Transfer ownership to another member?
    # 2. Keep org but mark as "orphaned"?
    # 3. Soft delete org?
    # For now: Keep org but owner_user_id remains (will be invalid, but data preserved)
    
    db.commit()
    
    # Log account deletion (before email is anonymized)
    try:
        log_activity(
            db,
            user_id=current_user.id,
            action="user.account_deleted",
            metadata={"original_email": original_email, "deleted_at": datetime.utcnow().isoformat()},
            request=request
        )
    except Exception:
        pass  # Don't fail if logging fails
    
    return {"success": True, "message": "Account deleted successfully"}


@router.delete("/organizations/{org_id}")
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    request: Request = None
):
    """
    Delete an organization (OWNER only, soft delete).
    
    Behavior:
    - Only owner can delete
    - Soft delete org + related data
    - Keep logs but detach personal identifiers
    """
    from backend.services.activity_logger import log_activity
    
    # Get organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check ownership
    if org.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can delete the organization"
        )
    
    # Soft delete organization (mark as inactive/deleted)
    # Note: If you add a deleted_at field later, set it here
    org_name = org.name
    org.name = f"deleted_{org_id}_{datetime.utcnow().timestamp()}"
    
    # Soft delete domains (mark as deleted)
    domains = db.query(DomainModel).filter(DomainModel.organization_id == org_id).all()
    for domain in domains:
        domain.status = "deleted"
        # Anonymize domain name if needed
        # domain.name = f"deleted_{domain.id}"
    
    # Soft delete previews (mark as deleted or remove)
    previews = db.query(PreviewModel).filter(PreviewModel.organization_id == org_id).all()
    for preview in previews:
        # Option: Delete previews or mark as deleted
        # For now: Keep previews but detach from org
        preview.organization_id = None  # Detach from org
    
    # Keep analytics events but detach org_id
    from backend.models.analytics_event import AnalyticsEvent
    events = db.query(AnalyticsEvent).filter(AnalyticsEvent.organization_id == org_id).all()
    for event in events:
        event.organization_id = None  # Detach but keep for internal analytics
    
    # Keep activity logs but detach org_id where applicable
    # (Activity logs don't have org_id directly, but keep for audit)
    
    db.commit()
    
    # Log organization deletion
    try:
        log_activity(
            db,
            user_id=current_user.id,
            action="organization.deleted",
            metadata={"organization_id": org_id, "organization_name": org_name},
            request=request
        )
    except Exception:
        pass
    
    return {"success": True, "message": f"Organization '{org_name}' deleted successfully"}

