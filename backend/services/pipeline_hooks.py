"""
Pipeline Hooks - Pre/post processing hooks for each generation stage.

Provides cross-cutting concerns that apply to every pipeline run:
- Input validation (URL security, format)
- Stage telemetry (automatic timing, logging)
- Error recovery (per-stage fallback strategies)
- Result enrichment (metadata injection into final output)

These hooks wrap the core pipeline stages without modifying them,
keeping the engine focused on business logic while hooks handle
operational concerns.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from backend.services.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


# =============================================================================
# INPUT VALIDATION HOOKS
# =============================================================================

class InputValidator:
    """Validates and normalizes pipeline inputs before processing."""

    # Blocked schemes that could be dangerous
    BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}

    # Private IP ranges (SSRF protection)
    PRIVATE_PATTERNS = [
        re.compile(r"^localhost", re.IGNORECASE),
        re.compile(r"^127\."),
        re.compile(r"^10\."),
        re.compile(r"^172\.(1[6-9]|2[0-9]|3[01])\."),
        re.compile(r"^192\.168\."),
        re.compile(r"^0\.0\.0\.0"),
        re.compile(r"^\[::1\]"),
    ]

    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Validate and normalize a URL for pipeline processing.

        Returns the normalized URL or raises ValueError.
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL is required")

        url = url.strip()

        # Block dangerous schemes before adding default
        lower_url = url.lower()
        for scheme in cls.BLOCKED_SCHEMES:
            if lower_url.startswith(f"{scheme}:"):
                raise ValueError(f"Blocked URL scheme: {scheme}")

        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
        except Exception:
            raise ValueError(f"Invalid URL format: {url}")

        # Scheme check
        if parsed.scheme.lower() in cls.BLOCKED_SCHEMES:
            raise ValueError(f"Blocked URL scheme: {parsed.scheme}")

        # Must have a hostname
        if not parsed.hostname:
            raise ValueError("URL must have a hostname")

        # SSRF protection - block private IPs. ALLOW_PRIVATE_URLS is a
        # development/test escape hatch (capture a locally served fixture);
        # it is ignored in production.
        import os
        allow_private = (
            os.getenv("ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")
            and os.getenv("ENV", "development").lower() != "production"
        )
        hostname = parsed.hostname.lower()
        if not allow_private:
            for pattern in cls.PRIVATE_PATTERNS:
                if pattern.match(hostname):
                    raise ValueError("URLs pointing to private/internal networks are not allowed")

        # Must have a valid TLD (basic check)
        if "." not in hostname and hostname != "localhost":
            raise ValueError(f"Invalid hostname: {hostname}")

        # Length sanity
        if len(url) > 2048:
            raise ValueError("URL too long (max 2048 characters)")

        return url

    @classmethod
    def validate_for_pipeline(cls, ctx: PipelineContext) -> str:
        """Validate URL and attach normalized version to context."""
        normalized = cls.validate_url(ctx.url)
        ctx.url = normalized
        return normalized


# =============================================================================
# STAGE RECOVERY HOOKS
# =============================================================================

class StageRecovery:
    """
    Per-stage error recovery strategies.

    When a stage fails, the recovery hook decides whether to:
    - Retry with modified parameters
    - Fall back to a simpler approach
    - Skip the stage and continue
    - Abort the pipeline
    """

    @staticmethod
    def recover_capture(ctx: PipelineContext, error: Exception) -> Optional[Dict[str, Any]]:
        """Recovery for screenshot capture failures."""
        ctx.warn(f"Capture failed: {error}, attempting HTML-only fallback")
        try:
            import httpx
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(ctx.url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MetaViewBot/1.0)"
                })
                if resp.status_code == 200:
                    html_content = resp.text

                    # Create a minimal placeholder screenshot
                    from PIL import Image
                    from io import BytesIO
                    placeholder = Image.new("RGB", (1200, 630), color="#f0f0f0")
                    buf = BytesIO()
                    placeholder.save(buf, format="PNG")

                    return {
                        "screenshot_bytes": buf.getvalue(),
                        "html_content": html_content,
                        "dom_data": {},
                        "is_placeholder": True,
                    }
        except Exception as fallback_err:
            ctx.warn(f"HTML-only fallback also failed: {fallback_err}")
        return None

    @staticmethod
    def recover_ai_reasoning(ctx: PipelineContext, error: Exception) -> Optional[Dict[str, Any]]:
        """Recovery for AI reasoning failures - fall back to HTML extraction."""
        ctx.record_ai_error()
        ctx.warn(f"AI reasoning failed: {error}, falling back to HTML metadata")

        html_content = ctx.shared.get("html_content", "")
        if not html_content:
            return None

        try:
            from backend.services.metadata_extractor import extract_metadata_from_html
            metadata = extract_metadata_from_html(html_content)

            title = metadata.get("og_title") or metadata.get("title") or "Untitled"
            description = metadata.get("og_description") or metadata.get("description") or ""

            ctx.current_tier = max(ctx.current_tier, PipelineContext.__dataclass_fields__["current_tier"].default, key=lambda t: list(tier_order()).index(t))

            return {
                "title": title,
                "description": description,
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
                },
                "reasoning_confidence": 0.3,
                "design_dna": {},
                "is_html_fallback": True,
            }
        except Exception:
            return None

    @staticmethod
    def recover_image_generation(ctx: PipelineContext, error: Exception) -> Optional[str]:
        """Recovery for image generation - use cropped screenshot as og:image."""
        ctx.warn(f"Image generation failed: {error}, using cropped screenshot")
        screenshot_bytes = ctx.shared.get("screenshot_bytes")
        if not screenshot_bytes:
            return None

        try:
            from PIL import Image
            from io import BytesIO
            from uuid import uuid4
            from backend.services.r2_client import upload_file_to_r2

            img = Image.open(BytesIO(screenshot_bytes)).convert("RGB")
            # Crop to 1200x630 from top-center
            target_ratio = 1200 / 630
            img_ratio = img.width / img.height

            if img_ratio > target_ratio:
                new_h = 630
                new_w = int(new_h * img_ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - 1200) // 2
                img = img.crop((left, 0, left + 1200, 630))
            else:
                new_w = 1200
                new_h = int(new_w / img_ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                img = img.crop((0, 0, 1200, 630))

            buf = BytesIO()
            img.save(buf, format="PNG")
            filename = f"previews/fallback/{uuid4()}.png"
            return upload_file_to_r2(buf.getvalue(), filename, "image/png")
        except Exception:
            return None


def tier_order():
    """Return tiers in degradation order."""
    from backend.services.graceful_degradation import QualityTier
    return [
        QualityTier.TIER_1_FULL,
        QualityTier.TIER_2_STANDARD,
        QualityTier.TIER_3_BASIC,
        QualityTier.TIER_4_MINIMAL,
    ]


# =============================================================================
# RESULT ENRICHMENT HOOKS
# =============================================================================

class ResultEnricher:
    """Enriches the final PreviewEngineResult with pipeline metadata."""

    @staticmethod
    def enrich(ctx: PipelineContext, result) -> None:
        """
        Inject pipeline telemetry and diagnostics into the result.

        Mutates result in-place (PreviewEngineResult dataclass).
        """
        # Processing time
        result.processing_time_ms = ctx.elapsed_ms()

        # Merge warnings
        if ctx.warnings:
            if not hasattr(result, "warnings") or result.warnings is None:
                result.warnings = []
            result.warnings.extend(ctx.warnings)

        # Merge quality scores from context
        if ctx.quality_scores:
            if not result.quality_scores:
                result.quality_scores = {}
            result.quality_scores.update(ctx.quality_scores)

        # Add stage timing to quality_scores for observability
        result.quality_scores["pipeline_stages"] = {
            s.name: round(s.duration_ms)
            for s in ctx.stages
        }
        result.quality_scores["total_ms"] = ctx.elapsed_ms()
        result.quality_scores["tier"] = ctx.current_tier.value
        result.quality_scores["request_id"] = ctx.request_id


# =============================================================================
# POST-GENERATION QUALITY CHECK
# =============================================================================

class PostGenerationValidator:
    """
    Final validation before returning a result to the caller.

    Ensures every result has the minimum required fields populated,
    regardless of which tier or path produced it.
    """

    REQUIRED_FIELDS = ["title", "url"]

    @classmethod
    def validate(cls, result, ctx: PipelineContext) -> bool:
        """
        Validate a PreviewEngineResult meets minimum requirements.

        Returns True if valid, False if result should be rejected.
        """
        issues = []

        # Title must exist and not be empty
        if not getattr(result, "title", None) or result.title.strip() == "":
            issues.append("Missing title")

        # URL must match what we were asked to generate
        if not getattr(result, "url", None):
            result.url = ctx.url

        # Description shouldn't be None (empty string is ok)
        if result.description is None:
            result.description = ""

        # Composited image should exist (warn if not, but don't reject)
        if not getattr(result, "composited_preview_image_url", None):
            ctx.warn("No composited preview image generated")

        if issues:
            for issue in issues:
                ctx.warn(f"Validation: {issue}")
            return False

        return True
