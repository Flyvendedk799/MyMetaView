"""Preview enhancement endpoints.

These used to wrap five PIL subsystems — a style-variant generator, a platform
optimizer that resized a finished card, a readability auto-fixer that painted a
dark overlay over cards it judged low-contrast, and two image scorers. All five
worked on the *output* of a render, which is why they existed and also why they
are gone: the engine now gets those things right while composing, and what
cannot be fixed while composing cannot be fixed by post-processing a PNG.

What replaced each, and what these endpoints now do:

  style variants     ← re-render from ``render_spec`` with a different layout,
                       panel or accent. Composed at that direction rather than
                       recoloured after the fact, and free of model cost.
  platform variants  ← re-render at each platform's aspect. A square card is
                       laid out as a square instead of being a wide card
                       cropped down.
  readability fix    ← logo/panel contrast resolution and WCAG-checked ink at
                       composition time. There is nothing left to fix later.
  image scoring      ← ``preview/quality/pixel_metrics``, the same measurements
                       CI gates the corpus on.

``/fix-readability`` is kept and now *reports* rather than repaints: it tells
you what is wrong with a card so you can regenerate it, which is the honest
answer.
"""

import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview-enhancements", tags=["preview-enhancements"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ValuePropRequest(BaseModel):
    title: str = Field(..., description="Original page title")
    description: Optional[str] = Field(None, description="Original page description")
    features: Optional[List[str]] = Field(None, description="List of features")
    page_type: str = Field("default", description="Page type (saas, product, article, …)")


class ValuePropResponse(BaseModel):
    hook: str
    benefit: str
    secondary_benefits: List[str] = []
    cta: str
    emotional_trigger: Optional[str] = None
    social_proof: Optional[str] = None
    confidence: float
    enhanced: bool


class CardScoreRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded rendered card")
    expected_colors: Optional[List[str]] = Field(
        None, description="Brand hex colors the card should match"
    )
    expect_logo: bool = Field(True, description="False when the brand has no mark")
    layout: Optional[str] = Field(
        None,
        description="Which layout rendered. A split card's panel bleeds to the "
                    "edge by design; without this it can read as overflow.",
    )


class CardScoreResponse(BaseModel):
    """Every mechanical measurement, plus the verdict CI would reach."""
    overall: float
    passed: bool
    title_contrast: float
    eyebrow_contrast: float
    overflow_risk: float
    logo_occupancy: float
    palette_delta_e: float
    gradient_only: bool
    balance: float
    width: int
    height: int
    issues: List[str] = []


class PlatformRenderRequest(BaseModel):
    render_spec: Dict[str, Any] = Field(..., description="A preview's stored render_spec")
    url: str
    title: str
    subtitle: Optional[str] = None
    sizes: Optional[List[str]] = Field(
        None, description="Subset of wide/square/portrait; omit for all"
    )


class PlatformRenderResponse(BaseModel):
    images: Dict[str, str] = Field(default_factory=dict, description="size → image URL")
    requested: List[str] = []
    rendered: List[str] = []


class DirectedRenderRequest(BaseModel):
    render_spec: Dict[str, Any]
    url: str
    title: str
    subtitle: Optional[str] = None
    layout: Optional[str] = None
    panel: Optional[str] = None
    accent: Optional[str] = None


class DirectedRenderResponse(BaseModel):
    image_url: Optional[str] = None
    rendered_layout: Optional[str] = None
    applied: Dict[str, Any] = Field(default_factory=dict)


class EnhancementsStatusResponse(BaseModel):
    premium_renderer: bool
    pixel_metrics: bool
    pixel_critic: bool
    svg_rasterizer: bool
    value_prop_extractor: bool
    platform_renders: bool
    layered_cache: bool


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/status", response_model=EnhancementsStatusResponse)
def get_enhancement_status():
    """Which optional subsystems this deployment can actually use."""
    from backend.services.preview_engine import get_available_enhancements

    return EnhancementsStatusResponse(**get_available_enhancements())


@router.get("/model-map")
def get_model_map_endpoint():
    """Which model runs which stage, as currently resolved.

    Reads through the env overrides, so this answers "what will the next
    generation actually call?" rather than "what does the table say".
    """
    from backend.services.preview_engine import get_model_map

    return {"purposes": get_model_map()}


