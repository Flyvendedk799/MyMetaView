"""Preview variant management routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.models.preview import Preview as PreviewModel
from backend.models.preview_variant import PreviewVariant as PreviewVariantModel
from backend.schemas.preview_variant import PreviewVariantPublic, PreviewVariantUpdate
from backend.services.activity_logger import log_activity
from backend.core.plans import has_feature, F_VARIANTS


def _require_variants(org: Organization) -> None:
    if not has_feature(org, F_VARIANTS):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="A/B preview variants are not included in this plan.",
        )

router = APIRouter(prefix="/preview-variants", tags=["preview-variants"])


@router.get("/preview/{preview_id}", response_model=List[PreviewVariantPublic])
def list_preview_variants(
    preview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get all variants for a preview."""
    # Verify preview belongs to organization
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not found"
        )
    
    variants = db.query(PreviewVariantModel).filter(
        PreviewVariantModel.preview_id == preview_id
    ).all()
    
    return variants


@router.get("/{variant_id}", response_model=PreviewVariantPublic)
def get_preview_variant(
    variant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get a specific preview variant."""
    variant = db.query(PreviewVariantModel).filter(
        PreviewVariantModel.id == variant_id
    ).first()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found"
        )
    
    # Verify preview belongs to organization
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == variant.preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return variant


@router.put("/{variant_id}", response_model=PreviewVariantPublic)
def update_preview_variant(
    variant_id: int,
    variant_update: PreviewVariantUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Update a preview variant (owner/admin/editor only)."""
    _require_variants(current_org)
    variant = db.query(PreviewVariantModel).filter(
        PreviewVariantModel.id == variant_id
    ).first()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found"
        )
    
    # Verify preview belongs to organization
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == variant.preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update variant
    update_data = variant_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(variant, key, value)
    
    db.commit()
    db.refresh(variant)
    
    log_activity(
        db,
        user_id=current_user.id,
        organization_id=current_org.id,
        action="preview.variant.updated",
        metadata={"variant_id": variant_id, "preview_id": variant.preview_id, "variant_key": variant.variant_key},
        request=request
    )
    
    return variant


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preview_variant(
    variant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """Delete a preview variant (owner/admin only)."""
    _require_variants(current_org)
    variant = db.query(PreviewVariantModel).filter(
        PreviewVariantModel.id == variant_id
    ).first()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found"
        )
    
    # Verify preview belongs to organization
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == variant.preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    variant_key = variant.variant_key
    preview_id = variant.preview_id
    db.delete(variant)
    db.commit()
    
    log_activity(
        db,
        user_id=current_user.id,
        organization_id=current_org.id,
        action="preview.variant.deleted",
        metadata={"variant_id": variant_id, "preview_id": preview_id, "variant_key": variant_key},
        request=request
    )
    
    return None

