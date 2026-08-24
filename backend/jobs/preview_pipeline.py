"""Main preview generation pipeline job."""
from typing import Dict
from backend.db.session import SessionLocal
from backend.models.domain import Domain as DomainModel
from backend.schemas.brand import BrandSettings as BrandSettingsSchema
from backend.services import brand_resolver
from backend.services.preview.branding import DISREGARD_KEY
from backend.utils.url_sanitizer import sanitize_url
from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig, PreviewEngineResult
from backend.services.preview_type_predictor import predict_preview_type
from backend.services.quality_profiles import get_quality_profile
from backend.services.generation_lane import LaneDecision, record_ai_generation, resolve_lane
from backend.services.card_rerender import rerender_card
from backend.jobs.preview_upsert import upsert_preview
from backend.jobs.platform_render_job import enqueue_platform_renders
from backend.services.brand_rewriter import rewrite_to_brand_voice
from backend.models.preview_variant import PreviewVariant as PreviewVariantModel
from backend.models.preview_job_failure import PreviewJobFailure as PreviewJobFailureModel
from backend.core.config import settings
from backend.services.activity_logger import log_activity
import logging
import traceback

logger = logging.getLogger("preview_worker")


def _derive_brand_tone_hint(brand_schema):
    """Derive brand tone hint from brand settings."""
    primary = brand_schema.primary_color.lower()
    if any(c in primary for c in ['ff', 'f00', 'e00']):
        return "bold"
    elif any(c in primary for c in ['00f', '009', '006']):
        return "professional"
    else:
        return "neutral"


def _replace_variants(
    db,
    *,
    preview,
    main_title: str,
    main_description: str,
    main_image_url: str,
    keywords: str,
    variants: list,
    render_spec: Dict,
    url: str,
) -> None:
    """Rewrite this preview's variants to match the current generation.

    Replace rather than append: a regeneration produces a new set of angles, and
    leaving the old ones behind would show the user variants whose copy no longer
    matches any card.

    Variant A mirrors the main card. B and C each get their own rendered image so
    an A/B test compares the actual artefacts that will be shared — rendering is
    a pure rasterize off the stored spec, so the extra cards cost no AI.
    """
    db.query(PreviewVariantModel).filter(
        PreviewVariantModel.preview_id == preview.id
    ).delete(synchronize_session=False)

    rows = [PreviewVariantModel(
        preview_id=preview.id,
        variant_key="a",
        angle="main",
        title=main_title[:200],
        subtitle=None,
        description=main_description[:500] if main_description else None,
        keywords=keywords,
        image_url=main_image_url,
    )]

    for key, variant in zip(("b", "c"), variants or []):
        title = str(variant.get("title") or "").strip()
        if not title:
            continue
        subtitle = variant.get("subtitle")
        image_url, _ = rerender_card(
            render_spec or {}, url=url, title=title, subtitle=subtitle,
        )
        rows.append(PreviewVariantModel(
            preview_id=preview.id,
            variant_key=key,
            angle=str(variant.get("angle") or "alternate"),
            title=title[:200],
            subtitle=(subtitle or None) and str(subtitle)[:300],
            # The variant's own hook is a better description of it than the
            # main card's copy, which is what the old duplicate code stored.
            description=(subtitle or title)[:500],
            keywords=keywords,
            # A failed re-render falls back to the main card rather than a
            # broken image; the copy is still a real alternative to test.
            image_url=image_url or main_image_url,
        ))

    for row in rows:
        db.add(row)


