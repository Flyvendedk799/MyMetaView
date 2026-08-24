"""The reasoning stage: what does this card say?

Wraps the single-pass art director with the three things the raw call lacks: a
content-keyed cache, a deadline, and a fallback that reads the page's own
metadata rather than inventing a stub.

The ladder is explicit and each rung is traced:

    reasoning cache  →  art director (vision)  →  page metadata  →  nothing

"Nothing" is a real outcome: the coordinator answers it with the deterministic
minimal card, which still renders through the premium renderer. The old engine
answered it with a hand-written placeholder dict that made every page render the
same card, and that dict is what this stage exists to delete.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.services.preview.branding import identity_brief, settings_of
from backend.services.preview.budgets import run_with_deadline
from backend.services.preview.caching.layers import (
    ReasoningCache,
    reasoning_fingerprint,
    screenshot_phash,
)
from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    Stage,
)
from backend.services.preview.reasoning.models import spec_for
from backend.services.preview.stages import (
    CaptureResult,
    PageClassification,
    PipelineState,
    ReasoningResult,
)

logger = logging.getLogger(__name__)

# Bumped whenever the prompt changes, so a prompt edit misses cache instead of
# serving output authored by the previous prompt.
PROMPT_VERSION = "single-pass-v3"


def run_reasoning(
    state: PipelineState,
    capture: CaptureResult,
    classification: Optional[PageClassification] = None,
) -> ReasoningResult:
    """Produce the card's copy and composition."""
    state.update_progress(0.45, "Reading the page…")
    state.trace.open_stage(Stage.REASONING)
    try:
        return _run(state, capture, classification)
    finally:
        state.trace.close_stage()


def _run(
    state: PipelineState,
    capture: CaptureResult,
    classification: Optional[PageClassification],
) -> ReasoningResult:
    if not getattr(state.config, "enable_ai_reasoning", True):
        state.trace.degrade(
            Degradation.REASONING_SKIPPED_TEMPLATE_LANE, Stage.REASONING,
            detail="template lane: building the card from the page's own metadata",
        )
        return _from_page_metadata(state, capture, source="template")

    spec = spec_for("art_director", profile=state.shared.get("profile"))
    brief = identity_brief(settings_of(state.config))
    fingerprint = reasoning_fingerprint(
        url=state.url,
        title=_page_title(capture),
        text=(capture.html or "")[:20000],
        screenshot_phash=screenshot_phash(capture.screenshot_bytes),
        model=spec.model,
        prompt_version=PROMPT_VERSION,
        brand_brief=brief,
    )

    cached = ReasoningCache.get(fingerprint)
    if cached and cached.get("title"):
        state.trace.degrade(
            Degradation.REASONING_CACHED, Stage.REASONING,
            detail="identical page content already reasoned about",
        )
        result = ReasoningResult.from_dict(cached)
        result.from_cache = True
        result.source = "cache"
        return result

    if not capture.has_screenshot:
        state.trace.degrade(
            Degradation.REASONING_FALLBACK_HTML, Stage.REASONING,
            detail="no screenshot for the vision call",
            reason=FailureReason.EXTRACTION_LOW_CONFIDENCE,
        )
        return _from_page_metadata(state, capture, source="html")

    result = run_with_deadline(
        lambda: _call_art_director(state, capture, brief),
        stage=Stage.REASONING,
        budget=state.budget,
        default=None,
        trace=state.trace,
        on_timeout_reason=FailureReason.EXTRACTION_AI_TIMEOUT,
    )

    if result is None or not result.ok:
        state.trace.degrade(
            Degradation.REASONING_FALLBACK_HTML, Stage.REASONING,
            detail="art director unavailable; using the page's own metadata",
            reason=FailureReason.EXTRACTION_AI_TIMEOUT,
        )
        return _from_page_metadata(state, capture, source="html")

    state.trace.extraction_confidence = result.confidence
    state.trace.degrade(
        Degradation.REASONING_OK, Stage.REASONING,
        detail=f"confidence={result.confidence:.2f} layout={result.composition.get('layout')}",
    )
    ReasoningCache.set(fingerprint, result.to_dict())
    return result


