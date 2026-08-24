"""Reason-code taxonomy for terminal pipeline outcomes.

The plan requires every fallback branch to emit a reason code + reason detail
and every job to resolve terminally as ``finished`` or ``failed``. These
enums are the single source of truth used by ``JobTrace`` and surfaced in the
frontend error taxonomy (Phase 5).
"""

from __future__ import annotations

from enum import Enum


class TerminalStatus(str, Enum):
    """Plan invariant: every job ends in one of these terminal states."""

    FINISHED = "finished"
    FAILED = "failed"


class FailureReason(str, Enum):
    """Closed taxonomy for failure / fallback explanations.

    Backend pipelines must select one of these before terminating. The
    frontend (Phase 5) maps each to a user-facing message.
    """

    # External capture failures
    CAPTURE_TIMEOUT = "capture_timeout"
    CAPTURE_BLOCKED = "capture_blocked"
    CAPTURE_HTTP_ERROR = "capture_http_error"
    CAPTURE_NETWORK_ERROR = "capture_network_error"

    # Extraction failures
    EXTRACTION_LOW_CONFIDENCE = "extraction_low_confidence"
    EXTRACTION_INVALID_PAYLOAD = "extraction_invalid_payload"
    EXTRACTION_AI_RATE_LIMIT = "extraction_ai_rate_limit"
    EXTRACTION_AI_AUTH = "extraction_ai_auth"
    EXTRACTION_AI_TIMEOUT = "extraction_ai_timeout"

    # Composition / rendering
    RENDER_FONT_FALLBACK = "render_font_fallback"
    RENDER_PALETTE_FALLBACK = "render_palette_fallback"
    RENDER_CONTRAST_FAILED = "render_contrast_failed"
    RENDER_LAYOUT_OVERFLOW = "render_layout_overflow"
    RENDER_IMAGE_PIPELINE_ERROR = "render_image_pipeline_error"

    # Quality gate
    QUALITY_GATE_FAILED = "quality_gate_failed"
    QUALITY_BUDGET_EXCEEDED = "quality_budget_exceeded"

    # Status / transient
    STATUS_CHECK_TRANSIENT = "status_check_transient"

    # Catch-all (must be rare; tracked as a metric in Phase 7)
    UNKNOWN = "unknown"

    @property
    def user_message(self) -> str:
        """Default copy surfaced to the frontend (overridable per-locale)."""
        return _USER_MESSAGES.get(self, "Something went wrong generating your preview.")


_USER_MESSAGES = {
    FailureReason.CAPTURE_TIMEOUT:
        "The page took too long to load. We'll retry with a simpler capture.",
    FailureReason.CAPTURE_BLOCKED:
        "The site blocked our preview crawler. Try a public URL or contact us.",
    FailureReason.CAPTURE_HTTP_ERROR:
        "The page responded with an error. Double-check the URL and try again.",
    FailureReason.CAPTURE_NETWORK_ERROR:
        "We couldn't reach the page. Check the URL and try again.",
    FailureReason.EXTRACTION_LOW_CONFIDENCE:
        "We couldn't read enough from the page to build a preview.",
    FailureReason.EXTRACTION_INVALID_PAYLOAD:
        "The page returned content we couldn't parse. We'll try a fallback.",
    FailureReason.EXTRACTION_AI_RATE_LIMIT:
        "Our AI provider rate-limited us. Please retry in a moment.",
    FailureReason.EXTRACTION_AI_AUTH:
        "Authentication issue with the AI provider — engineering is on it.",
    FailureReason.EXTRACTION_AI_TIMEOUT:
        "AI analysis timed out. We'll show a structured fallback.",
    FailureReason.RENDER_FONT_FALLBACK:
        "We rendered the preview with a fallback font.",
    FailureReason.RENDER_PALETTE_FALLBACK:
        "We rendered the preview with a fallback palette.",
    FailureReason.RENDER_CONTRAST_FAILED:
        "We adjusted text contrast to keep the preview readable.",
    FailureReason.RENDER_LAYOUT_OVERFLOW:
        "We trimmed text that would have overflowed the preview.",
    FailureReason.RENDER_IMAGE_PIPELINE_ERROR:
        "Image rendering hit an error — we used the screenshot as a fallback.",
    FailureReason.QUALITY_GATE_FAILED:
        "Quality didn't meet our bar so we shipped a safe fallback.",
    FailureReason.QUALITY_BUDGET_EXCEEDED:
        "We hit our time budget and shipped the best result we had.",
    FailureReason.STATUS_CHECK_TRANSIENT:
        "Status check hiccup — refresh in a moment.",
    FailureReason.UNKNOWN:
        "Something went wrong generating your preview.",
}


