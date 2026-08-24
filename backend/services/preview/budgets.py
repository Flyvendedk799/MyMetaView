"""Per-stage deadline budgets.

The engine used to carry one number: 600 seconds for the whole generation. That
is not a budget, it is a hang detector — a capture that stalls on a hostile page
burns ten minutes of an RQ worker before anything notices, and the stages that
would have degraded gracefully never get the chance because there is no
deadline to trip.

A budget per stage fixes both ends. Each stage gets the time it should
plausibly need; blowing it emits ``BUDGET_STAGE_EXCEEDED`` and degrades that
stage rather than the job. The remaining stages inherit whatever is left of the
total, so a slow-but-successful capture eats into the quality loop's iterations
instead of pushing the whole job past its deadline.

    capture 20s · extraction 15s · reasoning 60s · render 30s
    quality loop: whatever remains

``StageBudget.remaining()`` is what the quality loop asks before deciding it has
room for another iteration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    PreviewLane,
    Stage,
)

logger = logging.getLogger(__name__)


class StageDeadlineExceeded(TimeoutError):
    """A stage ran past its deadline.

    Carries the stage so the caller can degrade precisely rather than
    string-matching a timeout message.
    """

    def __init__(self, stage: Stage, budget_s: float, elapsed_s: float):
        self.stage = stage
        self.budget_s = budget_s
        self.elapsed_s = elapsed_s
        super().__init__(
            f"{stage.value} exceeded its {budget_s:.0f}s budget ({elapsed_s:.1f}s elapsed)"
        )


# The roadmap's numbers. Capture and render are wall-clock bound by an external
# process (Chromium); reasoning is bound by the model; extraction is mostly
# network. The quality loop deliberately has no fixed budget — it gets the
# remainder, which is the honest way to say "iterate if there is time".
DEFAULT_STAGE_BUDGETS: Dict[Stage, float] = {
    Stage.CACHE: 3.0,
    Stage.CAPTURE: 20.0,
    Stage.CLASSIFY: 8.0,
    Stage.EXTRACTION: 15.0,
    Stage.REASONING: 60.0,
    Stage.COMPOSITION: 15.0,
    Stage.RENDER: 30.0,
    Stage.QUALITY: 45.0,
    Stage.UPLOAD: 20.0,
    Stage.PERSIST: 10.0,
}

# The fast lane exists to answer quickly; halving the model-bound stages is what
# makes it fast, and the quality of a fast-lane card reflects that trade.
FAST_LANE_SCALE = 0.6
DEEP_LANE_SCALE = 1.0

# Total wall clock for one generation. Sized so that every stage can take its
# full budget and still leave the quality loop room for one iteration.
DEFAULT_TOTAL_BUDGET_S = 240.0


@dataclass
class StageBudget:
    """Deadline bookkeeping for one generation.

    Not a timeout mechanism — Python cannot interrupt a blocking call from the
    outside without threads — but a deadline *oracle*: stages ask whether they
    still have room, and long-running work is wrapped in ``run_with_deadline``
    which does use a worker thread.
    """

    total_s: float = DEFAULT_TOTAL_BUDGET_S
    stage_budgets: Dict[Stage, float] = field(
        default_factory=lambda: dict(DEFAULT_STAGE_BUDGETS)
    )
    started_at: float = field(default_factory=time.monotonic)
    spent: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def for_lane(
        cls,
        lane: Optional[PreviewLane] = None,
        total_s: Optional[float] = None,
    ) -> "StageBudget":
        scale = FAST_LANE_SCALE if lane == PreviewLane.FAST else DEEP_LANE_SCALE
        budgets = {stage: seconds * scale for stage, seconds in DEFAULT_STAGE_BUDGETS.items()}
        total = total_s if total_s is not None else DEFAULT_TOTAL_BUDGET_S * scale
        return cls(total_s=total, stage_budgets=budgets)

    # ---- accessors ------------------------------------------------------

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def remaining(self) -> float:
        """Seconds left in the whole generation. Never negative."""
        return max(0.0, self.total_s - self.elapsed())

    def for_stage(self, stage: Stage) -> float:
        """This stage's deadline, clamped to what is left of the total.

        A capture that took its full 20s does not get to hand the reasoning
        stage a fresh 60s if only 30s remain overall.
        """
        nominal = self.stage_budgets.get(stage, 30.0)
        return max(1.0, min(nominal, self.remaining()))

    def exhausted(self) -> bool:
        return self.remaining() <= 0.0

    def record(self, stage: Stage, seconds: float) -> None:
        self.spent[stage.value] = self.spent.get(stage.value, 0.0) + max(0.0, seconds)

    def summary(self) -> Dict[str, float]:
        out = dict(self.spent)
        out["_total_elapsed_s"] = round(self.elapsed(), 3)
        out["_total_budget_s"] = self.total_s
        return out


def run_with_deadline(
    fn,
    *,
    stage: Stage,
    budget: StageBudget,
    default=None,
    trace=None,
    on_timeout_reason: FailureReason = FailureReason.QUALITY_BUDGET_EXCEEDED,
):
    """Run ``fn()`` and give up on it when the stage deadline passes.

    The worker thread is left running — a blocking Chromium or HTTP call cannot
    be cancelled from Python — but it is a daemon, so it cannot hold the process
    open, and the pipeline stops waiting. That is the whole point: a blown stage
    degrades instead of stalling the worker.

    Returns ``default`` on timeout and records the degradation on ``trace``.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    deadline = budget.for_stage(stage)
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"pv-{stage.value}")
    future = pool.submit(fn)
    try:
        result = future.result(timeout=deadline)
        budget.record(stage, time.monotonic() - started)
        return result
    except FuturesTimeout:
        elapsed = time.monotonic() - started
        budget.record(stage, elapsed)
        logger.warning(
            "Stage %s exceeded its %.0fs budget; degrading", stage.value, deadline
        )
        if trace is not None:
            trace.degrade(
                Degradation.BUDGET_STAGE_EXCEEDED,
                stage,
                detail=f"{stage.value} exceeded {deadline:.0f}s budget",
                reason=on_timeout_reason,
            )
        return default
    finally:
        # Do not block on a thread we have already given up on.
        pool.shutdown(wait=False)
