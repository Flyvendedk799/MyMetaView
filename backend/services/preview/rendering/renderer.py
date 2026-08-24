"""The render stage."""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    Stage,
)
from backend.services.preview.stages import CompositionSpec, PipelineState, RenderResult

logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """The one rasterizer could not produce a card."""


def render_card(state: PipelineState, spec: CompositionSpec) -> RenderResult:
    """Rasterize a spec and upload the result.

    Returns a ``RenderResult`` whose ``error`` is set on failure rather than
    raising, because the caller's next move is to try the minimal spec — and
    that decision belongs to the coordinator, not here.
    """
    state.update_progress(0.82, "Rendering the card…")

    try:
        from backend.services.premium_card_renderer import render_premium_card_detailed

        png, rendered_layout = render_premium_card_detailed(**spec.render_kwargs())
    except Exception as exc:  # noqa: BLE001 — the coordinator decides what happens next
        detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        state.trace.degrade(
            Degradation.PREMIUM_RENDER_FAILED, Stage.RENDER,
            detail=detail, reason=FailureReason.RENDER_IMAGE_PIPELINE_ERROR,
        )
        logger.warning("Card render failed for %s: %s", state.url, detail)
        return RenderResult(error=detail, minimal=spec.minimal)

    if not png:
        state.trace.degrade(
            Degradation.PREMIUM_RENDER_FAILED, Stage.RENDER,
            detail="renderer returned no bytes",
            reason=FailureReason.RENDER_IMAGE_PIPELINE_ERROR,
        )
        return RenderResult(error="renderer returned no bytes", minimal=spec.minimal)

    image_url = upload_card(state, png, size=spec.size)
    if not image_url:
        state.trace.degrade(
            Degradation.RENDER_UPLOAD_FAILED, Stage.RENDER,
            detail="card rendered but upload failed",
            reason=FailureReason.RENDER_IMAGE_PIPELINE_ERROR,
        )
        return RenderResult(png=png, rendered_layout=rendered_layout,
                            error="upload failed", minimal=spec.minimal)

    state.trace.degrade(
        Degradation.PREMIUM_RENDER_MINIMAL_SPEC if spec.minimal
        else Degradation.PREMIUM_RENDER_OK,
        Stage.RENDER,
        detail=f"layout={rendered_layout} {len(png)}B",
    )
    return RenderResult(
        png=png,
        image_url=image_url,
        rendered_layout=rendered_layout,
        render_spec=render_spec_from(state, spec, rendered_layout),
        minimal=spec.minimal,
    )


def upload_card(state: PipelineState, png: bytes, *, size: str = "wide") -> Optional[str]:
    try:
        from backend.services.r2_client import upload_file_to_r2

        folder = "demo" if state.is_demo else "saas"
        suffix = "" if size == "wide" else f"-{size}"
        return upload_file_to_r2(png, f"previews/{folder}/{uuid4()}{suffix}.png", "image/png")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Card upload failed: %s", exc)
        return None


def render_spec_from(
    state: PipelineState,
    spec: CompositionSpec,
    rendered_layout: Optional[str],
) -> Dict[str, Any]:
    """Everything a later render needs, minus the page.

    The two crops go to object storage and the spec holds their URLs: this dict
    is JSON-cached in Redis and persisted per preview, and inlining hundreds of
    KB of base64 into both was never affordable.
    """
    return {
        "composition": dict(spec.composition),
        "colors": dict(spec.colors),
        "brand_name": spec.brand_name,
        "subtitle": spec.subtitle,
        "proof": spec.proof,
        "cta_text": spec.cta_text,
        "hide_watermark": spec.hide_watermark,
        "logo_url": _stash(state, spec.logo_data_uri, "logo"),
        "visual_url": _stash(state, spec.visual_data_uri, "visual"),
        "rendered_layout": rendered_layout,
        "minimal": spec.minimal,
    }


def _stash(state: PipelineState, data_uri: Optional[str], kind: str) -> Optional[str]:
    """Persist a crop so a later render can fetch it instead of re-deriving it."""
    if not data_uri or "," not in data_uri:
        return None
    try:
        from backend.services.r2_client import upload_file_to_r2

        header, payload = data_uri.split(",", 1)
        content_type = "image/svg+xml" if "svg" in header else "image/png"
        extension = "svg" if "svg" in header else "png"
        folder = "demo" if state.is_demo else "saas"
        return upload_file_to_r2(
            base64.b64decode(payload),
            f"crops/{folder}/{kind}-{uuid4()}.{extension}",
            content_type,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not stash %s crop: %s", kind, exc)
        return None
