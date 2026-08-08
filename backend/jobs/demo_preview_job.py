"""
Background job for demo preview generation (public, no auth required).
This job uses the unified preview engine for consistent, high-quality previews.
"""
from typing import Dict, Any
from uuid import uuid4
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from rq.job import Job, get_current_job
from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig, PreviewEngineResult
from backend.services.r2_client import upload_file_to_r2
from backend.services.preview_cache import (
    generate_cache_key,
    get_redis_client,
    CacheConfig,
    is_demo_cache_disabled
)
from backend.services.activity_logger import log_activity
from backend.db.session import SessionLocal
import json

logger = logging.getLogger(__name__)


def _update_job_progress(progress: float, message: str) -> None:
    """Update job progress in Redis for frontend polling."""
    try:
        job = get_current_job()
        if job:
            job.meta['progress'] = progress
            job.meta['message'] = message
            job.save_meta()
    except Exception as e:
        # Don't fail the job if progress update fails
        logger.warning(f"Failed to update job progress: {e}")


def generate_demo_preview_job(url: str, quality_mode: str = "ultra") -> Dict[str, Any]:
    """
    Background job to generate demo preview using unified preview engine.
    
    This uses the unified PreviewEngine for consistent, high-quality previews
    with robust edge case handling and intelligent fallbacks.
    
    Args:
        url: URL to generate preview for
        
    Returns:
        Dictionary with preview data matching DemoPreviewResponse schema
    """
    try:
        url_str = str(url)
        logger.info(f"🚀 Starting demo preview job for: {url_str}")
        
        # Check if demo caching is disabled via admin toggle
        cache_disabled = is_demo_cache_disabled()
        
        if cache_disabled:
            logger.info(f"🚫 Cache DISABLED - generating fresh preview for: {url_str[:50]}...")
            # Invalidate any existing cache to ensure fresh results
            from backend.services.preview_cache import invalidate_cache
            invalidate_cache(url_str)
            logger.info(f"🗑️  Cleared existing cache entries for: {url_str[:50]}...")
        else:
            logger.info(f"✅ Cache ENABLED - checking cache first for: {url_str[:50]}...")
        
        # Update initial progress
        _update_job_progress(0.05, "Starting preview generation...")

        quality_profiles = {
            "fast": {
                "multi_agent": False, "ui_extraction": False, "threshold": 0.78, "iterations": 2,
                "allow_soft_pass": True, "enforce_target_quality": False, "min_soft_pass_overall": 0.66, "min_soft_pass_visual": 0.52, "min_soft_pass_fidelity": 0.50
            },
            "balanced": {
                "multi_agent": True, "ui_extraction": True, "threshold": 0.82, "iterations": 3,
                "allow_soft_pass": True, "enforce_target_quality": False, "min_soft_pass_overall": 0.74, "min_soft_pass_visual": 0.62, "min_soft_pass_fidelity": 0.60
            },
            "ultra": {
                "multi_agent": True, "ui_extraction": True, "threshold": 0.88, "iterations": 4,
                "allow_soft_pass": False, "enforce_target_quality": True, "min_soft_pass_overall": 0.85, "min_soft_pass_visual": 0.75, "min_soft_pass_fidelity": 0.72
            },
        }
        selected_profile = quality_profiles.get((quality_mode or "ultra").lower(), quality_profiles["ultra"])
        
        # Configure engine for demo mode (optimized for speed)
        config = PreviewEngineConfig(
            is_demo=True,
            enable_brand_extraction=True,
            enable_ai_reasoning=True,
            enable_composited_image=True,
            enable_cache=not cache_disabled,
            enable_multi_agent=selected_profile["multi_agent"],
            enable_ui_element_extraction=selected_profile["ui_extraction"],
            quality_threshold=selected_profile["threshold"],
            max_quality_iterations=selected_profile["iterations"],
            allow_soft_pass=selected_profile["allow_soft_pass"],
            enforce_target_quality=selected_profile["enforce_target_quality"],
            min_soft_pass_overall=selected_profile["min_soft_pass_overall"],
            min_soft_pass_visual=selected_profile["min_soft_pass_visual"],
            min_soft_pass_fidelity=selected_profile["min_soft_pass_fidelity"],
            progress_callback=_update_job_progress
        )
        
        # Create engine and generate preview
        engine = PreviewEngine(config)
        result = engine.generate(url_str, cache_key_prefix=f"demo:preview:v3:{quality_mode}:")
        
        # Ensure progress is at 100% when job completes successfully
        # Do this BEFORE returning to ensure it's saved to Redis
        _update_job_progress(1.0, "Preview generation complete!")
        
        # Small delay to ensure progress update is saved before job completes
        import time
        time.sleep(0.1)
        
        # Prepare brand elements with fallbacks
        brand_data = result.brand if result.brand else {}
        brand_elements = {
            "brand_name": brand_data.get("brand_name"),
            "logo_base64": brand_data.get("logo_base64"),
            "hero_image_base64": brand_data.get("hero_image_base64")
        }

        # Prepare layout blueprint with fallbacks to avoid validation errors
        blueprint_data = result.blueprint if result.blueprint else {}
        layout_blueprint = {
            "template_type": blueprint_data.get("template_type", "article"),
            "primary_color": blueprint_data.get("primary_color", "#2563EB"),
            "secondary_color": blueprint_data.get("secondary_color", "#1E40AF"),
            "accent_color": blueprint_data.get("accent_color", "#F59E0B"),
            "coherence_score": blueprint_data.get("coherence_score", 0.0),
            "balance_score": blueprint_data.get("balance_score", 0.0),
            "clarity_score": blueprint_data.get("clarity_score", 0.0),
            "design_fidelity_score": blueprint_data.get("design_fidelity_score"),
            "overall_quality": str(blueprint_data.get("overall_quality", "good")),
            "layout_reasoning": blueprint_data.get("layout_reasoning", ""),
            "composition_notes": blueprint_data.get("composition_notes", "")
        }

        # Prepare design DNA if available
        design_dna = None
        if hasattr(result, 'design_dna') and result.design_dna:
            # Need to convert string to float for formality if it's not already
            formality = result.design_dna.get("formality", 0.5)
            try:
                formality = float(formality)
            except (ValueError, TypeError):
                formality = 0.5
                
            design_dna = {
                "style": result.design_dna.get("style", "corporate"),
                "mood": result.design_dna.get("mood", "balanced"),
                "formality": formality,
                "typography_personality": result.design_dna.get("typography_personality", "bold"),
                "color_emotion": result.design_dna.get("color_emotion", "trust"),
                "spacing_feel": result.design_dna.get("spacing_feel", "balanced"),
                "brand_adjectives": result.design_dna.get("brand_adjectives", []),
                "design_reasoning": result.design_dna.get("design_reasoning", "")
            }

        # Convert PreviewEngineResult to response dict exactly matching DemoPreviewResponse via Pydantic mapping
        response_data = {
            "url": result.url,
            
            # Content
            "title": result.title,
            "subtitle": result.subtitle,
            "description": result.description,
            "tags": result.tags,
            "context_items": result.context_items,
            "credibility_items": result.credibility_items,
            "cta_text": result.cta_text,
            
            # Images
            "primary_image_base64": result.primary_image_base64,
            "screenshot_url": result.screenshot_url,
            "composited_preview_image_url": result.composited_preview_image_url,
            
            # Brand elements
            "brand": brand_elements,
            
            # Blueprint
            "blueprint": layout_blueprint,
            
            # Design DNA
            "design_dna": design_dna,
            
            # Metrics
            "reasoning_confidence": result.reasoning_confidence,
            "design_fidelity_score": getattr(result, 'design_fidelity_score', layout_blueprint.get("design_fidelity_score")),
            "processing_time_ms": result.processing_time_ms,
            
            # Metadata
            "is_demo": True,
            "message": f"{result.message} [quality_mode={quality_mode}]",
            "trace_url": result.trace_url,

            # Temporary diagnostics (premium renderer rollout). Presence of this
            # block proves the new worker build is live; the fields show which
            # reasoning path ran and whether the premium card renderer succeeded.
            "_debug": {
                "engine_build": "premium-v3",
                "reasoning_path": getattr(engine, "_reasoning_path", "unset"),
                "premium_note": getattr(engine, "_premium_note", "unset"),
                "composited_url": result.composited_preview_image_url,
            },
        }
        
        # Add quality scores and warnings from pipeline
        if result.quality_scores:
            response_data["quality_scores"] = result.quality_scores
        if result.warnings:
            response_data["warnings"] = result.warnings
            logger.warning(f"Preview generated with warnings: {result.warnings}")

        logger.info(f"Preview generated in {result.processing_time_ms}ms")
        quality_scores = result.quality_scores or {}
        debug_scores = quality_scores.get("debug") if isinstance(quality_scores.get("debug"), dict) else {}
        pipeline_stages = quality_scores.get("pipeline_stages") if isinstance(quality_scores.get("pipeline_stages"), dict) else {}
        request_id = quality_scores.get("request_id") or debug_scores.get("request_id")
        quality_debug = {
            "decision": debug_scores.get("final_decision"),
            "retry_attempts_used": debug_scores.get("retry_attempts_used"),
            "retry_budget": debug_scores.get("retry_budget"),
            "quality_passed": debug_scores.get("quality_passed"),
            "thresholds": debug_scores.get("thresholds"),
            "metrics_snapshot": debug_scores.get("metrics_snapshot"),
            "warnings_count": debug_scores.get("warnings_count", len(result.warnings or [])),
        }
        generation_profile = {
            "quality_mode": quality_mode,
            "profile": selected_profile,
            "cache_disabled": cache_disabled,
        }

        # Log a single comprehensive completion entry for admin debugging
        try:
            db = SessionLocal()
            job = get_current_job()
            job_id = str(job.id) if job else None
            log_activity(
                db,
                action="demo.preview.completed",
                metadata={
                    "outcome": "success",
                    "job_id": job_id,
                    "url": url_str,
                    "title": (result.title or "")[:120],
                    "template_type": blueprint_data.get("template_type", "unknown"),
                    "processing_time_ms": result.processing_time_ms,
                    "confidence": result.reasoning_confidence,
                    "design_fidelity": getattr(result, "design_fidelity_score", blueprint_data.get("design_fidelity_score")),
                    "overall_quality": blueprint_data.get("overall_quality", "unknown"),
                    "coherence": blueprint_data.get("coherence_score", 0),
                    "balance_score": blueprint_data.get("balance_score"),
                    "clarity_score": blueprint_data.get("clarity_score"),
                    "has_composited_image": bool(result.composited_preview_image_url),
                    "has_screenshot": bool(result.screenshot_url),
                    "has_logo": bool(brand_data.get("logo_base64")),
                    "tags": (result.tags or [])[:5],
                    "credibility_items_count": len(result.credibility_items or []),
                    "warnings": (result.warnings or [])[:5],
                    "quality_scores": quality_scores,
                    "quality_debug": quality_debug,
                    "pipeline": {
                        "tier": quality_scores.get("tier"),
                        "total_ms": quality_scores.get("total_ms"),
                        "stages": pipeline_stages,
                    },
                    "message": (result.message or "")[:200],
                    "image_url": result.composited_preview_image_url or result.screenshot_url,
                    "trace_url": result.trace_url,
                    "request_id": request_id,
                    "quality_mode": quality_mode,
                    "generation_profile": generation_profile,
                },
            )
            db.close()
        except Exception as log_err:
            logger.warning(f"Activity logging failed (non-fatal): {log_err}")

        return response_data

    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Fatal error in demo preview job: {error_msg}", exc_info=True)
        try:
            _update_job_progress(0.0, f"Failed: {error_msg}")
        except Exception:
            pass

        # Log failure for admin debugging with extensive context
        try:
            db = SessionLocal()
            job = get_current_job()
            job_id = str(job.id) if job else None
            tb_lines = traceback.format_exc().splitlines()
            tb_snippet = "\n".join(tb_lines[-8:])[:800] if tb_lines else ""
            log_activity(
                db,
                action="demo.preview.failed",
                metadata={
                    "outcome": "failed",
                    "job_id": job_id,
                    "url": url_str if 'url_str' in dir() else str(url),
                    "error": error_msg[:500],
                    "exception_type": type(e).__name__,
                    "quality_mode": quality_mode,
                    "generation_profile": selected_profile if 'selected_profile' in locals() else None,
                    "job_meta": (job.get_meta(refresh=True) if job else None),
                    "traceback_snippet": tb_snippet,
                },
            )
            db.close()
        except Exception:
            pass

        raise










