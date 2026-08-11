"""Tracking endpoints for impressions and clicks."""
from fastapi import APIRouter, Query, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from urllib.parse import unquote, urlparse
from backend.db.session import get_db
from backend.models.preview import Preview as PreviewModel
from backend.models.domain import Domain as DomainModel
from backend.models.analytics_event import AnalyticsEvent
from backend.services.activity_logger import get_client_ip, get_user_agent
from backend.services.rate_limiter import (
    check_rate_limit,
    get_rate_limit_key_for_ip,
    get_rate_limit_key_for_ip_and_domain
)

router = APIRouter(prefix="/track", tags=["tracking"])


def validate_url(url: str) -> bool:
    """Validate that URL is safe (http/https only, no javascript:, data:, etc.)."""
    try:
        from backend.utils.url_sanitizer import validate_url_security
        validate_url_security(url)
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ['http', 'https']:
            return False
        if parsed.netloc == '':
            return False
        return True
    except Exception:
        return False


@router.get("/impression")
def track_impression(
    preview_id: int = Query(..., description="Preview ID"),
    domain: str = Query(None, description="Domain name (optional)"),
    ref: str = Query(None, description="Referrer override (optional)"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Track a preview impression.
    
    Returns JSON response with status.
    """
    # Rate limiting: 200 requests per 5 minutes per IP (or IP+domain if domain provided)
    client_ip = get_client_ip(request)
    if domain:
        rate_limit_key = get_rate_limit_key_for_ip_and_domain(client_ip, domain)
    else:
        rate_limit_key = get_rate_limit_key_for_ip(client_ip, "track_impression")
    
    if not check_rate_limit(rate_limit_key, limit=200, window_seconds=300):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"status": "error", "detail": "Rate limit exceeded. Please try again later."}
        )
    
    try:
        # Resolve preview to get user_id, domain_id
        preview = db.query(PreviewModel).filter(PreviewModel.id == preview_id).first()
        
        if not preview:
            # Still log the event but with limited info
            event = AnalyticsEvent(
                preview_id=preview_id,
                event_type="impression",
                referrer=ref or request.headers.get("Referer") if request else None,
                user_agent=get_user_agent(request),
                ip_address=get_client_ip(request)
            )
            db.add(event)
            db.commit()
            return JSONResponse({"status": "ok"})
        
        # Get domain_id if domain name matches
        domain_id = None
        if domain:
            domain_obj = db.query(DomainModel).filter(DomainModel.name == domain).first()
            if domain_obj:
                domain_id = domain_obj.id
        
        # Use preview's domain if domain_id not found
        if not domain_id and preview.domain:
            domain_obj = db.query(DomainModel).filter(DomainModel.name == preview.domain).first()
            if domain_obj:
                domain_id = domain_obj.id
        
        # Create impression event
        event = AnalyticsEvent(
            user_id=preview.user_id,
            domain_id=domain_id,
            preview_id=preview_id,
            organization_id=preview.organization_id,
            event_type="impression",
            referrer=ref or request.headers.get("Referer") if request else None,
            user_agent=get_user_agent(request),
            ip_address=get_client_ip(request)
        )
        db.add(event)
        db.commit()
        
        return JSONResponse({"status": "ok"})
    
    except Exception as e:
        # Don't fail the request if tracking fails
        return JSONResponse({"status": "ok", "error": str(e)})


@router.post("/social-visit")
@router.get("/social-visit")
def track_social_visit(
    url: str = Query(..., description="Page URL the visitor landed on"),
    ref: str = Query(None, description="Referrer (the social platform the visitor came from)"),
    site: str = Query(None, description="Registered domain override (snippet data-site)"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Record that a visitor reached a customer page from a social platform.

    Fired by the embed snippet (sendBeacon) when document.referrer is a known
    social network. This is the "click" side of preview CTR: the crawler fetch
    of /public/preview is the impression, a human arriving from the platform
    is the click. Resolves the preview by URL, so the snippet needs no IDs.
    """
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "track_social_visit")
    if not check_rate_limit(rate_limit_key, limit=120, window_seconds=300):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"status": "error", "detail": "Rate limit exceeded."}
        )

    try:
        if not validate_url(url):
            return JSONResponse({"status": "ignored"})

        parsed = urlparse(url)
        hostname = (site or parsed.netloc).lower().split(":")[0]
        if hostname.startswith("www."):
            hostname = hostname[4:]

        domain_obj = db.query(DomainModel).filter(DomainModel.name == hostname).first()
        if not domain_obj:
            return JSONResponse({"status": "ignored"})

        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        preview = db.query(PreviewModel).filter(
            PreviewModel.organization_id == domain_obj.organization_id,
            PreviewModel.url.in_([normalized, url]),
        ).first()

        event = AnalyticsEvent(
            user_id=domain_obj.user_id,
            domain_id=domain_obj.id,
            preview_id=preview.id if preview else None,
            organization_id=domain_obj.organization_id,
            event_type="click",
            referrer=(ref or (request.headers.get("Referer") if request else None) or "")[:500] or None,
            user_agent=get_user_agent(request),
            ip_address=client_ip,
        )
        db.add(event)
        # Keep the denormalized counters (gallery cards, domain rows) in step
        # with the event stream.
        if preview:
            preview.monthly_clicks = (preview.monthly_clicks or 0) + 1
        domain_obj.monthly_clicks = (domain_obj.monthly_clicks or 0) + 1
        db.commit()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        # Tracking must never break the customer's page
        return JSONResponse({"status": "ok", "error": str(e)[:100]})


@router.get("/click")
def track_click(
    preview_id: int = Query(..., description="Preview ID"),
    target_url: str = Query(..., description="Target URL (URL encoded)"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Track a preview click and redirect to target URL.
    
    Returns 307 redirect to target_url.
    """
    # Rate limiting: 200 requests per 5 minutes per IP
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "track_click")
    if not check_rate_limit(rate_limit_key, limit=200, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    try:
        # Decode and validate target URL
        decoded_url = unquote(target_url)
        
        # Enhanced URL validation
        from backend.utils.url_sanitizer import validate_url_security
        try:
            validate_url_security(decoded_url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        if not validate_url(decoded_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target URL"
            )
        
        # Resolve preview to get user_id, domain_id
        preview = db.query(PreviewModel).filter(PreviewModel.id == preview_id).first()
        
        domain_id = None
        if preview and preview.domain:
            domain_obj = db.query(DomainModel).filter(DomainModel.name == preview.domain).first()
            if domain_obj:
                domain_id = domain_obj.id
        
        # Create click event
        event = AnalyticsEvent(
            user_id=preview.user_id if preview else None,
            domain_id=domain_id,
            preview_id=preview_id,
            organization_id=preview.organization_id if preview else None,
            event_type="click",
            referrer=request.headers.get("Referer") if request else None,
            user_agent=get_user_agent(request),
            ip_address=get_client_ip(request)
        )
        db.add(event)
        db.commit()
        
        # Redirect to target URL
        return RedirectResponse(url=decoded_url, status_code=307)
    
    except HTTPException:
        raise
    except Exception as e:
        # If tracking fails, still redirect (don't break user experience)
        try:
            decoded_url = unquote(target_url)
            if validate_url(decoded_url):
                return RedirectResponse(url=decoded_url, status_code=307)
        except Exception:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track click"
        )

