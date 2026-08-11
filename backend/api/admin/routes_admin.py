"""Admin routes for system-wide management."""
from datetime import datetime, timedelta, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from backend.db.session import get_db
from backend.core.deps import get_admin_user
from backend.models.user import User
from backend.models.domain import Domain
from backend.models.preview import Preview
from backend.models.preview_variant import PreviewVariant
from backend.models.error import Error
from backend.models.analytics_event import AnalyticsEvent
from backend.models.preview_job_failure import PreviewJobFailure
from backend.queue.queue_connection import get_redis_connection, get_rq_redis_connection
from backend.services.activity_logger import log_activity
from backend.jobs.analytics_aggregation import aggregate_daily_analytics
from rq import Queue

router = APIRouter(prefix="/admin", tags=["admin"])


# Response schemas
class AdminUserSummary(BaseModel):
    """Summary of user for admin list."""
    id: int
    email: str
    is_active: bool
    subscription_status: str
    subscription_plan: Optional[str]
    created_at: str
    domains_count: int
    previews_count: int


class AdminUserDetail(BaseModel):
    """Detailed user profile for admin."""
    id: int
    email: str
    is_active: bool
    is_admin: bool
    subscription_status: str
    subscription_plan: Optional[str]
    trial_ends_at: Optional[str]
    created_at: str
    domains_count: int
    previews_count: int
    total_clicks: int
    stripe_customer_id: Optional[str]


class AdminDomain(BaseModel):
    """Domain info for admin."""
    id: int
    name: str
    environment: str
    status: str
    verification_method: Optional[str]
    verified_at: Optional[str]
    user_email: str
    user_id: int
    created_at: str
    monthly_clicks: int


class AdminPreview(BaseModel):
    """Preview info for admin."""
    id: int
    url: str
    domain: str
    title: str
    type: str
    user_email: str
    user_id: int
    created_at: str
    monthly_clicks: int


class SystemOverview(BaseModel):
    """System overview metrics."""
    total_users: int
    active_subscribers: int
    total_domains: int
    verified_domains: int
    previews_generated_24h: int
    jobs_running: int
    errors_past_24h: int
    redis_queue_length: int


class AdminAnalyticsOverview(BaseModel):
    """Admin analytics overview."""
    total_users: int
    active_subscribers: int
    total_domains: int
    total_previews: int
    total_impressions_24h: int
    total_clicks_24h: int
    total_impressions_30d: int
    total_clicks_30d: int


class AdminAnalyticsUserItem(BaseModel):
    """Admin analytics user item."""
    user_id: int
    email: str
    impressions_30d: int
    clicks_30d: int
    active_domains: int
    active_previews: int


@router.get("/users", response_model=List[AdminUserSummary])
def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get all users with summary information."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    
    result = []
    for user in users:
        domains_count = db.query(func.count(Domain.id)).filter(
            Domain.user_id == user.id
        ).scalar() or 0
        
        previews_count = db.query(func.count(Preview.id)).filter(
            Preview.user_id == user.id
        ).scalar() or 0
        
        result.append(AdminUserSummary(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            subscription_status=user.subscription_status,
            subscription_plan=user.subscription_plan,
            created_at=user.created_at.isoformat(),
            domains_count=domains_count,
            previews_count=previews_count
        ))
    
    return result


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get full user profile with activity summary."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    domains_count = db.query(func.count(Domain.id)).filter(
        Domain.user_id == user.id
    ).scalar() or 0
    
    previews_count = db.query(func.count(Preview.id)).filter(
        Preview.user_id == user.id
    ).scalar() or 0
    
    total_clicks = db.query(func.sum(Preview.monthly_clicks)).filter(
        Preview.user_id == user.id
    ).scalar() or 0
    
    return AdminUserDetail(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        subscription_status=user.subscription_status,
        subscription_plan=user.subscription_plan,
        trial_ends_at=user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        created_at=user.created_at.isoformat(),
        domains_count=domains_count,
        previews_count=previews_count,
        total_clicks=int(total_clicks),
        stripe_customer_id=user.stripe_customer_id
    )


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Activate or deactivate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    old_status = user.is_active
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    
    # Log admin action
    log_activity(
        db,
        user_id=admin_user.id,
        action="admin.user.toggled",
        metadata={"target_user_id": user_id, "target_email": user.email, "old_status": old_status, "new_status": user.is_active},
        request=request
    )
    
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": f"User {'activated' if user.is_active else 'deactivated'}"
    }


