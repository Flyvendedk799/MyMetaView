"""The coordinator.

Every stage is a function from one typed contract to the next; this is the file
that calls them in order and decides what happens when one degrades. It should
be readable start to finish, because the whole point of the decomposition is
that the pipeline *is* the code rather than something you reconstruct by reading
four thousand lines.

    cache → capture → classify → extract ∥ upload → reason → compose → render → grade

The rules it enforces, none of which lived anywhere legible before:

  * every stage has a deadline, clamped to what remains of the total;
  * every fallback records a degradation code, so a finished job carries the
    trail that explains how it finished;
  * degradation means a simpler spec into the *same* renderer, never an older
    renderer;
  * the thing that gets graded is the rendered PNG.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from backend.services.preview.branding import brand_signature, settings_of
from backend.services.preview.budgets import StageBudget
from backend.services.preview.capture.stage import capture_page, upload_screenshot
from backend.services.preview.composition.builder import build_minimal_spec, build_spec
from backend.services.preview.extraction.brand import extract_brand, to_legacy_dict
from backend.services.preview.observability.job_trace import (
    JobTrace,
    JobTraceStore,
    StageTiming,
    new_job_trace,
)
from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    Stage,
    TerminalStatus,
)
from backend.services.preview.quality.pixel_critic import critique_card
from backend.services.preview.quality.policy import SoftPassPolicy, evaluate_card
from backend.services.preview.reasoning.stage import run_reasoning
from backend.services.preview.rendering.renderer import render_card
from backend.services.preview.stages import (
    BrandResult,
    CaptureResult,
    CompositionSpec,
    PageClassification,
    PipelineState,
    ReasoningResult,
    RenderResult,
)

logger = logging.getLogger(__name__)


class _Timed:
    """Context manager that records a stage's timing on the trace.

    Timings were optional before, which meant the ones that mattered — the slow
    stages on the slow jobs — were exactly the ones nobody had numbers for.
    """

    def __init__(self, state: PipelineState, stage: Stage):
        self.state = state
        self.stage = stage
        self.started = 0.0
        self.outputs: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def __enter__(self) -> "_Timed":
        self.started = time.time()
        self.state.trace.open_stage(self.stage)
        return self

    def set(self, key: str, value: Any) -> None:
        self.outputs[key] = value

    def __exit__(self, exc_type, exc, tb) -> bool:
        finished = time.time()
        duration_ms = (finished - self.started) * 1000.0
        timing = StageTiming(
            name=self.stage.value,
            started_at=self.started,
            finished_at=finished,
            duration_ms=round(duration_ms, 2),
            success=exc is None,
            error=f"{exc_type.__name__}: {exc}"[:200] if exc else None,
            outputs=self.outputs,
            budget_ms=round(self.state.budget.for_stage(self.stage) * 1000.0, 2),
        )
        self.state.trace.add_stage(self.state.trace.attach_pending_usage(timing))
        self.state.trace.close_stage()
        self.state.budget.record(self.stage, duration_ms / 1000.0)
        if timing.over_budget:
            self.state.trace.degrade(
                Degradation.BUDGET_STAGE_EXCEEDED, self.stage,
                detail=f"{duration_ms / 1000:.1f}s against a {timing.budget_ms / 1000:.0f}s budget",
            )
        return False  # never swallow


def generate(
    url: str,
    config: Any,
    *,
    cache_key_prefix: str = "preview:engine:",
    profile: Any = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the pipeline for one URL.

    Returns a dict shaped like the legacy engine result plus the trace, so the
    calling engine can build its dataclass without this module importing it —
    which keeps the dependency pointing one way.
    """
    started = time.time()
    trace: JobTrace = new_job_trace(url=url, is_demo=bool(getattr(config, "is_demo", False)),
                                    job_id=job_id)
    budget = StageBudget.for_lane(
        total_s=float(getattr(config, "timeout_seconds", 0) or 0) or None,
    )
    state = PipelineState(
        url=url,
        config=config,
        trace=trace,
        budget=budget,
        progress=getattr(config, "progress_callback", None),
        lane_prefix=cache_key_prefix,
    )
    state.shared["profile"] = profile

    try:
        payload = _run(state, started, cache_key_prefix)
        trace.finalize_success()
        JobTraceStore.get_instance().save(trace)
        payload["_trace"] = trace.to_dict()
        return payload
    except Exception as exc:
        detail = str(exc)
        trace.finalize_failure(_reason_for(detail, trace), detail=detail)
        JobTraceStore.get_instance().save(trace)
        logger.error("Preview pipeline failed for %s: %s", url, detail, exc_info=True)
        raise


