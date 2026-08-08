"""
Result Normalizer - Ensures consistent output across all pipeline paths.

The preview engine has multiple code paths that produce results:
- Full AI pipeline (Tier 1)
- Multi-modal fusion fallback (Tier 2)
- HTML-only extraction (Tier 3)
- URL-based minimal (Tier 4)
- Quality retry paths
- Error recovery paths

This module ensures ALL paths produce a consistently shaped
PreviewEngineResult with required fields populated and
quality metadata attached.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def normalize_ai_result(raw: Optional[Dict[str, Any]], url: str) -> Dict[str, Any]:
    """
    Normalize a raw AI/fusion result dict to the standard schema.

    Handles missing fields, type coercion, and field name mapping
    from various upstream formats.
    """
    if not raw or not isinstance(raw, dict):
        return _empty_result(url)

    # Title normalization
    title = (
        raw.get("title")
        or raw.get("the_hook")
        or raw.get("hook")
        or raw.get("headline")
        or ""
    )
    if isinstance(title, list):
        title = title[0] if title else ""
    title = str(title).strip()
    if not title or title.lower() in ("none", "null", "untitled", "n/a"):
        title = _title_from_url(url)
    elif _is_generic_placeholder_title(title):
        title = _title_from_url(url)

    # Description normalization
    description = (
        raw.get("description")
        or raw.get("key_benefit")
        or raw.get("benefit")
        or raw.get("summary")
        or ""
    )
    if isinstance(description, list):
        description = " ".join(str(d) for d in description)
    description = str(description).strip()[:500]

    # Subtitle
    subtitle = raw.get("subtitle") or raw.get("tagline") or raw.get("subheadline")
    if subtitle:
        subtitle = str(subtitle).strip()[:200]

    # Tags - filter out single common words and garbage
    tags = raw.get("tags") or raw.get("keywords") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    # Filter: tags should be meaningful (2+ chars, not generic stop words)
    STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "shall", "can", "that", "this", "it", "its",
                  "with", "for", "from", "into", "about", "than", "then", "when", "where",
                  "what", "which", "who", "whom", "how", "all", "each", "every", "both",
                  "and", "but", "or", "not", "no", "nor", "so", "yet", "of", "in", "on",
                  "at", "to", "by", "up", "out", "off", "over", "under", "between"}
    tags = [str(t).strip() for t in tags if str(t).strip().lower() not in STOP_WORDS and len(str(t).strip()) > 2]
    tags = tags[:10]

    # Credibility items
    credibility = raw.get("credibility_items") or raw.get("social_proof") or []
    if isinstance(credibility, str):
        credibility = [{"type": "metric", "value": credibility}]
    elif isinstance(credibility, list):
        normalized_cred = []
        for item in credibility:
            if isinstance(item, dict):
                normalized_cred.append(item)
            elif isinstance(item, str) and item.strip():
                normalized_cred.append({"type": "metric", "value": item})
        credibility = normalized_cred

    # Context items
    context = raw.get("context_items") or []
    if isinstance(context, str):
        context = []

    # CTA
    cta = raw.get("cta_text") or raw.get("primary_cta") or raw.get("cta")
    if cta:
        cta = str(cta).strip()[:80]

    # Blueprint normalization
    blueprint = _normalize_blueprint(raw.get("blueprint", {}), raw)

    # Primary image
    primary_image = raw.get("primary_image_base64") or raw.get("hero_image_base64")

    # Confidence
    confidence = 0.0
    for key in ("reasoning_confidence", "confidence", "analysis_confidence"):
        val = raw.get(key)
        if isinstance(val, (int, float)) and val > confidence:
            confidence = float(val)

    return {
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "tags": tags,
        "context_items": context,
        "credibility_items": credibility,
        "cta_text": cta,
        "primary_image_base64": primary_image,
        "blueprint": blueprint,
        "reasoning_confidence": confidence,
        "design_dna": raw.get("design_dna", {}),
        # Composition spec authored by the art director (preview_reasoning
        # SINGLE_PASS_PROMPT Step 4). Preserved verbatim so the premium HTML
        # renderer can honour the layout/visual/color/accent decision.
        "composition": raw.get("composition") if isinstance(raw.get("composition"), dict) else {},
    }


def _normalize_blueprint(blueprint: Any, parent: Dict[str, Any]) -> Dict[str, str]:
    """Normalize blueprint/design data to consistent schema."""
    if not isinstance(blueprint, dict):
        blueprint = {}

    # Color extraction from multiple possible locations
    design = parent.get("design", {}) or {}
    palette = design.get("color_palette", {}) or {}
    fused_design = parent.get("fused_design", {}) or {}

    primary = (
        blueprint.get("primary_color")
        or palette.get("primary")
        or fused_design.get("primary_color")
        or "#2563EB"
    )
    secondary = (
        blueprint.get("secondary_color")
        or palette.get("secondary")
        or fused_design.get("secondary_color")
        or "#1E40AF"
    )
    accent = (
        blueprint.get("accent_color")
        or palette.get("accent")
        or fused_design.get("accent_color")
        or "#F59E0B"
    )

    # Validate hex colors
    primary = _validate_hex(primary, "#2563EB")
    secondary = _validate_hex(secondary, "#1E40AF")
    accent = _validate_hex(accent, "#F59E0B")

    template_type = (
        blueprint.get("template_type")
        or parent.get("template_type")
        or "landing"
    )

    return {
        "template_type": str(template_type),
        "primary_color": primary,
        "secondary_color": secondary,
        "accent_color": accent,
        "coherence_score": blueprint.get("coherence_score", 0.7),
        "balance_score": blueprint.get("balance_score", 0.7),
        "clarity_score": blueprint.get("clarity_score", 0.7),
        "overall_quality": blueprint.get("overall_quality", "good"),
        "layout_reasoning": blueprint.get("layout_reasoning", ""),
        "composition_notes": blueprint.get("composition_notes", ""),
    }


def _validate_hex(color: Any, fallback: str) -> str:
    """Validate a hex color string, return fallback if invalid."""
    if not color or not isinstance(color, str):
        return fallback
    color = color.strip()
    if not color.startswith("#"):
        color = "#" + color
    # Strip to 7 chars (#RRGGBB)
    hex_part = color[1:]
    if len(hex_part) == 3:
        hex_part = "".join(c * 2 for c in hex_part)
    if len(hex_part) != 6:
        return fallback
    try:
        int(hex_part, 16)
        return "#" + hex_part
    except ValueError:
        return fallback


# Generic placeholder titles from No Code platforms, templates, etc.
_GENERIC_TITLE_PATTERNS = (
    "your news site",
    "your site",
    "live today",
    "your website",
    "welcome to",
    "get started",
    "my site",
    "your blog",
    "your page",
    "coming soon",
    "under construction",
)


def _is_generic_placeholder_title(title: str) -> bool:
    """Detect generic/placeholder titles that should be replaced with domain-based title."""
    if not title or len(title) < 5:
        return False
    lower = title.lower()
    return any(p in lower for p in _GENERIC_TITLE_PATTERNS)


def _title_from_url(url: str) -> str:
    """Generate a reasonable title from a URL."""
    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").replace("www.", "")
        if domain:
            return domain.split(".")[0].replace("-", " ").title()
    except Exception:
        pass
    return "Untitled"


def _empty_result(url: str) -> Dict[str, Any]:
    """Return a minimal valid result dict."""
    return {
        "title": _title_from_url(url),
        "subtitle": None,
        "description": "",
        "tags": [],
        "context_items": [],
        "credibility_items": [],
        "cta_text": None,
        "primary_image_base64": None,
        "blueprint": {
            "template_type": "landing",
            "primary_color": "#2563EB",
            "secondary_color": "#1E40AF",
            "accent_color": "#F59E0B",
            "coherence_score": 0.5,
            "balance_score": 0.5,
            "clarity_score": 0.5,
            "overall_quality": "fair",
            "layout_reasoning": "",
            "composition_notes": "",
        },
        "reasoning_confidence": 0.0,
        "design_dna": {},
    }


def normalize_engine_result(result, url: str) -> None:
    """
    Validate and fix a PreviewEngineResult in-place.

    Ensures all required fields are populated with sensible values
    regardless of which pipeline path produced the result.
    """
    # Title must not be empty or generic placeholder
    if not result.title or result.title.strip() == "":
        result.title = _title_from_url(url)
    elif _is_generic_placeholder_title(result.title):
        result.title = _title_from_url(url)

    # Description should be a string
    if result.description is None:
        result.description = ""

    # URL must be set
    if not result.url:
        result.url = url

    # Ensure list fields aren't None
    if result.tags is None:
        result.tags = []
    if result.context_items is None:
        result.context_items = []
    if result.credibility_items is None:
        result.credibility_items = []
    if result.warnings is None:
        result.warnings = []
    if result.quality_scores is None:
        result.quality_scores = {}

    # Blueprint must be a dict
    if not isinstance(result.blueprint, dict):
        result.blueprint = {}

    # Brand must be a dict
    if not isinstance(result.brand, dict):
        result.brand = {}