def generate_preview_job(
    user_id: int,
    organization_id: int,
    url: str,
    domain: str,
    force_regenerate: bool = False,
    ignore_site_branding: bool = False,
) -> Dict:
    """
    Main background job to generate preview for a URL.

    This is the entry point called by RQ worker.

    Args:
        user_id: ID of the user requesting the preview
        organization_id: ID of the organization
        url: URL to generate preview for
        domain: Domain name
        force_regenerate: If True, bypass the engine cache so a fresh preview is
            produced (used by the "regenerate / re-roll" action and bulk re-runs).
        ignore_site_branding: If True, design this card from the page alone —
            the domain's My Site brand (identity, palette, logo, font, card
            preferences) is not applied. Set per preview from the gallery's
            "disregard my site branding" toggle; the white-label entitlement is
            deliberately still honoured.

    Returns:
        Dictionary with preview_id and preview data
    """
    db = SessionLocal()
    try:
        # Step 1: Validate domain ownership
        domain_obj = db.query(DomainModel).filter(
            DomainModel.name == domain,
            DomainModel.organization_id == organization_id
        ).first()
        
        if not domain_obj:
            raise ValueError("Domain not found or not owned by the organization")
        
        # Step 2: Sanitize URL
        sanitized_url = sanitize_url(url, domain)
        
        # Step 3: Load brand settings for THIS domain. Each connected domain is
        # its own site with its own identity; a domain that has not been
        # customised falls back to the organization default.
        brand_settings = brand_resolver.resolve(db, organization_id, domain_obj.id)

        # If the account has no brand settings at all, create the domain's row.
        if not brand_settings:
            brand_settings = brand_resolver.get_or_create(
                db, organization_id, user_id=user_id, domain_id=domain_obj.id
            )

        # Step 4: Convert to schema for brand rewriting
        brand_schema = BrandSettingsSchema.model_validate(brand_settings)
        
        # Plan-gated card features. White-label (hide the MetaView mark) and the
        # layout/panel/accent overrides only take effect on plans that include them;
        # otherwise the prefs fall back to "auto" (our art director decides).
        from backend.models.organization import Organization as _OrgModel
        from backend.core.plans import has_feature, F_HIDE_WATERMARK, F_CARD_CONTROLS, F_VARIANTS
        _org = db.query(_OrgModel).filter(_OrgModel.id == organization_id).first()
        _can_hide_watermark = bool(_org and has_feature(_org, F_HIDE_WATERMARK))
        _can_card_controls = bool(_org and has_feature(_org, F_CARD_CONTROLS))
        # A/B variants are a paid feature. Plans without it get variant A only —
        # the main card — rather than three tabs showing the same thing.
        _can_variants = bool(_org and has_feature(_org, F_VARIANTS))

        # Step 4.5: AI lane or template lane?
        # The AI lane is the product — the art director reads this page and
        # designs a card for it. It is metered per plan; past the allowance the
        # account still gets a card, built from the page's own metadata.
        lane = resolve_lane(db, _org) if _org else LaneDecision("ai", 0, None)
        if lane.lane == "ai":
            record_ai_generation(
                db,
                organization_id=organization_id,
                user_id=user_id,
                url=sanitized_url,
                domain=domain,
            )
        else:
            logger.info(
                "Template lane for %s — org %s has spent %s/%s AI previews this month",
                sanitized_url, organization_id, lane.used, lane.limit,
            )

        # Step 5: Use unified preview engine for core generation.
        # The profile comes from the same table the demo reads, pinned to
        # `ultra`, so a customer's preview is generated exactly as well as the
        # one they saw on the landing page before they signed up.
        profile = get_quality_profile("ultra" if lane.lane == "ai" else "template")
        logger.info(
            f"Using unified preview engine for: {sanitized_url} "
            f"(lane={lane.lane}, profile={profile.quality_mode})"
        )
        config = PreviewEngineConfig(
            is_demo=False,  # SaaS mode
            enable_brand_extraction=True,
            enable_ai_reasoning=profile.ai_reasoning,
            enable_composited_image=True,
            enable_cache=not force_regenerate,
            enable_ui_element_extraction=profile.ui_extraction,
            quality_threshold=profile.threshold,
            max_quality_iterations=profile.iterations,
            allow_soft_pass=profile.allow_soft_pass,
            enforce_target_quality=profile.enforce_target_quality,
            min_soft_pass_overall=profile.min_soft_pass_overall,
            min_soft_pass_visual=profile.min_soft_pass_visual,
            min_soft_pass_fidelity=profile.min_soft_pass_fidelity,
            brand_settings={
                # A preview added with branding disregarded carries the flag into
                # the engine rather than arriving with an empty payload: the
                # stages read it to explain the choice in the job trace, and it
                # is part of the cache signature, so a disregarded card and a
                # branded one for the same URL never stand in for each other.
                DISREGARD_KEY: bool(ignore_site_branding),
                "primary_color": brand_schema.primary_color,
                "secondary_color": brand_schema.secondary_color,
                "accent_color": brand_schema.accent_color,
                "font_family": brand_schema.font_family,
                "logo_url": brand_schema.logo_url,
                # Identity the user typed in (Brand & identity page). Blank fields
                # mean "keep inferring from the page", so nothing regresses for
                # accounts that never filled these in.
                "brand_name": (getattr(brand_schema, "brand_name", None) or "").strip() or None,
                "tagline": (getattr(brand_schema, "tagline", None) or "").strip() or None,
                # User's preview-card preferences — honoured by the engine's
                # compositing step (layout/panel/accent overrides, force-brand-
                # colours, hide-watermark). Layout/panel/accent are gated behind
                # F_CARD_CONTROLS; without it they collapse to "auto".
                "preview_layout": getattr(brand_schema, "preview_layout", "auto") if _can_card_controls else "auto",
                "preview_panel": getattr(brand_schema, "preview_panel", "auto") if _can_card_controls else "auto",
                "preview_accent": getattr(brand_schema, "preview_accent", "auto") if _can_card_controls else "auto",
                "force_brand_colors": bool(getattr(brand_schema, "force_brand_colors", False)),
                "hide_watermark": bool(getattr(brand_schema, "hide_watermark", False)) and _can_hide_watermark,
            }
        )
        
        engine = PreviewEngine(config)
        
        # The profile carries the thresholds and per-purpose model choices the
        
        # pipeline reads; passing it keeps the one-table principle intact.
        
        engine.quality_profile = profile
        # Separate cache namespaces per lane. Sharing one would let a template
        # card served during an exhausted month keep being returned after the
        # account upgrades — the customer pays and sees the same generic image.
        engine_result = engine.generate(
            sanitized_url, cache_key_prefix=f"saas:preview:{lane.lane}:"
        )
        
        # Step 6: Apply brand voice rewriting to description. Disregarding the
        # site's branding means the page speaks for itself, voice included.
        rewritten_description = (
            engine_result.description
            if ignore_site_branding
            else rewrite_to_brand_voice(engine_result.description, brand_schema)
        )
        
        # Step 7: Predict preview type (for database storage)
        # Use blueprint template_type from engine, or fallback to predictor
        preview_type = engine_result.blueprint.get("template_type", "article")
        if preview_type == "unknown":
            # Fallback to type predictor if needed
            from backend.services.metadata_extractor import extract_metadata_from_html
            from backend.services.preview_generator import fetch_page_html
            try:
                html_content = fetch_page_html(sanitized_url)
                metadata = extract_metadata_from_html(html_content)
                preview_type = predict_preview_type(metadata, sanitized_url, {
                    "title": engine_result.title,
                    "description": rewritten_description,
                    "type": preview_type
                })
            except Exception as e:
                logger.warning(f"Type prediction failed: {e}, using default")
                preview_type = "article"
        
        # Step 8: Prepare image URLs
        # Use composited image as main, screenshot as highlight
        main_image_url = engine_result.composited_preview_image_url or engine_result.screenshot_url
        highlight_image_url = engine_result.screenshot_url or main_image_url
        
        # Fallback to placeholder if no images
        if not main_image_url:
            main_image_url = settings.PLACEHOLDER_IMAGE_URL
            highlight_image_url = settings.PLACEHOLDER_IMAGE_URL
            logger.warning(f"Using placeholder image for URL: {sanitized_url}")
        
        # Step 9: Upsert preview in database with all metadata
        keywords_str = ",".join(engine_result.tags) if engine_result.tags else None
        
        preview = upsert_preview(
            db=db,
            url=sanitized_url,
            domain=domain,
            title=engine_result.title,
            description=rewritten_description,
            image_url=main_image_url,
            highlight_image_url=highlight_image_url,
            composited_image_url=engine_result.composited_preview_image_url,
            preview_type=preview_type,
            user_id=user_id,
            organization_id=organization_id,
            keywords=keywords_str,
            tone=None,  # Can be extracted from blueprint if needed
            ai_reasoning=engine_result.blueprint.get("layout_reasoning") or engine_result.message,
            generation_mode=lane.lane,
            layout=engine_result.rendered_layout,
            render_spec=engine_result.render_spec or None,
            ignore_site_branding=ignore_site_branding,
        )

        # Step 10: Variants — one card per distinct angle the art director found.
        # Variant A is always the main card (same copy, same image), so the tabs
        # compare like with like. B and C only exist when the page supported a
        # genuinely different argument; the director returns fewer rather than
        # padding with paraphrases, and we render exactly what it returned.
        _replace_variants(
            db,
            preview=preview,
            main_title=engine_result.title,
            main_description=rewritten_description,
            main_image_url=main_image_url,
            keywords=keywords_str,
            variants=engine_result.variants if _can_variants else [],
            render_spec=engine_result.render_spec,
            url=sanitized_url,
        )

        db.commit()
        db.refresh(preview)
        
        # Log successful job completion
        log_activity(
            db,
            user_id=user_id,
            action="preview.ai_job.completed",
            metadata={
                "preview_id": preview.id,
                "url": sanitized_url,
                "domain": domain,
                "type": preview_type,
                "lane": lane.lane,
                "layout": engine_result.rendered_layout,
                "ignore_site_branding": bool(ignore_site_branding),
                # Which fallbacks fired, and the id that opens the full trace.
                # Without these a support question about a generic-looking card
                # has no answer short of re-running the generation.
                "degradations": engine_result.degradations,
                "job_trace_id": engine_result.job_id,
                "quality": {
                    "overall": (engine_result.quality_scores or {}).get("overall"),
                    "gate_status": (engine_result.quality_scores or {}).get("gate_status"),
                    "is_fallback": bool((engine_result.quality_scores or {}).get("is_fallback")),
                },
            },
            request=None  # No request in background job
        )
        
        # The same card at the other platform aspects. A pure render off the
        # stored spec — no capture, no model call — so it costs nothing but
        # render time, and it runs on the bulk queue because the wide card is
        # already served and nobody is waiting for these.
        if engine_result.render_spec:
            enqueue_platform_renders(preview.id)

        return {
            "preview_id": preview.id,
            "preview": {
                "id": preview.id,
                "url": preview.url,
                "domain": preview.domain,
                "title": preview.title,
                "type": preview.type,
                "image_url": preview.image_url,
                "description": preview.description,
                "keywords": preview.keywords,
                "tone": preview.tone,
                "ai_reasoning": preview.ai_reasoning,
                "created_at": preview.created_at.isoformat(),
                "monthly_clicks": preview.monthly_clicks,
            }
        }
        
    except Exception as e:
        logger.error("Preview generation job failed", exc_info=True)

        # Some failures are the world's, not the input's: a capture timeout, a
        # provider 5xx, a rate limit. Those are worth another attempt; a 404 or
        # a refused URL will fail identically forever and retrying it only
        # delays real work. The reason code decides, not the exception text.
        decision = _schedule_retry_if_transient(
            e, url=url, domain=domain, user_id=user_id,
            organization_id=organization_id,
            ignore_site_branding=ignore_site_branding,
        )

        # Save to Dead Letter Queue (DLQ)
        try:
            failure_record = PreviewJobFailureModel(
                job_id=None,  # Could be passed from RQ if available
                preview_id=None,  # Preview wasn't created yet
                url=url,
                organization_id=organization_id,
                error_message=str(e),
                stacktrace=traceback.format_exc()
            )
            db.add(failure_record)
            db.commit()
        except Exception as dlq_error:
            logger.error(f"Failed to save job failure to DLQ: {dlq_error}", exc_info=True)
        
        # Log job failure
        try:
            log_activity(
                db,
                user_id=user_id,
                action="preview.ai_job.failed",
                metadata={
                    "url": url,
                    "domain": domain,
                    "error": str(e),
                    "retry": decision.to_dict(),
                },
                request=None
            )
        except Exception:
            pass  # Don't fail if logging fails
        
        raise
    finally:
        # Always close DB session
        db.close()


