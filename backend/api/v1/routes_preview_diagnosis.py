"""Phase 2 / Phase 7 — JobTrace diagnosis API.

Internal admin-only endpoints that surface the structured per-job trace
described in ``DEMO_PREVIEW_ENGINE_FINAL_PLAN.md``. The frontend regression
dashboard polls these endpoints to render the metric trend charts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.core.deps import get_admin_user  # type: ignore
from backend.models.user import User  # type: ignore
from backend.services.preview.observability.diagnosis import (
    diagnose,
    diagnose_job,
)
from backend.services.preview.observability.job_trace import JobTraceStore
from backend.services.preview.observability.reason_codes import FailureReason


router = APIRouter(prefix="/preview-diagnosis", tags=["preview-diagnosis"])


class DegradationExplanation(BaseModel):
    code: str
    stage: str
    says: str
    detail: str = ""


class DiagnosisResponse(BaseModel):
    job_id: Optional[str]
    url: Optional[str]
    verdict: str
    terminal_status: Optional[str]
    failure_reason: Optional[str]
    failure_detail: Optional[str]
    lane: Optional[str]
    template: Optional[str]
    palette_source: Optional[str]
    retry_count: int = 0
    extraction_confidence: Optional[float] = None
    quality_subscores: Dict[str, Any] = {}
    visual_quality: Dict[str, Any] = {}
    total_ms: Optional[int] = None
    ai_tokens_total: Optional[int] = None
    ai_call_count: Optional[int] = None
    bottleneck_stage: Optional[Dict[str, Any]] = None
    warnings: List[str] = []

    # The ordered trail of fallbacks and what each one means. This is the
    # answer to "why did this card come out generic?", which a terminal status
    # of "finished" on its own does not give you.
    degradation_trail: str = ""
    degradations: List[Dict[str, Any]] = []
    unhealthy_degradations: List[str] = []
    explanation: List[DegradationExplanation] = []

    # Per-stage latency and spend.
    ai_cost_usd: float = 0.0
    stage_costs: Dict[str, Dict[str, Any]] = {}
    stage_ms: Dict[str, int] = {}
    over_budget_stages: List[str] = []


@router.get("/jobs/{job_id}", response_model=DiagnosisResponse)
def diagnose_job_route(
    job_id: str,
    _admin: User = Depends(get_admin_user),
) -> DiagnosisResponse:
    diag = diagnose_job(job_id)
    if diag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return DiagnosisResponse(**diag)


@router.get("/recent")
def recent_jobs_route(
    limit: int = Query(default=25, ge=1, le=200),
    degraded_only: bool = Query(default=False, description="Only jobs that took a fallback"),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """The last N generations across every worker.

    Reads through the Redis-backed store rather than this process's LRU, so the
    panel sees what the workers actually produced.
    """
    from backend.services.preview.observability.redis_store import recent

    payloads = recent(limit=limit)
    jobs = [diagnose(p) for p in payloads]
    if degraded_only:
        jobs = [j for j in jobs if j.get("unhealthy_degradations")]
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/degradations")
def degradation_taxonomy_route(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """The closed set of degradation codes and what each one means."""
    from backend.services.preview.observability.diagnosis import _EXPLANATIONS
    from backend.services.preview.observability.reason_codes import Degradation

    return {
        "codes": [
            {
                "code": code.value,
                "healthy": code.is_healthy,
                "says": _EXPLANATIONS.get(code.value, ""),
            }
            for code in Degradation
        ]
    }


@router.get("/cost")
def cost_dashboard_route(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Latency and spend per stage, per lane, over the recent window.

    p50/p95 rather than a mean: an average hides the tail, and the tail is what
    blows a budget. Cost is summed from the per-stage attribution the provider
    layer records, so "which stage is expensive?" is answerable without
    instrumenting anything further.
    """
    from backend.services.preview.observability.redis_store import recent

    payloads = recent(limit=limit)
    if not payloads:
        return {"samples": 0, "stages": {}, "lanes": {}, "cost_per_preview_usd": 0.0}

    stage_durations: Dict[str, List[float]] = {}
    stage_cost: Dict[str, float] = {}
    lane_totals: Dict[str, Dict[str, float]] = {}
    total_cost = 0.0

    for payload in payloads:
        lane = payload.get("lane") or "unknown"
        lane_bucket = lane_totals.setdefault(lane, {"count": 0.0, "cost_usd": 0.0, "total_ms": 0.0})
        lane_bucket["count"] += 1
        lane_bucket["cost_usd"] += float(payload.get("ai_cost_usd") or 0.0)
        lane_bucket["total_ms"] += float(payload.get("total_ms") or 0.0)
        total_cost += float(payload.get("ai_cost_usd") or 0.0)

        for timing in payload.get("stage_timings") or []:
            name = timing.get("name") or "unknown"
            stage_durations.setdefault(name, []).append(float(timing.get("duration_ms") or 0.0))
            stage_cost[name] = stage_cost.get(name, 0.0) + float(timing.get("ai_cost_usd") or 0.0)

    def percentile(values: List[float], fraction: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
        return int(ordered[index])

    stages = {
        name: {
            "p50_ms": percentile(values, 0.50),
            "p95_ms": percentile(values, 0.95),
            "max_ms": int(max(values)) if values else 0,
            "samples": len(values),
            "cost_usd": round(stage_cost.get(name, 0.0), 6),
        }
        for name, values in stage_durations.items()
    }
    for bucket in lane_totals.values():
        count = bucket["count"] or 1
        bucket["avg_ms"] = int(bucket["total_ms"] / count)
        bucket["cost_per_preview_usd"] = round(bucket["cost_usd"] / count, 6)

    return {
        "samples": len(payloads),
        "stages": stages,
        "lanes": lane_totals,
        "cost_per_preview_usd": round(total_cost / len(payloads), 6),
        "total_cost_usd": round(total_cost, 4),
    }


@router.get("/failure-reasons")
def failure_reasons_route(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Dict[str, str]]:
    """Stable taxonomy + user-facing copy for the frontend."""
    return {
        reason.value: {
            "user_message": reason.user_message,
            "code": reason.value,
        }
        for reason in FailureReason
    }