def _run(state: PipelineState, started: float, cache_key_prefix: str) -> Dict[str, Any]:
    # ---- cache ---------------------------------------------------------
    if getattr(state.config, "enable_cache", True):
        with _Timed(state, Stage.CACHE) as timing:
            cached = _read_cache(state, cache_key_prefix)
            timing.set("hit", cached is not None)
            timing.set("brand", _brand_signature(state))
        if cached is not None:
            state.trace.degrade(Degradation.RESULT_CACHE_HIT, Stage.CACHE,
                                detail="served from the result cache")
            state.update_progress(1.0, "Preview loaded from cache")
            cached["_from_cache"] = True
            return cached
        state.trace.degrade(Degradation.RESULT_CACHE_MISS, Stage.CACHE)

    # ---- capture -------------------------------------------------------
    with _Timed(state, Stage.CAPTURE) as timing:
        capture = capture_page(state)
        timing.set("html_len", len(capture.html))
        timing.set("screenshot_bytes", len(capture.screenshot_bytes))
        timing.set("provider", capture.provider)

    # ---- classify ------------------------------------------------------
    with _Timed(state, Stage.CLASSIFY) as timing:
        classification = _classify(state, capture)
        timing.set("category", classification.category)
        timing.set("confidence", classification.confidence)

    # ---- extraction (brand ∥ screenshot upload) ------------------------
    with _Timed(state, Stage.EXTRACTION) as timing:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="pv-extract") as pool:
            upload_future = pool.submit(upload_screenshot, state, capture)
            brand_future = pool.submit(extract_brand, state, capture)
            brand = _settle(brand_future, BrandResult(), "brand extraction")
            capture.screenshot_url = _settle(upload_future, None, "screenshot upload")
        timing.set("brand_name", brand.brand_name)
        timing.set("has_logo", brand.has_logo)
        timing.set("palette_source", brand.palette_source.value)

    # ---- reasoning -----------------------------------------------------
    with _Timed(state, Stage.REASONING) as timing:
        reasoning = run_reasoning(state, capture, classification)
        timing.set("source", reasoning.source)
        timing.set("confidence", reasoning.confidence)
        timing.set("layout_requested", reasoning.composition.get("layout"))

    # ---- composition + render + grade, with bounded retries ------------
    render, spec, verdict = _render_and_grade(state, capture, brand, reasoning)

    # ---- assemble ------------------------------------------------------
    with _Timed(state, Stage.PERSIST):
        payload = _assemble(state, started, capture, brand, reasoning,
                            spec, render, verdict, classification)
        if getattr(state.config, "enable_cache", True) and render.ok:
            _write_cache(state, cache_key_prefix, payload)

    state.update_progress(1.0, "Preview generation complete!")
    return payload


