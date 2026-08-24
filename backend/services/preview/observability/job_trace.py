"""Structured per-job trace object.

Implements the trace schema from Phase 2 of the plan:

    job_id, url, start_ts, end_ts
    stage timings (capture/classify/extract/analyze/compose/quality)
    extraction confidence and quality-gate sub-scores
    template selected + rationale
    palette source (sampled, derived, default)
    retry_count + retry_deltas
    terminal status + reason code

The store is in-memory (LRU) by default; callers can plug in Redis or any
KV store via ``JobTraceStore.set_backend(...)``. The point is that every
trace is queryable for the developer "job diagnosis" utility called out by
the plan and for the nightly regression dashboard (Phase 7).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    PaletteSource,
    PreviewLane,
    Stage,
    TerminalStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage timing
# ---------------------------------------------------------------------------


@dataclass
class StageTiming:
    """Single stage measurement embedded in the JobTrace.

    Timings were already here; the token/cost fields are what make
    "cost per preview, broken down by stage" answerable. They are populated by
    the provider layer through ``JobTrace.record_ai_usage``, which attributes
    spend to whichever stage is open.
    """

    name: str
    started_at: float
    finished_at: float
    duration_ms: float
    success: bool = True
    skipped: bool = False
    error: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)

    # Per-stage AI accounting (Phase 0.3)
    ai_calls: int = 0
    ai_tokens_input: int = 0
    ai_tokens_output: int = 0
    ai_cost_usd: float = 0.0
    # Budget accounting (Phase 2.1)
    budget_ms: Optional[float] = None

    @property
    def over_budget(self) -> bool:
        return self.budget_ms is not None and self.duration_ms > self.budget_ms


@dataclass
class DegradationEvent:
    """One step down from the ideal path, in the order it happened.

    ``detail`` is the sentence a human reads in the admin "why" view, so keep
    it concrete ("logo was 18x18 after crop") rather than restating the code.
    """

    code: Degradation
    stage: Stage
    at: float = field(default_factory=time.time)
    detail: Optional[str] = None
    reason: Optional[FailureReason] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "stage": self.stage.value,
            "at": self.at,
            "detail": self.detail,
            "reason": self.reason.value if self.reason else None,
            "healthy": self.code.is_healthy,
        }


@dataclass
class RetryDelta:
    """Diff between two retry attempts (Phase 1 invariant)."""

    attempt: int
    changed_fields: List[str]
    overall_score: Optional[float] = None
    suggestions: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# JobTrace
# ---------------------------------------------------------------------------


@dataclass
class JobTrace:
    """Trace for a single preview generation job (Phase 2 schema)."""

    job_id: str = field(default_factory=lambda: str(uuid4()))
    url: str = ""
    start_ts: float = field(default_factory=time.time)
    end_ts: Optional[float] = None
    is_demo: bool = False
    lane: Optional[PreviewLane] = None

    # Stage timings, keyed by stage name for O(1) lookup, list preserves order.
    stage_timings: List[StageTiming] = field(default_factory=list)

    # Quality + extraction signals
    extraction_confidence: Optional[float] = None
    quality_subscores: Dict[str, float] = field(default_factory=dict)
    visual_quality: Dict[str, float] = field(default_factory=dict)

    # Template + palette provenance
    template_selected: Optional[str] = None
    template_rationale: Optional[str] = None
    palette_source: Optional[PaletteSource] = None

    # Retry audit
    retry_count: int = 0
    retry_deltas: List[RetryDelta] = field(default_factory=list)

    # Ordered trail of every fallback the job took (Phase 0.1). This is the
    # answer to "why did this card come out generic?" — a finished job with a
    # healthy trail and a finished job that limped through five fallbacks are
    # indistinguishable without it.
    degradations: List[DegradationEvent] = field(default_factory=list)

    # Which stage is currently open, so AI spend recorded by the provider layer
    # lands on the right stage without every call site passing it.
    _open_stage: Optional[str] = None

    # Terminal status
    terminal_status: Optional[TerminalStatus] = None
    failure_reason: Optional[FailureReason] = None
    failure_detail: Optional[str] = None

    # Token / cost accounting (Phase 6, per-stage in Phase 0.3)
    ai_tokens_input: int = 0
    ai_tokens_output: int = 0
    ai_call_count: int = 0
    ai_cost_usd: float = 0.0

    # Free-form notes (kept short)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    # Usage recorded before its stage closed; folded in by attach_pending_usage.
    _pending_usage: List[Any] = field(default_factory=list)

    # ---- mutators -------------------------------------------------------

    def add_stage(self, timing: StageTiming) -> None:
        self.stage_timings.append(timing)

    def open_stage(self, stage: "Stage | str") -> None:
        """Mark a stage as running so AI spend is attributed to it."""
        self._open_stage = stage.value if isinstance(stage, Stage) else str(stage)

    def close_stage(self) -> None:
        self._open_stage = None

    def degrade(
        self,
        code: Degradation,
        stage: Stage,
        detail: Optional[str] = None,
        reason: Optional[FailureReason] = None,
    ) -> None:
        """Record one step down from the ideal path.

        Cheap by design — it is called from every fallback branch in the engine,
        including the ones on the happy path, so the trail reads as a story
        rather than a list of complaints.
        """
        self.degradations.append(
            DegradationEvent(code=code, stage=stage,
                             detail=(detail or None) and str(detail)[:240],
                             reason=reason)
        )

    def degradation_codes(self) -> List[str]:
        """The trail as a flat, ordered list of codes."""
        return [d.code.value for d in self.degradations]

    def degradation_trail(self) -> str:
        """Human-readable trail: ``capture_ok → brand_logo_fallback_favicon → …``"""
        return " → ".join(self.degradation_codes())

    def unhealthy_degradations(self) -> List[str]:
        """Only the codes that mean something went less than perfectly."""
        return [d.code.value for d in self.degradations if not d.code.is_healthy]

    def add_retry(self, delta: RetryDelta) -> None:
        self.retry_count = max(self.retry_count, delta.attempt)
        self.retry_deltas.append(delta)

    def record_ai_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        stage: Optional[str] = None,
    ) -> None:
        """Attribute one model call to the job and to a stage.

        ``stage`` defaults to whichever stage is open, which is why call sites
        deep inside the reasoning code do not have to thread it through.
        """
        self.ai_tokens_input += int(input_tokens or 0)
        self.ai_tokens_output += int(output_tokens or 0)
        self.ai_cost_usd += float(cost_usd or 0.0)
        self.ai_call_count += 1

        target = stage or self._open_stage
        if not target:
            return
        for timing in reversed(self.stage_timings):
            if timing.name == target:
                timing.ai_calls += 1
                timing.ai_tokens_input += int(input_tokens or 0)
                timing.ai_tokens_output += int(output_tokens or 0)
                timing.ai_cost_usd += float(cost_usd or 0.0)
                return
        # The stage has not been closed yet (timings are appended on exit), so
        # park the usage and let ``attach_pending_usage`` fold it in.
        self._pending_usage.append(
            (target, int(input_tokens or 0), int(output_tokens or 0), float(cost_usd or 0.0))
        )

    def attach_pending_usage(self, timing: StageTiming) -> StageTiming:
        """Fold usage recorded while ``timing``'s stage was still open into it."""
        remaining = []
        for stage_name, tin, tout, cost in self._pending_usage:
            if stage_name == timing.name:
                timing.ai_calls += 1
                timing.ai_tokens_input += tin
                timing.ai_tokens_output += tout
                timing.ai_cost_usd += cost
            else:
                remaining.append((stage_name, tin, tout, cost))
        self._pending_usage = remaining
        return timing

    def finalize_success(self) -> None:
        self.end_ts = time.time()
        self.terminal_status = TerminalStatus.FINISHED

    def finalize_failure(
        self,
        reason: FailureReason,
        detail: Optional[str] = None,
    ) -> None:
        self.end_ts = time.time()
        self.terminal_status = TerminalStatus.FAILED
        self.failure_reason = reason
        if detail:
            self.failure_detail = detail[:500]

    # ---- accessors ------------------------------------------------------

    @property
    def total_ms(self) -> int:
        end = self.end_ts or time.time()
        return int((end - self.start_ts) * 1000)

    def stage_lookup(self) -> Dict[str, StageTiming]:
        return {t.name: t for t in self.stage_timings}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Private bookkeeping never leaves the object.
        d.pop("_open_stage", None)
        d.pop("_pending_usage", None)
        d["degradations"] = [event.to_dict() for event in self.degradations]
        d["degradation_trail"] = self.degradation_trail()
        d["unhealthy_degradations"] = self.unhealthy_degradations()
        # Enum serialization
        if self.lane:
            d["lane"] = self.lane.value
        if self.palette_source:
            d["palette_source"] = self.palette_source.value
        if self.terminal_status:
            d["terminal_status"] = self.terminal_status.value
        if self.failure_reason:
            d["failure_reason"] = self.failure_reason.value
        d["total_ms"] = self.total_ms
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


