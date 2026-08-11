"""Brand settings routes.

Brands are scoped per domain: an organization can connect several sites and each
has its own identity. Every endpoint here takes an optional ``domain_id``.
Omitting it operates on the organization-wide default row, which is what these
endpoints did before brands became per-domain.
"""
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from backend.schemas.brand import BrandSettings, BrandSettingsUpdate, VOICE_CHOICES
from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.models.domain import Domain as DomainModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.services import brand_resolver
from backend.services.cache import (
    get_cached_brand_settings,
    set_cached_brand_settings,
    invalidate_brand_settings
)

router = APIRouter(prefix="/brand", tags=["brand"])


def _checked_domain_id(
    db: Session, current_org: Organization, domain_id: Optional[int]
) -> Optional[int]:
    """Reject a domain that is not the caller's, so brands cannot leak across orgs."""
    if domain_id is None:
        return None
    owned = (
        db.query(DomainModel)
        .filter(DomainModel.id == domain_id, DomainModel.organization_id == current_org.id)
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain_id


def _as_dict(settings: BrandSettingsModel) -> dict:
    """Cache-safe view of a row."""
    return {
        "id": settings.id,
        "domain_id": getattr(settings, "domain_id", None),
        "primary_color": settings.primary_color,
        "secondary_color": settings.secondary_color,
        "accent_color": settings.accent_color,
        "font_family": settings.font_family,
        "logo_url": settings.logo_url,
        "brand_name": getattr(settings, "brand_name", None),
        "tagline": getattr(settings, "tagline", None),
        "brand_description": getattr(settings, "brand_description", None),
        "audience": getattr(settings, "audience", None),
        "voice": getattr(settings, "voice", "auto") or "auto",
        "preview_layout": getattr(settings, "preview_layout", "auto") or "auto",
        "preview_panel": getattr(settings, "preview_panel", "auto") or "auto",
        "preview_accent": getattr(settings, "preview_accent", "auto") or "auto",
        "force_brand_colors": bool(getattr(settings, "force_brand_colors", False)),
        "hide_watermark": bool(getattr(settings, "hide_watermark", False)),
    }


@router.get("", response_model=BrandSettings)
def get_brand_settings(
    domain_id: Optional[int] = Query(None, description="Domain to read; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get brand settings for a domain, or for the organization when none is given.

    A domain that has never been customised gets a row seeded from the
    organization default, so it opens showing the account's existing brand
    rather than stock colours.
    """
    domain_id = _checked_domain_id(db, current_org, domain_id)

    cached = get_cached_brand_settings(current_org.id, domain_id)
    if cached:
        return BrandSettings(**cached)

    settings = brand_resolver.get_or_create(
        db, current_org.id, user_id=current_user.id, domain_id=domain_id
    )

    set_cached_brand_settings(current_org.id, _as_dict(settings), domain_id)

    return settings


@router.put("", response_model=BrandSettings)
def update_brand_settings(
    settings_update: BrandSettingsUpdate,
    domain_id: Optional[int] = Query(None, description="Domain to update; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Update brand settings for a domain (owner/admin/editor only)."""
    domain_id = _checked_domain_id(db, current_org, domain_id)

    # Creates the row if this is the first edit for the scope, seeded from the
    # organization default, then applies EVERY provided field (uniform path so
    # the preview-preference columns persist too, not just colour/font).
    settings = brand_resolver.get_or_create(
        db, current_org.id, user_id=current_user.id, domain_id=domain_id
    )

    update_data = settings_update.model_dump(exclude_unset=True)
    if "voice" in update_data and update_data["voice"] not in VOICE_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=f"voice must be one of: {', '.join(VOICE_CHOICES)}",
        )
    # Free-text identity fields: trim, and treat "" as "unset" so the engine keeps
    # inferring rather than being handed an empty string.
    for field in ("brand_name", "tagline", "brand_description", "audience"):
        if field in update_data and isinstance(update_data[field], str):
            update_data[field] = update_data[field].strip() or None
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    # Invalidate cache
    invalidate_brand_settings(current_org.id, domain_id)

    return settings


@router.post("/logo", response_model=BrandSettings)
async def upload_brand_logo(
    file: UploadFile = File(...),
    domain_id: Optional[int] = Query(None, description="Domain to attach the logo to; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Upload a brand logo, store it in R2, and set logo_url on that domain's brand settings."""
    from backend.services.r2_client import upload_file_to_r2

    domain_id = _checked_domain_id(db, current_org, domain_id)

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

    settings = brand_resolver.get_or_create(
        db, current_org.id, user_id=current_user.id, domain_id=domain_id
    )
    settings.logo_url = url
    db.commit()
    db.refresh(settings)
    invalidate_brand_settings(current_org.id, domain_id)
    return settings


@router.post("/preview")
def render_brand_preview(
    domain_id: Optional[int] = Query(None, description="Domain to sample; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Render a SAMPLE share-card from a domain's brand settings + preview prefs so
    the user sees their customization live. Returns {"image_url": <r2 url>}."""
    import base64 as _b64
    import requests
    from backend.services.premium_card_renderer import render_premium_card
    from backend.services.r2_client import upload_file_to_r2

    domain_id = _checked_domain_id(db, current_org, domain_id)
    s = brand_resolver.resolve(db, current_org.id, domain_id)

    primary = getattr(s, "primary_color", None) or "#0B3B2E"
    secondary = getattr(s, "secondary_color", None) or "#12523F"
    accent = getattr(s, "accent_color", None) or "#E8622C"
    from backend.core.plans import has_feature, F_HIDE_WATERMARK, F_CARD_CONTROLS
    # Layout/panel/accent are Growth+ (F_CARD_CONTROLS); collapse to "auto" otherwise
    # so the sample matches what previews will actually render for this plan.
    _can_card_controls = has_feature(current_org, F_CARD_CONTROLS)
    layout = (getattr(s, "preview_layout", "auto") or "auto") if _can_card_controls else "auto"
    panel = (getattr(s, "preview_panel", "auto") or "auto") if _can_card_controls else "auto"
    accent_moment = (getattr(s, "preview_accent", "auto") or "auto") if _can_card_controls else "auto"
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

    # The sample uses the saved identity where it exists, so a name/tagline change
    # is visible on the card the moment it's saved.
    brand_name = (getattr(s, "brand_name", None) or current_org.name or "").strip() or None
    tagline = (getattr(s, "tagline", None) or "").strip() or None

    # Show the real hostname on the sample when we know which site this is for.
    sample_host = None
    if domain_id is not None:
        domain = db.query(DomainModel).filter(DomainModel.id == domain_id).first()
        sample_host = domain.name if domain else None
    if not sample_host:
        sample_host = f"{(brand_name or 'yourdomain').lower().replace(' ', '')}.com"

    try:
        png = render_premium_card(
            title="Plans that scale with your team",
            subtitle=tagline or "Usage-based pricing that grows only when you do.",
            url=f"{sample_host}/pricing",
            brand_name=brand_name,
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

