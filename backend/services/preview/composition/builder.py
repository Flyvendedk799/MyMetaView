"""Building the resolved composition spec."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from backend.services.preview.assets.focal import crop_focus
from backend.services.preview.assets.logo import (
    apply_contrast_fix_to_spec,
    logo_is_usable,
    resolve_logo_contrast,
)
from backend.services.preview.branding import disregarded, settings_of
from backend.services.preview.observability.reason_codes import Degradation, Stage
from backend.services.preview.stages import (
    BrandResult,
    CaptureResult,
    CompositionSpec,
    PipelineState,
    ReasoningResult,
)

logger = logging.getLogger(__name__)

# Only these layouts consume a side/top visual panel. Forcing a visual on any
# other layout reserves a panel the renderer never fills.
PANEL_LAYOUTS = ("split", "product")

DEFAULT_COMPOSITION: Dict[str, Any] = {
    "layout": "typographic",
    "use_visual": False,
    "visual_source": "none",
    "panel_color_role": "primary",
    "accent_moment": "bar",
    "mood": "confident",
}


def _panel_hex(colors: Dict[str, str], role: str) -> str:
    """Ask the renderer what a panel role resolves to, so contrast is measured
    against the color that will actually be painted rather than a guess."""
    try:
        from backend.services.premium_card_renderer import _panel_color

        return _panel_color(colors or {}, role)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Panel color resolution failed: %s", exc)
        return "#0B3B2E"


def _apply_customer_overrides(
    composition: Dict[str, Any],
    state: PipelineState,
) -> Dict[str, Any]:
    """Fold in the org's saved card preferences.

    ``auto`` means "the art director decides", which is why only explicit values
    override. The public demo has no preferences, so it is untouched, and a
    preview the user added with branding disregarded is treated the same way.
    """
    prefs = settings_of(state.config)
    if not prefs or disregarded(prefs):
        return composition

    changed = []
    layout = prefs.get("preview_layout")
    if layout and layout != "auto":
        composition["layout"] = layout
        composition["use_visual"] = layout in PANEL_LAYOUTS
        changed.append(f"layout={layout}")

    panel = prefs.get("preview_panel")
    if panel and panel != "auto":
        composition["panel_color_role"] = panel
        changed.append(f"panel={panel}")

    accent = prefs.get("preview_accent")
    if accent and accent != "auto":
        composition["accent_moment"] = accent
        changed.append(f"accent={accent}")

    if changed:
        state.trace.degrade(
            Degradation.COMPOSITION_BRAND_OVERRIDES_APPLIED, Stage.COMPOSITION,
            detail="; ".join(changed),
        )
    return composition


def _card_prefs(state: PipelineState) -> Dict[str, Any]:
    """The site's card preferences, or nothing when they are being disregarded.

    ``hide_watermark`` is deliberately not in here — see ``_hide_watermark``.
    """
    prefs = settings_of(state.config)
    return {} if disregarded(prefs) else prefs


def _hide_watermark(state: PipelineState) -> bool:
    """Whether to draw the MetaView mark.

    Read straight off the settings rather than through ``_card_prefs``: hiding
    the mark is a plan entitlement the account paid for, not a styling choice,
    so disregarding the site's branding for one preview must not put somebody
    else's watermark back on a white-label customer's card.
    """
    return bool(settings_of(state.config).get("hide_watermark"))


def _brand_font(state: PipelineState, prefs: Dict[str, Any]) -> Optional[str]:
    """The display font chosen on the My Site tab, if it is not the default."""
    font = str(prefs.get("font_family") or "").strip()
    if not font:
        return None
    state.trace.degrade(
        Degradation.COMPOSITION_BRAND_FONT_APPLIED, Stage.COMPOSITION,
        detail=f"font={font}",
    )
    return font


def resolve_visual(
    state: PipelineState,
    capture: CaptureResult,
    composition: Dict[str, Any],
) -> Optional[str]:
    """The hero crop, if the director asked for one and it survives QA.

    The director picks ``split`` from a scaled-down screenshot and cannot know
    whether the box it drew contains the hero or the nav bar. ``crop_focus``
    decides that on saliency; a rejected crop leaves the visual empty and the
    renderer degrades to typographic — a designed layout, not a broken one.
    """
    if not composition.get("use_visual"):
        return None
    if composition.get("visual_source") != "screenshot":
        return None
    if not capture.has_screenshot:
        state.trace.degrade(
            Degradation.COMPOSITION_FOCAL_CROP_FAILED, Stage.COMPOSITION,
            detail="no screenshot to crop",
        )
        return None

    focus = composition.get("visual_focus")
    result = crop_focus(capture.screenshot_bytes, focus)
    if result.accepted:
        state.trace.degrade(
            Degradation.COMPOSITION_FOCAL_CROP_OK, Stage.COMPOSITION,
            detail=result.reason,
        )
        return result.data_uri

    state.trace.degrade(
        Degradation.COMPOSITION_FOCAL_CROP_REJECTED, Stage.COMPOSITION,
        detail=result.reason,
    )
    return None


def build_spec(
    state: PipelineState,
    capture: CaptureResult,
    brand: BrandResult,
    reasoning: ReasoningResult,
    *,
    size: str = "wide",
) -> CompositionSpec:
    """Resolve everything the renderer needs into facts it can draw."""
    state.update_progress(0.72, "Composing the card…")

    composition = {**DEFAULT_COMPOSITION, **(reasoning.composition or {})}
    composition = _apply_customer_overrides(composition, state)

    colors = dict(brand.colors or {})
    blueprint_colors = reasoning.blueprint or {}
    for key in ("primary_color", "secondary_color", "accent_color"):
        if not colors.get(key) and blueprint_colors.get(key):
            colors[key] = blueprint_colors[key]

    visual_uri = resolve_visual(state, capture, composition)
    if composition.get("use_visual") and not visual_uri:
        composition["use_visual"] = False
        composition["visual_source"] = "none"

    logo_uri = brand.logo_data_uri
    if logo_uri and not logo_is_usable(logo_uri):
        state.trace.degrade(
            Degradation.COMPOSITION_LOGO_DROPPED_UNUSABLE, Stage.COMPOSITION,
            detail="logo crop reads as a smudge at card size; using the wordmark",
        )
        logo_uri = None

    if logo_uri:
        role = composition.get("panel_color_role", "primary")
        alternate_role = "light" if role != "light" else "dark"
        fix = resolve_logo_contrast(
            logo_uri,
            panel_hex=_panel_hex(colors, role),
            panel_color_role=role,
            alternate_panel_hex=_panel_hex(colors, alternate_role),
            alternate_role=alternate_role,
        )
        if fix.changed:
            state.trace.degrade(
                Degradation.COMPOSITION_LOGO_PANEL_CONTRAST_FIX, Stage.COMPOSITION,
                detail=fix.detail,
            )
        composition = apply_contrast_fix_to_spec(composition, fix)
        logo_uri = None if fix.drop_logo else fix.logo_data_uri

    prefs = _card_prefs(state)
    subtitle = reasoning.subtitle or prefs.get("tagline")
    font_family = _brand_font(state, prefs)

    spec = CompositionSpec(
        title=reasoning.title,
        subtitle=subtitle,
        url=state.url,
        brand_name=brand.brand_name,
        colors=colors,
        composition=composition,
        logo_data_uri=logo_uri,
        visual_data_uri=visual_uri,
        proof=reasoning.proof,
        cta_text=reasoning.cta_text,
        hide_watermark=_hide_watermark(state),
        font_family=font_family,
        size=size,
    )
    state.trace.template_selected = composition.get("layout")
    state.trace.template_rationale = (reasoning.blueprint or {}).get("layout_reasoning")
    state.trace.degrade(
        Degradation.COMPOSITION_OK, Stage.COMPOSITION,
        detail=f"layout={composition.get('layout')} visual={bool(visual_uri)} logo={bool(logo_uri)}",
    )
    return spec


def build_minimal_spec(
    state: PipelineState,
    capture: Optional[CaptureResult],
    brand: Optional[BrandResult],
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    size: str = "wide",
) -> CompositionSpec:
    """The deterministic fallback card: same renderer, simpler spec.

    This is what "degrade content, not design language" means. When reasoning
    fails there is still a title, a palette, and a wordmark — enough for the
    premium renderer to produce a card that looks like the product. The old
    engine instead fell through to a different rasterizer, which is how a
    reasoning hiccup turned into a visibly worse-looking card.

    Everything here is derived without a model call, so it cannot fail for the
    same reason reasoning just did.
    """
    brand = brand or BrandResult()
    resolved_title = (title or "").strip() or _title_from_page(capture, state.url)
    colors = dict(brand.colors or {})

    prefs = _card_prefs(state)
    logo_uri = brand.logo_data_uri if logo_is_usable(brand.logo_data_uri) else None

    state.trace.degrade(
        Degradation.COMPOSITION_MINIMAL_SPEC, Stage.COMPOSITION,
        detail="building the deterministic minimal card — title, palette, wordmark",
    )
    # The fallback card is simpler content, not a different brand: the site's
    # layout, panel, accent and font still apply. Dropping them here is what
    # made a degraded generation look like somebody else's product.
    composition = _apply_customer_overrides(dict(DEFAULT_COMPOSITION), state)
    return CompositionSpec(
        title=resolved_title,
        subtitle=subtitle or _description_from_page(capture) or prefs.get("tagline"),
        url=state.url,
        brand_name=brand.brand_name or _brand_from_url(state.url),
        colors=colors,
        composition=composition,
        logo_data_uri=logo_uri,
        visual_data_uri=None,
        proof=None,
        cta_text=None,
        hide_watermark=_hide_watermark(state),
        font_family=_brand_font(state, prefs),
        size=size,
        minimal=True,
    )


def _title_from_page(capture: Optional[CaptureResult], url: str) -> str:
    """The page's own best title, or a readable name derived from the URL."""
    if capture and capture.html:
        try:
            from backend.services.metadata_extractor import extract_metadata_from_html

            metadata = extract_metadata_from_html(capture.html) or {}
            for key in ("og_title", "title", "twitter_title"):
                value = (metadata.get(key) or "").strip()
                if len(value) > 3:
                    return value[:100]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Metadata title extraction failed: %s", exc)
    return _brand_from_url(url)


def _description_from_page(capture: Optional[CaptureResult]) -> Optional[str]:
    if not (capture and capture.html):
        return None
    try:
        from backend.services.metadata_extractor import extract_metadata_from_html

        metadata = extract_metadata_from_html(capture.html) or {}
        for key in ("og_description", "description", "twitter_description"):
            value = (metadata.get(key) or "").strip()
            if len(value) > 10:
                return value[:200]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Metadata description extraction failed: %s", exc)
    return None


def _brand_from_url(url: str) -> str:
    try:
        host = urlparse(url if "://" in url else f"https://{url}").hostname or url
        name = host.replace("www.", "").split(".")[0]
        return name.replace("-", " ").title() or url
    except Exception:  # noqa: BLE001
        return url
