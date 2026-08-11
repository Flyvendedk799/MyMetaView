"""Quality profiles for preview generation — shared by the demo and the app.

One table, both surfaces. The public demo and a signed-in customer's dashboard
run the *same* engine at the *same* settings; the demo picks its profile from
URL complexity, the app pins ``ultra`` because a paying customer's card is the
product. Keeping the numbers here is deliberate: when these lived in two places
the app silently drifted onto weaker settings and its previews came out looking
generic next to the demo's.

The ``template`` profile is the deliberately cheap lane: no AI reasoning at all,
just the page's own metadata rendered through the same premium card. It backs
the previews beyond an account's monthly AI allowance.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlparse


@dataclass(frozen=True)
class QualityProfile:
    quality_mode: str
    multi_agent: bool
    ui_extraction: bool
    threshold: float
    iterations: int
    allow_soft_pass: bool
    enforce_target_quality: bool
    min_soft_pass_overall: float
    min_soft_pass_visual: float
    min_soft_pass_fidelity: float
    # Template lane: skip vision reasoning entirely and build the card from the
    # page's own metadata. Cheap, generic, and never the default.
    ai_reasoning: bool = True


# Backwards-compatible alias — this type used to be demo-only.
DemoQualityProfile = QualityProfile


# multi_agent is False everywhere. The orchestrator fuses HTML metadata into a
# payload with no composition spec, which renders as the same neutral card for
# every page; `PreviewEngine._orchestrator_result_is_usable` rejects such a
# result anyway, so turning it on only buys latency.
_QUALITY_PROFILES: dict[str, QualityProfile] = {
    "template": QualityProfile(
        quality_mode="template",
        multi_agent=False,
        ui_extraction=False,
        threshold=0.55,
        iterations=1,
        allow_soft_pass=True,
        enforce_target_quality=False,
        min_soft_pass_overall=0.35,
        min_soft_pass_visual=0.0,
        min_soft_pass_fidelity=0.0,
        ai_reasoning=False,
    ),
    "fast": QualityProfile(
        quality_mode="fast",
        multi_agent=False,
        ui_extraction=False,
        threshold=0.78,
        iterations=2,
        allow_soft_pass=True,
        enforce_target_quality=False,
        min_soft_pass_overall=0.66,
        min_soft_pass_visual=0.52,
        min_soft_pass_fidelity=0.50,
    ),
    "balanced": QualityProfile(
        quality_mode="balanced",
        multi_agent=False,
        ui_extraction=True,
        threshold=0.82,
        iterations=3,
        allow_soft_pass=True,
        enforce_target_quality=False,
        min_soft_pass_overall=0.74,
        min_soft_pass_visual=0.62,
        min_soft_pass_fidelity=0.60,
    ),
    "ultra": QualityProfile(
        quality_mode="ultra",
        multi_agent=False,
        ui_extraction=True,
        threshold=0.88,
        iterations=4,
        allow_soft_pass=False,
        enforce_target_quality=True,
        min_soft_pass_overall=0.85,
        min_soft_pass_visual=0.75,
        min_soft_pass_fidelity=0.72,
    ),
}


def resolve_quality_mode(requested_mode: str | None, url: str | None = None) -> str:
    """Resolve requested mode to one of fast/balanced/ultra with auto fallback."""
    normalized = (requested_mode or "auto").strip().lower()
    if normalized in _QUALITY_PROFILES:
        return normalized
    if normalized != "auto":
        return "ultra"
    complexity = estimate_url_complexity(url or "")
    if complexity >= 8:
        return "ultra"
    if complexity >= 4:
        return "balanced"
    return "fast"


def get_quality_profile(requested_mode: str | None, url: str | None = None) -> QualityProfile:
    resolved_mode = resolve_quality_mode(requested_mode, url=url)
    return _QUALITY_PROFILES[resolved_mode]


def get_cache_prefix_for_mode(requested_mode: str | None, url: str | None = None) -> str:
    """Cache namespace for the public demo. Signed-in generations use their own."""
    resolved_mode = resolve_quality_mode(requested_mode, url=url)
    return f"demo:preview:v3:{resolved_mode}:"


def estimate_url_complexity(url: str) -> int:
    """
    Lightweight heuristic to pick a quality profile before heavy processing starts.

    Higher scores indicate pages that typically need deeper extraction and iteration.
    """
    if not url:
        return 6
    parsed = urlparse(url)
    score = 0

    path = (parsed.path or "").lower()
    path_parts = [segment for segment in path.split("/") if segment]
    depth = len(path_parts)
    score += min(depth, 4)

    query_count = len(parse_qsl(parsed.query or "", keep_blank_values=True))
    if query_count >= 3:
        score += 2
    elif query_count > 0:
        score += 1

    long_path_bonus = 1 if len(path) > 28 else 0
    score += long_path_bonus

    high_complexity_tokens = {
        "pricing",
        "features",
        "product",
        "products",
        "solutions",
        "platform",
        "integrations",
        "compare",
        "comparison",
        "enterprise",
        "developer",
        "docs",
        "documentation",
        "blog",
        "case-study",
        "customers",
    }
    medium_complexity_tokens = {"about", "services", "service", "category", "search"}

    for token in path_parts:
        if token in high_complexity_tokens:
            score += 2
        elif token in medium_complexity_tokens:
            score += 1

    if parsed.fragment:
        score += 1

    return min(score, 12)
