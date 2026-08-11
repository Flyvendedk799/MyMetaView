"""Main preview generation pipeline job."""
from typing import Dict
from backend.db.session import SessionLocal
from backend.models.domain import Domain as DomainModel
from backend.schemas.brand import BrandSettings as BrandSettingsSchema
from backend.services import brand_resolver
from backend.utils.url_sanitizer import sanitize_url
from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig, PreviewEngineResult
from backend.services.preview_type_predictor import predict_preview_type
from backend.services.quality_profiles import get_quality_profile
from backend.services.generation_lane import LaneDecision, record_ai_generation, resolve_lane
from backend.services.card_rerender import rerender_card
from backend.jobs.preview_upsert import upsert_preview
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


def generate_preview_job(user_id: int, organization_id: int, url: str, domain: str, force_regenerate: bool = False) -> Dict:
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
            enable_multi_agent=profile.multi_agent,
            enable_ui_element_extraction=profile.ui_extraction,
            quality_threshold=profile.threshold,
            max_quality_iterations=profile.iterations,
            allow_soft_pass=profile.allow_soft_pass,
            enforce_target_quality=profile.enforce_target_quality,
            min_soft_pass_overall=profile.min_soft_pass_overall,
            min_soft_pass_visual=profile.min_soft_pass_visual,
            min_soft_pass_fidelity=profile.min_soft_pass_fidelity,
            brand_settings={
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
        # Separate cache namespaces per lane. Sharing one would let a template
        # card served during an exhausted month keep being returned after the
        # account upgrades — the customer pays and sees the same generic image.
        engine_result = engine.generate(
            sanitized_url, cache_key_prefix=f"saas:preview:{lane.lane}:"
        )
        
        # Step 6: Apply brand voice rewriting to description
        rewritten_description = rewrite_to_brand_voice(engine_result.description, brand_schema)
        
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
            metadata={"preview_id": preview.id, "url": sanitized_url, "domain": domain, "type": preview_type},
            request=None  # No request in background job
        )
        
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
                metadata={"url": url, "domain": domain, "error": str(e)},
                request=None
            )
        except Exception:
            pass  # Don't fail if logging fails
        
        raise
    finally:
        # Always close DB session
        db.close()

