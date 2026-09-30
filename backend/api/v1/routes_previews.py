"""Preview gallery routes."""
from datetime import datetime
from fastapi import APIRouter, Query, Depends, HTTPException, status, Request
from typing import List, Optional
from pydantic import BaseModel, Field
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
from backend.services.premium_card_renderer import CARD_SIZES
from backend.services.manual_card import stamp_template_card
from backend.core.plans import has_feature, F_HIDE_WATERMARK
from backend.services.card_rerender import (
    DIRECTABLE_ACCENTS,
    DIRECTABLE_LAYOUTS,
    DIRECTABLE_PANELS,
    apply_direction,
    render_platform_sizes,
    rerender_card,
)
from backend.services.activity_logger import log_activity
from backend.utils.url_sanitizer import sanitize_url
from backend.services.cache import invalidate_preview, invalidate_public_preview_for_url
router = APIRouter(prefix="/previews", tags=["previews"])


def _stamp_if_imageless(preview, db, org, domain) -> None:
    """Give a hand-created preview a real template-lane card.

    A supplied image is kept. An empty image is rendered; failure aborts the
    save so the library never stores a title with no card.
    """
    if preview.image_url:
        preview.generation_mode = preview.generation_mode or "template"
        return
    brand = brand_resolver.resolve(db, org.id, domain.id) if domain is not None else None
    hide = bool(
        brand
        and getattr(brand, "hide_watermark", False)
        and has_feature(org, F_HIDE_WATERMARK)
    )
    try:
        stamp_template_card(preview, brand, hide_watermark=hide)
    except Exception as exc:
        logger_msg = str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not render a card for this preview. Nothing was saved. ({logger_msg})",
        ) from exc


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
        if preview_in.description is not None:
            existing_preview.description = preview_in.description
        existing_preview.ignore_site_branding = bool(preview_in.ignore_site_branding)
        if not existing_preview.image_url:
            _stamp_if_imageless(existing_preview, db, current_org, domain)

        db.commit()
        db.refresh(existing_preview)
        
        # Invalidate cache
        invalidate_preview(existing_preview.id)
        invalidate_public_preview_for_url(existing_preview.url)
        
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
        ignore_site_branding=bool(preview_in.ignore_site_branding),
        user_id=current_user.id,
        organization_id=current_org.id,
        created_at=datetime.utcnow(),
        monthly_clicks=0,
        generation_mode="template",
    )
    db.add(new_preview)
    _stamp_if_imageless(new_preview, db, current_org, domain)
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

    # Copy edits should show up on the card itself when we can re-render.
    if preview.can_rerender and any(k in update_data for k in ("title", "description")):
        spec = dict(preview.render_spec or {})
        spec["subtitle"] = preview.description or ""
        image_url, rendered_layout = rerender_card(
            spec, url=preview.url, title=preview.title, subtitle=preview.description,
        )
        if image_url:
            preview.image_url = image_url
            preview.composited_image_url = image_url
            preview.render_spec = spec
            if rendered_layout:
                preview.layout = rendered_layout

    db.commit()
    db.refresh(preview)
    
    # Invalidate cache
    invalidate_preview(preview_id)
    invalidate_public_preview_for_url(preview.url)
    
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
    invalidate_public_preview_for_url(preview_url)
    
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


@router.post("/generate", status_code=status.HTTP_410_GONE)
def generate_preview_with_ai(
    request: PreviewGenerateRequest,
    current_user: User = Depends(get_paid_user),
    current_org: Organization = Depends(get_current_org),
):
    """Retired synchronous generator. The dashboard uses POST /jobs/preview."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="POST /api/v1/previews/generate is retired. Queue a generation with POST /api/v1/jobs/preview.",
    )


class PreviewRestyleRequest(BaseModel):
    """Direction for a re-render. Every field is optional; omitted means keep."""
    layout: Optional[str] = Field(
        None, description=f"One of: {', '.join(DIRECTABLE_LAYOUTS)}"
    )
    panel: Optional[str] = Field(
        None, description=f"Panel colour role: {', '.join(DIRECTABLE_PANELS)}"
    )
    accent: Optional[str] = Field(
        None, description=f"Accent treatment: {', '.join(DIRECTABLE_ACCENTS)}"
    )


@router.post("/{preview_id}/restyle", response_model=Preview)
def restyle_preview(
    preview_id: int,
    request: PreviewRestyleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Re-render this card with a different layout, panel colour or accent.

    This is a pure render off the stored spec — no page capture, no vision call
    — so it does NOT spend an AI generation from the plan's allowance. The copy
    is unchanged; rewriting the hook is what a full regeneration is for.
    """
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == preview_id,
        PreviewModel.organization_id == current_org.id,
    ).first()
    if not preview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found")

    if not preview.can_rerender:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This preview predates styled re-rendering. Regenerate it once "
                   "to enable restyling.",
        )

    spec = apply_direction(
        preview.render_spec,
        layout=request.layout, panel=request.panel, accent=request.accent,
    )
    image_url, rendered_layout = rerender_card(
        spec, url=preview.url, title=preview.title,
    )
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not render the card. Your existing preview is unchanged.",
        )

    preview.image_url = image_url
    preview.composited_image_url = image_url
    preview.layout = rendered_layout
    # Persist the direction so the next restyle builds on this one rather than
    # silently reverting to what the art director originally chose.
    preview.render_spec = {**spec, "rendered_layout": rendered_layout}
    db.commit()
    db.refresh(preview)

    invalidate_preview(preview_id)
    invalidate_public_preview_for_url(preview.url)
    log_activity(
        db,
        user_id=current_user.id,
        action="preview.restyled",
        metadata={
            "preview_id": preview_id,
            "requested": request.model_dump(exclude_none=True),
            "rendered_layout": rendered_layout,
        },
        request=http_request,
    )
    return preview


@router.post("/{preview_id}/platform-cards")
def build_platform_cards(
    preview_id: int,
    http_request: Request,
    sizes: Optional[List[str]] = Query(
        None, description="Subset of sizes to render; defaults to all"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Render this card at each aspect ratio and return the image URLs.

    Each size is composed at its own dimensions rather than cropped from the
    wide card, so a square is laid out as a square. Like restyling, this is a
    pure render and spends no AI generation.
    """
    preview = db.query(PreviewModel).filter(
        PreviewModel.id == preview_id,
        PreviewModel.organization_id == current_org.id,
    ).first()
    if not preview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found")

    if not preview.can_rerender:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This preview predates multi-size rendering. Regenerate it once "
                   "to enable it.",
        )

    unknown = [s for s in (sizes or []) if s not in CARD_SIZES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown size(s): {', '.join(unknown)}. "
                   f"Available: {', '.join(CARD_SIZES)}",
        )

    cards = render_platform_sizes(
        preview.render_spec, url=preview.url, title=preview.title, sizes=sizes,
    )
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not render any sizes. Your existing preview is unchanged.",
        )

    log_activity(
        db,
        user_id=current_user.id,
        action="preview.platform_cards",
        metadata={"preview_id": preview_id, "sizes": sorted(cards)},
        request=http_request,
    )
    return {
        "preview_id": preview_id,
        "cards": [
            {
                "size": key,
                "width": CARD_SIZES[key].width,
                "height": CARD_SIZES[key].height,
                "image_url": url,
            }
            for key, url in cards.items()
        ],
        # Sizes that failed to render are simply absent; say so rather than
        # letting the caller infer it from a short list.
        "missing": [s for s in (sizes or list(CARD_SIZES)) if s not in cards],
    }