def _call_art_director(
    state: PipelineState,
    capture: CaptureResult,
    brand_brief: str = "",
) -> Optional[ReasoningResult]:
    """One vision call, adapted into the stage contract.

    ``brand_brief`` is the customer's own identity from the My Site tab. It is
    context for the copy, never content: the page still decides what is true.
    """
    try:
        from backend.services.preview_reasoning import generate_reasoned_preview

        reasoned = generate_reasoned_preview(
            capture.screenshot_bytes, state.url, brand_context=brand_brief,
        )
    except Exception as exc:  # noqa: BLE001 — the caller degrades to metadata
        logger.info("Art director call failed for %s: %s", state.url, exc)
        return None

    return _adapt(reasoned)


def _adapt(reasoned: Any) -> ReasoningResult:
    """``ReasonedPreview`` → ``ReasoningResult``."""
    blueprint = getattr(reasoned, "blueprint", None)
    blueprint_dict: Dict[str, Any] = {}
    if blueprint is not None:
        for field in (
            "template_type", "primary_color", "secondary_color", "accent_color",
            "background_color", "text_color", "layout_reasoning", "composition_notes",
            "coherence_score", "balance_score", "clarity_score", "overall_quality",
        ):
            value = getattr(blueprint, field, None)
            if value is not None:
                blueprint_dict[field] = value

    credibility = list(getattr(reasoned, "credibility_items", None) or [])
    proof = None
    for item in credibility:
        value = (item or {}).get("value")
        if value:
            proof = str(value)
            break

    return ReasoningResult(
        title=str(getattr(reasoned, "title", "") or ""),
        subtitle=getattr(reasoned, "subtitle", None),
        description=str(getattr(reasoned, "description", "") or ""),
        tags=list(getattr(reasoned, "tags", None) or []),
        cta_text=getattr(reasoned, "cta_text", None),
        proof=proof,
        context_items=list(getattr(reasoned, "context_items", None) or []),
        credibility_items=credibility,
        variants=list(getattr(reasoned, "variants", None) or []),
        composition=dict(getattr(reasoned, "composition", None) or {}),
        blueprint=blueprint_dict,
        confidence=float(
            getattr(blueprint, "analysis_confidence", None)
            or getattr(reasoned, "analysis_confidence", None)
            or getattr(blueprint, "coherence_score", None)
            or 0.0
        ),
        source="ai",
    )


def _page_title(capture: CaptureResult) -> str:
    try:
        from backend.services.metadata_extractor import extract_metadata_from_html

        metadata = extract_metadata_from_html(capture.html or "") or {}
        return str(metadata.get("og_title") or metadata.get("title") or "")
    except Exception:  # noqa: BLE001
        return ""


def _from_page_metadata(
    state: PipelineState,
    capture: CaptureResult,
    *,
    source: str,
) -> ReasoningResult:
    """Build the card's copy from the page's own metadata.

    Not a stub — the page's ``og:`` tags are real, specific copy, and a card
    built from them describes the actual page. That is the difference between
    this and the placeholder dict it replaces.
    """
    metadata: Dict[str, Any] = {}
    try:
        from backend.services.metadata_extractor import extract_metadata_from_html

        metadata = extract_metadata_from_html(capture.html or "") or {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Metadata extraction failed: %s", exc)

    title = str(
        metadata.get("og_title") or metadata.get("twitter_title") or metadata.get("title") or ""
    ).strip()
    description = str(
        metadata.get("og_description")
        or metadata.get("twitter_description")
        or metadata.get("description")
        or ""
    ).strip()

    if not title:
        from backend.services.preview.composition.builder import _brand_from_url

        title = _brand_from_url(state.url)

    proof = None
    try:
        from backend.services.preview.extraction.social_proof import extract_social_proof

        signals = extract_social_proof(capture.html or "")
        if signals:
            first = signals[0]
            proof = getattr(first, "text", None) or (
                first.get("text") if isinstance(first, dict) else None
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Social proof extraction failed: %s", exc)

    return ReasoningResult(
        title=title[:120],
        subtitle=description[:200] or None,
        description=description[:400],
        tags=[t for t in str(metadata.get("keywords") or "").split(",") if t.strip()][:6],
        proof=proof,
        composition={
            "layout": "typographic",
            "use_visual": False,
            "visual_source": "none",
            "panel_color_role": "primary",
            "accent_moment": "bar",
            "mood": "confident",
        },
        blueprint={"template_type": str(metadata.get("og_type") or "article")},
        # Metadata-derived copy is real but not authored, so it must never
        # outrank an AI read in the quality gate's confidence arithmetic.
        confidence=0.45,
        source=source,
    )