class PaletteSource(str, Enum):
    """Per-job palette provenance, required by the plan's trace schema."""

    SAMPLED = "sampled"
    DERIVED = "derived"
    DEFAULT = "default"


class PreviewLane(str, Enum):
    """Phase 6 — Dual-lane orchestration."""

    FAST = "fast"
    DEEP = "deep"


class Stage(str, Enum):
    """The engine's stages, in the order they run.

    Naming them once — rather than passing ad-hoc strings into timings, budgets
    and traces — is what lets "which stage degraded?" be a lookup instead of a
    grep. ``budgets.py`` keys deadlines off these, and every degradation event
    records the stage it happened in.
    """

    CACHE = "cache"
    CAPTURE = "capture"
    CLASSIFY = "classify"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    COMPOSITION = "composition"
    RENDER = "render"
    QUALITY = "quality"
    UPLOAD = "upload"
    PERSIST = "persist"


class Degradation(str, Enum):
    """Named steps down from the ideal path.

    A ``FailureReason`` answers "why did the job fail"; a ``Degradation``
    answers the question that actually gets asked in support — "why did this
    card come out generic when the job says it finished?". Every fallback
    branch in the engine emits one, so a finished generation carries an ordered
    trail like::

        capture_ok → brand_logo_fallback_favicon → reasoning_ok → premium_render_ok

    The values are stable strings: they are persisted in traces and activity
    logs, and the admin "why" view reads them back.
    """

    # ---- capture --------------------------------------------------------
    CAPTURE_OK = "capture_ok"
    CAPTURE_HEDGED_TO_API = "capture_hedged_to_api"
    CAPTURE_SCREENSHOT_MISSING = "capture_screenshot_missing"
    CAPTURE_HTML_ONLY = "capture_html_only"
    CAPTURE_PLACEHOLDER = "capture_placeholder"
    CAPTURE_CIRCUIT_OPEN = "capture_circuit_open"
    CAPTURE_CACHED = "capture_cached"

    # ---- brand / extraction ---------------------------------------------
    BRAND_OK = "brand_ok"
    BRAND_CACHED = "brand_cached"
    BRAND_EXTRACTION_FAILED = "brand_extraction_failed"
    BRAND_LOGO_FALLBACK_FAVICON = "brand_logo_fallback_favicon"
    BRAND_LOGO_FALLBACK_SCREENSHOT = "brand_logo_fallback_screenshot"
    BRAND_LOGO_SVG_RASTERIZED = "brand_logo_svg_rasterized"
    BRAND_LOGO_SVG_SKIPPED = "brand_logo_svg_skipped"
    BRAND_LOGO_NONE = "brand_logo_none"
    BRAND_COLORS_DEFAULT = "brand_colors_default"
    UI_EXTRACTION_SKIPPED = "ui_extraction_skipped"

    # ---- reasoning -------------------------------------------------------
    REASONING_OK = "reasoning_ok"
    REASONING_CACHED = "reasoning_cached"
    REASONING_SKIPPED_TEMPLATE_LANE = "reasoning_skipped_template_lane"
    REASONING_FALLBACK_HTML = "reasoning_fallback_html"
    REASONING_TIMEOUT = "reasoning_timeout"
    REASONING_SCHEMA_REPAIRED = "reasoning_schema_repaired"
    REASONING_TITLE_REFINED_FROM_PAGE = "reasoning_title_refined_from_page"

    # ---- composition -----------------------------------------------------
    COMPOSITION_OK = "composition_ok"
    COMPOSITION_LAYOUT_DEGRADED = "composition_layout_degraded"
    COMPOSITION_FOCAL_CROP_OK = "composition_focal_crop_ok"
    COMPOSITION_FOCAL_CROP_REJECTED = "composition_focal_crop_rejected"
    COMPOSITION_FOCAL_CROP_FAILED = "composition_focal_crop_failed"
    COMPOSITION_LOGO_PANEL_CONTRAST_FIX = "composition_logo_panel_contrast_fix"
    COMPOSITION_LOGO_DROPPED_UNUSABLE = "composition_logo_dropped_unusable"
    COMPOSITION_BRAND_OVERRIDES_APPLIED = "composition_brand_overrides_applied"
    COMPOSITION_MINIMAL_SPEC = "composition_minimal_spec"

    # ---- render ----------------------------------------------------------
    PREMIUM_RENDER_OK = "premium_render_ok"
    PREMIUM_RENDER_MINIMAL_SPEC = "premium_render_minimal_spec"
    PREMIUM_RENDER_FAILED = "premium_render_failed"
    RENDER_UPLOAD_FAILED = "render_upload_failed"

    # ---- quality ---------------------------------------------------------
    QUALITY_PASS = "quality_pass"
    QUALITY_SOFT_PASS = "quality_soft_pass"
    QUALITY_RETRY = "quality_retry"
    QUALITY_PIXEL_CRITIC_PASS = "quality_pixel_critic_pass"
    QUALITY_PIXEL_CRITIC_FAIL = "quality_pixel_critic_fail"
    QUALITY_PIXEL_CRITIC_SKIPPED = "quality_pixel_critic_skipped"
    QUALITY_FALLBACK_CARD = "quality_fallback_card"

    # ---- budgets ---------------------------------------------------------
    BUDGET_STAGE_EXCEEDED = "budget_stage_exceeded"
    BUDGET_TOTAL_EXCEEDED = "budget_total_exceeded"

    # ---- cache -----------------------------------------------------------
    RESULT_CACHE_HIT = "result_cache_hit"
    RESULT_CACHE_MISS = "result_cache_miss"

    @property
    def is_healthy(self) -> bool:
        """True for the "nothing went wrong" markers.

        The trail records successes too, so a card that came out generic can be
        told apart from one that never reached the stage at all. Counting only
        the unhealthy entries is how the corpus reports degradation rate.
        """
        return self in _HEALTHY_DEGRADATIONS


