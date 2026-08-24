"""Which model runs which stage, and what it cost.

``gpt-4o`` was written into six call sites across three files. Every model
migration was therefore a code change in three places, and the one time the
gateway changed behind us — rejecting ``temperature`` with a 400 — the incident
was "the multi-agent orchestrator is broken" rather than "one parameter needs a
config edit".

The fix is a table. Stages name what they need; the table says which model
answers and with what parameters; the resolver reads an env override first so a
migration is a deploy variable, not a release.

The tiering is the other half. Vision reasoning genuinely needs the flagship
model — it is reading a screenshot and authoring a composition. Classifying a
page, cleaning up a brand name, and extracting tags do not, and paying flagship
rates for them was most of the per-preview cost. Every downgrade here is
arbitrated by the corpus scores and the cost dashboard, which is why the map
lives beside them rather than being spread through the call sites.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Dict, Optional

from backend.services.preview.observability.reason_codes import Stage

logger = logging.getLogger(__name__)


# Prices per 1M tokens, mirrored from ai_cost_optimizer so cost accounting works
# for models that table does not know about. Unknown models cost 0 rather than
# raising: a missing price should under-report a dashboard, never fail a job.
MODEL_PRICES_PER_MTOK: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}


@dataclass(frozen=True)
class ModelSpec:
    """One stage's model and the parameters it is called with.

    ``supports_temperature`` exists because of the gateway incident: the model
    behind our gateway 400s on it. Rather than a global SDK monkey-patch that
    silently drops the parameter for everyone, the stage declares whether its
    model accepts it, and the caller simply does not send it. Config, not a
    patch — which was the roadmap's whole point about that incident.
    """

    model: str
    max_tokens: int = 2000
    temperature: Optional[float] = None
    supports_temperature: bool = False
    supports_vision: bool = False
    supports_json_schema: bool = True
    timeout_s: int = 60

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        prices = MODEL_PRICES_PER_MTOK.get(self.model)
        if not prices:
            return 0.0
        return round(
            (input_tokens / 1_000_000) * prices["input"]
            + (output_tokens / 1_000_000) * prices["output"],
            6,
        )

    def request_kwargs(self) -> Dict[str, object]:
        """Kwargs for a chat completion, minus what this model rejects."""
        kwargs: Dict[str, object] = {"model": self.model, "max_tokens": self.max_tokens}
        if self.supports_temperature and self.temperature is not None:
            kwargs["temperature"] = self.temperature
        return kwargs


# The flagship: reads a screenshot and authors copy plus a composition spec.
# This is the card. Do not tier it down without a corpus run that says so.
_ART_DIRECTOR = ModelSpec(
    model="gpt-4o",
    max_tokens=4000,
    supports_vision=True,
    timeout_s=60,
)

# Vision, but a narrower job: find the logo, read the palette off the page.
_VISION_UTILITY = ModelSpec(
    model="gpt-4o",
    max_tokens=1200,
    supports_vision=True,
    timeout_s=30,
)

# Text-only bookkeeping: classify, tidy a brand name, pull tags. A small model
# is as good at these and roughly 16× cheaper.
_TEXT_UTILITY = ModelSpec(
    model="gpt-4o-mini",
    max_tokens=1000,
    supports_vision=False,
    timeout_s=25,
)

# Grades a rendered PNG against a short rubric. Needs eyes, not brilliance.
_PIXEL_CRITIC = ModelSpec(
    model="gpt-4o-mini",
    max_tokens=600,
    supports_vision=True,
    timeout_s=25,
)


# Purpose → spec. Purposes are finer-grained than stages because one stage runs
# several kinds of call (the extraction stage does both logo vision and brand
# name cleanup) and they do not deserve the same model.
STAGE_MODELS: Dict[str, ModelSpec] = {
    "art_director": _ART_DIRECTOR,
    "layout_reasoning": _ART_DIRECTOR,
    "logo_detection": _VISION_UTILITY,
    "brand_extraction": _VISION_UTILITY,
    "ui_elements": _VISION_UTILITY,
    "classification": _TEXT_UTILITY,
    "tags": _TEXT_UTILITY,
    "brand_name": _TEXT_UTILITY,
    "copy_refinement": _TEXT_UTILITY,
    "quality_critic": _PIXEL_CRITIC,
    "pixel_critic": _PIXEL_CRITIC,
}

# Fallback for a purpose nobody registered — the flagship, because guessing
# small on an unknown call is how quality regresses quietly.
DEFAULT_SPEC = _ART_DIRECTOR

# Which stage a purpose belongs to, for cost attribution in the trace.
PURPOSE_STAGES: Dict[str, Stage] = {
    "art_director": Stage.REASONING,
    "layout_reasoning": Stage.REASONING,
    "logo_detection": Stage.EXTRACTION,
    "brand_extraction": Stage.EXTRACTION,
    "ui_elements": Stage.EXTRACTION,
    "classification": Stage.CLASSIFY,
    "tags": Stage.REASONING,
    "brand_name": Stage.EXTRACTION,
    "copy_refinement": Stage.REASONING,
    "quality_critic": Stage.QUALITY,
    "pixel_critic": Stage.QUALITY,
}


def _env_override(purpose: str) -> Optional[str]:
    """``PREVIEW_MODEL_ART_DIRECTOR=gpt-4.1`` overrides one purpose.

    ``PREVIEW_MODEL_DEFAULT`` overrides every purpose that has no specific
    variable, which is what makes a gateway migration one deploy variable.
    """
    specific = os.getenv(f"PREVIEW_MODEL_{purpose.upper()}")
    if specific:
        return specific.strip()
    shared = os.getenv("PREVIEW_MODEL_DEFAULT")
    return shared.strip() if shared else None


def spec_for(purpose: str, *, profile: Optional[object] = None) -> ModelSpec:
    """The model spec for one purpose.

    Resolution order: env override → the profile's own map → the table. A
    profile can carry ``model_overrides`` so the template lane and the ultra
    lane can differ without a second table.
    """
    spec = STAGE_MODELS.get(purpose, DEFAULT_SPEC)

    overrides = getattr(profile, "model_overrides", None) if profile is not None else None
    if isinstance(overrides, dict) and purpose in overrides:
        spec = replace(spec, model=str(overrides[purpose]))

    override = _env_override(purpose)
    if override:
        spec = replace(spec, model=override)

    return spec


def stage_for(purpose: str) -> Stage:
    return PURPOSE_STAGES.get(purpose, Stage.REASONING)


def record_usage(
    trace: Optional[object],
    purpose: str,
    spec: ModelSpec,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Attribute one call's tokens and dollars to its stage on the trace.

    Returns the cost so a caller without a trace can still log it.
    """
    cost = spec.cost_usd(input_tokens, output_tokens)
    if trace is not None:
        try:
            trace.record_ai_usage(
                input_tokens, output_tokens,
                cost_usd=cost,
                stage=stage_for(purpose).value,
            )
        except Exception as exc:  # noqa: BLE001 — accounting never breaks a job
            logger.debug("Could not record AI usage for %s: %s", purpose, exc)
    return cost


def describe_map() -> Dict[str, Dict[str, object]]:
    """The resolved map, for the admin panel and the cost dashboard."""
    return {
        purpose: {
            "model": spec_for(purpose).model,
            "stage": stage_for(purpose).value,
            "vision": spec_for(purpose).supports_vision,
            "max_tokens": spec_for(purpose).max_tokens,
        }
        for purpose in sorted(STAGE_MODELS)
    }
