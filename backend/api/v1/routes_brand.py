"""Brand settings routes.

Brands are scoped per domain: an organization can connect several sites and each
has its own identity. Every endpoint here takes an optional ``domain_id``.
Omitting it operates on the organization-wide default row, which is what these
endpoints did before brands became per-domain.

A domain with no brand of its own *follows* the default: reading it does not
write anything (``inherits_default`` says so), saving it creates its own row,
and ``DELETE`` puts it back on the default.
"""
from types import SimpleNamespace
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.core.deps import get_current_org, get_current_user, role_required
from backend.db.session import get_db
from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.models.domain import Domain as DomainModel
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.models.user import User
from backend.schemas.brand import BrandSettings, BrandSettingsUpdate, BrandSuggestion
from backend.services import brand_resolver
from backend.services.cache import (
    get_cached_brand_settings,
    invalidate_brand_settings,
    set_cached_brand_settings,
)

router = APIRouter(prefix="/brand", tags=["brand"])

_EDITORS = role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR])


def _checked_domain(
    db: Session, current_org: Organization, domain_id: Optional[int]
) -> Optional[DomainModel]:
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
    return owned


def _view(row: BrandSettingsModel, *, domain_id: Optional[int], inherits: bool) -> dict:
    """What the tab reads for a scope. Cache-safe (plain JSON types).

    Built from the schema rather than a hand-kept field list — the hand-kept one
    left out ``white_label_name``, so a cached read showed it blank and the next
    save wiped it.
    """
    data = BrandSettings.model_validate(row).model_dump()
    data["domain_id"] = domain_id
    data["inherits_default"] = inherits
    if inherits:
        data["id"] = None
    return data


def _invalidate(db: Session, org: Organization, domain_id: Optional[int], reason: str) -> None:
    """Drop the cached settings views and the previews a brand change makes stale.

    Editing the account default changes every domain that follows it, so their
    cached views go too — otherwise those domains keep showing the old default.
    """
    from backend.services.preview.caching.invalidation import invalidate_org_previews

    invalidate_brand_settings(org.id, domain_id)
    if domain_id is None:
        for (other_id,) in db.query(DomainModel.id).filter(DomainModel.organization_id == org.id):
            invalidate_brand_settings(org.id, other_id)
    invalidate_org_previews(db, org.id, domain_id=domain_id, reason=reason)


