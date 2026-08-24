"""
AI-driven visual focus detection for link preview images.

Production-hardened implementation with:
- Strict output schema validation
- Explicit page intent detection
- Deterministic fallback logic
- Performance guardrails
- Full observability
"""
import json
import base64
import logging
import time
import hashlib
from io import BytesIO
from typing import Tuple, Optional, Dict, Any, List, Literal
from dataclasses import dataclass, asdict
from enum import Enum
from PIL import Image
from openai import OpenAI
from backend.core.config import settings

logger = logging.getLogger("preview_worker")


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

class PageIntent(str, Enum):
    """Supported page intent types with explicit crop strategies."""
    CONVERSION = "conversion"  # CTA / form focused
    CONTENT = "content"        # Headline / hero / article
    PRODUCT = "product"        # Product image / pricing
    BRANDING = "branding"      # Brand visual identity
    DATA = "data"              # Metrics, charts, dashboards
    UNKNOWN = "unknown"        # Fallback


@dataclass
class FocusRegion:
    """Validated focus region coordinates (0.0 - 1.0 normalized)."""
    x: float
    y: float
    width: float
    height: float
    
    def __post_init__(self):
        """Validate coordinates are within bounds."""
        self.x = max(0.0, min(1.0, float(self.x)))
        self.y = max(0.0, min(1.0, float(self.y)))
        self.width = max(0.1, min(1.0, float(self.width)))
        self.height = max(0.1, min(1.0, float(self.height)))
        
        # Ensure region doesn't exceed image bounds
        if self.x + self.width > 1.0:
            self.width = 1.0 - self.x
        if self.y + self.height > 1.0:
            self.height = 1.0 - self.y
    
    def is_valid(self) -> bool:
        """Check if region is geometrically valid."""
        return (
            0 <= self.x <= 1.0 and
            0 <= self.y <= 1.0 and
            self.width >= 0.1 and
            self.height >= 0.1 and
            self.x + self.width <= 1.0 and
            self.y + self.height <= 1.0
        )