@router.get("/domains", response_model=List[AdminDomain])
def list_domains(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get all domains across the system."""
    # Optimize: Use joinedload to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    domains = db.query(Domain).options(
        joinedload(Domain.user)
    ).join(User, Domain.user_id == User.id).order_by(Domain.created_at.desc()).all()
    
    result = []
    for domain in domains:
        result.append(AdminDomain(
            id=domain.id,
            name=domain.name,
            environment=domain.environment,
            status=domain.status,
            verification_method=domain.verification_method,
            verified_at=domain.verified_at.isoformat() if domain.verified_at else None,
            user_email=domain.user.email if domain.user else "Unknown",
            user_id=domain.user_id,
            created_at=domain.created_at.isoformat(),
            monthly_clicks=domain.monthly_clicks
        ))
    
    return result


@router.delete("/domains/{domain_id}")
def delete_domain(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Force delete any domain in the system."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    domain_name = domain.name
    domain_owner_id = domain.user_id
    db.delete(domain)
    db.commit()
    
    # Log admin action
    log_activity(
        db,
        user_id=admin_user.id,
        action="admin.domain.deleted",
        metadata={"domain_id": domain_id, "domain_name": domain_name, "owner_user_id": domain_owner_id},
        request=request
    )
    
    return {"message": f"Domain {domain_name} deleted successfully"}


@router.get("/previews", response_model=List[AdminPreview])
def list_previews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get latest previews from all users with pagination."""
    # Optimize: Use joinedload to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    previews = db.query(Preview).options(
        joinedload(Preview.user)
    ).join(User, Preview.user_id == User.id).order_by(
        desc(Preview.created_at)
    ).offset(skip).limit(limit).all()
    
    result = []
    for preview in previews:
        result.append(AdminPreview(
            id=preview.id,
            url=preview.url,
            domain=preview.domain,
            title=preview.title,
            type=preview.type,
            user_email=preview.user.email if preview.user else "Unknown",
            user_id=preview.user_id,
            created_at=preview.created_at.isoformat(),
            monthly_clicks=preview.monthly_clicks
        ))
    
    return result


@router.delete("/previews/{preview_id}")
def delete_preview(
    preview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Moderation delete of a preview."""
    preview = db.query(Preview).filter(Preview.id == preview_id).first()
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not found"
        )
    
    preview_title = preview.title
    preview_url = preview.url
    preview_owner_id = preview.user_id
    db.delete(preview)
    db.commit()
    
    # Log admin action
    log_activity(
        db,
        user_id=admin_user.id,
        action="admin.preview.deleted",
        metadata={"preview_id": preview_id, "preview_title": preview_title, "preview_url": preview_url, "owner_user_id": preview_owner_id},
        request=request
    )
    
    return {"message": f"Preview {preview_title} deleted successfully"}


@router.get("/previews/{preview_id}/variants")
def list_preview_variants(
    preview_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all variants for a preview (admin only)."""
    preview = db.query(Preview).filter(Preview.id == preview_id).first()
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not found"
        )
    
    variants = db.query(PreviewVariant).filter(
        PreviewVariant.preview_id == preview_id
    ).all()
    
    return [
        {
            "id": v.id,
            "preview_id": v.preview_id,
            "variant_key": v.variant_key,
            "title": v.title,
            "description": v.description,
            "tone": v.tone,
            "keywords": v.keywords,
            "image_url": v.image_url,
            "created_at": v.created_at.isoformat()
        }
        for v in variants
    ]


