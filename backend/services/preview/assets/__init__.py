"""Asset resolution: turning what a page offers into what the card can draw.

A logo arrives as an ``<img src>`` that might be a PNG, a WebP, an SVG, a data
URI, or a 404. A hero visual arrives as a box the art director drew on a
screenshot. Neither is usable until something checks it — which is what this
package does, and why the checks live here rather than scattered through the
renderer.

  ``rasterize_svg``  makes SVG logos drawable (they were skipped entirely)
  ``logo_is_usable`` rejects the crops that read as a smudge at 34px
  ``resolve_logo_contrast`` stops a white logo shipping on a white panel
  ``focal_crop``     crops the hero box and refuses the ones that grabbed a nav bar
"""

from backend.services.preview.assets.focal import (
    FocalCropResult,
    crop_focus,
    saliency_of,
)
from backend.services.preview.assets.logo import (
    LogoContrastFix,
    logo_dominant_tone,
    logo_is_usable,
    normalize_logo,
    rasterize_svg,
    resolve_logo_contrast,
    svg_rasterizer_available,
)

__all__ = [
    "FocalCropResult",
    "LogoContrastFix",
    "crop_focus",
    "logo_dominant_tone",
    "logo_is_usable",
    "normalize_logo",
    "rasterize_svg",
    "resolve_logo_contrast",
    "saliency_of",
    "svg_rasterizer_available",
]
