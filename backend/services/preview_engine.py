"""The preview engine — a coordinator, not an implementation.

This file used to be 4,100 lines and 44 methods: capture, extraction, vision
reasoning, five render stacks, a quality loop, caching and object-storage
uploads, all sharing state through local variables and ``self._last_*``
attributes. Nothing in it could be tested without standing up a browser, a
vision model and an object store, and the answer to "why did this card come out
generic?" was log archaeology.

The pipeline now lives in ``backend/services/preview/`` as typed stages, and
``PreviewEngine`` is what remains: the public surface the app already imports,
translating its config into a pipeline run and the pipeline's payload back into
``PreviewEngineResult``. The interesting code is one import away:

    preview/capture/       html + screenshot, hedged across providers
    preview/extraction/    brand identity, cached per domain
    preview/reasoning/     the art director, its model map, its output contract
    preview/composition/   resolving a request into a renderable fact
    preview/rendering/     the one rasterizer
    preview/quality/       pixel metrics, soft-pass policy, the critic
    preview/pipeline.py    the order they run in

Behaviour is unchanged where it was right and different where the roadmap said
it was wrong: there is one render path, every fallback is reason-coded, and what
gets graded is the PNG.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.services.preview.observability.job_trace import JobTraceStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PreviewEngineConfig:
    """How this generation should behave.

    ``enable_multi_agent`` is gone. The orchestrator was off in every profile,
    rejected by its own usability check when forced on, and fused HTML metadata
    into a payload with no composition spec — so every page it touched rendered
    as the same neutral card. The single-pass art director plus the quality loop
    is the system worth perfecting, and keeping a second one around cost import
    weight, config surface and the mental overhead of wondering which path ran.
    """

    # Environment
    is_demo: bool = False

    # Feature flags
    enable_brand_extraction: bool = True
    enable_ai_reasoning: bool = True
    enable_composited_image: bool = True
    enable_cache: bool = True
    enable_ui_element_extraction: bool = True

    # Quality loop
    enable_quality_iteration: bool = True
    quality_threshold: float = 0.80
    max_quality_iterations: int = 2
    enforce_target_quality: bool = False
    allow_soft_pass: bool = True
    min_soft_pass_overall: float = 0.60
    min_soft_pass_visual: float = 0.0
    min_soft_pass_fidelity: float = 0.0

    # Brand settings (SaaS)
    brand_settings: Optional[Dict[str, Any]] = None

    # Progress callback (for async jobs)
    progress_callback: Optional[Callable[[float, str], None]] = None

    # Deadlines. Per-stage budgets do the real work (``preview/budgets.py``);
    # this is the wall-clock ceiling they are clamped to.
    max_retries: int = 2
    timeout_seconds: int = 240

    # Thresholds
    min_content_confidence: float = 0.3
    min_image_quality: int = 50


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class PreviewEngineResult:
    """Everything one generation produced."""

    # Core content
    url: str
    title: str
    subtitle: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Images
    screenshot_url: Optional[str] = None
    composited_preview_image_url: Optional[str] = None
    primary_image_base64: Optional[str] = None

    # Brand + page structure
    brand: Dict[str, Any] = field(default_factory=dict)
    ui_elements: Dict[str, Any] = field(default_factory=dict)
    dom_data: Dict[str, Any] = field(default_factory=dict)
    blueprint: Dict[str, Any] = field(default_factory=dict)

    # Context and credibility
    context_items: List[Dict[str, Any]] = field(default_factory=list)
    credibility_items: List[Dict[str, Any]] = field(default_factory=list)
    cta_text: Optional[str] = None

    # Metadata
    reasoning_confidence: float = 0.0
    processing_time_ms: int = 0
    is_demo: bool = False
    message: str = ""
    trace_url: Optional[str] = None

    # Quality
    quality_scores: Dict[str, Any] = field(default_factory=dict)
    design_fidelity_score: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    # Alternative hooks the art director authored alongside the main copy —
    # [{angle, title, subtitle}]. The caller renders a card per angle.
    variants: List[Dict[str, Any]] = field(default_factory=list)

    # Everything needed to re-render this card without capturing the page or
    # calling the model again: composition, palette, brand name, proof line, and
    # the crops the panel uses. Persisted by the pipeline so a directed re-roll
    # and the per-platform sizes are a pure render, not a full regeneration.
    render_spec: Dict[str, Any] = field(default_factory=dict)

    # The layout that actually rendered. The art director's pick and what
    # survives asset resolution differ whenever a crop or a proof went missing.
    rendered_layout: Optional[str] = None

    # The ordered list of fallbacks this generation took. A finished job that
    # limped through five degradations and one that sailed through are otherwise
    # indistinguishable, which is exactly the question support keeps asking.
    degradations: List[str] = field(default_factory=list)
    job_id: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PreviewEngineResult":
        """Build a result from the pipeline's dict."""
        trace = payload.get("_trace") or {}
        return cls(
            url=payload.get("url", ""),
            title=payload.get("title", ""),
            subtitle=payload.get("subtitle"),
            description=payload.get("description", "") or "",
            tags=list(payload.get("tags") or []),
            screenshot_url=payload.get("screenshot_url"),
            composited_preview_image_url=payload.get("composited_preview_image_url"),
            brand=dict(payload.get("brand") or {}),
            ui_elements=dict(payload.get("ui_elements") or {}),
            dom_data=dict(payload.get("dom_data") or {}),
            blueprint=dict(payload.get("blueprint") or {}),
            context_items=list(payload.get("context_items") or []),
            credibility_items=list(payload.get("credibility_items") or []),
            cta_text=payload.get("cta_text"),
            reasoning_confidence=float(payload.get("reasoning_confidence") or 0.0),
            processing_time_ms=int(payload.get("processing_time_ms") or 0),
            is_demo=bool(payload.get("is_demo")),
            message=payload.get("message", ""),
            quality_scores=dict(payload.get("quality_scores") or {}),
            design_fidelity_score=payload.get("design_fidelity_score"),
            warnings=list(payload.get("warnings") or []),
            variants=list(payload.get("variants") or []),
            render_spec=dict(payload.get("render_spec") or {}),
            rendered_layout=payload.get("rendered_layout"),
            degradations=list(trace.get("degradation_trail", "").split(" → ")) if trace.get("degradation_trail") else [],
            job_id=trace.get("job_id"),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PreviewEngine:
    """Generates previews. One engine, both surfaces.

    The demo and a signed-in customer's dashboard run this same class at the
    same settings, with profiles from one table. That was hard-won — the app
    previously drifted onto weaker settings and its previews came out looking
    generic next to the demo's — and every change here has to preserve it.
    """

    def __init__(self, config: PreviewEngineConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.quality_profile: Any = None

    def generate(
        self,
        url: str,
        cache_key_prefix: str = "preview:engine:",
        *,
        job_id: Optional[str] = None,
    ) -> PreviewEngineResult:
        """Generate a preview for one URL.

        Raises ``ValueError`` when no card could be produced at all — which now
        means the renderer failed on both the authored spec and the
        deterministic minimal one, not merely that reasoning had a bad day.
        """
        from backend.services.preview.pipeline import generate as run_pipeline

        url_str = str(url).strip()
        if not url_str:
            raise ValueError("Invalid URL: empty")

        payload = run_pipeline(
            url_str,
            self.config,
            cache_key_prefix=cache_key_prefix,
            profile=self.quality_profile,
            job_id=job_id,
        )
        result = PreviewEngineResult.from_payload(payload)
        self.logger.info(
            "[%s] Preview for %s in %dms — %s",
            result.job_id, url_str, result.processing_time_ms,
            payload.get("_trace", {}).get("degradation_trail", "no trace"),
        )
        return result

    # ---- helpers the app and its tests rely on --------------------------

    def _has_rich_og_metadata(self, html_content: str) -> bool:
        """Does this page already ship a complete, substantial OG card?

        Used for lane selection. Note what it is *not* used for: the demo runs
        the art director regardless, because the demo's whole point is to show
        MetaView's reconstruction rather than echo a site's own og: tags back at
        it — and well-known sites all have rich OG, so an "OG-rich fast path"
        made the demo look generic on exactly the URLs people try first.
        """
        if not html_content:
            return False
        try:
            from backend.services.metadata_extractor import extract_metadata_from_html

            metadata = extract_metadata_from_html(html_content) or {}
        except Exception:  # noqa: BLE001
            return False

        title = (metadata.get("og_title") or "").strip()
        description = (metadata.get("og_description") or "").strip()
        image = (metadata.get("og_image") or "").strip()
        return len(title) >= 15 and len(description) >= 40 and bool(image)

    def _is_cache_eligible_result(self, result: PreviewEngineResult) -> bool:
        """Should this result be cached?

        A fallback card must never be cached: it is what we shipped because
        something went wrong, and caching it turns one bad generation into a
        day of bad generations for that URL. In strict mode a below-target card
        is treated the same way.
        """
        scores = result.quality_scores or {}
        if scores.get("is_fallback"):
            return False
        if not self.config.enforce_target_quality:
            return True

        def below(key: str, floor: float) -> bool:
            value = scores.get(key)
            return isinstance(value, (int, float)) and float(value) < floor

        return not (
            below("overall", self.config.quality_threshold)
            or below("design_fidelity", self.config.min_soft_pass_fidelity)
            or (self.config.min_soft_pass_visual > 0
                and below("visual", self.config.min_soft_pass_visual))
        )

    def trace(self, job_id: str) -> Optional[Dict[str, Any]]:
        """The full trace for one generation — the admin "why" view reads this."""
        return JobTraceStore.get_instance().get(job_id)

    # ---- content enhancement helpers (public API surface) ---------------

    def enhance_content_with_value_prop(
        self,
        title: str,
        description: Optional[str],
        features: Optional[List[str]] = None,
        page_type: str = "default",
    ) -> Dict[str, Any]:
        """Turn a raw title into a hook. Used by the enhancements API."""
        try:
            from backend.services.value_prop_extractor import extract_value_proposition

            value_prop = extract_value_proposition(
                title=title, description=description,
                features=features, page_type=page_type,
            )
            trigger = getattr(value_prop, "emotional_trigger", None)
            return {
                "hook": value_prop.hook,
                "benefit": value_prop.primary_benefit,
                "secondary_benefits": list(value_prop.secondary_benefits or []),
                "cta": value_prop.cta,
                "emotional_trigger": trigger.value if trigger else None,
                "social_proof": value_prop.social_proof,
                "confidence": value_prop.confidence,
                "enhanced": True,
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.info("Value prop enhancement unavailable: %s", exc)
            return {
                "hook": title,
                "benefit": description or "",
                "secondary_benefits": [],
                "cta": "Learn More",
                "emotional_trigger": None,
                "social_proof": None,
                "confidence": 0.0,
                "enhanced": False,
            }

    def generate_platform_variants(
        self,
        render_spec: Dict[str, Any],
        *,
        url: str,
        title: str,
        subtitle: Optional[str] = None,
        sizes: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Render this card at every platform aspect, from the stored spec.

        A pure rasterize per size — no capture, no model call — which is why
        the per-platform set costs nothing beyond render time. Composing at each
        aspect beats cropping the wide card: a square Instagram card is laid out
        as a square rather than being a chopped-up link preview.
        """
        from backend.services.card_rerender import render_platform_sizes

        return render_platform_sizes(
            render_spec, url=url, title=title, subtitle=subtitle,
            sizes=sizes, is_demo=self.config.is_demo,
        )

    def score_card_image(
        self,
        image_bytes: bytes,
        *,
        expected_colors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mechanically score a rendered card — the same metrics CI gates on."""
        from backend.services.preview.quality import score_card

        return score_card(image_bytes, expected_colors=expected_colors).to_dict()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def get_available_enhancements() -> Dict[str, bool]:
    """Which optional subsystems this deployment can actually use.

    Reported by probing rather than by a table of import flags, so the answer
    reflects the running container instead of what someone believed when the
    list was written.
    """
    def available(module: str) -> bool:
        import importlib

        try:
            importlib.import_module(module)
            return True
        except Exception:  # noqa: BLE001
            return False

    from backend.services.preview.assets.logo import svg_rasterizer_available

    return {
        "premium_renderer": available("backend.services.premium_card_renderer"),
        "pixel_metrics": available("backend.services.preview.quality.pixel_metrics"),
        "pixel_critic": available("backend.services.preview.quality.pixel_critic"),
        "svg_rasterizer": svg_rasterizer_available() is not None,
        "value_prop_extractor": available("backend.services.value_prop_extractor"),
        "platform_renders": available("backend.services.card_rerender"),
        "layered_cache": available("backend.services.preview.caching.layers"),
    }


def get_model_map() -> Dict[str, Dict[str, Any]]:
    """Which model runs which stage, as currently resolved."""
    from backend.services.preview.reasoning.models import describe_map

    return describe_map()