def _render_and_grade(
    state: PipelineState,
    capture: CaptureResult,
    brand: BrandResult,
    reasoning: ReasoningResult,
):
    """Compose, render, and grade the PNG — retrying while budget allows.

    The retry loop is bounded by *both* the profile's iteration count and the
    remaining wall-clock budget, because a quality loop that outlives its
    deadline ships nothing at all.
    """
    profile = state.shared.get("profile")
    policy = SoftPassPolicy.from_profile(profile) if profile else SoftPassPolicy(
        threshold=float(getattr(state.config, "quality_threshold", 0.80)),
        allow_soft_pass=bool(getattr(state.config, "allow_soft_pass", True)),
        min_soft_pass_overall=float(getattr(state.config, "min_soft_pass_overall", 0.60)),
        enforce_target_quality=bool(getattr(state.config, "enforce_target_quality", False)),
    )
    max_attempts = max(1, int(getattr(state.config, "max_quality_iterations", 2)))
    expected_colors = [
        c for c in (
            (brand.colors or {}).get("primary_color"),
            (brand.colors or {}).get("secondary_color"),
        ) if c
    ]

    spec: Optional[CompositionSpec] = None
    render = RenderResult()
    verdict = None

    for attempt in range(max_attempts):
        with _Timed(state, Stage.COMPOSITION):
            spec = build_spec(state, capture, brand, reasoning)

        with _Timed(state, Stage.RENDER):
            render = render_card(state, spec)

        if not render.ok:
            break

        with _Timed(state, Stage.QUALITY) as timing:
            attempts_left = max_attempts - attempt - 1
            if state.budget.remaining() < 15.0:
                attempts_left = 0  # no room to try again even if we wanted to
            verdict = evaluate_card(
                render.png,
                policy=policy,
                expected_colors=expected_colors,
                expect_logo=brand.has_logo,
                # The layout that actually rendered — a split card's panel
                # bleeds to the edge by design, and scoring that as overflow
                # would fail a perfectly good card.
                layout=render.rendered_layout,
                attempts_left=attempts_left,
                trace=state.trace,
            )
            timing.set("decision", verdict.decision)
            timing.set("overall", verdict.score.overall)

            # The critic only weighs in on cards the metrics already accepted;
            # a card that fails on contrast does not need a second opinion.
            if verdict.shippable and attempt == 0:
                critique = critique_card(
                    render.png, url=state.url,
                    brand_name=brand.brand_name, state=state,
                )
                if critique.ran:
                    state.trace.quality_subscores.update({
                        "critic_readability": critique.readability,
                        "critic_balance": critique.balance,
                        "critic_brand_match": critique.brand_match,
                    })
                    timing.set("critic_verdict", critique.verdict)
                    if critique.rejects and attempts_left > 0:
                        verdict.decision = "retry"
                        verdict.reasons.extend(critique.issues)

        if verdict.shippable:
            break

        if verdict.decision == "reject":
            break

        state.trace.retry_count = attempt + 1
        reasoning = _strengthen(reasoning, capture, verdict)

    # A card the grader rejected outright is worse than the deterministic
    # minimal one, which is correct by construction. This is the only fallback
    # in the engine and it goes through the same renderer.
    if not render.ok or (verdict is not None and verdict.decision == "reject"):
        minimal = build_minimal_spec(state, capture, brand, title=reasoning.title or None)
        with _Timed(state, Stage.RENDER):
            fallback = render_card(state, minimal)
        if fallback.ok:
            state.trace.degrade(
                Degradation.QUALITY_FALLBACK_CARD, Stage.QUALITY,
                detail="shipped the deterministic minimal card",
                reason=FailureReason.QUALITY_GATE_FAILED,
            )
            # Grade it too. The fallback is correct by construction, but
            # "correct by construction" is what the premium renderer was also
            # assumed to be — and shipping an ungraded card is the practice this
            # whole phase exists to end.
            with _Timed(state, Stage.QUALITY) as timing:
                fallback_verdict = evaluate_card(
                    fallback.png,
                    policy=policy,
                    expected_colors=expected_colors,
                    expect_logo=bool(minimal.logo_data_uri),
                    layout=fallback.rendered_layout,
                    attempts_left=0,
                    trace=state.trace,
                )
                timing.set("decision", fallback_verdict.decision)
                timing.set("overall", fallback_verdict.score.overall)
            return fallback, minimal, fallback_verdict
        if not render.ok:
            raise ValueError(
                f"Could not render a card for {state.url}: "
                f"{render.error or 'unknown'} (minimal spec also failed: {fallback.error})"
            )

    return render, spec, verdict


