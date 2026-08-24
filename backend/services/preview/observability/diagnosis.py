"""Developer-facing job diagnosis utility.

The plan exit gate for Phase 2 is:
"Any bad preview can be root-caused in <2 minutes from traces."

This module renders a JobTrace into a compact, human-readable diagnosis with
an explicit verdict (success / fallback / fail) and the smallest set of
signals needed to triage. The same data is exposed via API in
``backend/api/v1/preview_diagnosis.py`` (Phase 7).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.preview.observability.job_trace import (
    JobTrace,
    JobTraceStore,
)
from backend.services.preview.observability.reason_codes import (
    FailureReason,
    TerminalStatus,
)


def diagnose(trace_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a trace payload to a triage view."""
    if not trace_payload:
        return {"verdict": "unknown", "reason": "trace_not_found"}

    terminal = trace_payload.get("terminal_status")
    failure_reason = trace_payload.get("failure_reason")
    retry_count = int(trace_payload.get("retry_count") or 0)
    palette_source = trace_payload.get("palette_source")
    template = trace_payload.get("template_selected")
    extraction_conf = trace_payload.get("extraction_confidence")
    quality = trace_payload.get("quality_subscores") or {}
    visual = trace_payload.get("visual_quality") or {}
    stages = trace_payload.get("stage_timings") or []

    if terminal == TerminalStatus.FINISHED.value and not failure_reason:
        verdict = "success"
    elif failure_reason and failure_reason != FailureReason.UNKNOWN.value:
        verdict = "fallback" if terminal == TerminalStatus.FINISHED.value else "fail"
    else:
        verdict = "unknown"

    bottleneck = _identify_bottleneck(stages)
    degradations = trace_payload.get("degradations") or []
    unhealthy = trace_payload.get("unhealthy_degradations") or []

    # A finished job that limped through five fallbacks and one that sailed
    # through are the same "success" without this. The trail is the answer to
    # the question support actually asks, which is not "did it fail?" but "why
    # does this card look generic?".
    if verdict == "success" and unhealthy:
        verdict = "degraded"

    return {
        "job_id": trace_payload.get("job_id"),
        "url": trace_payload.get("url"),
        "verdict": verdict,
        "terminal_status": terminal,
        "failure_reason": failure_reason,
        "failure_detail": trace_payload.get("failure_detail"),
        "lane": trace_payload.get("lane"),
        "template": template,
        "palette_source": palette_source,
        "retry_count": retry_count,
        "extraction_confidence": extraction_conf,
        "quality_subscores": quality,
        "visual_quality": visual,
        "total_ms": trace_payload.get("total_ms"),
        "ai_tokens_total": int(trace_payload.get("ai_tokens_input", 0))
                           + int(trace_payload.get("ai_tokens_output", 0)),
        "ai_call_count": trace_payload.get("ai_call_count"),
        "bottleneck_stage": bottleneck,
        "warnings": trace_payload.get("warnings") or [],
        "degradation_trail": trace_payload.get("degradation_trail") or "",
        "degradations": degradations,
        "unhealthy_degradations": unhealthy,
        "explanation": explain(degradations),
        "ai_cost_usd": round(float(trace_payload.get("ai_cost_usd") or 0.0), 6),
        "stage_costs": _stage_costs(stages),
        "stage_ms": {s.get("name"): int(s.get("duration_ms") or 0) for s in stages},
        "over_budget_stages": [
            s.get("name") for s in stages
            if s.get("budget_ms") and float(s.get("duration_ms") or 0) > float(s["budget_ms"])
        ],
    }


# What each degradation means, in the words an operator would use. Keyed by
# code so the admin panel renders a sentence rather than a slug.
_EXPLANATIONS: Dict[str, str] = {
    "capture_hedged_to_api": "The browser was slow, so the screenshot API answered instead.",
    "capture_html_only": "No screenshot — the card was built from the page's markup.",
    "capture_screenshot_missing": "The page rendered no usable screenshot.",
    "capture_circuit_open": "This domain has failed repeatedly; capture was skipped.",
    "capture_placeholder": "The page could not be captured at all.",
    "brand_extraction_failed": "The page's brand identity could not be read.",
    "brand_logo_fallback_favicon": "No header logo — the favicon was used instead.",
    "brand_logo_fallback_screenshot": "The logo was cropped out of the screenshot.",
    "brand_logo_svg_skipped": "The logo is an SVG and no rasterizer is installed.",
    "brand_logo_none": "No usable logo was found; the card shows the text wordmark.",
    "brand_colors_default": "No dominant brand color; a neutral palette was used.",
    "reasoning_skipped_template_lane": "Template lane — the card uses the page's own metadata.",
    "reasoning_fallback_html": "The art director was unavailable; the page's og: tags were used.",
    "reasoning_timeout": "The art director ran past its deadline.",
    "reasoning_schema_repaired": "The model's output needed repairing before use.",
    "composition_layout_degraded": "The requested layout needed an asset that was missing.",
    "composition_focal_crop_rejected": "The hero crop looked like page chrome, so no panel was used.",
    "composition_focal_crop_failed": "The hero crop could not be taken.",
    "composition_logo_panel_contrast_fix": "The logo would not have been visible; the panel was adjusted.",
    "composition_logo_dropped_unusable": "The logo read as a smudge at card size; the wordmark was used.",
    "composition_minimal_spec": "The card was built from title, palette and wordmark only.",
    "premium_render_minimal_spec": "The card was rendered from the deterministic minimal spec.",
    "premium_render_failed": "The renderer could not produce a card.",
    "render_upload_failed": "The card rendered but could not be stored.",
    "quality_soft_pass": "Quality was below target but the card is shippable.",
    "quality_retry": "The first card was rejected and regenerated.",
    "quality_pixel_critic_fail": "The visual critic flagged problems with the card.",
    "quality_fallback_card": "Quality gates rejected the card; the minimal one shipped.",
    "budget_stage_exceeded": "A stage ran past its time budget and degraded.",
    "budget_total_exceeded": "The generation ran out of time.",
}


def explain(degradations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Turn the trail into sentences, keeping only what went less than perfectly."""
    out: List[Dict[str, str]] = []
    for event in degradations:
        code = event.get("code")
        if event.get("healthy") or code not in _EXPLANATIONS:
            continue
        out.append({
            "code": code,
            "stage": event.get("stage", ""),
            "says": _EXPLANATIONS[code],
            "detail": event.get("detail") or "",
        })
    return out


def _stage_costs(stages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-stage AI spend — the breakdown behind cost-per-preview."""
    return {
        s.get("name"): {
            "usd": round(float(s.get("ai_cost_usd") or 0.0), 6),
            "calls": int(s.get("ai_calls") or 0),
            "tokens_in": int(s.get("ai_tokens_input") or 0),
            "tokens_out": int(s.get("ai_tokens_output") or 0),
        }
        for s in stages
        if float(s.get("ai_cost_usd") or 0.0) > 0 or int(s.get("ai_calls") or 0) > 0
    }


def _identify_bottleneck(stages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stages:
        return None
    slowest = max(stages, key=lambda s: float(s.get("duration_ms") or 0))
    return {
        "name": slowest.get("name"),
        "duration_ms": int(slowest.get("duration_ms") or 0),
        "success": slowest.get("success", True),
    }


def diagnose_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Look up a job in the store and return its diagnosis."""
    payload = JobTraceStore.get_instance().get(job_id)
    if not payload:
        return None
    return diagnose(payload)


def diagnose_trace(trace: JobTrace) -> Dict[str, Any]:
    return diagnose(trace.to_dict())