_HEALTHY_DEGRADATIONS = frozenset({
    Degradation.CAPTURE_OK,
    Degradation.CAPTURE_CACHED,
    Degradation.BRAND_OK,
    Degradation.BRAND_CACHED,
    Degradation.REASONING_OK,
    Degradation.REASONING_CACHED,
    Degradation.COMPOSITION_OK,
    Degradation.COMPOSITION_FOCAL_CROP_OK,
    Degradation.PREMIUM_RENDER_OK,
    Degradation.QUALITY_PASS,
    Degradation.QUALITY_PIXEL_CRITIC_PASS,
    Degradation.RESULT_CACHE_HIT,
    Degradation.RESULT_CACHE_MISS,
})


# Reason codes worth retrying automatically: the failure is in the world, not
# in the input, so the same job run again has a real chance of succeeding.
# Phase 5's bounded retry policy reads this set.
TRANSIENT_FAILURE_REASONS = frozenset({
    FailureReason.CAPTURE_TIMEOUT,
    FailureReason.CAPTURE_NETWORK_ERROR,
    FailureReason.EXTRACTION_AI_RATE_LIMIT,
    FailureReason.EXTRACTION_AI_TIMEOUT,
    FailureReason.STATUS_CHECK_TRANSIENT,
    FailureReason.QUALITY_BUDGET_EXCEEDED,
})


def is_transient(reason: FailureReason | str | None) -> bool:
    """Should a job that ended on this reason be retried automatically?"""
    if reason is None:
        return False
    if isinstance(reason, str):
        try:
            reason = FailureReason(reason)
        except ValueError:
            return False
    return reason in TRANSIENT_FAILURE_REASONS