@dataclass
class AIFocusResult:
    """Strict schema for AI focus analysis output."""
    focus_region: FocusRegion
    intent_type: PageIntent
    confidence: float
    primary_reason: str
    secondary_elements: List[str]
    
    # Metadata for observability
    model_used: str = "gpt-4o"
    processing_time_ms: int = 0
    fallback_used: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize fields."""
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if isinstance(self.intent_type, str):
            try:
                self.intent_type = PageIntent(self.intent_type.lower())
            except ValueError:
                self.intent_type = PageIntent.UNKNOWN
    
    def meets_threshold(self, min_confidence: float = 0.7) -> bool:
        """Check if result meets confidence threshold."""
        return self.confidence >= min_confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "focus_region": asdict(self.focus_region),
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "primary_reason": self.primary_reason,
            "secondary_elements": self.secondary_elements,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
            "fallback_used": self.fallback_used
        }


# =============================================================================
# CONFIGURATION
# =============================================================================

class FocusConfig:
    """Configuration for AI visual focus system."""
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD: float = 0.7
    RELAXED_CONFIDENCE_THRESHOLD: float = 0.5
    
    # Timeouts (seconds)
    AI_CALL_TIMEOUT: int = 30
    TOTAL_PROCESSING_TIMEOUT: int = 45
    
    # Retry settings
    MAX_RETRIES: int = 2
    RETRY_DELAY: float = 1.0
    
    # Image settings
    MAX_IMAGE_DIMENSION: int = 2048  # Resize if larger
    JPEG_QUALITY: int = 85  # For compression before AI
    
    # Fallback order (explicit)
    FALLBACK_ORDER: List[str] = [
        "ai_high_confidence",
        "ai_relaxed_confidence", 
        "cv_heuristic",
        "og_image",
        "full_screenshot"
    ]


# =============================================================================
# INTENT-BASED CROP STRATEGIES
# =============================================================================

def get_crop_strategy(intent: PageIntent) -> Dict[str, Any]:
    """
    Get crop strategy based on detected page intent.
    
    Each intent has specific guidance for what to prioritize.
    """
    strategies = {
        PageIntent.CONVERSION: {
            "priority_elements": ["cta_button", "form", "signup"],
            "include_context": True,
            "prefer_region": "center",
            "min_cta_coverage": 0.3,
            "description": "Focus on CTA with supporting context"
        },
        PageIntent.CONTENT: {
            "priority_elements": ["headline", "hero_image", "article_header"],
            "include_context": True,
            "prefer_region": "top",
            "min_headline_coverage": 0.4,
            "description": "Focus on headline and hero image"
        },
        PageIntent.PRODUCT: {
            "priority_elements": ["product_image", "price", "usp"],
            "include_context": True,
            "prefer_region": "center",
            "min_product_coverage": 0.5,
            "description": "Focus on product with price/USP"
        },
        PageIntent.BRANDING: {
            "priority_elements": ["logo", "brand_visual", "tagline"],
            "include_context": False,
            "prefer_region": "top",
            "min_brand_coverage": 0.3,
            "description": "Focus on brand visual identity"
        },
        PageIntent.DATA: {
            "priority_elements": ["chart", "metric", "dashboard_widget"],
            "include_context": True,
            "prefer_region": "center",
            "min_data_coverage": 0.4,
            "description": "Focus on primary metric or chart"
        },
        PageIntent.UNKNOWN: {
            "priority_elements": ["headline", "hero"],
            "include_context": True,
            "prefer_region": "top",
            "description": "Default to top-center content"
        }
    }
    return strategies.get(intent, strategies[PageIntent.UNKNOWN])


# =============================================================================
# SCHEMA VALIDATION
# =============================================================================

def validate_ai_response(response_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate AI response matches expected schema.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["focus_region", "intent_type", "confidence", "primary_reason"]
    
    # Check required fields
    for field in required_fields:
        if field not in response_data:
            return False, f"Missing required field: {field}"
    
    # Validate focus_region structure
    region = response_data.get("focus_region", {})
    region_fields = ["x", "y", "width", "height"]
    for field in region_fields:
        if field not in region:
            return False, f"Missing focus_region field: {field}"
        try:
            val = float(region[field])
            if not (0.0 <= val <= 1.0):
                return False, f"focus_region.{field} out of range: {val}"
        except (TypeError, ValueError):
            return False, f"focus_region.{field} is not a valid number"
    
    # Validate intent_type
    intent = response_data.get("intent_type", "").lower()
    valid_intents = [e.value for e in PageIntent]
    if intent not in valid_intents:
        return False, f"Invalid intent_type: {intent}"
    
    # Validate confidence
    try:
        conf = float(response_data.get("confidence", 0))
        if not (0.0 <= conf <= 1.0):
            return False, f"Confidence out of range: {conf}"
    except (TypeError, ValueError):
        return False, "Confidence is not a valid number"
    
    # Validate primary_reason is a non-empty string
    reason = response_data.get("primary_reason", "")
    if not isinstance(reason, str) or len(reason) < 5:
        return False, "primary_reason must be a meaningful string"
    
    return True, None


def parse_ai_response(raw_content: str, processing_time_ms: int) -> Tuple[Optional[AIFocusResult], Optional[str]]:
    """
    Parse and validate AI response into typed schema.
    
    Returns:
        Tuple of (result, error_message)
    """
    try:
        # Extract JSON from potential markdown
        content = raw_content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        
        # Validate schema
        is_valid, error = validate_ai_response(data)
        if not is_valid:
            return None, f"Schema validation failed: {error}"
        
        # Build typed result
        region = data["focus_region"]
        result = AIFocusResult(
            focus_region=FocusRegion(
                x=float(region["x"]),
                y=float(region["y"]),
                width=float(region["width"]),
                height=float(region["height"])
            ),
            intent_type=data["intent_type"],
            confidence=float(data["confidence"]),
            primary_reason=data["primary_reason"],
            secondary_elements=data.get("secondary_elements", []),
            processing_time_ms=processing_time_ms
        )
        
        # Final geometry validation
        if not result.focus_region.is_valid():
            return None, "Focus region geometry is invalid"
        
        return result, None
        
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except Exception as e:
        return None, f"Parse error: {e}"


# =============================================================================
# AI ANALYSIS CORE
# =============================================================================

def call_vision_api(image_base64: str, timeout: int = FocusConfig.AI_CALL_TIMEOUT) -> Tuple[Optional[str], Optional[str], int]:
    """
    Call OpenAI Vision API with timeout and error handling.
    
    Returns:
        Tuple of (response_content, error_message, processing_time_ms)
    """
    start_time = time.time()
    
    try:
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("visual_focus")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "system",
                    "content": """You are a UI/UX visual analysis expert. Analyze webpage screenshots to identify the PRIMARY FOCAL REGION.

