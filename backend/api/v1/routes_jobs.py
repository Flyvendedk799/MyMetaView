"""Job queue routes for async preview generation."""
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from rq import Queue
from rq.job import Job
from backend.queue.queue_connection import get_rq_redis_connection
from backend.models.domain import Domain as DomainModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.core.paid_user import get_paid_user
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.jobs.preview_pipeline import generate_preview_job
from backend.jobs.bulk_preview_job import (
    generate_bulk_preview_job,
    get_bulk_batch_data,
    seed_batch,
    list_org_batches,
)
from backend.services.sitemap_discovery import discover_sitemap_urls
from backend.utils.url_sanitizer import sanitize_url
from backend.services.activity_logger import log_activity
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_org
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Cap on how many URLs one bulk run will accept, before quota trimming.
MAX_BULK_URLS = 50


class PreviewJobRequest(BaseModel):
    """Schema for preview generation job request."""
    url: str
    domain: str
    force: bool = False  # bypass cache to regenerate / re-roll an existing preview


class DiscoverUrlsRequest(BaseModel):
    """Request to discover a verified domain's page URLs from its sitemap."""
    domain: str


class BulkPreviewJobRequest(BaseModel):
    """Request to generate previews for many URLs on one verified domain."""
    domain: str
    urls: List[str]
    force: bool = False


class JobStatusResponse(BaseModel):
    """Schema for job status response."""
    status: str
    result: dict | None = None
    error: str | None = None


@router.post("/preview", status_code=status.HTTP_202_ACCEPTED)
def create_preview_job(
    request: PreviewJobRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_paid_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """
    Create a background job to generate AI preview (owner/admin/editor only).
    
    Returns job_id that can be used to poll for status.
    """
    # Rate limiting: 100 generations per hour per organization
    rate_limit_key = get_rate_limit_key_for_org(current_org.id)
    if not check_rate_limit(rate_limit_key, limit=100, window_seconds=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    # Validate domain ownership
    domain = db.query(DomainModel).filter(
        DomainModel.name == request.domain,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not found or not owned by this organization."
        )
    
    # Check domain verification
    if domain.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before generating previews."
        )

    # Enforce the plan's monthly preview quota
    from backend.core.plans import plan_limit
    from backend.models.preview import Preview as PreviewModel
    from datetime import datetime
    _pv_limit = plan_limit(current_org, "previews_month")
    if _pv_limit is not None:
        _month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _pv_count = db.query(PreviewModel).filter(
            PreviewModel.organization_id == current_org.id,
            PreviewModel.created_at >= _month_start,
        ).count()
        if _pv_count >= _pv_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"You've reached your plan's monthly limit of {_pv_limit} previews. Upgrade for more."
            )

    # Sanitize URL before enqueueing
    try:
        sanitized_url = sanitize_url(request.url, request.domain)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Enqueue job (pass organization_id to worker)
    try:
        redis_conn = get_rq_redis_connection()
        queue = Queue("preview_generation", connection=redis_conn)
        job = queue.enqueue(
            generate_preview_job,
            current_user.id,
            current_org.id,  # Pass organization_id
            sanitized_url,
            request.domain,
            request.force,  # force_regenerate: bypass cache on re-roll
            job_timeout='10m'  # 10 minute timeout for AI generation
        )
        
        # Log job enqueue
        log_activity(
            db,
            user_id=current_user.id,
            action="preview.ai_job.queued",
            metadata={"job_id": job.id, "url": sanitized_url, "domain": request.domain},
            request=http_request
        )
        
        return {"job_id": job.id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@router.post("/preview/discover")
def discover_domain_urls(
    request: DiscoverUrlsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Discover a verified domain's page URLs from its sitemap (for bulk coverage).

    Read-only — just reads the public sitemap. The URLs are returned for the user
    to review/trim before kicking off a bulk generation.
    """
    domain = db.query(DomainModel).filter(
        DomainModel.name == request.domain,
        DomainModel.organization_id == current_org.id,
    ).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not found or not owned by this organization.",
        )
    if domain.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before generating previews.",
        )
    try:
        urls = discover_sitemap_urls(request.domain, max_urls=200)
    except Exception as e:
        logger.error(f"Sitemap discovery failed for {request.domain}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not read the site's sitemap.",
        )
    return {"domain": request.domain, "count": len(urls), "urls": urls}


@router.post("/preview/bulk", status_code=status.HTTP_202_ACCEPTED)
def create_bulk_preview_job(
    request: BulkPreviewJobRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_paid_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Generate previews for many URLs on one verified domain (owner/admin/editor).

    Sanitises + de-dupes the URLs, trims to the plan's remaining monthly quota, and
    enqueues one background job that persists each preview. Returns a batch_id to poll.
    """
    rate_limit_key = get_rate_limit_key_for_org(current_org.id)
    if not check_rate_limit(rate_limit_key, limit=100, window_seconds=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )

    domain = db.query(DomainModel).filter(
        DomainModel.name == request.domain,
        DomainModel.organization_id == current_org.id,
    ).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not found or not owned by this organization.",
        )
    if domain.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before generating previews.",
        )

    # Sanitise + de-dupe; drop URLs that don't belong to this domain; cap the batch.
    seen: set[str] = set()
    clean_urls: List[str] = []
    for raw in request.urls:
        if not raw or not raw.strip():
            continue
        try:
            sanitized = sanitize_url(raw.strip(), request.domain)
        except ValueError:
            continue
        if sanitized in seen:
            continue
        seen.add(sanitized)
        clean_urls.append(sanitized)
        if len(clean_urls) >= MAX_BULK_URLS:
            break

    if not clean_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid URLs for this domain. Make sure the URLs are on the selected domain.",
        )

    # Trim to remaining monthly quota
    skipped_quota = 0
    from backend.core.plans import plan_limit
    from backend.models.preview import Preview as PreviewModel
    from datetime import datetime
    pv_limit = plan_limit(current_org, "previews_month")
    if pv_limit is not None:
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = db.query(PreviewModel).filter(
            PreviewModel.organization_id == current_org.id,
            PreviewModel.created_at >= month_start,
        ).count()
        remaining = max(0, pv_limit - used)
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"You've reached your plan's monthly limit of {pv_limit} previews. Upgrade for more.",
            )
        if len(clean_urls) > remaining:
            skipped_quota = len(clean_urls) - remaining
            clean_urls = clean_urls[:remaining]

    from datetime import datetime as _dt
    batch_id = str(uuid4())
    created_at = _dt.utcnow().isoformat()
    # Seed a 'queued' record + index it so the run is visible immediately (survives
    # tab close / reload) even before a bulk worker picks it up.
    seed_batch(batch_id, current_org.id, request.domain, len(clean_urls), created_at)
    try:
        redis_conn = get_rq_redis_connection()
        # Dedicated queue so a long bulk run can't block interactive previews.
        queue = Queue("bulk_generation", connection=redis_conn)
        queue.enqueue(
            generate_bulk_preview_job,
            batch_id,
            current_user.id,
            current_org.id,
            request.domain,
            clean_urls,
            request.force,
            created_at,
            job_timeout='2h',  # bulk runs many URLs sequentially
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bulk job: {str(e)}",
        )

    log_activity(
        db,
        user_id=current_user.id,
        action="preview.bulk_job.queued",
        metadata={"batch_id": batch_id, "domain": request.domain, "count": len(clean_urls)},
        request=http_request,
    )

    return {
        "batch_id": batch_id,
        "queued": len(clean_urls),
        "skipped_quota": skipped_quota,
        "domain": request.domain,
    }