@router.post("/value-prop", response_model=ValuePropResponse)
def enhance_value_proposition(request: ValuePropRequest):
    """Turn a raw title into a hook."""
    from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig

    engine = PreviewEngine(PreviewEngineConfig())
    result = engine.enhance_content_with_value_prop(
        title=request.title,
        description=request.description,
        features=request.features,
        page_type=request.page_type,
    )
    return ValuePropResponse(**result)


@router.post("/score-card", response_model=CardScoreResponse)
def score_card_endpoint(request: CardScoreRequest):
    """Score a rendered card the way the corpus gate does.

    Same functions, same thresholds — a score here means what a score in the
    nightly report means.
    """
    try:
        image_bytes = base64.b64decode(request.image_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode image_base64: {exc}",
        ) from exc

    from backend.services.preview.quality import score_card

    score = score_card(
        image_bytes,
        expected_colors=request.expected_colors,
        expect_logo=request.expect_logo,
        layout=request.layout,
    )
    if not score.scored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(score.issues) or "Image could not be scored",
        )

    payload = score.to_dict()
    payload.pop("scored", None)
    payload.pop("bytes_len", None)
    return CardScoreResponse(**payload)


@router.post("/render-platforms", response_model=PlatformRenderResponse)
def render_platform_sizes_endpoint(request: PlatformRenderRequest):
    """Render one card at every platform aspect from its stored spec.

    A pure rasterize per size: no page capture, no model call, no AI allowance
    spent. Sizes that fail to render are simply absent from the response rather
    than failing the request, because a partial set is still useful.
    """
    from backend.services.card_rerender import spec_is_renderable
    from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig

    if not spec_is_renderable(request.render_spec):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This preview has no render_spec — regenerate it first.",
        )

    engine = PreviewEngine(PreviewEngineConfig())
    images = engine.generate_platform_variants(
        request.render_spec,
        url=request.url,
        title=request.title,
        subtitle=request.subtitle,
        sizes=request.sizes,
    )
    from backend.services.premium_card_renderer import CARD_SIZES

    requested = request.sizes or list(CARD_SIZES)
    return PlatformRenderResponse(
        images=images,
        requested=requested,
        rendered=sorted(images),
    )


@router.post("/render-directed", response_model=DirectedRenderResponse)
def render_directed_endpoint(request: DirectedRenderRequest):
    """Re-render a card with a different layout, panel or accent.

    This is what "style variants" became. The difference from the old generator
    is that the card is *composed* at the new direction rather than recoloured
    afterwards, so asking for a split layout produces a split layout instead of
    a typographic card with a filter over it.
    """
    from backend.services.card_rerender import (
        apply_direction,
        rerender_card,
        spec_is_renderable,
    )

    if not spec_is_renderable(request.render_spec):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This preview has no render_spec — regenerate it first.",
        )

    directed = apply_direction(
        request.render_spec,
        layout=request.layout,
        panel=request.panel,
        accent=request.accent,
    )
    image_url, rendered_layout = rerender_card(
        directed, url=request.url, title=request.title, subtitle=request.subtitle,
    )
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The card could not be re-rendered.",
        )
    return DirectedRenderResponse(
        image_url=image_url,
        rendered_layout=rendered_layout,
        applied=directed.get("composition", {}),
    )


@router.get("/available-directions")
def get_available_directions():
    """What a re-roll may steer.

    Copy is deliberately absent: rewriting the hook needs the model, which is
    what the AI allowance meters.
    """
    from backend.services.card_rerender import (
        DIRECTABLE_ACCENTS,
        DIRECTABLE_LAYOUTS,
        DIRECTABLE_PANELS,
    )
    from backend.services.premium_card_renderer import CARD_SIZES

    return {
        "layouts": list(DIRECTABLE_LAYOUTS),
        "panels": list(DIRECTABLE_PANELS),
        "accents": list(DIRECTABLE_ACCENTS),
        "sizes": [
            {"key": size.key, "width": size.width, "height": size.height}
            for size in CARD_SIZES.values()
        ],
    }
