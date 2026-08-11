"""Public preview API routes (no authentication required).

This is the endpoint customer sites (snippet, Cloudflare Worker, WordPress
plugin) and social crawlers ultimately depend on. Design goals:

- Fast: one Redis GET satisfies repeat human/snippet traffic for 3 minutes.
- Honest: fallbacks never fabricate marketing copy; description stays empty
  so integrations can keep the page's own tags.
- Measured: a crawler fetch is the closest observable proxy for "this link
  was shared and a platform rendered its card", so crawler hits are recorded
  as impression events (best-effort, never blocking the response).
"""
from urllib.parse import urlparse
from fastapi import APIRouter, Query, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from backend.schemas.public_preview import PublicPreview
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.models.preview_variant import PreviewVariant as PreviewVariantModel
from backend.db.session import get_db
from backend.core.config import settings, placeholder_image_url
from backend.services.cache import (
    get_cached_public_preview,
    set_cached_public_preview,
)
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip
from backend.services.activity_logger import get_client_ip
from backend.utils.crawler_detection import (
    detect_crawler,
    log_crawler_detection,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

# How long integrations and browsers may reuse a response before revalidating.
PUBLIC_PREVIEW_MAX_AGE = 300


@router.get("/preview", response_model=PublicPreview)
def get_public_preview(
    full_url: str = Query(..., description="Full URL to generate preview for"),
    variant: str = Query(None, description="Variant key: 'a', 'b', or 'c' (optional)"),
    site: str = Query(None, description="Registered domain to resolve against, when it differs from the URL's hostname"),
    request: Request = None,
    response: Response = None,
    db: Session = Depends(get_db)
):
    """
    Get preview metadata for a given URL.
    This endpoint is public and does not require authentication.

    If variant is provided, returns variant metadata instead of main preview.

    If site is provided, the preview is resolved against that registered domain
    instead of the URL's own hostname. This lets a subdomain (blog.example.com)
    serve previews owned by the registered apex domain.
    """
    user_agent = request.headers.get("user-agent") if request else None
    crawler_name, platform = detect_crawler(user_agent)
    log_crawler_detection(user_agent, full_url, crawler_name, platform)

    # Rate limiting: 200 requests per 5 minutes per IP
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "public_preview")
    if not check_rate_limit(rate_limit_key, limit=200, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )

    # Validate URL security
    from backend.utils.url_sanitizer import validate_url_security
    try:
        validate_url_security(full_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if response is not None:
        response.headers["Cache-Control"] = f"public, max-age={PUBLIC_PREVIEW_MAX_AGE}"

    variant_key = variant.lower() if variant and variant.lower() in ("a", "b", "c") else None
    cache_key = (site or "", full_url, variant_key or "")

    # Response-level cache for repeat snippet/browser traffic. Crawler hits
    # deliberately bypass it so every crawler fetch is observed and recorded.
    if not crawler_name:
        cached = get_cached_public_preview(*cache_key)
        if cached:
            return PublicPreview(**cached)

    result = _get_preview_logic(full_url, db, variant_key, crawler_name, platform, site, user_agent)

    if not crawler_name:
        set_cached_public_preview(*cache_key, value=result.model_dump())

    return result


def _normalize_hostname(value: str) -> str:
    """Reduce a hostname or URL to the bare lowercase host used for domain lookup."""
    if not value:
        return ""
    candidate = value.strip().lower()
    if "//" in candidate:
        candidate = urlparse(candidate).netloc or candidate
    # Drop any path, port, credentials or trailing dot.
    candidate = candidate.split("/")[0].split("@")[-1].split(":")[0].rstrip(".")
    if candidate.startswith("www."):
        candidate = candidate[4:]
    return candidate


def _normalize_url_for_matching(url: str) -> str:
    """
    Normalize URL for deterministic matching.

    This ensures the same URL always matches the same preview,
    regardless of query params, fragments, or trailing slashes.
    """
    parsed = urlparse(url)
    # Normalize: scheme + netloc + path (ignore query and fragment for matching)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    return normalized


def _record_impression(
    db: Session,
    domain: DomainModel,
    preview: PreviewModel,
    crawler_name: str,
    platform: str,
    user_agent: str,
) -> None:
    """Record a crawler fetch as an impression event. Best-effort only."""
    try:
        from backend.models.analytics_event import AnalyticsEvent
        event = AnalyticsEvent(
            user_id=domain.user_id,
            organization_id=domain.organization_id,
            domain_id=domain.id,
            preview_id=preview.id if preview else None,
            event_type="impression",
            referrer=platform or crawler_name,
            user_agent=(user_agent or "")[:500],
        )
        db.add(event)
        db.commit()
    except Exception as e:  # pragma: no cover - metrics must never break serving
        logger.warning(f"Failed to record impression: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _fallback(full_url: str, hostname: str, reason: str) -> PublicPreview:
    """A safe fallback that never invents copy.

    The description is intentionally empty: integrations run in "fill"
    spirit — an empty field means "keep whatever the page already has",
    while a fabricated sentence like "Domain not verified." would end up
    as the og:description users actually share.
    """
    return PublicPreview(
        url=full_url,
        title=hostname or "Untitled Page",
        description="",
        image_url=placeholder_image_url(),
        site_name=hostname,
        status="fallback",
        version=reason,
    )


def _get_preview_logic(
    full_url: str,
    db: Session,
    variant: str = None,
    crawler_name: str = None,
    platform: str = None,
    site: str = None,
    user_agent: str = None,
) -> PublicPreview:
    """
    Core logic for getting preview metadata.

    This function is deterministic: the same URL always returns the same preview
    (or fallback) for reliability and caching.
    """
    try:
        parsed = urlparse(full_url)
        hostname = _normalize_hostname(parsed.netloc or parsed.path.split('/')[0])

        # An explicit `site` from the snippet's data-site attribute wins, so a
        # subdomain can resolve against the registered apex domain.
        lookup_hostname = _normalize_hostname(site) or hostname

        domain = db.query(DomainModel).filter(
            DomainModel.name == lookup_hostname
        ).first()

        if not domain:
            return _fallback(full_url, hostname, "no_domain")

        if domain.status != "verified":
            return _fallback(full_url, hostname, "unverified")

        organization_id = domain.organization_id
        if organization_id is None:
            return _fallback(full_url, hostname, "no_org")

        # Normalize URL for deterministic matching
        normalized_url = _normalize_url_for_matching(full_url)

        # Try to find a matching preview for this organization and URL
        preview = db.query(PreviewModel).filter(
            PreviewModel.organization_id == organization_id,
            PreviewModel.url == normalized_url
        ).first()

        if not preview:
            preview = db.query(PreviewModel).filter(
                PreviewModel.organization_id == organization_id,
                PreviewModel.url == full_url
            ).first()

        if not preview and parsed.path:
            path_only = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
            preview = db.query(PreviewModel).filter(
                PreviewModel.organization_id == organization_id,
                PreviewModel.url == path_only
            ).first()

        # A crawler fetching this URL means a share is being rendered.
        if crawler_name:
            _record_impression(db, domain, preview, crawler_name, platform, user_agent)

        if not preview:
            return _fallback(full_url, hostname, "no_preview")

        preview_status = "fully_generated" if preview.ai_reasoning else "pending_ai"

        if variant:
            variant_obj = db.query(PreviewVariantModel).filter(
                PreviewVariantModel.preview_id == preview.id,
                PreviewVariantModel.variant_key == variant
            ).first()

            if variant_obj:
                # The variant's own rendered card must win — serving the main
                # image under variant copy silently breaks A/B comparisons.
                image_url = (
                    variant_obj.image_url
                    or preview.composited_image_url
                    or preview.highlight_image_url
                    or preview.image_url
                    or placeholder_image_url()
                )
                return PublicPreview(
                    url=full_url,
                    title=variant_obj.title,
                    description=variant_obj.description or preview.description or "",
                    image_url=image_url,
                    site_name=domain.name,
                    type=preview.type,
                    status=preview_status,
                    version=variant_obj.variant_key
                )
            # Variant not found, fall through to main preview

        image_url = (
            preview.composited_image_url
            or preview.highlight_image_url
            or preview.image_url
            or placeholder_image_url()
        )

        return PublicPreview(
            url=full_url,
            title=preview.title,
            description=preview.description or "",
            image_url=image_url,
            site_name=domain.name,
            type=preview.type,
            status=preview_status,
            version="main"
        )

    except Exception as e:
        # On any error, return a safe fallback with placeholder
        logger.error(f"Error generating preview for {full_url}: {e}", exc_info=True)
        return PublicPreview(
            url=full_url,
            title="Untitled Page",
            description="",
            image_url=placeholder_image_url(),
            site_name=None,
            status="fallback",
            version="error",
        )