OUTPUT STRICT JSON SCHEMA (no markdown, no explanation):
{
    "focus_region": {
        "x": <0.0-1.0 left edge ratio>,
        "y": <0.0-1.0 top edge ratio>,
        "width": <0.0-1.0 width ratio>,
        "height": <0.0-1.0 height ratio>
    },
    "intent_type": "<conversion|content|product|branding|data>",
    "confidence": <0.0-1.0>,
    "primary_reason": "<one sentence explaining the focus choice>",
    "secondary_elements": ["<other notable elements>"]
}

INTENT TYPES:
- conversion: Page has CTA, form, signup as primary focus
- content: Page focuses on headline, article, or hero content
- product: Page showcases product, pricing, or features
- branding: Page emphasizes brand identity, logo, visual style
- data: Page displays metrics, charts, or dashboard data

PRINCIPLES:
1. Visual hierarchy - larger, bolder, higher contrast elements
2. CTA prominence - buttons and forms are intentional focus points
3. F-pattern scanning - users focus top-left first, then scan right
4. The region should work at small sizes (preview cards)
5. Prefer 1.91:1 aspect ratio coverage"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this webpage and return the focus region JSON. Be precise with coordinates."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=400,
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content
        return content, None, elapsed_ms
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return None, str(e), elapsed_ms


def analyze_visual_focus(screenshot_bytes: bytes) -> AIFocusResult:
    """
    Analyze screenshot using AI with full validation and fallback.
    
    This is the main entry point for AI analysis.
    
    Args:
        screenshot_bytes: Raw PNG screenshot bytes
        
    Returns:
        AIFocusResult with focus region and metadata
    """
    # Prepare image (compress for API efficiency)
    image_base64, prep_info = prepare_image_for_api(screenshot_bytes)
    
    # Attempt AI analysis with retries
    last_error = None
    for attempt in range(FocusConfig.MAX_RETRIES):
        content, error, elapsed_ms = call_vision_api(image_base64)
        
        if error:
            last_error = error
            logger.warning(f"AI vision call failed (attempt {attempt + 1}): {error}")
            if attempt < FocusConfig.MAX_RETRIES - 1:
                time.sleep(FocusConfig.RETRY_DELAY)
            continue
        
        # Parse and validate response
        result, parse_error = parse_ai_response(content, elapsed_ms)
        
        if parse_error:
            last_error = parse_error
            logger.warning(f"AI response validation failed (attempt {attempt + 1}): {parse_error}")
            if attempt < FocusConfig.MAX_RETRIES - 1:
                time.sleep(FocusConfig.RETRY_DELAY)
            continue
        
        # Check confidence threshold
        if result.meets_threshold(FocusConfig.HIGH_CONFIDENCE_THRESHOLD):
            logger.info(f"AI focus analysis succeeded: intent={result.intent_type.value}, "
                       f"confidence={result.confidence:.2f}, time={elapsed_ms}ms")
            return result
        
        # Try relaxed threshold
        if result.meets_threshold(FocusConfig.RELAXED_CONFIDENCE_THRESHOLD):
            result.fallback_used = "ai_relaxed_confidence"
            logger.info(f"AI focus analysis (relaxed): intent={result.intent_type.value}, "
                       f"confidence={result.confidence:.2f}")
            return result
        
        # Below relaxed threshold
        last_error = f"Confidence too low: {result.confidence:.2f}"
        logger.warning(f"AI confidence below threshold: {result.confidence:.2f}")
    
    # All retries failed - return fallback
    logger.warning(f"AI analysis failed after {FocusConfig.MAX_RETRIES} attempts: {last_error}")
    return get_fallback_result("ai_failed", last_error)


