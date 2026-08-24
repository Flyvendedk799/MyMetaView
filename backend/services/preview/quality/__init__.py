"""Quality: gates, critics, and the pixel metrics they all read.

The engine's guiding principle is that the rendered PNG is the unit of quality.
Everything in this package therefore takes bytes of a finished card and returns
numbers about *that*, not about the dicts that produced it.

``pixel_metrics`` is the shared substrate: the corpus scorer, the runtime
soft-pass policy, and the CI regression gate all call the same functions, so a
score in a nightly report means the same thing as a score in a job trace.
"""

from backend.services.preview.quality.pixel_metrics import (
    CardScore,
    contrast_ratio,
    detect_gradient_only,
    logo_slot_occupancy,
    palette_delta_e,
    score_card,
    text_overflow_risk,
)
from backend.services.preview.quality.policy import (
    SoftPassPolicy,
    evaluate_card,
)

__all__ = [
    "CardScore",
    "SoftPassPolicy",
    "contrast_ratio",
    "detect_gradient_only",
    "evaluate_card",
    "logo_slot_occupancy",
    "palette_delta_e",
    "score_card",
    "text_overflow_risk",
]