# ---------------------------------------------------------------------------
# Pluggable store
# ---------------------------------------------------------------------------


class _LRUStore:
    """Simple thread-safe LRU used as the default backend."""

    def __init__(self, max_entries: int = 1024):
        self._max = max_entries
        self._data: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def put(self, job_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._data[job_id] = payload
            self._data.move_to_end(job_id)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            payload = self._data.get(job_id)
            if payload:
                self._data.move_to_end(job_id)
            return payload

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._data.values())[-limit:]
            return list(reversed(items))


class JobTraceStore:
    """Persists and reads JobTrace objects.

    Default backend is an in-process LRU. Production callers can wire a
    Redis or BigQuery sink by providing a ``writer`` callable that accepts a
    ``Dict[str, Any]`` payload. The store still keeps the LRU mirror so the
    in-process diagnosis tool keeps working.
    """

    _instance: Optional["JobTraceStore"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._lru = _LRUStore()
        self._writer: Optional[Callable[[Dict[str, Any]], None]] = None
        self._reader: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None

    @classmethod
    def get_instance(cls) -> "JobTraceStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_backend(
        self,
        writer: Optional[Callable[[Dict[str, Any]], None]] = None,
        reader: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self._writer = writer
        self._reader = reader

    def save(self, trace: JobTrace) -> None:
        payload = trace.to_dict()
        self._lru.put(trace.job_id, payload)
        if self._writer is not None:
            try:
                self._writer(payload)
            except Exception as exc:  # noqa: BLE001 — never crash the pipeline
                logger.warning("JobTrace external writer failed: %s", exc)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self._reader is not None:
            try:
                payload = self._reader(job_id)
                if payload is not None:
                    return payload
            except Exception as exc:  # noqa: BLE001
                logger.warning("JobTrace external reader failed: %s", exc)
        return self._lru.get(job_id)

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._lru.list_recent(limit=limit)


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def new_job_trace(
    url: str,
    is_demo: bool = False,
    job_id: Optional[str] = None,
    lane: Optional[PreviewLane] = None,
) -> JobTrace:
    """Create a JobTrace with sensible defaults."""
    trace = JobTrace(url=url, is_demo=is_demo, lane=lane)
    if job_id:
        trace.job_id = job_id
    return trace