def _strengthen(
    reasoning: ReasoningResult,
    capture: CaptureResult,
    verdict: Any,
) -> ReasoningResult:
    """Change something before retrying.

    A retry that re-renders identical inputs produces an identical card and
    wastes the budget — the old engine did exactly that and then detected the
    non-improvement afterwards. Here the retry only happens alongside a concrete
    change, driven by what the grader complained about.
    """
    issues = " ".join(verdict.reasons).lower() if verdict else ""

    if "contrast" in issues:
        # Push the panel to the role with the most headroom for text.
        composition = dict(reasoning.composition)
        current = composition.get("panel_color_role", "primary")
        composition["panel_color_role"] = "dark" if current != "dark" else "light"
        reasoning.composition = composition

    if "overflow" in issues or "truncat" in issues:
        # Shorter copy is the fix for copy that did not fit.
        if reasoning.title and len(reasoning.title) > 48:
            reasoning.title = reasoning.title[:46].rsplit(" ", 1)[0]
        if reasoning.subtitle and len(reasoning.subtitle) > 90:
            reasoning.subtitle = reasoning.subtitle[:88].rsplit(" ", 1)[0]

    if "gradient" in issues:
        # A card with no readable content came out of a layout that expected a
        # visual it never got; typographic always has something to draw.
        composition = dict(reasoning.composition)
        composition["layout"] = "typographic"
        composition["use_visual"] = False
        reasoning.composition = composition

    return reasoning


# ---------------------------------------------------------------------------
# Supporting steps
# ---------------------------------------------------------------------------

def _classify(state: PipelineState, capture: CaptureResult) -> PageClassification:
    try:
        from backend.services.intelligent_page_classifier import get_page_classifier

        classified = get_page_classifier().classify(
            state.url, capture.html, capture.screenshot_bytes or None
        )
        return PageClassification(
            category=classified.primary_category.value,
            confidence=float(classified.confidence or 0.0),
            strategy=dict(getattr(classified, "preview_strategy", None) or {}),
            reasoning=str(getattr(classified, "reasoning", "") or ""),
        )
    except Exception as exc:  # noqa: BLE001 — classification is advisory
        logger.info("Page classification unavailable: %s", exc)
        return PageClassification()


def _settle(future, default, label: str):
    try:
        return future.result()
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", label, exc)
        return default


def _assemble(
    state: PipelineState,
    started: float,
    capture: CaptureResult,
    brand: BrandResult,
    reasoning: ReasoningResult,
    spec: Optional[CompositionSpec],
    render: RenderResult,
    verdict: Any,
    classification: PageClassification,
) -> Dict[str, Any]:
    """The result payload, in the shape the rest of the app already consumes."""
    trace = state.trace
    scores = verdict.score if verdict else None

    quality_scores: Dict[str, Any] = {
        "overall": scores.overall if scores else 0.0,
        "visual": scores.overall if scores else 0.0,
        "contrast": scores.title_contrast if scores else 0.0,
        "gate_status": verdict.decision if verdict else "unknown",
        "quality_level": _level(scores.overall if scores else 0.0),
        "is_fallback": bool(render.minimal),
    }
    quality_scores["debug"] = {
        "request_id": trace.job_id,
        "degradations": trace.degradation_codes(),
        "degradation_trail": trace.degradation_trail(),
        "unhealthy": trace.unhealthy_degradations(),
        "final_decision": verdict.decision if verdict else "unknown",
        "retry_attempts_used": trace.retry_count,
        "pixel_score": scores.to_dict() if scores else {},
        "stage_ms": {t.name: t.duration_ms for t in trace.stage_timings},
        "ai_cost_usd": round(trace.ai_cost_usd, 6),
        "ai_calls": trace.ai_call_count,
        "budget": state.budget.summary(),
    }

    blueprint = dict(reasoning.blueprint or {})
    blueprint.setdefault("template_type", classification.category or "article")
    for key, value in (spec.colors if spec else {}).items():
        blueprint.setdefault(key, value)

    return {
        "url": state.url,
        "title": (spec.title if spec else reasoning.title) or reasoning.title,
        "subtitle": spec.subtitle if spec else reasoning.subtitle,
        "description": reasoning.description,
        "tags": list(reasoning.tags),
        "screenshot_url": capture.screenshot_url,
        "composited_preview_image_url": render.image_url,
        "brand": to_legacy_dict(brand),
        "blueprint": blueprint,
        "context_items": list(reasoning.context_items),
        "credibility_items": list(reasoning.credibility_items),
        "cta_text": reasoning.cta_text,
        "reasoning_confidence": reasoning.confidence,
        "processing_time_ms": int((time.time() - started) * 1000),
        "is_demo": state.is_demo,
        "message": _message(verdict, render),
        "quality_scores": quality_scores,
        "design_fidelity_score": scores.overall if scores else None,
        "warnings": list(verdict.reasons) if verdict and not verdict.shippable else [],
        "variants": list(reasoning.variants),
        "render_spec": dict(render.render_spec),
        "rendered_layout": render.rendered_layout,
        "ui_elements": {},
        "dom_data": dict(capture.dom_data or {}),
    }


