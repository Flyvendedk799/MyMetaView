"""Brand settings routes."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from backend.schemas.brand import BrandSettings, BrandSettingsUpdate
from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.services.cache import (
    get_cached_brand_settings,
    set_cached_brand_settings,
    invalidate_brand_settings
)

router = APIRouter(prefix="/brand", tags=["brand"])


@router.get("", response_model=BrandSettings)
def get_brand_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get brand settings for the current organization."""
    # Try cache first
    cached = get_cached_brand_settings(current_org.id)
    if cached:
        return BrandSettings(**cached)
    
    settings = db.query(BrandSettingsModel).filter(
        BrandSettingsModel.organization_id == current_org.id
    ).first()
    
    # If no settings exist, create default ones for this organization
    if not settings:
        settings = BrandSettingsModel(
            primary_color="#2979FF",
            secondary_color="#0A1A3C",
            accent_color="#3FFFD3",
            font_family="Inter",
            logo_url=None,
            user_id=current_user.id,
            organization_id=current_org.id,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    # Cache the result
    settings_dict = {
        "id": settings.id,
        "primary_color": settings.primary_color,
        "secondary_color": settings.secondary_color,
        "accent_color": settings.accent_color,
        "font_family": settings.font_family,
        "logo_url": settings.logo_url,
        "preview_layout": getattr(settings, "preview_layout", "auto") or "auto",
        "preview_panel": getattr(settings, "preview_panel", "auto") or "auto",
        "preview_accent": getattr(settings, "preview_accent", "auto") or "auto",
        "force_brand_colors": bool(getattr(settings, "force_brand_colors", False)),
        "hide_watermark": bool(getattr(settings, "hide_watermark", False)),
    }
    set_cached_brand_settings(current_org.id, settings_dict)
    
    return settings


@router.put("", response_model=BrandSettings)
def update_brand_settings(
    settings_update: BrandSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Update brand settings for the current organization (owner/admin/editor only)."""
    settings = db.query(BrandSettingsModel).filter(
        BrandSettingsModel.organization_id == current_org.id
    ).first()
    
    # Create a defaulted row if none exists yet, then apply EVERY provided field
    # (uniform path so the new preview-preference columns persist for new users too,
    # not just the legacy colour/font fields).
    if not settings:
        settings = BrandSettingsModel(
            primary_color="#2979FF", secondary_color="#0A1A3C", accent_color="#3FFFD3",
            font_family="Inter", user_id=current_user.id, organization_id=current_org.id,
        )
        db.add(settings)

    update_data = settings_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    
    # Invalidate cache
    invalidate_brand_settings(current_org.id)

    return settings


@router.post("/logo", response_model=BrandSettings)
async def upload_brand_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Upload a brand logo, store it in R2, and set logo_url on the org's brand settings."""
    from backend.services.r2_client import upload_file_to_r2

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 5 MB")
    content_type = file.content_type or "image/png"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    ext = (file.filename or "logo").rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "webp", "svg", "gif"):
        ext = "png"

    url = upload_file_to_r2(content, f"brand-logos/{current_org.id}/{uuid4()}.{ext}", content_type)
    if not url:
        raise HTTPException(status_code=500, detail="Logo upload failed")

    settings = db.query(BrandSettingsModel).filter(
        BrandSettingsModel.organization_id == current_org.id
    ).first()
    if not settings:
        settings = BrandSettingsModel(
            primary_color="#2979FF", secondary_color="#0A1A3C", accent_color="#3FFFD3",
            font_family="Inter", user_id=current_user.id, organization_id=current_org.id,
        )
        db.add(settings)
    settings.logo_url = url
    db.commit()
    db.refresh(settings)
    invalidate_brand_settings(current_org.id)
    return settings


@router.post("/preview")
def render_brand_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Render a SAMPLE share-card from the org's brand settings + preview prefs so
    the user sees their customization live. Returns {"image_url": <r2 url>}."""
    import base64 as _b64
    import requests
    from backend.services.premium_card_renderer import render_premium_card
    from backend.services.r2_client import upload_file_to_r2

    s = db.query(BrandSettingsModel).filter(
        BrandSettingsModel.organization_id == current_org.id
    ).first()

    primary = getattr(s, "primary_color", None) or "#0B3B2E"
    secondary = getattr(s, "secondary_color", None) or "#12523F"
    accent = getattr(s, "accent_color", None) or "#E8622C"
    layout = getattr(s, "preview_layout", "auto") or "auto"
    panel = getattr(s, "preview_panel", "auto") or "auto"
    accent_moment = getattr(s, "preview_accent", "auto") or "auto"
    from backend.core.plans import has_feature, F_HIDE_WATERMARK
    hide_watermark = bool(getattr(s, "hide_watermark", False)) and has_feature(current_org, F_HIDE_WATERMARK)
    logo_url = getattr(s, "logo_url", None)

    composition = {
        "layout": "typographic" if layout == "auto" else layout,
        "use_visual": False,  # sample has no page screenshot
        "panel_color_role": "primary" if panel == "auto" else panel,
        "accent_moment": "bar" if accent_moment == "auto" else accent_moment,
        "mood": "confident",
    }

    logo_data_uri = None
    if logo_url:
        try:
            r = requests.get(logo_url, timeout=8)
            if r.status_code == 200 and r.content:
                ct = r.headers.get("content-type", "image/png")
                logo_data_uri = f"data:{ct};base64," + _b64.b64encode(r.content).decode()
        except Exception:
            logo_data_uri = None

    org_slug = (current_org.name or "yourdomain").lower().replace(" ", "")
    try:
        png = render_premium_card(
            title="Plans that scale with your team",
            subtitle="Usage-based pricing that grows only when you do.",
            url=f"{org_slug}.com/pricing",
            brand_name=current_org.name,
            colors={"primary_color": primary, "secondary_color": secondary, "accent_color": accent},
            composition=composition,
            logo_data_uri=logo_data_uri,
            hide_watermark=hide_watermark,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview render failed: {e}")

    out_url = upload_file_to_r2(png, f"brand-previews/{current_org.id}/{uuid4()}.png", "image/png")
    if not out_url:
        raise HTTPException(status_code=500, detail="Preview upload failed")
    return {"image_url": out_url}