def _schedule_retry_if_transient(
    error: Exception,
    *,
    url: str,
    domain: str,
    user_id: int,
    organization_id: int,
    ignore_site_branding: bool = False,
):
    """Re-enqueue a failed job when its reason code says that could help.

    Bounded by attempt count and keyed by the job's inputs, so a retry takes
    over the first attempt's identity instead of racing it — which is what stops
    a retried job double-inserting variants.
    """
    from backend.services.preview.retry import (
        attempt_count,
        decide_retry,
        idempotency_key,
        record_attempt,
    )
    from backend.services.preview.observability.reason_codes import FailureReason

    key = idempotency_key(url=url, organization_id=organization_id, lane="ai")
    attempts = attempt_count(key)

    reason = getattr(error, "failure_reason", None)
    if reason is None:
        reason = _reason_from_error(str(error))
    decision = decide_retry(reason, attempt=attempts)

    if not decision.should_retry:
        logger.info("Not retrying %s: %s", url, decision.reason)
        return decision

    try:
        from backend.queue.queue_connection import get_rq_redis_connection
        from rq import Queue

        record_attempt(key)
        queue = Queue("preview_generation", connection=get_rq_redis_connection())
        queue.enqueue_in(
            __import__("datetime").timedelta(seconds=decision.delay_s),
            generate_preview_job,
            user_id, organization_id, url, domain, False, ignore_site_branding,
            job_timeout=900,
        )
        logger.info("Retrying %s: %s", url, decision.reason)
    except Exception as enqueue_error:  # noqa: BLE001 — a failed retry is not a new failure
        logger.warning("Could not schedule retry for %s: %s", url, enqueue_error)
        return type(decision)(False, reason=f"enqueue failed: {enqueue_error}")

    return decision


def _reason_from_error(message: str):
    """Best-effort reason code when the failure did not carry one."""
    from backend.services.preview.observability.reason_codes import FailureReason

    text = (message or "").lower()
    if "refusing to capture" in text or "ssrf" in text:
        return FailureReason.CAPTURE_BLOCKED
    if "rate limit" in text or "429" in text:
        return FailureReason.EXTRACTION_AI_RATE_LIMIT
    if "timed out" in text or "timeout" in text:
        return FailureReason.CAPTURE_TIMEOUT
    if "404" in text or "not found" in text:
        return FailureReason.CAPTURE_HTTP_ERROR
    if "capture" in text or "screenshot" in text:
        return FailureReason.CAPTURE_NETWORK_ERROR
    return FailureReason.UNKNOWN