def _level(overall: float) -> str:
    if overall >= 0.85:
        return "excellent"
    if overall >= 0.70:
        return "good"
    if overall >= 0.55:
        return "fair"
    return "poor"


def _message(verdict: Any, render: RenderResult) -> str:
    if render.minimal:
        return "Preview generated from the page's own metadata."
    if verdict and verdict.decision == "soft_pass":
        return "Preview generated; quality below target but shippable."
    return "Preview generated successfully."


def _reason_for(detail: str, trace: JobTrace) -> FailureReason:
    """Pick the terminal reason code, preferring one a stage already recorded.

    A degradation that carried a reason knows more than a regex over the
    exception string, which is what the engine used to rely on entirely.
    """
    for event in reversed(trace.degradations):
        if event.reason is not None:
            return event.reason

    message = (detail or "").lower()
    if "refusing to capture" in message:
        return FailureReason.CAPTURE_BLOCKED
    if "rate limit" in message or "429" in message:
        return FailureReason.EXTRACTION_AI_RATE_LIMIT
    if "timeout" in message or "timed out" in message:
        return FailureReason.CAPTURE_TIMEOUT
    if "render" in message:
        return FailureReason.RENDER_IMAGE_PIPELINE_ERROR
    if "capture" in message:
        return FailureReason.CAPTURE_NETWORK_ERROR
    return FailureReason.UNKNOWN


# ---------------------------------------------------------------------------
# Result cache
# ---------------------------------------------------------------------------

def _brand_signature(state: PipelineState) -> str:
    """Which branding this generation is running with."""
    return brand_signature(settings_of(state.config))


def _read_cache(state: PipelineState, prefix: str) -> Optional[Dict[str, Any]]:
    """A cached card, but only one generated for *this* branding.

    Result entries are keyed by URL alone, which was fine while every card for a
    URL looked the same. Once the customer's own colours, mark, font and layout
    preferences reach the renderer they no longer do: the same URL under a
    different brand is a different card, and serving the stored one hands a
    customer somebody else's identity — or their own, from before they changed
    it. The signature travels with the payload, so a mismatch is a miss.
    """
    try:
        import json

        from backend.services.preview_cache import generate_cache_key, get_redis_client

        client = get_redis_client()
        if client is None:
            return None
        raw = client.get(generate_cache_key(state.url, prefix))
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        cached_brand = str(payload.get("brand_signature") or "none")
        if cached_brand != _brand_signature(state):
            state.trace.degrade(
                Degradation.RESULT_CACHE_BRAND_CHANGED, Stage.CACHE,
                detail="cached card was generated with different branding",
            )
            return None
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.debug("Result cache read failed: %s", exc)
        return None


def _write_cache(state: PipelineState, prefix: str, payload: Dict[str, Any]) -> None:
    try:
        import json

        from backend.services.preview_cache import (
            CacheConfig,
            generate_cache_key,
            get_redis_client,
        )

        client = get_redis_client()
        if client is None:
            return
        ttl_hours = CacheConfig.DEMO_TTL_HOURS if state.is_demo else CacheConfig.DEFAULT_TTL_HOURS
        body = {k: v for k, v in payload.items() if not k.startswith("_")}
        body["brand_signature"] = _brand_signature(state)
        client.setex(
            generate_cache_key(state.url, prefix),
            int(ttl_hours) * 3600,
            json.dumps(body, default=str),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Result cache write failed: %s", exc)
