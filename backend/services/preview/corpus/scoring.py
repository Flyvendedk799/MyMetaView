"""Scoring a corpus run, and deciding whether it regressed.

A corpus run used to produce success rate, title fidelity, and a default-palette
count — all read off the result dict. None of it looked at the card. A run could
therefore be green while every PNG shipped a headline at 1.2:1 contrast, which
is exactly the class of regression the corpus exists to catch.

Two things here:

  ``score_run``    downloads each run's rendered card and scores its pixels,
                   adding the visual half of the report.
  ``compare_runs`` diffs a run against a stored baseline and decides whether
                   CI should fail — with a tolerance, because these are
                   real-world pages and small movement is noise, and with a
                   hard floor, because some failures are not a matter of degree.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# How much the mean visual score may drop before CI calls it a regression.
# Corpus URLs are live pages: they get redesigned, they A/B test, they go down.
# A tolerance under about 2 points would fail on the world changing rather than
# on our code changing.
MEAN_SCORE_TOLERANCE = 0.02

# Failures that are not a matter of degree. Any increase fails the run.
HARD_FLOORS = ("gradient_only_count", "unreadable_count", "render_failure_count")


@dataclass
class RunScores:
    """The visual half of a corpus report."""

    commit: str = ""
    ran_at: str = ""
    per_url: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    mean_overall: float = 0.0
    mean_title_contrast: float = 0.0
    pass_rate: float = 0.0
    gradient_only_count: int = 0
    unreadable_count: int = 0
    render_failure_count: int = 0
    scored_count: int = 0
    degradation_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commit": self.commit,
            "ran_at": self.ran_at,
            "mean_overall": round(self.mean_overall, 4),
            "mean_title_contrast": round(self.mean_title_contrast, 3),
            "pass_rate": round(self.pass_rate, 4),
            "gradient_only_count": self.gradient_only_count,
            "unreadable_count": self.unreadable_count,
            "render_failure_count": self.render_failure_count,
            "scored_count": self.scored_count,
            "degradation_counts": dict(self.degradation_counts),
            "per_url": self.per_url,
        }


def score_run(
    records: Sequence[Dict[str, Any]],
    *,
    commit: str = "",
    ran_at: str = "",
    fetch_image=None,
) -> RunScores:
    """Score every card a run produced.

    ``fetch_image`` is injectable so a test can score local bytes without a
    network; production passes the guarded fetcher.
    """
    if fetch_image is None:
        fetch_image = _default_fetch

    scores = RunScores(commit=commit, ran_at=ran_at)
    overalls: List[float] = []
    contrasts: List[float] = []
    passes = 0

    from backend.services.preview.quality.pixel_metrics import score_card

    for record in records:
        url = record.get("url", "")

        for code in record.get("degradations") or []:
            scores.degradation_counts[code] = scores.degradation_counts.get(code, 0) + 1

        image_url = record.get("primary_image_url")
        if record.get("status") != "ok" or not image_url:
            scores.render_failure_count += 1
            scores.per_url[url] = {"scored": False, "reason": record.get("error") or "no card"}
            continue

        image_bytes = fetch_image(image_url)
        if not image_bytes:
            scores.render_failure_count += 1
            scores.per_url[url] = {"scored": False, "reason": "card could not be downloaded"}
            continue

        expected = [
            c for c in (
                (record.get("blueprint") or {}).get("primary_color"),
                (record.get("blueprint") or {}).get("secondary_color"),
            ) if c
        ]
        card = score_card(image_bytes, expected_colors=expected)

        scores.scored_count += 1
        overalls.append(card.overall)
        contrasts.append(card.title_contrast)
        if card.passed:
            passes += 1
        if card.gradient_only:
            scores.gradient_only_count += 1
        if card.title_contrast < 3.0:
            scores.unreadable_count += 1

        scores.per_url[url] = {"scored": True, **card.to_dict()}

    total = max(1, scores.scored_count)
    scores.mean_overall = sum(overalls) / total if overalls else 0.0
    scores.mean_title_contrast = sum(contrasts) / total if contrasts else 0.0
    scores.pass_rate = passes / total
    return scores


def _default_fetch(image_url: str) -> Optional[bytes]:
    try:
        from backend.services.preview.net import fetch

        result = fetch(image_url, timeout=15.0)
        return result.content if result.ok else None
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not download card %s: %s", image_url, exc)
        return None


@dataclass
class Comparison:
    """Did this run regress against the baseline?"""

    regressed: bool
    reasons: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    deltas: Dict[str, float] = field(default_factory=dict)
    per_url_regressions: List[Dict[str, Any]] = field(default_factory=list)

    def report(self) -> str:
        lines = []
        if self.regressed:
            lines.append("CORPUS REGRESSION")
            lines.extend(f"  ✗ {reason}" for reason in self.reasons)
        else:
            lines.append("Corpus within tolerance")
        lines.extend(f"  ✓ {note}" for note in self.improvements)
        if self.per_url_regressions:
            lines.append(f"  {len(self.per_url_regressions)} URL(s) got visibly worse:")
            for item in self.per_url_regressions[:10]:
                lines.append(
                    f"    {item['url']}: {item['before']:.3f} → {item['after']:.3f}"
                    + (f" ({'; '.join(item['issues'][:2])})" if item.get("issues") else "")
                )
        return "\n".join(lines)


def compare_runs(
    current: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    *,
    tolerance: float = MEAN_SCORE_TOLERANCE,
) -> Comparison:
    """Decide whether ``current`` is worse than ``baseline``.

    No baseline means no verdict: the first run on a branch establishes one
    rather than failing for having nothing to compare against.
    """
    if not baseline:
        return Comparison(regressed=False, improvements=["no baseline — this run becomes one"])

    reasons: List[str] = []
    improvements: List[str] = []
    deltas: Dict[str, float] = {}

    for metric in ("mean_overall", "mean_title_contrast", "pass_rate"):
        before = float(baseline.get(metric) or 0.0)
        after = float(current.get(metric) or 0.0)
        deltas[metric] = round(after - before, 4)
        if metric == "mean_title_contrast":
            # A contrast ratio is on a 1..21 scale, so the same fractional
            # tolerance would be far too tight; 0.3 of a ratio point is noise.
            if after < before - 0.3:
                reasons.append(f"{metric} fell {before:.2f} → {after:.2f}")
            elif after > before + 0.3:
                improvements.append(f"{metric} rose {before:.2f} → {after:.2f}")
            continue
        if after < before - tolerance:
            reasons.append(f"{metric} fell {before:.3f} → {after:.3f}")
        elif after > before + tolerance:
            improvements.append(f"{metric} rose {before:.3f} → {after:.3f}")

    for metric in HARD_FLOORS:
        before = int(baseline.get(metric) or 0)
        after = int(current.get(metric) or 0)
        deltas[metric] = after - before
        if after > before:
            reasons.append(f"{metric} rose {before} → {after} (hard floor: no increase allowed)")
        elif after < before:
            improvements.append(f"{metric} fell {before} → {after}")

    per_url = _per_url_regressions(current, baseline)
    # One URL moving is a redesign; several moving together is us.
    if len(per_url) >= 3:
        reasons.append(f"{len(per_url)} URLs scored materially worse")

    return Comparison(
        regressed=bool(reasons),
        reasons=reasons,
        improvements=improvements,
        deltas=deltas,
        per_url_regressions=per_url,
    )


def _per_url_regressions(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    drop: float = 0.08,
) -> List[Dict[str, Any]]:
    """URLs whose card got visibly worse. 0.08 is about one grade band."""
    out: List[Dict[str, Any]] = []
    before_urls = baseline.get("per_url") or {}
    after_urls = current.get("per_url") or {}

    for url, after in after_urls.items():
        before = before_urls.get(url)
        if not before or not before.get("scored") or not after.get("scored"):
            continue
        before_score = float(before.get("overall") or 0.0)
        after_score = float(after.get("overall") or 0.0)
        if after_score < before_score - drop:
            out.append({
                "url": url,
                "before": before_score,
                "after": after_score,
                "issues": after.get("issues") or [],
            })
    return sorted(out, key=lambda item: item["after"] - item["before"])


# ---------------------------------------------------------------------------
# Trend storage
# ---------------------------------------------------------------------------

def append_trend(path: Path, scores: Dict[str, Any]) -> None:
    """Append one run's headline numbers to the trend file.

    Per-URL detail stays in the run's own artifacts; the trend file holds only
    what a chart needs, so it stays readable after a year of nightlies.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        key: scores.get(key)
        for key in (
            "commit", "ran_at", "mean_overall", "mean_title_contrast",
            "pass_rate", "gradient_only_count", "unreadable_count",
            "render_failure_count", "scored_count",
        )
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")


def load_baseline(path: Path) -> Optional[Dict[str, Any]]:
    """The stored baseline, or None when there is not one yet."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def save_baseline(path: Path, scores: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2), encoding="utf-8")