@router.delete("/preview-variants/{variant_id}")
def delete_preview_variant(
    variant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Delete a preview variant (admin only)."""
    variant = db.query(PreviewVariant).filter(PreviewVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found"
        )
    
    variant_key = variant.variant_key
    preview_id = variant.preview_id
    db.delete(variant)
    db.commit()
    
    # Log admin action
    log_activity(
        db,
        user_id=admin_user.id,
        action="admin.preview_variant.deleted",
        metadata={"variant_id": variant_id, "preview_id": preview_id, "variant_key": variant_key},
        request=request
    )
    
    return {"message": f"Variant {variant_key} deleted successfully"}


@router.get("/system/overview", response_model=SystemOverview)
def get_system_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get system-wide overview metrics."""
    # Total users
    total_users = db.query(func.count(User.id)).scalar() or 0
    
    # Active subscribers (subscriptions are organization-level)
    from backend.models.organization import Organization as OrgModel
    active_subscribers = db.query(func.count(OrgModel.id)).filter(
        OrgModel.subscription_status.in_(['active', 'trialing'])
    ).scalar() or 0
    
    # Total domains
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    
    # Verified domains
    verified_domains = db.query(func.count(Domain.id)).filter(
        Domain.verified_at.isnot(None)
    ).scalar() or 0
    
    # Previews generated in last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    previews_generated_24h = db.query(func.count(Preview.id)).filter(
        Preview.created_at >= twenty_four_hours_ago
    ).scalar() or 0
    
    # Jobs running (stub - would need actual job tracking)
    jobs_running = 0  # TODO: Implement actual job tracking
    
    # Errors in past 24 hours
    errors_past_24h = db.query(func.count(Error.id)).filter(
        Error.timestamp >= twenty_four_hours_ago
    ).scalar() or 0
    
    # Redis queue length
    redis_queue_length = 0
    try:
        redis_conn = get_rq_redis_connection()
        if redis_conn:
            # RQ stores jobs in 'rq:queue:preview_generation' key
            queue_key = 'rq:queue:preview_generation'
            redis_queue_length = redis_conn.llen(queue_key) or 0
    except Exception:
        pass  # Redis not available or error
    
    return SystemOverview(
        total_users=total_users,
        active_subscribers=active_subscribers,
        total_domains=total_domains,
        verified_domains=verified_domains,
        previews_generated_24h=previews_generated_24h,
        jobs_running=jobs_running,
        errors_past_24h=errors_past_24h,
        redis_queue_length=redis_queue_length
    )


@router.get("/analytics/overview", response_model=AdminAnalyticsOverview)
def get_admin_analytics_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get admin analytics overview."""
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Total users
    total_users = db.query(func.count(User.id)).scalar() or 0
    
    # Active subscribers (subscriptions are organization-level)
    from backend.models.organization import Organization as OrgModel
    active_subscribers = db.query(func.count(OrgModel.id)).filter(
        OrgModel.subscription_status.in_(['active', 'trialing'])
    ).scalar() or 0
    
    # Total domains
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    
    # Total previews
    total_previews = db.query(func.count(Preview.id)).scalar() or 0
    
    # Impressions 24h
    total_impressions_24h = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_type == "impression",
        AnalyticsEvent.created_at >= twenty_four_hours_ago
    ).scalar() or 0
    
    # Clicks 24h
    total_clicks_24h = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_type == "click",
        AnalyticsEvent.created_at >= twenty_four_hours_ago
    ).scalar() or 0
    
    # Impressions 30d
    total_impressions_30d = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_type == "impression",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).scalar() or 0
    
    # Clicks 30d
    total_clicks_30d = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_type == "click",
        AnalyticsEvent.created_at >= thirty_days_ago
    ).scalar() or 0
    
    return AdminAnalyticsOverview(
        total_users=total_users,
        active_subscribers=active_subscribers,
        total_domains=total_domains,
        total_previews=total_previews,
        total_impressions_24h=total_impressions_24h,
        total_clicks_24h=total_clicks_24h,
        total_impressions_30d=total_impressions_30d,
        total_clicks_30d=total_clicks_30d
    )


@router.get("/analytics/users", response_model=List[AdminAnalyticsUserItem])
def get_admin_analytics_users(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get top users by analytics usage."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get all users
    users = db.query(User).all()
    
    result = []
    for user in users:
        # Impressions 30d
        impressions_30d = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.user_id == user.id,
            AnalyticsEvent.event_type == "impression",
            AnalyticsEvent.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Clicks 30d
        clicks_30d = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.user_id == user.id,
            AnalyticsEvent.event_type == "click",
            AnalyticsEvent.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Active domains (domains with events in last 30 days)
        active_domains = db.query(func.count(func.distinct(AnalyticsEvent.domain_id))).filter(
            AnalyticsEvent.user_id == user.id,
            AnalyticsEvent.created_at >= thirty_days_ago,
            AnalyticsEvent.domain_id.isnot(None)
        ).scalar() or 0
        
        # Active previews (previews with events in last 30 days)
        active_previews = db.query(func.count(func.distinct(AnalyticsEvent.preview_id))).filter(
            AnalyticsEvent.user_id == user.id,
            AnalyticsEvent.created_at >= thirty_days_ago,
            AnalyticsEvent.preview_id.isnot(None)
        ).scalar() or 0
        
        result.append(AdminAnalyticsUserItem(
            user_id=user.id,
            email=user.email,
            impressions_30d=impressions_30d,
            clicks_30d=clicks_30d,
            active_domains=active_domains,
            active_previews=active_previews
        ))
    
    # Sort by impressions descending and limit
    result.sort(key=lambda x: x.impressions_30d, reverse=True)
    return result[:limit]


@router.post("/analytics/aggregate")
def trigger_analytics_aggregation(
    target_date: Optional[str] = Query(None, description="Date to aggregate (YYYY-MM-DD), defaults to yesterday"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Trigger analytics aggregation job for a specific date."""
    try:
        aggregation_date = None
        if target_date:
            aggregation_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        result = aggregate_daily_analytics(aggregation_date)
        
        return {
            "status": "success",
            "message": f"Aggregation completed for {result['date']}",
            "result": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate analytics: {str(e)}"
        )


