"""Preview gallery routes."""
from datetime import datetime
from fastapi import APIRouter, Query, Depends, HTTPException, status, Request
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.schemas.preview import Preview, PreviewCreate, PreviewUpdate
from backend.models.preview import Preview as PreviewModel
from backend.models.domain import Domain as DomainModel
from backend.services import brand_resolver
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_paid_user, get_current_org, role_required
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.services.preview_generator import generate_ai_preview
from backend.services.generation_lane import record_ai_generation
from backend.services.activity_logger import log_activity
from backend.utils.url_sanitizer import sanitize_url
from backend.services.cache import invalidate_preview
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_org

router = APIRouter(prefix="/previews", tags=["previews"])


@router.get("", response_model=List[Preview])
def list_previews(
    type: Optional[str] = Query(None, description="Filter by preview type: 'product', 'blog', or 'landing'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get all previews for the current organization, optionally filtered by type."""
    query = db.query(PreviewModel).filter(
        PreviewModel.organization_id == current_org.id
    )
    
    if type:
        query = query.filter(PreviewModel.type == type.lower())
    
    previews = query.order_by(PreviewModel.created_at.desc()).all()
    return previews


@router.post("", response_model=Preview, status_code=status.HTTP_201_CREATED)
def create_or_update_preview(
    preview_in: PreviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Create a new preview or update existing one if URL already exists for this organization (owner/admin/editor only)."""
    # Check that the domain belongs to the current organization
    domain = db.query(DomainModel).filter(
        DomainModel.name == preview_in.domain,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not found or not owned by this organization."
        )
    
    # Sanitize URL
    try:
        sanitized_url = sanitize_url(preview_in.url, preview_in.domain)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Check if a preview with the same URL already exists for this organization
    existing_preview = db.query(PreviewModel).filter(
        PreviewModel.url == sanitized_url,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if existing_preview:
        # Update existing preview
        if preview_in.title is not None:
            existing_preview.title = preview_in.title
        if preview_in.type is not None:
            existing_preview.type = preview_in.type
        if preview_in.image_url is not None:
            existing_preview.image_url = preview_in.image_url
        if preview_in.domain is not None:
            existing_preview.domain = preview_in.domain
        
        db.commit()
        db.refresh(existing_preview)
        
        # Invalidate cache
        invalidate_preview(existing_preview.id)
        
        # Log preview update
        log_activity(
            db,
            user_id=current_user.id,
            action="preview.updated",
            metadata={"preview_id": existing_preview.id, "url": sanitized_url, "domain": preview_in.domain},
            request=request
        )
        
        return existing_preview
    
    # Create new preview
    new_preview = PreviewModel(
        url=sanitized_url,
        domain=preview_in.domain,
        title=preview_in.title,
        type=preview_in.type,
        image_url=preview_in.image_url or "",
        description=preview_in.description,
        user_id=current_user.id,
        organization_id=current_org.id,
        created_at=datetime.utcnow(),
        monthly_clicks=0,
    )
    db.add(new_preview)
    db.commit()
    db.refresh(new_preview)
    
    # Log preview creation
    log_activity(
        db,
        user_id=current_user.id,
        action="preview.created",
        metadata={"preview_id": new_preview.id, "url": sanitized_url, "domain": preview_in.domain, "type": preview_in.type},
        request=request
    )
    
    return new_preview


@router.put("/{preview_id}", response_model=Preview)
def update_preview(
    preview_id: int,
    preview_update: PreviewUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Update an existing preview (owner/admin/editor only)."""
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview with ID {preview_id} not found"
        )
    
    # Update fields that are not None
    update_data = preview_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Handle image_url: if None, set to empty string (model requires non-null)
        if field == 'image_url' and value is None:
            setattr(preview, field, "")
        else:
            setattr(preview, field, value)
    
    db.commit()
    db.refresh(preview)
    
    # Invalidate cache
    invalidate_preview(preview_id)
    
    # Log preview edit
    log_activity(
        db,
        user_id=current_user.id,
        action="preview.edited",
        metadata={"preview_id": preview_id, "url": preview.url, "changes": update_data},
        request=request
    )
    
    return preview


@router.delete("/{preview_id}")
def delete_preview(
    preview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """Delete a preview (owner/admin only)."""
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == preview_id,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview with ID {preview_id} not found"
        )
    
    preview_url = preview.url
    preview_title = preview.title
    db.delete(preview)
    db.commit()
    
    # Invalidate cache
    invalidate_preview(preview_id)
    
    # Log preview deletion
    log_activity(
        db,
        user_id=current_user.id,
        action="preview.deleted",
        metadata={"preview_id": preview_id, "url": preview_url, "title": preview_title},
        request=request
    )
    
    return {"success": True}


class PreviewGenerateRequest(BaseModel):
    """Schema for AI preview generation request."""
    url: str
    domain: str


@router.post("/generate", response_model=Preview, status_code=status.HTTP_201_CREATED)
def generate_preview_with_ai(
    request: PreviewGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_paid_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Generate a preview using AI for a given URL (owner/admin/editor only)."""
    # Rate limiting: 100 generations per hour per organization
    rate_limit_key = get_rate_limit_key_for_org(current_org.id)
    if not check_rate_limit(rate_limit_key, limit=100, window_seconds=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    # Step 1: Validate that domain belongs to current organization
    domain = db.query(DomainModel).filter(
        DomainModel.name == request.domain,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not found or not owned by this organization."
        )
    
    # Step 1.5: Check domain verification
    if domain.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before generating previews."
        )
    
    # Step 2: Load brand settings for THIS domain, falling back to the
    # organization default when the domain has not been customised.
    brand_settings = brand_resolver.resolve(db, current_org.id, domain.id)

    if not brand_settings:
        brand_settings = brand_resolver.get_or_create(
            db, current_org.id, user_id=current_user.id, domain_id=domain.id
        )

    # Step 3: Call AI preview generator.
    # This is the legacy synchronous path: it predates the unified engine and
    # does not run the art director or the premium card renderer, so it cannot
    # honour the template lane. It still costs a vision call, so it spends from
    # the account's monthly AI allowance rather than quietly bypassing the meter.
    # The metered, engine-backed path the dashboard uses is POST /jobs/preview.
    record_ai_generation(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        url=request.url,
        domain=request.domain,
    )
    try:
        from backend.schemas.brand import BrandSettings as BrandSettingsSchema
        brand_schema = BrandSettingsSchema.model_validate(brand_settings)
        ai_result = generate_ai_preview(request.url, brand_schema)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {str(e)}"
        )
    
    # Step 4: Upsert Preview record
    existing_preview = db.query(PreviewModel).filter(
        PreviewModel.url == request.url,
        PreviewModel.organization_id == current_org.id
    ).first()
    
    if existing_preview:
        # Update existing preview
        existing_preview.title = ai_result["title"]
        existing_preview.description = ai_result.get("description")
        existing_preview.image_url = ai_result.get("image_url") or ""
        # Determine type based on URL or keep existing
        if not existing_preview.type:
            # Simple heuristic: determine type from URL
            url_lower = request.url.lower()
            if "/product" in url_lower or "/shop" in url_lower:
                existing_preview.type = "product"
            elif "/blog" in url_lower or "/post" in url_lower:
                existing_preview.type = "blog"
            else:
                existing_preview.type = "landing"
        
        db.commit()
        db.refresh(existing_preview)
        return existing_preview
    else:
        # Create new preview
        # Determine type based on URL
        url_lower = request.url.lower()
        if "/product" in url_lower or "/shop" in url_lower:
            preview_type = "product"
        elif "/blog" in url_lower or "/post" in url_lower:
            preview_type = "blog"
        else:
            preview_type = "landing"
        
        new_preview = PreviewModel(
            url=request.url,
            domain=request.domain,
            title=ai_result["title"],
            description=ai_result.get("description"),
            type=preview_type,
            image_url=ai_result.get("image_url") or "",
            user_id=current_user.id,
            organization_id=current_org.id,
            created_at=datetime.utcnow(),
            monthly_clicks=0,
        )
        db.add(new_preview)
        db.commit()
        db.refresh(new_preview)
        return new_preview

