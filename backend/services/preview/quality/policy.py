"""Does this card ship?

Two questions, kept apart on purpose.

*Is it broken?* — a gradient with no text, a headline at 1.2:1, copy running off
the canvas. Those are defects; no threshold argues them into acceptability, and
``CardScore.passed`` already answers it from pixels.

*Is it good enough?* — everything else. Here the profile's numbers apply, and a
card below the bar can still ship as a soft pass because a slightly weak real
card beats a fallback that is generic by construction.

The old engine collapsed both into one score and got the first question wrong:
a premium card was hard-coded to visual 0.9 to stop a variance-based validator
from misreading it, which also meant a genuinely broken premium card scored 0.9.
Scoring the actual pixels is what lets the special case go away.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from backend.services.preview.observability.reason_codes import Degradation, Stage
from backend.services.preview.quality.pixel_metrics import CardScore, score_card

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SoftPassPolicy:
    """The profile's thresholds, in the shape the evaluator wants them."""

    threshold: float = 0.80
    allow_soft_pass: bool = True
    min_soft_pass_overall: float = 0.60
    enforce_target_quality: bool = False

    @classmethod
    def from_profile(cls, profile: Any) -> "SoftPassPolicy":
        return cls(
            threshold=float(getattr(profile, "threshold", 0.80)),
            allow_soft_pass=bool(getattr(profile, "allow_soft_pass", True)),
            min_soft_pass_overall=float(getattr(profile, "min_soft_pass_overall", 0.60)),
            enforce_target_quality=bool(getattr(profile, "enforce_target_quality", False)),
        )


@dataclass
class CardVerdict:
    """What the policy decided, and enough detail to explain it."""

    decision: str  # pass | soft_pass | retry | reject
    score: CardScore
    reasons: List[str]

    @property
    def shippable(self) -> bool:
        return self.decision in ("pass", "soft_pass")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": self.reasons,
            "pixel_score": self.score.to_dict(),
        }


def evaluate_card(
    image_bytes: Optional[bytes],
    *,
    policy: SoftPassPolicy,
    expected_colors: Optional[Sequence[str]] = None,
    expect_logo: bool = True,
    layout: Optional[str] = None,
    attempts_left: int = 0,
    trace: Optional[Any] = None,
) -> CardVerdict:
    """Score a rendered card and decide what to do with it.

    ``attempts_left`` is what separates "retry" from "reject": with budget
    remaining a broken card is worth another pass, without it the honest
    outcome is the deterministic fallback card, not shipping the broken one.
    """
    score = score_card(
        image_bytes,
        expected_colors=expected_colors,
        expect_logo=expect_logo,
        layout=layout,
    )

    if not score.scored:
        verdict = CardVerdict("retry" if attempts_left > 0 else "reject", score,
                              ["card could not be scored"])
        _record(trace, verdict)
        return verdict

    # Question one: is it broken?
    if not score.passed:
        decision = "retry" if attempts_left > 0 else "reject"
        verdict = CardVerdict(decision, score, list(score.issues))
        _record(trace, verdict)
        return verdict

    # Question two: is it good enough?
    overall = score.overall
    if overall >= policy.threshold:
        verdict = CardVerdict("pass", score, [])
        _record(trace, verdict)
        return verdict

    if policy.enforce_target_quality and attempts_left > 0:
        verdict = CardVerdict(
            "retry", score,
            [f"overall {overall:.2f} below target {policy.threshold:.2f}"],
        )
        _record(trace, verdict)
        return verdict

    if policy.allow_soft_pass and overall >= policy.min_soft_pass_overall:
        verdict = CardVerdict(
            "soft_pass", score,
            [f"overall {overall:.2f} below target {policy.threshold:.2f} but above soft floor"],
        )
        _record(trace, verdict)
        return verdict

    decision = "retry" if attempts_left > 0 else "reject"
    verdict = CardVerdict(
        decision, score,
        [f"overall {overall:.2f} below soft floor {policy.min_soft_pass_overall:.2f}"],
    )
    _record(trace, verdict)
    return verdict


_DECISION_DEGRADATIONS = {
    "pass": Degradation.QUALITY_PASS,
    "soft_pass": Degradation.QUALITY_SOFT_PASS,
    "retry": Degradation.QUALITY_RETRY,
    "reject": Degradation.QUALITY_FALLBACK_CARD,
}


def _record(trace: Optional[Any], verdict: CardVerdict) -> None:
    if trace is None:
        return
    code = _DECISION_DEGRADATIONS.get(verdict.decision, Degradation.QUALITY_RETRY)
    detail = "; ".join(verdict.reasons)[:200] or f"overall={verdict.score.overall:.2f}"
    try:
        trace.degrade(code, Stage.QUALITY, detail=detail)
        trace.visual_quality = verdict.score.to_dict()
    except Exception as exc:  # noqa: BLE001 — tracing must never break the pipeline
        logger.debug("Could not record quality verdict on trace: %s", exc)