@router.get("", response_model=BrandSettings)
def get_brand_settings(
    domain_id: Optional[int] = Query(None, description="Domain to read; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Brand settings for a domain, or for the organization when none is given.

    Read-only. A domain that has not been customised shows the organization
    default with ``inherits_default: true`` — it used to get a copy written on
    first view, which silently detached it from the default the user edited
    afterwards.
    """
    _checked_domain(db, current_org, domain_id)

    cached = get_cached_brand_settings(current_org.id, domain_id)
    if cached and "inherits_default" in cached:
        return BrandSettings(**cached)

    row, inherits = brand_resolver.resolve_view(db, current_org.id, domain_id)
    view = _view(row, domain_id=domain_id, inherits=inherits)
    set_cached_brand_settings(current_org.id, view, domain_id)
    return BrandSettings(**view)


def _check_white_label(
    org: Organization, row: BrandSettingsModel, update: dict
) -> None:
    """Only a *change* to the white-label name needs the plan.

    The tab always sends every field, so a form that merely carries the value
    along (null on almost every account) is not an attempt to set one — and
    treating it as one returned 402 on every save for every plan without
    white-label. That is what "My Site does not save" was.
    """
    if "white_label_name" not in update:
        return
    from backend.core.plans import F_WHITE_LABEL, has_feature

    if has_feature(org, F_WHITE_LABEL):
        return
    if update["white_label_name"] == (getattr(row, "white_label_name", None) or None):
        update.pop("white_label_name")
        return
    if update["white_label_name"] is None:
        # Clearing a name left over from a downgraded plan is always allowed.
        return
    raise HTTPException(status_code=402, detail="White-label naming is not included in this plan.")


@router.put("", response_model=BrandSettings)
def update_brand_settings(
    settings_update: BrandSettingsUpdate,
    domain_id: Optional[int] = Query(None, description="Domain to update; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(_EDITORS),
):
    """Update brand settings for a domain (owner/admin/editor only).

    The first save for a domain gives it its own row, seeded from the
    organization default, so it starts where the account left off.
    """
    _checked_domain(db, current_org, domain_id)

    settings = brand_resolver.get_or_create(
        db, current_org.id, user_id=current_user.id, domain_id=domain_id
    )
    update_data = settings_update.model_dump(exclude_unset=True)
    _check_white_label(current_org, settings, update_data)

    for field, value in update_data.items():
        if field in brand_resolver.REQUIRED_FIELDS and value is None:
            continue  # a non-null column cannot be "unset"; keep what is stored
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    _invalidate(db, current_org, domain_id, "brand settings updated")
    return BrandSettings(**_view(settings, domain_id=domain_id, inherits=False))


@router.delete("", response_model=BrandSettings)
def reset_brand_settings(
    domain_id: int = Query(..., description="Domain to put back on the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(_EDITORS),
):
    """Forget a domain's own brand so it follows the organization default again."""
    _checked_domain(db, current_org, domain_id)
    if brand_resolver.delete_for_domain(db, current_org.id, domain_id):
        _invalidate(db, current_org, domain_id, "domain brand reset to default")
    else:
        invalidate_brand_settings(current_org.id, domain_id)

    row, inherits = brand_resolver.resolve_view(db, current_org.id, domain_id)
    return BrandSettings(**_view(row, domain_id=domain_id, inherits=inherits))


@router.post("/logo", response_model=BrandSettings)
async def upload_brand_logo(
    file: UploadFile = File(...),
    domain_id: Optional[int] = Query(None, description="Domain to attach the logo to; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(_EDITORS),
):
    """Upload a brand logo, store it, and set logo_url on that domain's brand settings."""
    from backend.services.r2_client import upload_file_to_r2

    _checked_domain(db, current_org, domain_id)

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
    # A new logo changes every card this scope will serve. Without this the
    # customer waits out the cache TTL and reasonably concludes the upload
    # silently failed.
    _invalidate(db, current_org, domain_id, "brand logo uploaded")
    return BrandSettings(**_view(settings, domain_id=domain_id, inherits=False))


@router.post("/preview")
def render_brand_preview(
    draft: Optional[BrandSettingsUpdate] = Body(None),
    domain_id: Optional[int] = Query(None, description="Domain to sample; omit for the organization default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Render a sample share-card from a scope's brand settings.

    An optional body is the unsaved draft from the form, laid over what is
    saved, so the sample answers every edit before it is saved. Gating, the
    font rule and the logo treatment are the engine's own (``brand_sample``).
    Returns ``{"image_data_uri": "data:image/png;base64,..."}``.
    """
    from backend.core.plans import F_CARD_CONTROLS, F_HIDE_WATERMARK, has_feature
    from backend.services.preview.brand_sample import render_sample_data_uri, sample_host
    from backend.services.preview.branding import engine_payload

    domain = _checked_domain(db, current_org, domain_id)
    row, _ = brand_resolver.resolve_view(db, current_org.id, domain_id)

    merged = {c.name: getattr(row, c.name, None) for c in BrandSettingsModel.__table__.columns}
    if draft is not None:
        merged.update(draft.model_dump(exclude_unset=True))
    settings = engine_payload(
        SimpleNamespace(**merged),
        can_card_controls=has_feature(current_org, F_CARD_CONTROLS),
        can_hide_watermark=has_feature(current_org, F_HIDE_WATERMARK),
    )
    host = sample_host(settings.get("brand_name") or current_org.name, domain.name if domain else None)

    try:
        image = render_sample_data_uri(settings, host=host, fallback_name=current_org.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview render failed: {e}")
    return {"image_data_uri": image}


@router.post("/detect", response_model=BrandSuggestion)
def detect_brand_from_site(
    domain_id: int = Query(..., description="Domain whose home page to read"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(_EDITORS),
):
    """Read name, strapline, description, palette and logo off the domain's home page.

    Suggestions only: nothing is saved until the user saves the form.
    """
    from backend.services.preview.extraction.site_brand import SiteUnreachable, detect_site_brand

    domain = _checked_domain(db, current_org, domain_id)
    try:
        found = detect_site_brand(domain.name, organization_id=current_org.id)
    except SiteUnreachable as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read https://{domain.name}/ ({exc}). Fill the form in by hand.",
        )
    return BrandSuggestion(**found)
