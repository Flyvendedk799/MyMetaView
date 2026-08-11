"""Public preview API routes (no authentication required)."""
from urllib.parse import urlparse
from fastapi import APIRouter, Query, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from backend.schemas.public_preview import PublicPreview
from backend.models.domain import Domain as DomainModel
from backend.models.preview import Preview as PreviewModel
from backend.models.preview_variant import PreviewVariant as PreviewVariantModel
from backend.db.session import get_db
from backend.core.config import settings
from backend.services.cache import (
    get_cached_domain_by_name,
    set_cached_domain_by_name,
    get_cached_preview_metadata,
    set_cached_preview_metadata,
)
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip
from backend.services.activity_logger import get_client_ip
from backend.utils.crawler_detection import (
    detect_crawler,
    log_crawler_detection,
    get_crawler_metadata
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/preview", response_model=PublicPreview)
def get_public_preview(
    full_url: str = Query(..., description="Full URL to generate preview for"),
    variant: str = Query(None, description="Variant key: 'a', 'b', or 'c' (optional)"),
    site: str = Query(None, description="Registered domain to resolve against, when it differs from the URL's hostname"),
    request: Request = None,
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
    # Detect and log crawler user agents (prep work for future server-side interception)
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
    
    return _get_preview_logic(full_url, db, variant, crawler_name, site)


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


def _get_preview_logic(
    full_url: str,
    db: Session,
    variant: str = None,
    crawler_name: str = None,
    site: str = None,
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

        # Try cache first for domain lookup (we need org_id for cache key, so check cache after domain lookup)
        # Look up domain by hostname
        domain = db.query(DomainModel).filter(
            DomainModel.name == lookup_hostname
        ).first()

        # Cache domain if found
        if domain and domain.organization_id:
            domain_cache_data = {
                "id": domain.id,
                "name": domain.name,
                "status": domain.status,
                "organization_id": domain.organization_id,
            }
            set_cached_domain_by_name(domain.organization_id, lookup_hostname, domain_cache_data)

        if not domain:
            # No matching domain found - return fallback with placeholder
            return PublicPreview(
                url=full_url,
                title=hostname or "Untitled Page",
                description="Preview not configured yet.",
                image_url=settings.PLACEHOLDER_IMAGE_URL,
                site_name=hostname,
                status="fallback"
            )
        
        # Domain found - check if verified
        if domain.status != "verified":
            # Domain not verified - return fallback with placeholder
            return PublicPreview(
                url=full_url,
                title=hostname or "Untitled Page",
                description="Domain not verified.",
                image_url=settings.PLACEHOLDER_IMAGE_URL,
                site_name=hostname,
                type=None,
                status="fallback"
            )
        
        # Domain found - get organization_id
        organization_id = domain.organization_id
        
        if organization_id is None:
            # Domain exists but has no organization (legacy data) - return fallback with placeholder
            return PublicPreview(
                url=full_url,
                title=hostname or "Untitled Page",
                description="Preview not configured yet.",
                image_url=settings.PLACEHOLDER_IMAGE_URL,
                site_name=hostname,
                status="fallback"
            )
        
        # Try cache first for preview metadata
        preview = None
        preview_cache_key = None
        
        # Normalize URL for deterministic matching
        normalized_url = _normalize_url_for_matching(full_url)
        
        # Try to find a matching preview for this organization and URL
        # Match on normalized URL first (most deterministic)
        preview = db.query(PreviewModel).filter(
            PreviewModel.organization_id == organization_id,
            PreviewModel.url == normalized_url
        ).first()
        
        # If no normalized match, try exact URL match
        if not preview:
            preview = db.query(PreviewModel).filter(
                PreviewModel.organization_id == organization_id,
                PreviewModel.url == full_url
            ).first()
        
        # If still no match, try matching on path only (for legacy URLs)
        if not preview and parsed.path:
            path_only = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
            preview = db.query(PreviewModel).filter(
                PreviewModel.organization_id == organization_id,
                PreviewModel.url == path_only
            ).first()
        
        if preview:
            # Cache preview metadata
            preview_cache_data = {
                "id": preview.id,
                "title": preview.title,
                "description": preview.description,
                "image_url": preview.image_url,
                "type": preview.type,
            }
            set_cached_preview_metadata(preview.id, preview_cache_data)
            # Check if variant is requested
            if variant and variant.lower() in ['a', 'b', 'c']:
                variant_obj = db.query(PreviewVariantModel).filter(
                    PreviewVariantModel.preview_id == preview.id,
                    PreviewVariantModel.variant_key == variant.lower()
                ).first()
                
                if variant_obj:
                    # Use variant data
                    # Determine status: fully_generated if has AI content, otherwise pending_ai
                    preview_status = "fully_generated" if preview.ai_reasoning else "pending_ai"
                    
                    # Use composited_image_url if available (designed UI card), otherwise fall back to variant or preview images
                    image_url = preview.composited_image_url or variant_obj.image_url or preview.highlight_image_url or preview.image_url or settings.PLACEHOLDER_IMAGE_URL
                    
                    return PublicPreview(
                        url=full_url,
                        title=variant_obj.title,
                        description=variant_obj.description if variant_obj.description else "No preview description available.",
                        image_url=image_url,
                        site_name=domain.name,
                        type=preview.type,
                        status=preview_status,
                        version=variant_obj.variant_key  # Use variant key as version for A/B testing
                    )
                # Variant not found, fall through to main preview
            
            # Use main preview data
            # Determine status: fully_generated if has AI content, otherwise pending_ai
            preview_status = "fully_generated" if preview.ai_reasoning else "pending_ai"
            
            # Use composited_image_url if available (designed UI card), otherwise fall back to highlight_image_url or image_url
            image_url = preview.composited_image_url or preview.highlight_image_url or preview.image_url or settings.PLACEHOLDER_IMAGE_URL
            
            return PublicPreview(
                url=full_url,
                title=preview.title,
                description=preview.description if preview.description else "No preview description available.",
                image_url=image_url,
                site_name=domain.name,
                type=preview.type,
                status=preview_status,
                version="main"  # Main preview version
            )
        else:
            # Domain exists but no preview found - return fallback with placeholder
            path_display = parsed.path if parsed.path else "/"
            return PublicPreview(
                url=full_url,
                title=hostname or "Untitled Page",
                description="Preview not generated yet.",
                image_url=settings.PLACEHOLDER_IMAGE_URL,
                site_name=hostname,
                status="fallback"
            )
            
    except Exception as e:
        # On any error, return a safe fallback with placeholder
        logger.error(f"Error generating preview for {full_url}: {e}", exc_info=True)
        return PublicPreview(
            url=full_url,
            title="Untitled Page",
            description="Preview not available.",
            image_url=settings.PLACEHOLDER_IMAGE_URL,
            site_name=None,
            status="fallback"
        )