class WorkerHealthResponse(BaseModel):
    """Worker health response."""
    main_queue_length: int
    dlq_length: int
    recent_failures_count: int
    last_successful_job_at: Optional[str]
    last_failure_at: Optional[str]
    playwright_available: bool


def check_playwright_installed():
    """Check if Playwright Chromium is installed."""
    import subprocess
    try:
        subprocess.run(
            ["playwright", "install", "chromium", "--dry-run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return True
    except Exception:
        return False


@router.get("/system/worker-health", response_model=WorkerHealthResponse)
def get_worker_health(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get worker health metrics (admin only)."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        redis_conn = get_rq_redis_connection()
        
        # Main queue length
        queue = Queue('preview_generation', connection=redis_conn)
        main_queue_length = len(queue)
        
        # DLQ length (from database)
        dlq_length = db.query(func.count(PreviewJobFailure.id)).scalar() or 0
        
        # Recent failures (last 24 hours)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_failures_count = db.query(func.count(PreviewJobFailure.id)).filter(
            PreviewJobFailure.created_at >= twenty_four_hours_ago
        ).scalar() or 0
        
        # Last successful job (from previews table)
        # Handle missing composited_image_url column gracefully
        try:
            last_preview = db.query(Preview).order_by(desc(Preview.created_at)).first()
            last_successful_job_at = last_preview.created_at.isoformat() if last_preview else None
        except Exception as e:
            # If column doesn't exist, query without it
            logger.warning(f"Error querying previews (possibly missing column): {e}")
            # Try querying with explicit columns
            from sqlalchemy import select
            from backend.models.preview import Preview
            try:
                # Select only columns that definitely exist
                result = db.execute(
                    select(
                        Preview.id,
                        Preview.created_at
                    ).order_by(desc(Preview.created_at)).limit(1)
                ).first()
                last_successful_job_at = result.created_at.isoformat() if result else None
            except Exception as e2:
                logger.error(f"Failed to query previews: {e2}")
                last_successful_job_at = None
        
        # Last failure
        last_failure = db.query(PreviewJobFailure).order_by(desc(PreviewJobFailure.created_at)).first()
        last_failure_at = last_failure.created_at.isoformat() if last_failure else None
        
        # Check Playwright availability
        playwright_available = check_playwright_installed()
        
    except Exception as e:
        # Fallback if Redis or DB unavailable
        logger.error(f"Error getting worker health: {e}", exc_info=True)
        return WorkerHealthResponse(
            main_queue_length=0,
            dlq_length=0,
            recent_failures_count=0,
            last_successful_job_at=None,
            last_failure_at=None,
            playwright_available=False
        )
    
    return WorkerHealthResponse(
        main_queue_length=main_queue_length,
        dlq_length=dlq_length,
        recent_failures_count=recent_failures_count,
        last_successful_job_at=last_successful_job_at,
        last_failure_at=last_failure_at,
        playwright_available=playwright_available
    )


@router.get("/errors")
def list_errors(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List recent errors (admin only)."""
    import json
    errors = db.query(Error).order_by(
        desc(Error.timestamp)
    ).offset(skip).limit(limit).all()
    
    result = []
    for err in errors:
        details = {}
        if err.details:
            try:
                details = json.loads(err.details)
            except:
                details = {"raw": err.details}
        
        result.append({
            "id": err.id,
            "path": details.get("path", ""),
            "method": details.get("method", ""),
            "user_id": details.get("user_id"),
            "organization_id": details.get("organization_id"),
            "error_message": err.message,
            "stacktrace": details.get("stacktrace"),
            "request_id": details.get("request_id"),
            "timestamp": err.timestamp.isoformat(),
        })
    
    return result


class DeploymentResponse(BaseModel):
    """Deployment response."""
    success: bool
    message: str
    output: Optional[str] = None
    branch_merged: Optional[str] = None


@router.post("/deploy/merge-claude-branch", response_model=DeploymentResponse)
def deploy_merge_claude_branch(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Merge latest claude branch into main and push to trigger Railway deployment.
    
    Uses GitHub API if available, otherwise falls back to git commands.
    Railway runtime containers typically don't have git, so GitHub API is preferred.
    """
    import subprocess
    import logging
    import re
    import shutil
    import os
    import requests
    
    logger = logging.getLogger(__name__)
    
    def find_git():
        """Find git executable path."""
        # Try to find git in PATH
        git_path = shutil.which("git")
        if git_path:
            return git_path
        
        # Try common paths on Linux/Unix
        common_paths = ["/usr/bin/git", "/usr/local/bin/git", "/bin/git"]
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        # Try to find git in common installation locations
        # On Railway, git is usually in /usr/bin/git
        return "git"  # Fallback to just "git" and let subprocess handle the error

    # Collected progress lines returned to the admin UI. Must be bound before
    # the try block — it previously sat unreachable inside find_git(), so every
    # call died with NameError on the first append.
    output_lines = []

    try:
        # Log admin action
        log_activity(
            db,
            user_id=admin_user.id,
            action="admin.deployment.triggered",
            metadata={"action": "merge_claude_branch"},
            request=request
        )
        
        # Try GitHub API first (preferred for Railway)
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPO", "Flyvendedk799/preview")  # Default to your repo
        
        if not github_token:
            # No GitHub token - provide helpful instructions
            return DeploymentResponse(
                success=False,
                message="GitHub API token not configured. To enable remote deployment, please set the GITHUB_TOKEN environment variable in Railway. Go to Railway Dashboard → Your Service → Variables → Add GITHUB_TOKEN with a GitHub Personal Access Token (repo scope).",
                output="GitHub token not found. Git is not available in Railway runtime containers."
            )
        
        if github_token:
            logger.info("Attempting to use GitHub API for merge")
            output_lines.append("Using GitHub API for merge")
            
            try:
                # Get list of branches
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                # Get all branches
                branches_url = f"https://api.github.com/repos/{github_repo}/branches"
                branches_response = requests.get(branches_url, headers=headers, timeout=10)
                
                if branches_response.status_code != 200:
                    raise Exception(f"Failed to fetch branches: {branches_response.text}")
                
                branches = branches_response.json()
                claude_branches = [b for b in branches if b["name"].startswith("claude/")]
                
                if not claude_branches:
                    return DeploymentResponse(
                        success=False,
                        message="No claude branches found to merge",
                        output="\n".join(output_lines)
                    )
                
                # Sort by commit date (most recent first)
                claude_branches.sort(key=lambda b: b["commit"]["commit"]["committer"]["date"], reverse=True)
                latest_branch = claude_branches[0]["name"]
                output_lines.append(f"Found latest claude branch: {latest_branch}")
                
                # Create a merge via GitHub API
                merge_url = f"https://api.github.com/repos/{github_repo}/merges"
                merge_data = {
                    "base": "main",
                    "head": latest_branch,
                    "commit_message": f"Merge {latest_branch} into main via admin dashboard"
                }
                
                merge_response = requests.post(merge_url, json=merge_data, headers=headers, timeout=30)
                
                if merge_response.status_code == 201:
                    # Merge successful
                    output_lines.append(f"Successfully merged {latest_branch} into main via GitHub API")
                    return DeploymentResponse(
                        success=True,
                        message=f"Successfully merged {latest_branch} into main. Railway will automatically redeploy.",
                        output="\n".join(output_lines),
                        branch_merged=latest_branch
                    )
                elif merge_response.status_code == 409:
                    # Merge conflict or already merged
                    error_data = merge_response.json()
                    return DeploymentResponse(
                        success=False,
                        message=f"Merge conflict or branch already merged: {error_data.get('message', 'Unknown error')}",
                        output="\n".join(output_lines),
                        branch_merged=latest_branch
                    )
                else:
                    raise Exception(f"GitHub API merge failed: {merge_response.status_code} - {merge_response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"GitHub API failed, falling back to git: {e}")
                output_lines.append(f"GitHub API failed: {str(e)}, trying git fallback...")
                # Fall through to git method
        
        # Fallback to git commands
        logger.info("Using git commands for merge")
        output_lines.append("Using git commands (GitHub API not available)")
        
        # Find git executable
        git_cmd = find_git()
        logger.info(f"Using git at: {git_cmd}")
        
        # Verify git is available
        try:
            check_result = subprocess.run(
                [git_cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if check_result.returncode != 0:
                raise Exception(f"Git not available: {check_result.stderr}")
        except FileNotFoundError:
            raise Exception(
                "Git executable not found and GitHub API not configured. "
                "Please set GITHUB_TOKEN environment variable or ensure git is installed."
            )
        except Exception as e:
            raise Exception(f"Failed to verify git: {str(e)}")
        
        output_lines.append(f"Using git: {git_cmd}")
        
        # Check if we're in a git repository
        check_repo_result = subprocess.run(
            [git_cmd, "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd="."
        )
        if check_repo_result.returncode != 0:
            raise Exception(
                "Not in a git repository. Railway runtime containers typically don't have git access. "
                "Please set GITHUB_TOKEN environment variable to use GitHub API, or merge branches manually via GitHub."
            )
        
        # Get current working directory
        cwd = os.getcwd()
        output_lines.append(f"Working directory: {cwd}")
        
        # Step 1: Fetch latest changes from remote
        logger.info("Fetching latest changes from remote...")
        try:
            fetch_result = subprocess.run(
                [git_cmd, "fetch", "origin"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd="."
            )
            output_lines.append(f"Fetch stdout: {fetch_result.stdout}")
            if fetch_result.stderr:
                output_lines.append(f"Fetch stderr: {fetch_result.stderr}")
            
            if fetch_result.returncode != 0:
                raise Exception(f"Git fetch failed: {fetch_result.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Git fetch timed out after 30 seconds")
        except Exception as e:
            raise Exception(f"Git fetch error: {str(e)}")
        
        # Step 2: Get list of remote branches and find latest claude branch
        branch_result = subprocess.run(
            [git_cmd, "branch", "-r"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="."
        )
        
        if branch_result.returncode != 0:
            raise Exception(f"Failed to list branches: {branch_result.stderr}")
        
        # Find claude branches (pattern: origin/claude/*)
        claude_branches = []
        for line in branch_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('origin/claude/'):
                claude_branches.append(line)
        
        if not claude_branches:
            return DeploymentResponse(
                success=False,
                message="No claude branches found to merge",
                output="\n".join(output_lines)
            )
        
        # Sort branches to get the latest one (assuming they have timestamps or are sorted by creation)
        # Get the most recent one by checking commit dates
        latest_branch = None
        latest_date = None
        
        for branch in claude_branches:
            branch_name = branch.replace('origin/', '')
            date_result = subprocess.run(
                [git_cmd, "log", "-1", "--format=%ct", branch],
                capture_output=True,
                text=True,
                timeout=10,
                cwd="."
            )
            if date_result.returncode == 0 and date_result.stdout.strip():
                commit_date = int(date_result.stdout.strip())
                if latest_date is None or commit_date > latest_date:
                    latest_date = commit_date
                    latest_branch = branch_name
        
        if not latest_branch:
            # Fallback: use the first claude branch
            latest_branch = claude_branches[0].replace('origin/', '')
        
        output_lines.append(f"Found latest claude branch: {latest_branch}")
        
        # Step 3: Checkout main and ensure it's up to date
        checkout_result = subprocess.run(
            [git_cmd, "checkout", "main"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="."
        )
        output_lines.append(f"Checkout main: {checkout_result.stdout}")
        if checkout_result.stderr:
            output_lines.append(f"Checkout stderr: {checkout_result.stderr}")
        
        # Step 4: Merge the claude branch
        logger.info(f"Merging {latest_branch} into main...")
        merge_result = subprocess.run(
            [git_cmd, "merge", f"origin/{latest_branch}", "--no-edit"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd="."
        )
        output_lines.append(f"Merge: {merge_result.stdout}")
        if merge_result.stderr:
            output_lines.append(f"Merge stderr: {merge_result.stderr}")
        
        if merge_result.returncode != 0:
            # Check if it's a merge conflict or other error
            if "CONFLICT" in merge_result.stdout or "conflict" in merge_result.stdout.lower():
                return DeploymentResponse(
                    success=False,
                    message=f"Merge conflict detected. Manual resolution required.",
                    output="\n".join(output_lines),
                    branch_merged=latest_branch
                )
            else:
                raise Exception(f"Git merge failed: {merge_result.stderr}")
        
        # Step 5: Push to origin/main
        logger.info("Pushing to origin/main...")
        push_result = subprocess.run(
            [git_cmd, "push", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="."
        )
        output_lines.append(f"Push: {push_result.stdout}")
        if push_result.stderr:
            output_lines.append(f"Push stderr: {push_result.stderr}")
        
        if push_result.returncode != 0:
            raise Exception(f"Git push failed: {push_result.stderr}")
        
        return DeploymentResponse(
            success=True,
            message=f"Successfully merged {latest_branch} into main and pushed to trigger Railway deployment",
            output="\n".join(output_lines),
            branch_merged=latest_branch
        )
        
    except subprocess.TimeoutExpired as e:
        logger.error("Git operation timed out", exc_info=True)
        return DeploymentResponse(
            success=False,
            message="Git operation timed out. Railway runtime containers may not have git access. Please merge branches manually via GitHub.",
            output="\n".join(output_lines) if output_lines else "No output available"
        )
    except FileNotFoundError as e:
        logger.error(f"Git not found: {e}", exc_info=True)
        return DeploymentResponse(
            success=False,
            message="Git is not available in the Railway runtime environment. Railway containers typically don't include git. Please merge branches manually via GitHub or use Railway's GitHub integration.",
            output="\n".join(output_lines) if output_lines else f"Error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Deployment failed: {error_msg}", exc_info=True)
        
        # Provide helpful error messages for common issues
        if "not a git repository" in error_msg.lower() or "not in a git repository" in error_msg.lower():
            helpful_msg = "Railway runtime containers don't have git repository access. Please merge branches manually via GitHub."
        elif "git" in error_msg.lower() and "not found" in error_msg.lower():
            helpful_msg = "Git is not installed in the Railway runtime. Please merge branches manually via GitHub."
        else:
            helpful_msg = f"Deployment failed: {error_msg}"
        
        return DeploymentResponse(
            success=False,
            message=helpful_msg,
            output="\n".join(output_lines) if output_lines else f"Error details: {error_msg}"
        )


# =============================================================================
# ADMIN SETTINGS: DEMO CACHE CONTROL
# =============================================================================

class DemoCacheDisabledResponse(BaseModel):
    """Response for demo cache disabled setting."""
    disabled: bool


@router.get("/settings/demo-cache-disabled", response_model=DemoCacheDisabledResponse)
def get_demo_cache_disabled(
    admin_user: User = Depends(get_admin_user)
):
    """Get current demo cache disabled setting."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from backend.services.preview_cache import get_redis_client
        redis_client = get_redis_client()
        if redis_client is None:
            logger.warning("Redis not available, returning default (cache enabled)")
            return DemoCacheDisabledResponse(disabled=False)
        
        key = "admin:settings:demo_cache_disabled"
        value = redis_client.get(key)
        disabled = value is not None and str(value).lower() == "true"
        
        logger.info(f"Retrieved demo cache disabled setting: key={key}, raw_value={value}, disabled={disabled}")
        return DemoCacheDisabledResponse(disabled=disabled)
    except Exception as e:
        logger.error(f"Failed to get demo cache disabled setting: {e}", exc_info=True)
        return DemoCacheDisabledResponse(disabled=False)


class DemoCacheDisabledUpdate(BaseModel):
    """Request to update demo cache disabled setting."""
    disabled: bool


@router.post("/settings/demo-cache-disabled", response_model=DemoCacheDisabledResponse)
def set_demo_cache_disabled(
    update: DemoCacheDisabledUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Update demo cache disabled setting."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from backend.services.preview_cache import get_redis_client
        redis_client = get_redis_client()
        if redis_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is not available"
            )
        
        key = "admin:settings:demo_cache_disabled"
        value = "true" if update.disabled else "false"
        
        logger.info(f"Setting demo cache disabled: key={key}, value={value}, disabled={update.disabled}")
        
        # Store setting (no expiration - persistent)
        redis_client.set(key, value)
        
        # Small delay to ensure write is complete
        import time
        time.sleep(0.1)
        
        # Verify the value was saved
        saved_value = redis_client.get(key)
        logger.info(f"Verification: saved_value={saved_value}, expected={value}, match={saved_value == value}")
        
        if saved_value != value:
            logger.error(f"Failed to verify saved value. Expected: {value}, Got: {saved_value}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify setting was saved. Expected: {value}, Got: {saved_value}"
            )
        
        # Log admin action
        log_activity(
            db=db,
            user_id=admin_user.id,
            action="admin.settings.demo_cache_disabled",
            metadata={"disabled": update.disabled},
            request=request
        )
        
        logger.info(f"Demo cache disabled setting updated to: {update.disabled} by admin {admin_user.email} (verified in Redis)")
        
        return DemoCacheDisabledResponse(disabled=update.disabled)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update demo cache disabled setting: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update setting: {str(e)}"
        )


# =============================================================================
# CACHE INVALIDATION
# =============================================================================

class CacheInvalidateRequest(BaseModel):
    """Request to invalidate cache for a URL."""
    url: str


class CacheInvalidateResponse(BaseModel):
    """Response for cache invalidation."""
    success: bool
    message: str


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
def invalidate_url_cache(
    request_body: CacheInvalidateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Invalidate all cache entries for a specific URL.
    
    Use this to force regeneration of a preview.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from backend.services.preview_cache import invalidate_cache
        
        url = request_body.url
        logger.info(f"Admin {admin_user.email} invalidating cache for: {url}")
        
        success = invalidate_cache(url)
        
        if success:
            # Log admin action
            log_admin_action(
                db,
                admin_user.id,
                action="admin.cache.invalidate",
                details={"url": url},
                ip_address=request.client.host
            )
            return CacheInvalidateResponse(
                success=True,
                message=f"Cache invalidated for {url}"
            )
        else:
            return CacheInvalidateResponse(
                success=False,
                message="Redis not available or invalidation failed"
            )
    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache invalidation failed: {str(e)}"
        )


@router.post("/cache/clear-all-demo")
def clear_all_demo_cache(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Clear ALL demo cache entries.
    
    WARNING: This clears all cached demo previews.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from backend.services.preview_cache import get_redis_client
        redis_client = get_redis_client()
        
        if redis_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is not available"
            )
        
        # Find and delete all demo cache keys
        patterns = ["demo:preview:*", "demo:preview:v2:*"]
        total_deleted = 0
        
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted = redis_client.delete(*keys)
                    total_deleted += deleted
                if cursor == 0:
                    break
        
        logger.info(f"Admin {admin_user.email} cleared {total_deleted} demo cache entries")
        
        # Log admin action
        log_admin_action(
            db,
            admin_user.id,
            action="admin.cache.clear_all_demo",
            details={"deleted_count": total_deleted},
            ip_address=request.client.host
        )
        
        return {"success": True, "deleted_count": total_deleted}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear demo cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear demo cache: {str(e)}"
        )