@router.get("/bulk/recent")
def list_recent_bulk_jobs(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Recent bulk runs for the org (newest first) — powers a jobs view that works
    without keeping a tab open (resume in-progress runs, see recent ones)."""
    return {"batches": list_org_batches(current_org.id)}


@router.get("/bulk/{batch_id}/status")
def get_bulk_job_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll a bulk generation batch. Returns total/completed/failed + per-URL results."""
    data = get_bulk_batch_data(batch_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bulk job not found or expired.",
        )
    return data


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of a background job.
    
    Returns:
        - status: "queued", "started", "finished", or "failed"
        - result: Preview data if finished, None otherwise
        - error: Error message if failed, None otherwise
    """
    try:
        redis_conn = get_rq_redis_connection()
        job = Job.fetch(job_id, connection=redis_conn)
        
        # Check if job belongs to current user (security check)
        # We can't easily check this without inspecting job args, so we'll trust
        # that the job_id is secret enough. In production, you might want to store
        # user_id with the job metadata.
        
        status_map = {
            'queued': 'queued',
            'started': 'started',
            'finished': 'finished',
            'failed': 'failed',
        }
        
        job_status = status_map.get(job.get_status(), 'unknown')
        
        result = None
        error = None
        
        if job_status == 'finished':
            try:
                result = job.result
            except Exception as result_error:
                # Handle cases where result can't be deserialized
                logger.error(f"Failed to deserialize job result for {job_id}: {result_error}")
                error = "Job completed but result could not be retrieved"
                job_status = 'failed'
        elif job_status == 'failed':
            try:
                error = str(job.exc_info) if job.exc_info else "Job failed"
            except Exception:
                error = "Job failed (error details unavailable)"
        
        return JobStatusResponse(
            status=job_status,
            result=result,
            error=error
        )
    except Exception as e:
        # Job not found or other error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {str(e)}"
        )

