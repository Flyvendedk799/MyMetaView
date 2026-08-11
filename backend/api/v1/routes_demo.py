"""Demo/landing page routes for marketing campaigns.

DEPRECATED: /demo/preview is deprecated. Use /demo-v2/jobs for new integrations.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from backend.db.session import get_db
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip
from backend.services.activity_logger import get_client_ip, log_activity, get_authenticated_user_id
from backend.utils.url_sanitizer import validate_url_security
from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig
from backend.services.preview_cache import (
    generate_cache_key,
    get_redis_client,
    CacheConfig,
    is_demo_cache_disabled
)
from backend.schemas.demo_schemas import (
    DemoPreviewRequest,
    ContextItem,
    CredibilityItem,
    BrandElements,
    LayoutBlueprint,
)
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoPreviewResponse(BaseModel):
    """Legacy demo preview response - kept for backward compatibility with /demo endpoint."""
    url: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    context_items: List[ContextItem] = []
    credibility_items: List[CredibilityItem] = []
    cta_text: Optional[str] = None
    primary_image_base64: Optional[str] = None
    screenshot_url: Optional[str] = None
    composited_preview_image_url: Optional[str] = None
    brand: Optional[BrandElements] = None
    blueprint: LayoutBlueprint
    reasoning_confidence: float
    processing_time_ms: int
    quality_scores: Optional[Dict[str, Any]] = None
    is_fallback: bool = False
    is_demo: bool = True
    message: str = "AI-reconstructed preview using multi-stage reasoning."


@router.post(
    "/preview",
    response_model=DemoPreviewResponse,
    deprecated=True,
    summary="[DEPRECATED] Use POST /api/v1/demo-v2/jobs instead",
)
def generate_demo_preview(
    request_data: DemoPreviewRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    [DEPRECATED] Use POST /api/v1/demo-v2/jobs for new integrations.
    This sync endpoint can hit Railway's 60s timeout. Job flow provides progress and reliability.

    Generate a premium-quality preview using multi-stage reasoning.
    
    The system follows a rigorous 6-stage process:
    1. SEGMENTATION: Identify distinct UI regions
    2. PURPOSE ANALYSIS: Determine each region's communication role
    3. PRIORITY ASSIGNMENT: Rank by visual importance
    4. COMPOSITION DECISION: What to keep, reorder, or remove
    5. LAYOUT SYNTHESIS: Generate optimized structure
    6. COHERENCE CHECK: Validate balance and flow
    
    IMPROVEMENT: Added caching for repeated URLs to improve performance.
    Rate limited to prevent abuse.
    """
    url_str = str(request_data.url)
    redis_client = None
    cache_key = None
    user_id = get_authenticated_user_id(request, db)
    client_ip = get_client_ip(request)

    # Check if demo caching is disabled via admin toggle
    cache_disabled = is_demo_cache_disabled()

    if cache_disabled:
        logger.info(f"Cache DISABLED - generating fresh preview for: {url_str[:50]}...")
        from backend.services.preview_cache import invalidate_cache
        invalidate_cache(url_str)
    else:
        logger.info(f"Cache ENABLED - checking cache first for: {url_str[:50]}...")
        redis_client = get_redis_client()
        cache_key = generate_cache_key(url_str, "demo:preview:")

        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for demo preview: {url_str[:50]}...")
                    return DemoPreviewResponse(**json.loads(cached_data))
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

    # Rate limiting: 10 previews per hour per IP
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "demo_preview")
    if not check_rate_limit(rate_limit_key, limit=10, window_seconds=3600):
        log_activity(db, user_id=user_id, action="demo.preview.completed", request=request,
                     metadata={"url": url_str, "outcome": "rate_limited", "client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )

    # Validate URL security
    try:
        validate_url_security(url_str)
    except ValueError as e:
        log_activity(db, user_id=user_id, action="demo.preview.completed", request=request,
                     metadata={"url": url_str, "outcome": "invalid_url", "error": str(e), "client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Use unified preview engine
    logger.info(f"Using unified preview engine for: {url_str}")

    try:
        # Same quality profile and cache namespace as the demo-v2 job path, so
        # this legacy sync route can never serve a lower-grade preview of the
        # same URL than the main demo does.
        from backend.services.quality_profiles import get_quality_profile
        profile = get_quality_profile("ultra")
        config = PreviewEngineConfig(
            is_demo=True,
            enable_brand_extraction=True,
            enable_ai_reasoning=profile.ai_reasoning,
            enable_composited_image=True,
            enable_cache=not cache_disabled,
            enable_multi_agent=profile.multi_agent,
            enable_ui_element_extraction=profile.ui_extraction,
            quality_threshold=profile.threshold,
            max_quality_iterations=profile.iterations,
            allow_soft_pass=profile.allow_soft_pass,
            enforce_target_quality=profile.enforce_target_quality,
            min_soft_pass_overall=profile.min_soft_pass_overall,
            min_soft_pass_visual=profile.min_soft_pass_visual,
            min_soft_pass_fidelity=profile.min_soft_pass_fidelity,
        )

        engine = PreviewEngine(config)
        engine_result = engine.generate(url_str, cache_key_prefix="demo:preview:v3:ultra:")

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Preview generation failed: {error_msg}")
        log_activity(db, user_id=user_id, action="demo.preview.completed", request=request,
                     metadata={"url": url_str, "outcome": "quality_gate_failed", "error": error_msg, "client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Preview generation failed quality checks: {error_msg}. Please try again or contact support."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in preview generation: {error_msg}", exc_info=True)
        log_activity(db, user_id=user_id, action="demo.preview.completed", request=request,
                     metadata={"url": url_str, "outcome": "error", "error": error_msg, "client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {error_msg}. Please try again."
        )
    
    # Convert PreviewEngineResult to DemoPreviewResponse
    response = DemoPreviewResponse(
        url=engine_result.url,
        
        # Content
        title=engine_result.title,
        subtitle=engine_result.subtitle,
        description=engine_result.description,
        tags=engine_result.tags,
        context_items=[
            ContextItem(icon=c["icon"], text=c["text"])
            for c in engine_result.context_items
        ],
        credibility_items=[
            CredibilityItem(type=c["type"], value=c["value"])
            for c in engine_result.credibility_items
        ],
        cta_text=engine_result.cta_text,
        
        # Images
        primary_image_base64=engine_result.primary_image_base64,
        screenshot_url=engine_result.screenshot_url,
        composited_preview_image_url=engine_result.composited_preview_image_url,
        
        # Brand elements
        brand=BrandElements(
            brand_name=engine_result.brand.get("brand_name"),
            logo_base64=engine_result.brand.get("logo_base64"),
            hero_image_base64=engine_result.brand.get("hero_image_base64")
        ),
        
        # Blueprint
        blueprint=LayoutBlueprint(
            template_type=engine_result.blueprint.get("template_type", "article"),
            primary_color=engine_result.blueprint.get("primary_color", "#2563EB"),
            secondary_color=engine_result.blueprint.get("secondary_color", "#1E40AF"),
            accent_color=engine_result.blueprint.get("accent_color", "#F59E0B"),
            coherence_score=engine_result.blueprint.get("coherence_score", 0.0),
            balance_score=engine_result.blueprint.get("balance_score", 0.0),
            clarity_score=engine_result.blueprint.get("clarity_score", 0.0),
            overall_quality=engine_result.blueprint.get("overall_quality", 0.0),
            layout_reasoning=engine_result.blueprint.get("layout_reasoning", ""),
            composition_notes=engine_result.blueprint.get("composition_notes", "")
        ),
        
        # Metrics
        reasoning_confidence=engine_result.reasoning_confidence,
        processing_time_ms=engine_result.processing_time_ms,
        
        # Quality indicators
        quality_scores=engine_result.quality_scores,
        is_fallback=engine_result.quality_scores.get("is_fallback", False) if engine_result.quality_scores else False,
        
        # Metadata
        is_demo=True,
        message=engine_result.message
    )
    
    # Cache the result for future requests (24 hour TTL)
    if redis_client and cache_key and not cache_disabled:
        try:
            response_dict = response.model_dump()
            cache_data = json.dumps(response_dict)
            ttl_seconds = CacheConfig.DEFAULT_TTL_HOURS * 3600
            redis_client.setex(cache_key, ttl_seconds, cache_data)
            logger.info(f"Cached demo preview result for: {url_str[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    # Single consolidated log entry for the entire sync flow (extensive for debugging)
    log_activity(
        db, user_id=user_id, action="demo.preview.completed", request=request,
        metadata={
            "url": url_str,
            "outcome": "success",
            "source": "sync",
            "title": (response.title or "")[:120],
            "template_type": response.blueprint.template_type if response.blueprint else "unknown",
            "processing_time_ms": response.processing_time_ms,
            "confidence": response.reasoning_confidence,
            "overall_quality": response.blueprint.overall_quality if response.blueprint else "unknown",
            "has_composited_image": bool(response.composited_preview_image_url),
            "warnings": (engine_result.warnings or [])[:5],
            "quality_scores": engine_result.quality_scores,
            "client_ip": client_ip,
        },
    )

    return response
