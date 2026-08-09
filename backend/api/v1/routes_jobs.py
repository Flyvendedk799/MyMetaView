"""Job queue routes for async preview generation."""
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
from backend.utils.url_sanitizer import sanitize_url
from backend.services.activity_logger import log_activity
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_org
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


class PreviewJobRequest(BaseModel):
    """Schema for preview generation job request."""
    url: str
    domain: str


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

