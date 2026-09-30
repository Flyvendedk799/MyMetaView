"""Newsletter subscription routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from backend.schemas.newsletter import (
    NewsletterSubscribeRequest,
    NewsletterSubscriberResponse,
    NewsletterSubscriberListResponse
)
from backend.models.newsletter_subscriber import NewsletterSubscriber as NewsletterSubscriberModel
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_admin_user
from backend.models.user import User
from backend.services.activity_logger import get_client_ip, get_user_agent
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


def _public_unsub(row) -> NewsletterSubscriberResponse:
    from backend.core.config import settings
    payload = NewsletterSubscriberResponse.model_validate(row)
    token = unsubscribe_token(row.email)
    origin = settings.APP_PUBLIC_URL.rstrip("/")
    payload.unsubscribe_url = f"{origin}/unsubscribe?token={token}"
    return payload


@router.post("/subscribe", response_model=NewsletterSubscriberResponse, status_code=status.HTTP_201_CREATED)
def subscribe_to_newsletter(
    request_data: NewsletterSubscribeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Subscribe to newsletter (public endpoint, no auth required).
    Rate limited to prevent abuse.
    """
    # Rate limiting: 5 subscriptions per 15 minutes per IP
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "newsletter_subscribe")
    if not check_rate_limit(rate_limit_key, limit=5, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Check if email already exists
    existing = db.query(NewsletterSubscriberModel).filter(
        NewsletterSubscriberModel.email == request_data.email
    ).first()
    
    if existing:
        # Update existing subscriber if inactive
        if not existing.is_active:
            existing.is_active = True
            existing.source = request_data.source
            existing.consent_given = request_data.consent_given
            db.commit()
            db.refresh(existing)
            return _public_unsub(existing)
        return _public_unsub(existing)
    
    # Create new subscriber
    subscriber = NewsletterSubscriberModel(
        email=request_data.email,
        source=request_data.source,
        consent_given=request_data.consent_given,
        ip_address=client_ip,
        user_agent=get_user_agent(request)
    )
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)

    return _public_unsub(subscriber)


@router.get("/subscribers", response_model=NewsletterSubscriberListResponse)
def list_subscribers(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    List newsletter subscribers (admin only).
    Supports pagination, search, and filtering by source.
    """
    query = db.query(NewsletterSubscriberModel)
    
    # Apply search filter
    if search:
        query = query.filter(
            NewsletterSubscriberModel.email.ilike(f"%{search}%")
        )
    
    # Apply source filter
    if source:
        query = query.filter(NewsletterSubscriberModel.source == source)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    skip = (page - 1) * per_page
    subscribers = query.order_by(NewsletterSubscriberModel.subscribed_at.desc()).offset(skip).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page
    
    return NewsletterSubscriberListResponse(
        items=subscribers,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/subscribers/export")
def export_subscribers(
    format: str = Query("csv", regex="^(csv|xlsx)$", description="Export format: csv or xlsx"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Export newsletter subscribers (admin only).
    Returns CSV or XLSX file.
    """
    from fastapi.responses import Response
    import csv
    import io
    from datetime import datetime
    
    query = db.query(NewsletterSubscriberModel)
    
    # Apply source filter
    if source:
        query = query.filter(NewsletterSubscriberModel.source == source)
    
    subscribers = query.order_by(NewsletterSubscriberModel.subscribed_at.desc()).all()
    
    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Email", "Source", "Subscribed At", "Is Active", "Consent Given", "IP Address"])
        
        # Write data
        for sub in subscribers:
            writer.writerow([
                sub.email,
                sub.source,
                sub.subscribed_at.isoformat(),
                sub.is_active,
                sub.consent_given,
                sub.ip_address or ""
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=newsletter_subscribers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    
    else:  # xlsx
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Newsletter Subscribers"
            
            # Write header
            ws.append(["Email", "Source", "Subscribed At", "Is Active", "Consent Given", "IP Address"])
            
            # Write data
            for sub in subscribers:
                ws.append([
                    sub.email,
                    sub.source,
                    sub.subscribed_at.isoformat(),
                    sub.is_active,
                    sub.consent_given,
                    sub.ip_address or ""
                ])
            
            # Save to bytes
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            return Response(
                content=output.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=newsletter_subscribers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                }
            )
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="XLSX export requires openpyxl package. Please install it or use CSV format."
            )


def unsubscribe_token(email: str) -> str:
    """Public token a subscriber can use to leave the list."""
    import hashlib
    import hmac
    from backend.core.config import settings
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), email.lower().encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{email}|{sig}"


def _email_from_token(token: str) -> Optional[str]:
    import hashlib
    import hmac
    from backend.core.config import settings
    if "|" not in token:
        return None
    email, sig = token.rsplit("|", 1)
    expected = hmac.new(settings.SECRET_KEY.encode("utf-8"), email.lower().encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return email


@router.get("/unsubscribe")
def unsubscribe(token: str = Query(...), db: Session = Depends(get_db)):
    """Public unsubscribe. The token is the address plus a signature."""
    email = _email_from_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid unsubscribe link")
    row = db.query(NewsletterSubscriberModel).filter(
        func.lower(NewsletterSubscriberModel.email) == email.lower()
    ).first()
    if row:
        row.is_active = False
        db.commit()
    return {"success": True, "message": "You are unsubscribed."}


@router.delete("/subscribers/{subscriber_id}")
def remove_subscriber(
    subscriber_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    row = db.query(NewsletterSubscriberModel).filter(NewsletterSubscriberModel.id == subscriber_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscriber not found")
    db.delete(row)
    db.commit()
    return {"success": True}

