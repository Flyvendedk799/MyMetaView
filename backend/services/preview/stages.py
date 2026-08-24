"""Typed contracts between engine stages.

The engine used to pass state between its stages as a growing pile of local
variables and ``self._last_*`` attributes, which is why a 4,100-line method was
the only place the pipeline could be read: no stage had a signature, so no stage
could be tested without standing up half the world.

Each dataclass here is one stage's output and the next stage's input. That is
the entire contract — a stage is a function from one of these to the next, and a
test for it needs to build one small object rather than mock a browser, a vision
model, and an object store.

    CaptureResult      what the browser saw
    BrandResult        who the page belongs to
    ReasoningResult    what the card should say and how it is composed
    CompositionSpec    the resolved, renderable description of one card
    RenderResult       the PNG and where it landed

``PipelineState`` carries the pieces that genuinely are cross-cutting — the
trace, the budget, the config — so they do not have to be threaded through
every signature individually.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from backend.services.preview.budgets import StageBudget
from backend.services.preview.observability.job_trace import JobTrace
from backend.services.preview.observability.reason_codes import (
    Degradation,
    PaletteSource,
    Stage,
)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

@dataclass
class CaptureResult:
    """What the capture stage got from the page.

    ``screenshot_bytes`` may be empty — a page that refuses a browser but serves
    HTML still produces a real card from its metadata, and pretending capture
    failed entirely would throw that away.
    """

    url: str
    html: str = ""
    screenshot_bytes: bytes = b""
    dom_data: Dict[str, Any] = field(default_factory=dict)
    screenshot_url: Optional[str] = None
    provider: str = ""
    from_cache: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool(self.html or self.screenshot_bytes)

    @property
    def has_screenshot(self) -> bool:
        return len(self.screenshot_bytes) > 1024


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

@dataclass
class BrandResult:
    """The page's identity: name, mark, palette.

    ``palette_source`` is provenance, not decoration: a palette sampled from the
    page and a palette we made up look identical downstream, and only one of
    them should ever override what the art director saw.
    """

    brand_name: Optional[str] = None
    logo_data_uri: Optional[str] = None
    hero_data_uri: Optional[str] = None
    colors: Dict[str, str] = field(default_factory=dict)
    palette_source: PaletteSource = PaletteSource.DEFAULT
    from_cache: bool = False
    domain: str = ""

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_data_uri)


@dataclass
class PageClassification:
    """What kind of page this is, and how sure we are."""

    category: str = "unknown"
    confidence: float = 0.0
    strategy: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------

@dataclass
class ReasoningResult:
    """The art director's output: the story and the composition.

    ``composition`` is a request, not a fact — it names a layout and asks for a
    visual, both of which the composition stage has to confirm are possible with
    the assets that actually resolved.
    """

    title: str = ""
    subtitle: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    cta_text: Optional[str] = None
    proof: Optional[str] = None
    context_items: List[Dict[str, Any]] = field(default_factory=list)
    credibility_items: List[Dict[str, Any]] = field(default_factory=list)
    variants: List[Dict[str, Any]] = field(default_factory=list)
    composition: Dict[str, Any] = field(default_factory=dict)
    blueprint: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "ai"  # ai | html | cache | minimal
    from_cache: bool = False
    repaired: bool = False

    @property
    def ok(self) -> bool:
        return bool((self.title or "").strip())

    def to_dict(self) -> Dict[str, Any]:
        """The legacy ``ai_result`` shape, for code not yet on the contract."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "tags": list(self.tags),
            "cta_text": self.cta_text,
            "context_items": list(self.context_items),
            "credibility_items": list(self.credibility_items),
            "variants": list(self.variants),
            "composition": dict(self.composition),
            "blueprint": dict(self.blueprint),
            "confidence": self.confidence,
            "analysis_confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ReasoningResult":
        """Adapt a legacy ``ai_result`` dict into the contract."""
        data = data or {}
        confidence = data.get("confidence") or data.get("analysis_confidence") or 0.0
        return cls(
            title=str(data.get("title") or ""),
            subtitle=data.get("subtitle"),
            description=str(data.get("description") or ""),
            tags=list(data.get("tags") or []),
            cta_text=data.get("cta_text"),
            context_items=list(data.get("context_items") or []),
            credibility_items=list(data.get("credibility_items") or []),
            variants=list(data.get("variants") or []),
            composition=dict(data.get("composition") or {}),
            blueprint=dict(data.get("blueprint") or {}),
            confidence=float(confidence or 0.0),
        )


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

@dataclass
class CompositionSpec:
    """A card, fully resolved and ready to rasterize.

    Everything here is a fact rather than a request: the layout is one the
    assets support, the logo is one that will be visible on the panel, the crop
    is one that passed saliency. That is the difference between this and
    ``ReasoningResult.composition``, and it is why re-rendering from a stored
    spec is a pure function.
    """

    title: str = ""
    subtitle: Optional[str] = None
    url: str = ""
    brand_name: Optional[str] = None
    colors: Dict[str, str] = field(default_factory=dict)
    composition: Dict[str, Any] = field(default_factory=dict)
    logo_data_uri: Optional[str] = None
    visual_data_uri: Optional[str] = None
    proof: Optional[str] = None
    cta_text: Optional[str] = None
    hide_watermark: bool = False
    # The display font chosen on the My Site tab. None means the house font.
    font_family: Optional[str] = None
    size: str = "wide"
    minimal: bool = False  # built by the deterministic fallback, not the AI

    def render_kwargs(self) -> Dict[str, Any]:
        """Exactly what ``render_premium_card_detailed`` takes."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "url": self.url,
            "brand_name": self.brand_name,
            "colors": dict(self.colors),
            "composition": dict(self.composition),
            "logo_data_uri": self.logo_data_uri,
            "visual_data_uri": self.visual_data_uri,
            "hide_watermark": self.hide_watermark,
            "font_family": self.font_family,
            "proof": self.proof,
            "cta_text": self.cta_text,
            "size": self.size,
        }


@dataclass
class RenderResult:
    """The rendered card and where it went."""

    png: bytes = b""
    image_url: Optional[str] = None
    rendered_layout: Optional[str] = None
    render_spec: Dict[str, Any] = field(default_factory=dict)
    minimal: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool(self.png) and bool(self.image_url)


# ---------------------------------------------------------------------------
# Cross-cutting state
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """The things every stage needs and none of them own.

    Passing this rather than six separate parameters is what keeps stage
    signatures to ``(state, previous_result) -> next_result``.
    """

    url: str
    config: Any
    trace: JobTrace
    budget: StageBudget
    progress: Optional[Callable[[float, str], None]] = None
    lane_prefix: str = "preview:engine:"
    shared: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_demo(self) -> bool:
        return bool(getattr(self.config, "is_demo", False))

    def update_progress(self, fraction: float, message: str) -> None:
        if self.progress is None:
            return
        try:
            self.progress(float(fraction), str(message))
        except Exception:  # noqa: BLE001 — progress is cosmetic
            pass

    def degrade(
        self,
        code: Degradation,
        stage: Stage,
        detail: Optional[str] = None,
    ) -> None:
        self.trace.degrade(code, stage, detail=detail)