def prepare_image_for_api(screenshot_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Prepare image for API call (resize if needed, compress).
    
    Returns:
        Tuple of (base64_string, preparation_info)
    """
    image = Image.open(BytesIO(screenshot_bytes))
    original_size = image.size
    
    # Resize if too large
    max_dim = FocusConfig.MAX_IMAGE_DIMENSION
    if image.width > max_dim or image.height > max_dim:
        ratio = min(max_dim / image.width, max_dim / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to RGB if needed (JPEG doesn't support alpha)
    if image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    
    # Compress as JPEG for smaller payload
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=FocusConfig.JPEG_QUALITY)
    
    info = {
        "original_size": original_size,
        "processed_size": image.size,
        "compressed_bytes": buffer.tell()
    }
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8'), info


# =============================================================================
# FALLBACK LOGIC
# =============================================================================

def get_fallback_result(fallback_type: str, reason: str) -> AIFocusResult:
    """
    Get a deterministic fallback result with explicit logging.
    
    Fallback uses F-pattern principle: top-left focus.
    """
    logger.info(f"Using fallback: type={fallback_type}, reason={reason}")
    
    return AIFocusResult(
        focus_region=FocusRegion(
            x=0.0,
            y=0.0,
            width=1.0,
            height=0.55  # Top 55% - above the fold
        ),
        intent_type=PageIntent.UNKNOWN,
        confidence=0.3,
        primary_reason=f"Fallback ({fallback_type}): {reason}",
        secondary_elements=[],
        fallback_used=fallback_type
    )


# =============================================================================
# IMAGE CROPPING
# =============================================================================

def apply_focus_crop(
    screenshot_bytes: bytes,
    focus_result: AIFocusResult,
    target_ratio: float = 1.91
) -> bytes:
    """
    Apply focus crop to screenshot based on AI analysis.
    
    Args:
        screenshot_bytes: Original screenshot
        focus_result: AI analysis result
        target_ratio: Target aspect ratio (width/height)
        
    Returns:
        Cropped and resized image bytes
    """
    image = Image.open(BytesIO(screenshot_bytes))
    img_width, img_height = image.size
    
    region = focus_result.focus_region
    
    # Convert normalized coordinates to pixels
    focal_x = int(img_width * region.x)
    focal_y = int(img_height * region.y)
    focal_w = int(img_width * region.width)
    focal_h = int(img_height * region.height)
    
    # Calculate crop that fits target aspect ratio
    crop_box = calculate_aspect_crop(
        img_width, img_height,
        focal_x, focal_y, focal_w, focal_h,
        target_ratio
    )
    
    # Crop
    cropped = image.crop(crop_box)
    
    # Resize to standard output dimensions
    if target_ratio > 1.5:  # Wide format (OG)
        output_size = (1200, 630)
    else:  # Square-ish
        output_size = (600, 600)
    
    final = cropped.resize(output_size, Image.Resampling.LANCZOS)
    
    # Output as PNG
    buffer = BytesIO()
    final.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def calculate_aspect_crop(
    img_w: int, img_h: int,
    focal_x: int, focal_y: int,
    focal_w: int, focal_h: int,
    target_ratio: float
) -> Tuple[int, int, int, int]:
    """
    Calculate crop box that includes focal region and matches aspect ratio.
    """
    # Focal center
    center_x = focal_x + focal_w // 2
    center_y = focal_y + focal_h // 2
    
    # Start with focal dimensions, adjust to aspect ratio
    if focal_w / max(focal_h, 1) > target_ratio:
        crop_w = focal_w
        crop_h = int(crop_w / target_ratio)
    else:
        crop_h = focal_h
        crop_w = int(crop_h * target_ratio)
    
    # Ensure minimum coverage (50% of image width)
    min_w = int(img_w * 0.5)
    if crop_w < min_w:
        crop_w = min_w
        crop_h = int(crop_w / target_ratio)
    
    # Clamp to image bounds
    crop_w = min(crop_w, img_w)
    crop_h = min(crop_h, img_h)
    
    # Recalculate to maintain ratio
    if crop_w / crop_h > target_ratio:
        crop_w = int(crop_h * target_ratio)
    else:
        crop_h = int(crop_w / target_ratio)
    
    # Position centered on focal point
    left = center_x - crop_w // 2
    top = center_y - crop_h // 2
    
    # Adjust if out of bounds
    left = max(0, min(left, img_w - crop_w))
    top = max(0, min(top, img_h - crop_h))
    
    return (left, top, left + crop_w, top + crop_h)


# =============================================================================
# MAIN ENTRY POINTS
# =============================================================================

def generate_ai_focused_preview(
    screenshot_bytes: bytes,
    target_ratio: str = "1.91:1"
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Generate AI-focused preview image with full pipeline.
    
    Args:
        screenshot_bytes: Raw PNG screenshot bytes
        target_ratio: Target aspect ratio string
        
    Returns:
        Tuple of (cropped_image_bytes, analysis_metadata)
    """
    ratio_value = 1.0 if target_ratio == "1:1" else 1.91
    
    # Run AI analysis
    analysis = analyze_visual_focus(screenshot_bytes)
    
    # Apply crop based on analysis
    cropped_bytes = apply_focus_crop(screenshot_bytes, analysis, ratio_value)
    
    # Return with full metadata
    return cropped_bytes, analysis.to_dict()


# =============================================================================
# VERIFICATION & TESTING
# =============================================================================

def run_comparison_test(
    screenshot_bytes: bytes,
    url: str,
    save_debug: bool = False
) -> Dict[str, Any]:
    """
    Run comparison test between AI crop and basic heuristic crop.
    
    Used for verification and proof of improvement.
    
    Args:
        screenshot_bytes: Raw screenshot
        url: Source URL for logging
        save_debug: Whether to save debug images
        
    Returns:
        Comparison results with both crops and metadata
    """
    from backend.jobs.screenshot_generation import generate_basic_highlight_image
    
    results = {
        "url": url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": None,
        "ai_crop_success": False,
        "heuristic_crop_success": False,
        "comparison": {}
    }
    
    # AI crop
    try:
        ai_bytes, ai_metadata = generate_ai_focused_preview(screenshot_bytes)
        results["ai_analysis"] = ai_metadata
        results["ai_crop_success"] = True
        results["ai_crop_size"] = len(ai_bytes)
    except Exception as e:
        results["ai_error"] = str(e)
    
    # Heuristic crop
    try:
        heuristic_bytes = generate_basic_highlight_image(screenshot_bytes)
        results["heuristic_crop_success"] = True
        results["heuristic_crop_size"] = len(heuristic_bytes)
    except Exception as e:
        results["heuristic_error"] = str(e)
    
    # Comparison metrics
    if results["ai_crop_success"] and results.get("ai_analysis"):
        analysis = results["ai_analysis"]
        results["comparison"] = {
            "ai_confidence": analysis.get("confidence", 0),
            "ai_intent": analysis.get("intent_type", "unknown"),
            "ai_reason": analysis.get("primary_reason", ""),
            "ai_fallback_used": analysis.get("fallback_used"),
            "ai_processing_time_ms": analysis.get("processing_time_ms", 0)
        }
    
    logger.info(f"Comparison test completed for {url}: "
                f"AI={results['ai_crop_success']}, "
                f"Heuristic={results['heuristic_crop_success']}")
    
    return results


# =============================================================================
# TEST URL SET
# =============================================================================

TEST_URLS = [
    # Landing pages with CTAs
    "https://stripe.com",
    "https://www.notion.so",
    "https://slack.com",
    "https://www.dropbox.com",
    
    # Blog/articles
    "https://blog.google",
    "https://engineering.fb.com",
    
    # Product pages
    "https://www.apple.com/iphone",
    "https://www.samsung.com/smartphones",
    
    # SaaS dashboards (public pages)
    "https://analytics.google.com",
    "https://www.datadog.com",
    
    # E-commerce
    "https://www.amazon.com",
    "https://www.shopify.com",
]


def run_verification_suite(urls: List[str] = None) -> List[Dict[str, Any]]:
    """
    Run verification suite on test URLs.
    
    This is for internal testing and proof of improvement.
    """
    from backend.services.playwright_screenshot import capture_screenshot
    
    if urls is None:
        urls = TEST_URLS
    
    results = []
    
    for url in urls:
        logger.info(f"Testing URL: {url}")
        try:
            # Capture screenshot
            screenshot = capture_screenshot(url)
            
            # Run comparison
            result = run_comparison_test(screenshot, url)
            results.append(result)
            
        except Exception as e:
            results.append({
                "url": url,
                "error": str(e),
                "ai_crop_success": False,
                "heuristic_crop_success": False
            })
    
    # Summary
    ai_success = sum(1 for r in results if r.get("ai_crop_success"))
    heuristic_success = sum(1 for r in results if r.get("heuristic_crop_success"))
    
    logger.info(f"Verification complete: {ai_success}/{len(results)} AI success, "
                f"{heuristic_success}/{len(results)} heuristic success")
    
    return results
