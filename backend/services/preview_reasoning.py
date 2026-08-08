"""
Multi-Stage Preview Reasoning Framework with Design DNA Integration.

This module implements a systematic, step-by-step reasoning process for
generating high-quality preview reconstructions. The framework is designed
to generalize across different websites, layouts, and industries.

ENHANCED WITH DESIGN DNA:
- Now extracts design philosophy, typography personality, color psychology
- Understands WHY designers made choices, not just WHAT they made
- Produces previews that honor the original design's soul

DESIGN PRINCIPLES:
1. Explicit multi-stage reasoning (not heuristics)
2. Generalization over perfection for edge cases
3. Transparent decision framework
4. Premium SaaS quality bar
5. Modular and extensible
6. Design fidelity - honor the original design's intent

REASONING STAGES:
1. SEGMENTATION: Identify distinct UI/UX regions
2. PURPOSE ANALYSIS: Determine each region's communication role
3. PRIORITY ASSIGNMENT: Rank by visual importance
4. COMPOSITION DECISION: What to keep, reorder, or remove
5. LAYOUT SYNTHESIS: Generate optimized structure
6. COHERENCE CHECK: Validate balance, flow, and DESIGN FIDELITY
"""

import json
import re
import base64
import logging
import time
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from PIL import Image
from openai import OpenAI
from backend.core.config import settings
from backend.services.graceful_degradation import OpenAICircuitBreaker

# Initialize logger FIRST (before any code that uses it)
logger = logging.getLogger(__name__)

# Design DNA Integration
try:
    from backend.services.design_dna_extractor import extract_design_dna, extract_quick_dna, DesignDNA
    DESIGN_DNA_AVAILABLE = True
except ImportError:
    DESIGN_DNA_AVAILABLE = False

# ENHANCED: Quality Assurance Integrations
try:
    from backend.services.ai_output_validator import AIOutputValidator, validate_extraction_result
    from backend.services.extraction_quality_scorer import ExtractionQualityScorer, score_extraction_quality
    from backend.services.quality_gates import QualityGateEvaluator, QualityGateConfig, evaluate_quality_gates
    from backend.services.extraction_fallback_system import ExtractionFallbackSystem
    QUALITY_ASSURANCE_AVAILABLE = True
    logger.info("✨ Quality assurance system enabled (validation, scoring, gates, fallbacks)")
except ImportError as e:
    QUALITY_ASSURANCE_AVAILABLE = False
    logger.warning(f"Quality assurance system not available: {e}")

# Product Intelligence Integration (NEW - for e-commerce enhancement)
try:
    from backend.services.product_intelligence import (
        extract_product_intelligence,
        ProductInformation,
        ProductCategory
    )
    PRODUCT_INTELLIGENCE_AVAILABLE = True
    logger.info("🛍️ Product intelligence system enabled (pricing, urgency, ratings)")
except ImportError as e:
    PRODUCT_INTELLIGENCE_AVAILABLE = False
    logger.warning(f"Product intelligence system not available: {e}")


# =============================================================================
# REASONING SCHEMA
# =============================================================================

class RegionPurpose(str, Enum):
    """The communication purpose of a UI region."""
    IDENTITY = "identity"       # Who/what this is (name, logo, profile)
    VALUE_PROP = "value_prop"   # Core message or offering
    CONTEXT = "context"         # Supporting information (location, date)
    CREDIBILITY = "credibility" # Trust signals (ratings, testimonials)
    ACTION = "action"           # CTAs and conversion elements
    NAVIGATION = "navigation"   # Wayfinding elements
    DECORATION = "decoration"   # Visual enhancement only


class VisualWeight(str, Enum):
    """The visual weight/importance of an element."""
    HERO = "hero"           # Dominant visual anchor (1 per preview)
    PRIMARY = "primary"     # Key supporting element (1-2 per preview)
    SECONDARY = "secondary" # Supporting detail (2-4 per preview)
    TERTIARY = "tertiary"   # Minor detail (use sparingly)
    OMIT = "omit"           # Should not appear in preview


@dataclass
class AnalyzedRegion:
    """A UI region with full reasoning attached."""
    id: str
    content_type: str  # image, text, badge, button, etc.
    raw_content: str   # Exact extracted content
    
    # Stage 2: Purpose
    purpose: RegionPurpose
    purpose_reasoning: str
    
    # Stage 3: Priority
    visual_weight: VisualWeight
    priority_score: float  # 0-1
    priority_reasoning: str
    
    # Stage 4: Decision
    include_in_preview: bool
    decision_reasoning: str
    
    # Extracted values
    display_text: Optional[str] = None  # Clean text for display
    image_data: Optional[str] = None    # Base64 if image
    
    # Bounding box for cropping
    bbox: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content_type": self.content_type,
            "raw_content": self.raw_content,
            "purpose": self.purpose.value,
            "purpose_reasoning": self.purpose_reasoning,
            "visual_weight": self.visual_weight.value,
            "priority_score": self.priority_score,
            "priority_reasoning": self.priority_reasoning,
            "include_in_preview": self.include_in_preview,
            "decision_reasoning": self.decision_reasoning,
            "display_text": self.display_text,
            "has_image": self.image_data is not None,
            "bbox": self.bbox
        }


@dataclass
class LayoutBlueprint:
    """The final layout structure with explicit reasoning."""
    template_type: str  # profile, product, landing, article, service
    
    # Color palette extracted
    primary_color: str
    secondary_color: str
    accent_color: str
    
    # Content slots with assigned regions
    identity_slot: Optional[str] = None      # Main identifier (name/title)
    identity_image_slot: Optional[str] = None  # Avatar/logo/hero
    tagline_slot: Optional[str] = None       # Brief descriptor
    value_slot: Optional[str] = None         # Core value proposition
    context_slots: List[str] = field(default_factory=list)  # Location, date, etc.
    credibility_slots: List[str] = field(default_factory=list)  # Ratings, social proof
    action_slot: Optional[str] = None        # Primary CTA
    tags_slots: List[str] = field(default_factory=list)  # Skills, categories
    
    # Layout decisions
    layout_reasoning: str = ""
    composition_notes: str = ""
    
    # Quality metrics
    coherence_score: float = 0.0
    balance_score: float = 0.0
    clarity_score: float = 0.0
    overall_quality: str = "good"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_type": self.template_type,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "identity_slot": self.identity_slot,
            "identity_image_slot": self.identity_image_slot,
            "tagline_slot": self.tagline_slot,
            "value_slot": self.value_slot,
            "context_slots": self.context_slots,
            "credibility_slots": self.credibility_slots,
            "action_slot": self.action_slot,
            "tags_slots": self.tags_slots,
            "layout_reasoning": self.layout_reasoning,
            "composition_notes": self.composition_notes,
            "coherence_score": self.coherence_score,
            "balance_score": self.balance_score,
            "clarity_score": self.clarity_score,
            "overall_quality": self.overall_quality
        }


@dataclass
class ReasonedPreview:
    """Complete preview with full reasoning chain."""
    # Analyzed regions
    regions: List[AnalyzedRegion]
    
    # Layout blueprint
    blueprint: LayoutBlueprint
    
    # Final content for rendering
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    tags: List[str]
    context_items: List[Dict[str, str]]  # {icon, text}
    credibility_items: List[Dict[str, str]]  # {type, value}
    cta_text: Optional[str]
    
    # Images
    primary_image_base64: Optional[str]

    # Design DNA (NEW - for design-intelligent rendering)
    design_dna: Optional[Dict[str, Any]] = None

    # Composition spec — the art director's decision on how to lay out the
    # card (typographic vs split, whether to show a visual, which brand colour
    # anchors the panel, where the single accent lands). Consumed by the
    # premium HTML renderer. See SINGLE_PASS_PROMPT "composition" block.
    composition: Optional[Dict[str, Any]] = None

    # Processing metadata
    processing_time_ms: int = 0
    reasoning_confidence: float = 0.0
    design_fidelity_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regions": [r.to_dict() for r in self.regions],
            "blueprint": self.blueprint.to_dict(),
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "tags": self.tags,
            "context_items": self.context_items,
            "credibility_items": self.credibility_items,
            "cta_text": self.cta_text,
            "has_primary_image": self.primary_image_base64 is not None,
            "design_dna": self.design_dna,
            "composition": self.composition,
            "processing_time_ms": self.processing_time_ms,
            "reasoning_confidence": self.reasoning_confidence,
            "design_fidelity_score": self.design_fidelity_score
        }


# =============================================================================
# AI PROMPTS - Multi-Stage Reasoning (loaded from backend/prompts/)
# =============================================================================

try:
    from backend.prompts.loader import (
        get_layout_stage1_prompt,
        get_layout_stage4_prompt,
        MODEL_LAYOUT_REASONING,
    )
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False
    MODEL_LAYOUT_REASONING = "gpt-4o"

# Fallback prompts if loader unavailable (keep minimal inline)
_STAGE_1_2_3_FALLBACK = "You are an expert web analyst. Extract primary_headline, credibility_signals, value_statement, page_type, regions, design_dna, analysis_confidence. Output valid JSON only."
_STAGE_4_5_6_FALLBACK = "You are a layout designer. Output valid JSON with layout, layout_reasoning, accuracy_score, clarity_score, engagement_score, design_fidelity_score, overall_quality."


# =============================================================================
# IMAGE PREPARATION
# =============================================================================

def prepare_image(screenshot_bytes: bytes) -> Tuple[str, Image.Image]:
    """Prepare image for AI analysis."""
    image = Image.open(BytesIO(screenshot_bytes))
    
    # Resize if needed
    max_dim = 2048
    if image.width > max_dim or image.height > max_dim:
        ratio = min(max_dim / image.width, max_dim / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to RGB
    if image.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        if image.mode in ('RGBA', 'LA'):
            background.paste(image, mask=image.split()[-1])
        image = background
    
    # To base64
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=90)
    base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return base64_str, image


def _find_content_center(image: Image.Image) -> tuple[int, int]:
    """
    Find the center of actual content (non-background) in an image.
    Uses variance analysis to detect where the actual image content is.
    For circular profile images, this finds the center of the face/avatar.
    """
    from PIL import ImageStat
    
    # Convert to grayscale for analysis
    gray = image.convert('L')
    width, height = gray.size
    
    # Sample regions in a grid to find content density
    grid_size = 8  # 8x8 grid
    step_x = max(1, width // grid_size)
    step_y = max(1, height // grid_size)
    
    # Calculate variance for each region (high variance = content, low = background)
    max_variance = 0
    weighted_x = 0
    weighted_y = 0
    total_weight = 0
    
    # Sample regions to find where content is
    for y in range(0, height - step_y, step_y):
        for x in range(0, width - step_x, step_x):
            region = gray.crop((x, y, min(x + step_x, width), min(y + step_y, height)))
            stat = ImageStat.Stat(region)
            variance = stat.var[0] if stat.var else 0
            
            # Track max variance
            if variance > max_variance:
                max_variance = variance
            
            # Weight regions with significant content (at least 50% of max variance)
            if variance > max_variance * 0.5 or max_variance == 0:
                weight = variance if variance > 0 else 1
                region_center_x = x + step_x // 2
                region_center_y = y + step_y // 2
                weighted_x += region_center_x * weight
                weighted_y += region_center_y * weight
                total_weight += weight
    
    # Calculate weighted center
    if total_weight > 0:
        content_center_x = int(weighted_x / total_weight)
        content_center_y = int(weighted_y / total_weight)
    else:
        # Fallback to geometric center
        content_center_x = width // 2
        content_center_y = height // 2
    
    return content_center_x, content_center_y


def crop_region(image: Image.Image, bbox: Dict[str, float], is_profile_image: bool = False) -> str:
    """
    Crop a region from the image with intelligent handling.
    
    For profile images/avatars, detects actual content center and creates perfectly centered square crop.
    """
    # Calculate raw coordinates from AI-detected bounding box
    left = int(bbox['x'] * image.width)
    top = int(bbox['y'] * image.height)
    right = int((bbox['x'] + bbox['width']) * image.width)
    bottom = int((bbox['y'] + bbox['height']) * image.height)
    
    if right <= left or bottom <= top:
        return ""
    
    # For profile images/avatars, find actual content center and create perfectly centered square crop
    if is_profile_image:
        # First, get an initial crop to analyze
        width = right - left
        height = bottom - top
        initial_size = max(width, height)
        
        # Add some padding to ensure we capture the full image
        padded_size = int(initial_size * 1.2)
        half_padded = padded_size // 2
        
        # Calculate initial center from bounding box
        bbox_center_x = (left + right) // 2
        bbox_center_y = (top + bottom) // 2
        
        # Get a larger crop area to analyze
        analysis_left = max(0, bbox_center_x - half_padded)
        analysis_top = max(0, bbox_center_y - half_padded)
        analysis_right = min(image.width, bbox_center_x + half_padded)
        analysis_bottom = min(image.height, bbox_center_y + half_padded)
        
        analysis_crop = image.crop((analysis_left, analysis_top, analysis_right, analysis_bottom))
        
        # Find the actual content center within the analysis crop
        content_x, content_y = _find_content_center(analysis_crop)
        
        # Convert back to full image coordinates
        actual_center_x = analysis_left + content_x
        actual_center_y = analysis_top + content_y
        
        # Use the smaller dimension of the bounding box as the base size (circular images should be roughly square)
        base_size = min(width, height) if abs(width - height) / max(width, height) < 0.3 else max(width, height)
        
        # For circular profile images, use the base size with minimal padding
        size = int(base_size * 1.05)  # 5% padding to ensure we get the full circle
        
        # Create perfectly centered square crop on actual content center
        half_size = size // 2
        left = max(0, actual_center_x - half_size)
        top = max(0, actual_center_y - half_size)
        right = min(image.width, actual_center_x + half_size)
        bottom = min(image.height, actual_center_y + half_size)
        
        # Ensure square
        actual_width = right - left
        actual_height = bottom - top
        if actual_width != actual_height:
            min_dim = min(actual_width, actual_height)
            half_min = min_dim // 2
            left = max(0, actual_center_x - half_min)
            top = max(0, actual_center_y - half_min)
            right = min(image.width, actual_center_x + half_min)
            bottom = min(image.height, actual_center_y + half_min)
    else:
        # For non-profile images, add moderate padding
        padding_factor = 0.15
        padding_x = int((right - left) * padding_factor)
        padding_y = int((bottom - top) * padding_factor)
        
        left = max(0, left - padding_x)
        top = max(0, top - padding_y)
        right = min(image.width, right + padding_x)
        bottom = min(image.height, bottom + padding_y)
    
    if right <= left or bottom <= top:
        return ""
    
    cropped = image.crop((left, top, right, bottom))
    
    # For profile images, resize to high quality
    if is_profile_image and cropped.width > 0:
        # Use larger target size for better quality
        target_size = 400  # Increased from 256 for better quality
        cropped = cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    buffer = BytesIO()
    # Use high quality for profile images
    quality = 95 if is_profile_image else 85
    cropped.save(buffer, format='PNG', optimize=True, quality=quality)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


# =============================================================================
# CORE REASONING ENGINE
# =============================================================================

def run_stages_1_2_3(screenshot_bytes: bytes) -> Tuple[List[Dict], Dict[str, str], str, float, Dict[str, Any], Dict[str, Any]]:
    """
    Run Stages 1-3: Segmentation, Purpose Analysis, Priority Assignment.
    
    Now also extracts Design DNA for design-intelligent rendering.
    
    Returns:
        Tuple of (regions_list, color_palette, page_type, confidence, extracted_highlights, design_dna)
    """
    image_base64, pil_image = prepare_image(screenshot_bytes)

    # Check circuit breaker before making OpenAI call
    circuit_breaker = OpenAICircuitBreaker.get_instance()
    if circuit_breaker.is_open():
        logger.warning("Circuit breaker OPEN - skipping Stage 1-2-3 OpenAI call, using fallback")
        raise Exception("OpenAI circuit breaker is open - too many recent errors")

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60)

    stage1_prompt = (
        get_layout_stage1_prompt() if PROMPT_LOADER_AVAILABLE else _STAGE_1_2_3_FALLBACK
    )
    if not stage1_prompt:
        stage1_prompt = _STAGE_1_2_3_FALLBACK

    def _call_stage1(retry_simplified: bool = False) -> str:
        prompt_text = (
            "Return valid JSON only. Extract primary_headline, credibility_signals, value_statement, page_type, regions, design_dna, analysis_confidence."
            if retry_simplified
            else stage1_prompt
        )
        resp = client.chat.completions.create(
            model=MODEL_LAYOUT_REASONING,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert web analyst. Extract EXACT text as it appears. Output valid JSON only."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "high"}
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0.0,
            seed=42
        )
        return resp.choices[0].message.content.strip()

    try:
        content = _call_stage1(retry_simplified=False)
        circuit_breaker.record_success()
    except Exception as e:
        circuit_breaker.record_error()
        raise
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    # FIX 1: Robust JSON parsing with retry on parse failure (AIL-112)
    def _parse_stage1_content(raw: str) -> Optional[Dict]:
        c = raw.strip()
        if "```json" in c:
            c = c.split("```json")[1].split("```")[0].strip()
        elif "```" in c:
            c = c.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', c, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    data = _parse_stage1_content(content)
    if data is None:
        # Retry once with simplified prompt (AIL-112 schema enforcement)
        logger.warning("⚠️ Stage 1-3 parse failed, retrying with simplified prompt")
        try:
            content = _call_stage1(retry_simplified=True)
            data = _parse_stage1_content(content)
        except Exception as retry_err:
            logger.warning(f"Retry failed: {retry_err}")
        if data is None:
            data = {
                "page_type": "unknown",
                "primary_headline": None,
                "credibility_signals": None,
                "value_statement": None,
                "regions": [],
                "detected_palette": {"primary": "#3B82F6", "secondary": "#1E293B", "accent": "#F59E0B"},
                "detected_logo": {},
                "analysis_confidence": 0.3
            }
            logger.warning("⚠️ Using fallback structure after parse failure")

    # Pydantic validation (AIL-112)
    try:
        from backend.schemas.ai_output_schemas import validate_reasoning_output
        validated = validate_reasoning_output(data)
        data = validated.model_dump()
    except Exception as val_err:
        logger.debug(f"Pydantic validation skipped: {val_err}")
    
    # Extract highlights - support both old and new field names
    # Robustness: coerce to str to avoid TypeError on malformed JSON (AIL-75, AIL-99)
    def _safe_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        return str(v) if v else ""

    raw_highlights = {
        "the_hook": data.get("primary_headline") or data.get("the_hook"),
        "social_proof_found": data.get("credibility_signals") or data.get("social_proof_found"),
        "key_benefit": data.get("value_statement") or data.get("key_benefit")
    }
    extracted_highlights = {k: (_safe_str(v) or "") for k, v in raw_highlights.items()}

    # Extract Design DNA (NEW - for design-intelligent rendering)
    # Guard: design_dna can be None from schema/model_dump when parse fails
    _default_dna = {
        "style": "corporate",
        "mood": "balanced",
        "formality": 0.5,
        "typography_personality": "bold",
        "color_emotion": "trust",
        "spacing_feel": "balanced",
        "brand_adjectives": ["professional", "modern"],
        "design_reasoning": "Default design DNA"
    }
    design_dna = data.get("design_dna") or _default_dna
    if not isinstance(design_dna, dict):
        design_dna = _default_dna

    hook_val = extracted_highlights.get("the_hook") or "none"
    proof_val = extracted_highlights.get("social_proof_found") or "none"
    logger.info(f"🎯 Extracted highlights: hook='{str(hook_val)[:50]}...', proof='{proof_val}'")
    logger.info(f"🧬 Design DNA: style={design_dna.get('style')}, mood={design_dna.get('mood')}, typography={design_dna.get('typography_personality')}")
    
    # ENHANCED: Validate and score extraction quality
    if QUALITY_ASSURANCE_AVAILABLE:
        try:
            # Validate extraction
            validation_result = validate_extraction_result(data)
            
            # Score quality
            quality_breakdown = score_extraction_quality(data)
            
            # Evaluate quality gates
            gate_config = QualityGateConfig(
                min_extraction_quality=0.60,
                min_confidence=0.50,
                enforce_profile_name_validation=True
            )
            gate_result = evaluate_quality_gates(
                data,
                quality_breakdown.overall_score,
                validation_result,
                gate_config
            )
            
            # Log quality metrics
            logger.info(
                f"📊 Quality: {quality_breakdown.overall_score:.2f} "
                f"(Grade {quality_breakdown.grade.value}), "
                f"Confidence: {data.get('analysis_confidence', 0.0):.2f}, "
                f"Gates: {gate_result.status.value}"
            )
            
            # Add quality metrics to data for downstream use
            data["_quality_metrics"] = {
                "quality_score": quality_breakdown.overall_score,
                "quality_grade": quality_breakdown.grade.value,
                "validation_passed": validation_result.is_valid,
                "gate_status": gate_result.status.value,
                "should_retry": gate_result.should_retry
            }
            
            # Log issues if any
            if not validation_result.is_valid:
                logger.warning(f"⚠️  Validation issues: {len(validation_result.issues)} found")
                for issue in validation_result.get_critical_issues()[:3]:
                    logger.warning(f"  - {issue.message}")
            
        except Exception as e:
            logger.warning(f"⚠️  Quality assessment failed: {e}")
    
    # ENHANCED: Extract Product Intelligence (for e-commerce pages)
    page_type = data.get("page_type", "").lower()
    if PRODUCT_INTELLIGENCE_AVAILABLE and page_type in ["ecommerce", "product", "marketplace"]:
        try:
            product_info = extract_product_intelligence(data)
            
            # Add product intelligence to data for downstream use
            data["_product_intelligence"] = {
                "pricing": {
                    "current_price": product_info.pricing.current_price,
                    "original_price": product_info.pricing.original_price,
                    "discount_percentage": product_info.pricing.discount_percentage,
                    "is_on_sale": product_info.pricing.is_on_sale,
                    "deal_ends": product_info.pricing.deal_ends
                },
                "availability": {
                    "in_stock": product_info.availability.in_stock,
                    "limited_quantity": product_info.availability.limited_quantity,
                    "stock_level": product_info.availability.stock_level
                },
                "rating": {
                    "rating": product_info.rating.rating,
                    "review_count": product_info.rating.review_count,
                    "rating_display": product_info.rating.rating_display
                },
                "urgency": {
                    "has_urgency": product_info.urgency_signals.has_urgency,
                    "deal_countdown": product_info.urgency_signals.deal_countdown,
                    "stock_message": product_info.urgency_signals.stock_message
                },
                "trust_signals": {
                    "badges": product_info.trust_signals.badges[:5],  # Top 5 badges
                    "shipping": product_info.trust_signals.shipping_info,
                    "returns": product_info.trust_signals.return_policy
                },
                "category": product_info.details.product_type.value,
                "brand": product_info.details.brand,
                "extraction_confidence": product_info.extraction_confidence
            }
            
            logger.info(
                f"🛍️ Product Intelligence: "
                f"Price: {product_info.pricing.current_price}"
                + (f" (was {product_info.pricing.original_price}, -{product_info.pricing.discount_percentage}%)" if product_info.pricing.is_on_sale else "")
                + f", Rating: {product_info.rating.rating}★"
                + (f" ({product_info.rating.review_count:,} reviews)" if product_info.rating.review_count else "")
                + (f", Urgency: {product_info.urgency_signals.deal_countdown or product_info.urgency_signals.stock_message}" if product_info.urgency_signals.has_urgency else "")
                + f", Badges: {len(product_info.trust_signals.badges)}"
            )
            
        except Exception as e:
            logger.warning(f"⚠️  Product intelligence extraction failed: {e}")
    
    # Extract logo information if detected
    detected_logo = data.get("detected_logo", {})
    logo_region_id = detected_logo.get("region_id") if detected_logo else None
    
    # Crop images for included regions
    for region in data.get("regions", []):
        content_type = region.get("content_type", "").lower()
        if content_type in ["hero_image", "logo", "image", "profile_image", "avatar"] and region.get("bbox"):
            # Detect profile images more accurately
            is_profile = (
                region.get("purpose") == "identity" or
                content_type in ["profile_image", "avatar"] or
                "profile" in content_type or
                "avatar" in content_type
            )
            is_logo = region.get("is_logo", False) or region.get("id") == logo_region_id or content_type == "logo"
            
            # For profile pages, profile logos/avatars should use profile cropping logic
            # even if they're marked as logos (they're the identity element)
            page_type = data.get("page_type", "").lower()
            is_profile_logo = is_profile and (is_logo or page_type == "profile")
            
            try:
                # Use profile image cropping for profile images/avatars, including profile logos
                image_data = crop_region(pil_image, region["bbox"], is_profile_image=(is_profile or is_profile_logo))
                if image_data:
                    region["image_data"] = image_data
                    if is_logo:
                        region["is_logo"] = True
                    if is_profile:
                        logger.info(f"✅ Cropped profile image from region {region.get('id')}")
            except Exception as e:
                logger.warning(f"Failed to crop region {region.get('id')}: {e}")
    
    return (
        data.get("regions", []),
        data.get("detected_palette", {"primary": "#3B82F6", "secondary": "#1E293B", "accent": "#F59E0B"}),
        data.get("page_type", "unknown"),
        data.get("analysis_confidence", 0.7),
        extracted_highlights,
        design_dna
    )


def run_stages_4_5(regions: List[Dict], page_type: str, palette: Dict[str, str]) -> Dict[str, Any]:
    """Backward-compatible wrapper that calls the merged stages 4-5-6."""
    return run_stages_4_5_6(regions, page_type, palette)


def run_stages_4_5_6(regions: List[Dict], page_type: str, palette: Dict[str, str], design_dna: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Run Stages 4-6: Composition Decision, Layout Synthesis, and Quality Check.

    Merged into a single API call for ~4s latency reduction.

    Returns:
        Layout plan dictionary with quality scores and normalized slot names.
    """
    # Filter to non-omit regions for composition decisions
    relevant_regions = [r for r in regions if r.get("visual_weight") != "omit"]

    # Remove image_data from regions to reduce token usage
    regions_for_ai = []
    for r in relevant_regions:
        region_copy = {k: v for k, v in r.items() if k != "image_data"}
        if r.get("image_data"):
            region_copy["has_image"] = True
        # Truncate long content
        if "raw_content" in region_copy:
            region_copy["raw_content"] = region_copy["raw_content"][:200]
        regions_for_ai.append(region_copy)

    # Check circuit breaker before making OpenAI call
    circuit_breaker = OpenAICircuitBreaker.get_instance()
    if circuit_breaker.is_open():
        logger.warning("Circuit breaker OPEN - skipping Stage 4-5-6 OpenAI call, using fallback")
        return _fallback_layout_result(page_type)

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=45)

    stage4_prompt = ""
    if PROMPT_LOADER_AVAILABLE:
        stage4_prompt = get_layout_stage4_prompt(
            regions_json=json.dumps(regions_for_ai, indent=2),
            page_type=page_type,
            primary=palette.get("primary", "#3B82F6"),
            secondary=palette.get("secondary", "#1E293B"),
            accent=palette.get("accent", "#F59E0B"),
            design_dna_json=json.dumps(design_dna or {}, indent=2),
        )
    if not stage4_prompt:
        stage4_prompt = _STAGE_4_5_6_FALLBACK

    def _parse_stage4_content(raw: str) -> Optional[Dict]:
        c = raw.strip()
        if "```json" in c:
            c = c.split("```json")[1].split("```")[0].strip()
        elif "```" in c:
            c = c.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', c, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    try:
        response = client.chat.completions.create(
            model=MODEL_LAYOUT_REASONING,
            messages=[
                {
                    "role": "system",
                    "content": "You are a layout designer and quality assessor for social media previews. Create clear, accurate layouts. Output valid JSON only."
                },
                {"role": "user", "content": stage4_prompt}
            ],
            max_tokens=2000,
            temperature=0.0
        )
        circuit_breaker.record_success()

        content = response.choices[0].message.content.strip()
        result = _parse_stage4_content(content)
        if result is None:
            logger.warning("⚠️ Stage 4-5-6 parse failed, retrying with simplified prompt")
            retry_resp = client.chat.completions.create(
                model=MODEL_LAYOUT_REASONING,
                messages=[
                    {"role": "system", "content": "You are a layout designer. Output valid JSON only."},
                    {"role": "user", "content": stage4_prompt + "\n\nReturn valid JSON only."}
                ],
                max_tokens=2000,
                temperature=0.0
            )
            result = _parse_stage4_content(retry_resp.choices[0].message.content.strip())
        if result is None:
            result = _fallback_layout_result(page_type)
        else:
            try:
                from backend.schemas.ai_output_schemas import validate_layout_result
                validated = validate_layout_result(result)
                result = validated.model_dump()
            except Exception as val_err:
                logger.debug(f"Layout Pydantic validation skipped: {val_err}")

    except Exception as e:
        circuit_breaker.record_error()
        error_msg = str(e)
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            logger.warning(f"Stage 4-5-6 rate limited, using fallback: {error_msg[:200]}")
        else:
            logger.warning(f"Stage 4-5-6 failed, using fallback: {error_msg[:200]}")
        result = _fallback_layout_result(page_type)

    # Normalize layout for backward compatibility
    layout = result.get("layout", {})

    if "headline_slot" in layout and "identity_slot" not in layout:
        layout["identity_slot"] = layout["headline_slot"]
    if "visual_slot" in layout and "identity_image_slot" not in layout:
        layout["identity_image_slot"] = layout["visual_slot"]
    if "benefit_slot" in layout and "value_slot" not in layout:
        layout["value_slot"] = layout["benefit_slot"]
    if "cta_slot" in layout and "action_slot" not in layout:
        layout["action_slot"] = layout["cta_slot"]
    if "proof_slot" in layout:
        if "credibility_slots" not in layout:
            layout["credibility_slots"] = [layout["proof_slot"]]
        elif layout["proof_slot"] not in layout["credibility_slots"]:
            layout["credibility_slots"].insert(0, layout["proof_slot"])

    layout.setdefault("template_type", layout.get("template_style", page_type))
    layout.setdefault("context_slots", [])
    layout.setdefault("tags_slots", [])
    layout.setdefault("credibility_slots", [])
    layout.setdefault("benefits_slots", [])

    if layout.get("secondary_benefit_slot"):
        if layout["secondary_benefit_slot"] not in layout["benefits_slots"]:
            layout["benefits_slots"].append(layout["secondary_benefit_slot"])

    result["layout"] = layout
    return result


def _fallback_layout_result(page_type: str) -> Dict[str, Any]:
    """Return a minimal valid layout result for error cases."""
    return {
        "composition_decisions": [],
        "layout": {
            "template_style": page_type,
            "headline_slot": None,
            "visual_slot": None,
            "proof_slot": None,
            "benefit_slot": None,
            "cta_slot": None
        },
        "layout_reasoning": "Fallback due to error",
        "preview_strength": "weak",
        "accuracy_score": 0.7,
        "clarity_score": 0.7,
        "engagement_score": 0.7,
        "design_fidelity_score": 0.7,
        "overall_quality": "good",
        "improvement_suggestions": []
    }


def _extract_quality_from_merged(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract quality scores from merged stage 4-5-6 result."""
    quality = {
        "coherence_score": result.get("accuracy_score", 0.7),
        "balance_score": result.get("engagement_score", 0.7),
        "clarity_score": result.get("clarity_score", 0.7),
        "design_fidelity_score": result.get("design_fidelity_score", 0.7),
        "overall_quality": result.get("overall_quality", "good"),
        "improvement_suggestions": result.get("improvement_suggestions", []),
        "hook_score": result.get("accuracy_score", 0.7),
        "trust_score": result.get("engagement_score", 0.7),
        "click_motivation_score": result.get("engagement_score", 0.7)
    }
    return quality


def run_stage_6(layout: Dict[str, Any], included_regions: List[Dict], design_dna: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Stage 6 is now merged into run_stages_4_5_6.
    This function extracts quality scores from the merged result.
    If called with the merged result (which contains quality scores), it returns them directly.
    Otherwise returns fallback scores.
    """
    return _extract_quality_from_merged(layout)


# =============================================================================
# CONTENT REFINEMENT
# =============================================================================

def smart_truncate_text(text: str, max_chars: int) -> str:
    """
    PHASE 4: Smart truncation at sentence or word boundary.
    
    Priority order:
    1. End at sentence boundary (. ! ?) if it preserves >50% of content
    2. Fall back to word boundary
    3. Never cut mid-word
    
    Args:
        text: Text to truncate
        max_chars: Maximum characters
        
    Returns:
        Truncated text with natural ending
    """
    if not text or len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    
    # Priority 1: Sentence boundary
    sentence_ends = ['. ', '! ', '? ', '." ', '!" ', '?" ']
    best_end = -1
    
    for marker in sentence_ends:
        pos = truncated.rfind(marker)
        if pos > max_chars * 0.5 and pos > best_end:
            best_end = pos + len(marker) - 1
    
    # Check for sentence ending at very end
    if truncated.rstrip() and truncated.rstrip()[-1] in '.!?':
        return truncated.rstrip()
    
    if best_end > 0:
        return truncated[:best_end + 1].rstrip()
    
    # Priority 2: Word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.6:
        result = truncated[:last_space].rstrip()
        
        # Avoid ending on short connecting words
        last_word = result.split()[-1].lower() if result.split() else ""
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for', 'by', 'is'}
        
        if last_word in stop_words and len(result.split()) > 2:
            earlier_space = result.rfind(' ')
            if earlier_space > max_chars * 0.5:
                result = result[:earlier_space].rstrip()
        
        return result + "..."
    
    # Priority 3: Hard truncate at word boundary
    if last_space > 0:
        return truncated[:last_space] + "..."
    
    return truncated[:max_chars - 3] + "..."


def clean_display_text(raw_text: str, purpose: str) -> str:
    """
    PHASE 4: Clean and validate display text with smart truncation.
    
    Features:
    - Sentence-aware truncation
    - Word boundary awareness
    - Purpose-specific length limits
    - Prefix cleaning for identity slots
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    
    # Remove excessive whitespace
    cleaned = " ".join(raw_text.split())
    
    # Remove control characters but keep normal punctuation
    import re
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    
    # For identity slots, remove common prefixes
    if purpose == "identity":
        prefixes_to_remove = ["om ", "about ", "meet ", "introducing "]
        text_lower = cleaned.lower()
        for prefix in prefixes_to_remove:
            if text_lower.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
    
    # Limit length based on purpose with smart truncation
    max_lengths = {
        "hook": 120,
        "identity": 100,
        "proof": 80,
        "benefit": 250,
        "benefits": 250,
        "description": 350,
        "value_prop": 350,
        "tagline": 120
    }
    max_len = max_lengths.get(purpose, 200)
    
    # Use smart truncation instead of simple character cut
    if len(cleaned) > max_len:
        cleaned = smart_truncate_text(cleaned, max_len)
    
    # Validate minimum length
    if len(cleaned.strip()) < 3:
        return ""
    
    return cleaned.strip()


def extract_final_content(
    regions: List[Dict],
    layout: Dict[str, Any],
    composition_decisions: List[Dict],
    highlights: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Extract final content for rendering based on layout slots.
    
    Uses extracted highlights (the_hook, social_proof_found, key_benefit) 
    as primary sources, falling back to slot-based extraction.
    """
    # Build region lookup
    region_map = {r["id"]: r for r in regions}
    
    # Build inclusion map
    included = {d["region_id"]: d["include"] for d in composition_decisions}

    # Ensure highlights dict exists
    if highlights is None:
        highlights = {}

    layout_slots = layout.get("layout", {})

    # Ensure slot-referenced regions are considered included
    for slot_key in ['headline_slot', 'visual_slot', 'proof_slot', 'benefit_slot', 'cta_slot']:
        slot_region_id = layout_slots.get(slot_key)
        if slot_region_id and slot_region_id in region_map and slot_region_id not in included:
            included[slot_region_id] = True
            logger.info(f"Auto-including slot-referenced region: {slot_region_id} ({slot_key})")
    
    # Extract content for each slot
    def get_region_content(region_id: str, purpose: str = "") -> Optional[str]:
        if not region_id or region_id not in region_map:
            return None
        region = region_map[region_id]
        raw = region.get("raw_content", "")
        return clean_display_text(raw, purpose)
    
    def get_region_image(region_id: str) -> Optional[str]:
        if not region_id or region_id not in region_map:
            return None
        region = region_map[region_id]
        return region.get("image_data")
    
    # === TITLE EXTRACTION (prioritize based on page type) ===
    # For profile pages, prioritize identity/name over hook
    page_type = layout.get("page_type", "").lower() if isinstance(layout, dict) else ""
    is_profile = "profile" in page_type or any(r.get("content_type") == "profile_image" or r.get("content_type") == "avatar" for r in regions[:5])
    
    title = None
    
    if is_profile:
        # For profiles: Extract name from HTML metadata FIRST (most reliable)
        # This will be enhanced by preview_engine with HTML metadata
        # For now, look for short, name-like text in regions
        
        # PRIORITY 1: Look for short text that looks like a name (2-4 words, capitalized)
        # Names are typically: "First Last" or "First Middle Last"
        for region_id, include_flag in included.items():
            if include_flag and region_id in region_map:
                region = region_map[region_id]
                raw = region.get("raw_content", "").strip()
                
                # Check if this looks like a name (2-4 words, each capitalized, total < 50 chars)
                words = raw.split()
                if 2 <= len(words) <= 4 and len(raw) < 50:
                    # Check if most words start with capital letter (name pattern)
                    capitalized_words = sum(1 for w in words if w and w[0].isupper())
                    if capitalized_words >= len(words) * 0.75:  # At least 75% capitalized
                        # Avoid common non-name patterns
                        if not any(word.lower() in ["og", "and", "er", "is", "the", "med", "til"] for word in words):
                            title = raw
                            logger.info(f"📌 Using name-like region as profile name: '{title}'")
                            break
        
        # PRIORITY 2: Identity slot (person's name)
        if not title:
            title = get_region_content(layout_slots.get("identity_slot"), "identity")
            if title and len(title) < 80:  # Names are usually shorter
                logger.info(f"📌 Using identity slot as profile name: '{title}'")
        
        # PRIORITY 3: Look for identity-purpose regions
        if not title:
            for region_id, include_flag in included.items():
                if include_flag and region_id in region_map:
                    region = region_map[region_id]
                    if region.get("purpose") == "identity":
                        candidate = get_region_content(region_id, "identity")
                        # Filter out long descriptions - names are short
                        if candidate and 2 < len(candidate) < 60 and len(candidate.split()) <= 4:
                            title = candidate
                            logger.info(f"📌 Using identity region as profile name: '{title}'")
                            break
    
    # PRIORITY 2: Use the extracted "the_hook" (for non-profiles or fallback)
    if not title:
        title = highlights.get("the_hook")
        if title:
            title = clean_display_text(title, "hook")
            logger.info(f"📌 Using extracted hook as title: '{title[:50]}...'")
    
    # PRIORITY 3: Try slot-based extraction
    if not title or len(title) < 5:
        title = get_region_content(layout_slots.get("headline_slot"), "hook")
    if not title:
        title = get_region_content(layout_slots.get("identity_slot"), "identity")
    
    # PRIORITY 3: Search included regions for best title candidate
    if not title or title == "Untitled":
        for region_id, include_flag in included.items():
            if include_flag and region_id in region_map:
                region = region_map[region_id]
                if region.get("purpose") in ("hook", "headline") or region.get("content_type") == "headline":
                    candidate = get_region_content(region_id, region.get("purpose", ""))
                    if candidate and 5 < len(candidate) < 120:
                        title = candidate
                        break
    
    # PRIORITY 4: High-priority text from any included region
    if not title or title == "Untitled":
        for region in sorted(regions, key=lambda r: r.get("priority_score", 0), reverse=True):
            if included.get(region["id"], False):
                raw = region.get("raw_content", "")
                if raw and 5 < len(raw.strip()) < 100:
                    title = clean_display_text(raw, "identity")
                    if title and title != "Untitled":
                        break
    
    if not title or title == "Untitled":
        title = "Untitled"
    
    # === SUBTITLE/PROOF EXTRACTION (prioritize social proof) ===
    # PRIORITY 1: Use extracted social proof - this builds trust
    subtitle = highlights.get("social_proof_found")
    if subtitle:
        subtitle = clean_display_text(subtitle, "proof")
        logger.info(f"📌 Using extracted social proof as subtitle: '{subtitle}'")
    
    # PRIORITY 2: Try slot-based extraction
    if not subtitle:
        subtitle = get_region_content(layout_slots.get("proof_slot"), "proof")
    if not subtitle:
        subtitle = get_region_content(layout_slots.get("tagline_slot"), "tagline")

    # PRIORITY 3: Search included regions for credibility/proof content
    if not subtitle:
        for region_id, include_flag in included.items():
            if include_flag and region_id in region_map:
                region = region_map[region_id]
                if region.get("purpose") in ("proof", "credibility") or region.get("content_type") in ("rating", "user_count", "testimonial", "statistic"):
                    candidate = get_region_content(region_id, "proof")
                    if candidate and len(candidate) > 5:
                        subtitle = candidate
                        logger.info(f"Using credibility region as subtitle: '{subtitle}'")
                        break

    # Track proof text separately for credibility_items
    proof_text = subtitle if subtitle else get_region_content(layout_slots.get("proof_slot"), "proof")
    
    # === DESCRIPTION/BENEFIT EXTRACTION (prioritize key benefit) ===
    # PRIORITY 1: Use extracted key benefit
    description = highlights.get("key_benefit")
    if description:
        description = clean_display_text(description, "description")
        logger.info(f"📌 Using extracted key benefit as description: '{description[:50]}...'")
    
    # PRIORITY 2: Try slot-based extraction
    if not description:
        description = get_region_content(layout_slots.get("benefit_slot"), "benefits")
    if not description:
        description = get_region_content(layout_slots.get("value_slot"), "value_prop")
    
    # Try secondary benefit as additional content
    secondary_benefit = get_region_content(layout_slots.get("secondary_benefit_slot"), "benefits")
    
    # PRIORITY 3: Search included regions for benefits
    if not description:
        for region_id, include_flag in included.items():
            if include_flag and region_id in region_map:
                region = region_map[region_id]
                if region.get("purpose") in ["benefit", "value_prop", "benefits"]:
                    description = get_region_content(region_id, region.get("purpose", ""))
                    if description:
                        break
    
    # === BENEFITS EXTRACTION ===
    benefits = []
    benefit_text = get_region_content(layout_slots.get("benefit_slot"), "benefits")
    if benefit_text:
        benefits.append(benefit_text)
    if secondary_benefit and secondary_benefit not in benefits:
        benefits.append(secondary_benefit)
    
    # Old-style benefits slots
    for benefit_id in layout_slots.get("benefits_slots", [])[:3]:
        benefit_text = get_region_content(benefit_id, "benefits")
        if benefit_text and benefit_text not in benefits:
            benefits.append(benefit_text)
    
    # === CREDIBILITY/PROOF EXTRACTION ===
    credibility_items = []
    
    # New-style: proof_slot
    if proof_text:
        credibility_items.append({"type": "proof", "value": proof_text})
    
    # Old-style: credibility_slots
    for cred_id in layout_slots.get("credibility_slots", [])[:3]:
        if cred_id in region_map:
            region = region_map[cred_id]
            cred_type = region.get("content_type", "other")
            cred_text = get_region_content(cred_id)
            if cred_text and cred_text not in [c["value"] for c in credibility_items]:
                credibility_items.append({"type": cred_type, "value": cred_text})
    
    # Search for proof/credibility in included regions
    if not credibility_items:
        for region_id, include_flag in included.items():
            if include_flag and region_id in region_map:
                region = region_map[region_id]
                if region.get("purpose") in ["proof", "credibility"]:
                    cred_text = get_region_content(region_id)
                    if cred_text:
                        credibility_items.append({
                            "type": region.get("content_type", "proof"),
                            "value": cred_text
                        })
                        if len(credibility_items) >= 2:
                            break
    
    # === TAGS EXTRACTION ===
    tags = []
    for tag_id in layout_slots.get("tags_slots", [])[:4]:
        tag_text = get_region_content(tag_id)
        if tag_text:
            tags.append(tag_text)
    
    # === CONTEXT EXTRACTION ===
    context_items = []
    for ctx_id in layout_slots.get("context_slots", [])[:2]:
        if ctx_id in region_map:
            region = region_map[ctx_id]
            ctx_type = region.get("content_type", "other")
            ctx_text = get_region_content(ctx_id)
            if ctx_text:
                icon = "location" if "location" in ctx_type.lower() else "info"
                context_items.append({"icon": icon, "text": ctx_text})
    
    # === CTA EXTRACTION ===
    cta_text = get_region_content(layout_slots.get("cta_slot"))
    if not cta_text:
        cta_text = get_region_content(layout_slots.get("action_slot"))
    
    # === PRIMARY IMAGE EXTRACTION ===
    # For profile pages, prioritize profile images/avatars
    primary_image = None
    
    if is_profile:
        # PRIORITY 1: Look for profile_image or avatar content types
        for region in regions:
            if included.get(region.get("id"), False):
                content_type = region.get("content_type", "").lower()
                if content_type in ["profile_image", "avatar"] and region.get("image_data"):
                    # FIX 4: Validate image data before using
                    image_data = region.get("image_data")
                    if image_data and len(image_data) > 100:  # Basic validation: not empty, has some data
                        try:
                            # Try to decode to validate it's valid base64
                            import base64
                            decoded = base64.b64decode(image_data)
                            if len(decoded) > 1000:  # At least 1KB
                                primary_image = image_data
                                logger.info("✅ Using validated profile image/avatar as primary image")
                                break
                        except Exception as e:
                            logger.warning(f"Invalid image data in region {region.get('id')}: {e}")
                    else:
                        logger.warning(f"Image data too small or empty in region {region.get('id')}")
        
        # PRIORITY 2: Visual slot (may contain profile image)
        if not primary_image:
            primary_image = get_region_image(layout_slots.get("visual_slot"))
    
    # PRIORITY 3: Try new visual_slot first, then old identity_image_slot
    if not primary_image:
        primary_image = get_region_image(layout_slots.get("visual_slot"))
    if not primary_image:
        primary_image = get_region_image(layout_slots.get("identity_image_slot"))
    
    # PRIORITY 4: Fallback: look for detected logo (but not for profiles - they need avatar)
    if not primary_image and not is_profile:
        for region in regions:
            if region.get("is_logo") and region.get("image_data"):
                primary_image = region.get("image_data")
                logger.info("Using detected logo as primary image")
                break
    
    # PRIORITY 5: For profiles, look for any image in included regions
    if not primary_image and is_profile:
        for region in regions:
            if included.get(region.get("id"), False) and region.get("image_data"):
                primary_image = region.get("image_data")
                logger.info("Using included region image as profile image")
                break
    
    # === ENRICH THIN CONTENT ===
    # If description is missing entirely, use the first benefit as description
    if not description and benefits:
        description = benefits[0]
    
    # If subtitle is missing but we have proof, use that
    if not subtitle and credibility_items:
        subtitle = credibility_items[0]["value"]
    
    return {
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "tags": tags,
        "benefits": benefits,
        "context_items": context_items,
        "credibility_items": credibility_items,
        "cta_text": cta_text,
        "primary_image_base64": primary_image
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def _normalize_purpose(purpose_str: str) -> RegionPurpose:
    """Map AI output purpose strings to RegionPurpose enum values."""
    mapping = {
        "headline": RegionPurpose.VALUE_PROP,
        "hook": RegionPurpose.VALUE_PROP,
        "credibility": RegionPurpose.CREDIBILITY,
        "proof": RegionPurpose.CREDIBILITY,
        "value": RegionPurpose.VALUE_PROP,
        "benefit": RegionPurpose.VALUE_PROP,
        "identity": RegionPurpose.IDENTITY,
        "action": RegionPurpose.ACTION,
        "filler": RegionPurpose.DECORATION,
        "navigation": RegionPurpose.NAVIGATION,
        "decoration": RegionPurpose.DECORATION,
        "context": RegionPurpose.CONTEXT,
        "value_prop": RegionPurpose.VALUE_PROP,
    }
    return mapping.get(purpose_str.lower(), RegionPurpose.DECORATION)


SINGLE_PASS_PROMPT = """You are MetaView's art director and conversion copywriter. From a screenshot of a webpage, you compose a single link-preview card — the image that shows when someone shares this URL on Twitter/LinkedIn/Slack.

MetaView's whole promise: the card tells the story the page is trying to tell, SHARPER than the site's own OpenGraph image. You are not a scraper echoing the page's raw text — you are an editor who understands the page's goal and frames it so someone wants to click. But you are honest: you never invent facts, features, numbers, prices, or claims the page does not support.

=== STEP 1: READ THE PAGE'S INTENT ===
First, silently answer for yourself: What is this page? What does it want the visitor to do or feel? What is the single most compelling, TRUE thing about it? Then classify page_type:
- "saas" / "tool" — software product with features/pricing
- "ecommerce" / "product" — a thing for sale with price/reviews
- "profile" — an individual person (name + photo + bio)
- "article" / "blog" / "news" — written content
- "agency" / "portfolio" — showcasing work/services
- "landing" — generic marketing/company page
- "docs" / "educational" — reference/learning content

=== STEP 2: WRITE THE CARD ===

**title** (REQUIRED) — the hook. The one line that makes someone stop scrolling.
   - Capture the page's core value, sharpened. You MAY rephrase, tighten, or lead with the benefit — you are writing a headline, not transcribing one. Aim for specific and concrete over vague and grand.
   - Ground every word in what the page actually offers. No invented features, no fake urgency, no clickbait.
   - Ideal ≤ 55 characters, hard max 80. Title Case or sentence case, no trailing period.
   - EXCEPTION — profiles: the title is the person's real full name exactly (e.g. "Sarah Chen"). Do not editorialize a person's name.

**subtitle** — one supporting line that earns the click: the concrete "what you get" or "why it matters." Grounded in the page. ≤ 90 characters, or null if the page gives you nothing real to say.
   - Profiles: their role/company as shown (e.g. "Senior Product Designer at Stripe").

**description** — a tight 1-sentence value framing for downstream use. ≤ 160 chars. Grounded; null if nothing real.

**credibility** — the single strongest trust signal, VERBATIM, WITH specific numbers or named sources visible on the page ("4.9★ from 2,847 reviews", "Trusted by 50,000+ teams", "Featured in TechCrunch"). This one field is copy-exactly: if no concrete number/name is visible, return null. NEVER fabricate a statistic.

**cta_text** — the primary action verb phrase as shown ("Start free trial", "Shop now"). null if only generic ("Submit").

**tags** — 2-3 short topic labels (1-2 words each) describing the space (e.g. "AI", "Developer Tools").

=== STEP 3: READ THE VISUAL IDENTITY ===

**colors** — the page's 3 real brand colors as hex:
   - primary: dominant brand color (buttons/headers)
   - secondary: background or secondary brand color
   - accent: highlight/CTA color

**logo_bbox** — bounding box of the logo (or, for profiles, the avatar), as fractions 0.0-1.0 {"x","y","width","height"}, usually the top ~15% of the page. null if none is clearly visible.

**design_dna** — the brand's personality:
   - style: minimalist | corporate | luxurious | playful | technical | editorial | brutalist
   - mood: calm | balanced | dynamic | dramatic
   - typography_personality: authoritative | friendly | elegant | technical | bold
   - color_emotion: trust | energy | calm | sophistication | warmth | innovation
   - spacing_feel: compact | balanced | spacious
   - brand_adjectives: 3 words for the brand personality

=== STEP 4: DIRECT THE COMPOSITION ===
Decide how MetaView should lay out the card. MetaView's house style is confident and typographic: a brand-colored panel, a strong headline, ONE accent moment. Restraint reads as premium — a clean type-only card almost always beats a card cluttered with a screenshot.

**composition**:
   - layout: "typographic" (headline-led, no image — the default and usually best) OR "split" (headline on one side, a single clean visual on the other). Choose "split" ONLY when the page has ONE genuinely strong, self-contained hero visual (a product shot, a person's photo, a clean device mockup) that would make the card MORE compelling. Most SaaS/marketing pages are stronger typographic — when in doubt, "typographic".
   - use_visual: true only if layout is "split" and a clean visual exists; else false.
   - visual_source: "screenshot" (a crop of the page) | "logo" | "none".
   - visual_focus: ONLY when layout is "split" — the bounding box of that single best visual region, as fractions {"x","y","width","height"} 0-1 of the screenshot. Frame the hero product/graphic/photo tightly; EXCLUDE the top nav bar, cookie/consent banners, and text-only areas. Prefer a roughly square-to-portrait region (it fills a tall panel). null when layout is "typographic".
   - panel_color_role: which brand color anchors the card background — "primary" | "secondary" | "dark" (a deep near-black tint of the brand) | "light" (a soft off-white). Pick for contrast and mood; "dark" and "primary" feel premium for most brands.
   - accent_moment: where the single accent lands — "bar" (a short rule under the headline) | "dot" | "shape" (a soft corner shape).
   - mood: one word matching the brand (e.g. "confident", "warm", "precise", "bold", "calm").
   - reasoning: one short sentence on why this composition tells THIS page's story.

=== EXCLUSIONS ===
Ignore cookie banners, nav menus, footers, popups, breadcrumbs, "Skip to content".

=== OUTPUT (valid JSON only, no markdown fences) ===
{
    "page_type": "<type>",
    "title": "<authored hook, grounded in the page>",
    "subtitle": "<authored supporting line or null>",
    "description": "<1-sentence value framing or null>",
    "credibility": "<VERBATIM trust signal with numbers, or null>",
    "cta_text": "<action phrase or null>",
    "tags": ["<tag1>", "<tag2>"],
    "is_individual_profile": <true|false>,
    "colors": {"primary": "<hex>", "secondary": "<hex>", "accent": "<hex>"},
    "logo_bbox": {"x": <0-1>, "y": <0-1>, "width": <0-1>, "height": <0-1>} or null,
    "design_dna": {
        "style": "<style>", "mood": "<mood>", "typography_personality": "<personality>",
        "color_emotion": "<emotion>", "spacing_feel": "<feel>",
        "brand_adjectives": ["<w1>", "<w2>", "<w3>"]
    },
    "composition": {
        "layout": "typographic|split",
        "use_visual": <true|false>,
        "visual_source": "screenshot|logo|none",
        "visual_focus": {"x": <0-1>, "y": <0-1>, "width": <0-1>, "height": <0-1>} or null,
        "panel_color_role": "primary|secondary|dark|light",
        "accent_moment": "bar|dot|shape",
        "mood": "<one word>",
        "reasoning": "<one sentence>"
    },
    "confidence": <0.0-1.0>
}

RULES:
1. AUTHOR the title/subtitle/description — sharpen the page's real story; never transcribe blindly, never fabricate facts.
2. credibility is the ONE verbatim field — real numbers/names only, else null.
3. NULL OVER FABRICATION everywhere.
4. TITLE IS MANDATORY.
5. Prefer restraint: a clean typographic card beats a busy one."""


def generate_reasoned_preview(screenshot_bytes: bytes, url: str = "") -> ReasonedPreview:
    """
    Generate a preview using a single, focused AI vision call.

    Uses one optimized prompt that extracts title, subtitle, description,
    credibility, colors, and design DNA in a single pass. This is faster
    and produces more consistent results than the multi-stage approach.

    Args:
        screenshot_bytes: Raw PNG screenshot
        url: URL for context

    Returns:
        ReasonedPreview with extracted content
    """
    start_time = time.time()
    logger.info(f"[SinglePass] Starting preview extraction for: {url}")

    image_base64, pil_image = prepare_image(screenshot_bytes)

    # Circuit breaker check
    circuit_breaker = OpenAICircuitBreaker.get_instance()
    if circuit_breaker.is_open():
        logger.warning("Circuit breaker OPEN - using fallback")
        raise Exception("OpenAI circuit breaker is open")

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are MetaView's art director and conversion copywriter. From a webpage screenshot you "
                        "compose a link-preview card that tells the page's story sharper than its own OG image. "
                        "Author the headline and supporting line — grounded in what the page actually offers, never "
                        "fabricating facts, numbers, or claims. Trust signals (credibility) stay strictly verbatim. "
                        "Output valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SINGLE_PASS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "high"},
                        },
                    ],
                },
            ],
            max_tokens=2000,
            # NOTE: no temperature/seed — the gateway routes to an Anthropic model
            # that 400s on `temperature` ("deprecated for this model"), which would
            # crash this call and drop us to mojibaked HTML-only extraction.
        )
        circuit_breaker.record_success()
    except Exception as e:
        circuit_breaker.record_error()
        raise

    # Parse response
    content = response.choices[0].message.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
            except Exception:
                data = {}
        else:
            data = {}

    # Extract fields with safe defaults
    page_type = (data.get("page_type") or "landing").lower()
    title = data.get("title") or "Untitled"
    subtitle = data.get("subtitle")
    description = data.get("description")
    credibility = data.get("credibility")
    cta_text = data.get("cta_text")
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags if t][:3]
    confidence = float(data.get("confidence", 0.7))
    colors = data.get("colors", {})
    design_dna = data.get("design_dna", {})
    logo_bbox = data.get("logo_bbox")

    # Set design DNA defaults
    design_dna.setdefault("style", "corporate")
    design_dna.setdefault("mood", "balanced")
    design_dna.setdefault("typography_personality", "bold")
    design_dna.setdefault("color_emotion", "trust")
    design_dna.setdefault("spacing_feel", "balanced")
    design_dna.setdefault("brand_adjectives", ["professional", "modern"])

    # Composition spec authored by the art director (Step 4). Defaults keep
    # the premium house style (clean typographic card) if the model omits it.
    composition = data.get("composition")
    if not isinstance(composition, dict):
        composition = {}
    composition.setdefault("layout", "typographic")
    composition.setdefault("use_visual", False)
    composition.setdefault("visual_source", "none")
    composition.setdefault("panel_color_role", "primary")
    composition.setdefault("accent_moment", "bar")
    composition.setdefault("mood", design_dna.get("mood") or "confident")
    # Validate the focal box (fractions, sane size) — a bad box would crop garbage.
    vf = composition.get("visual_focus")
    if isinstance(vf, dict):
        try:
            x, y = float(vf.get("x", 0)), float(vf.get("y", 0))
            w, h = float(vf.get("width", 0)), float(vf.get("height", 0))
            ok = (0 <= x < 1 and 0 <= y < 1 and 0.08 <= w <= 1 and 0.05 <= h <= 1
                  and x + w <= 1.02 and y + h <= 1.02)
            composition["visual_focus"] = {"x": x, "y": y, "width": w, "height": h} if ok else None
        except (TypeError, ValueError):
            composition["visual_focus"] = None
    else:
        composition["visual_focus"] = None
    # Guard: a visual only makes sense on a split layout with a valid focus box.
    if composition.get("layout") != "split" or not composition.get("visual_focus"):
        composition["use_visual"] = False
        composition["visual_source"] = "none"
        composition["visual_focus"] = None

    palette = {
        "primary": colors.get("primary", "#3B82F6"),
        "secondary": colors.get("secondary", "#1E293B"),
        "accent": colors.get("accent", "#F59E0B"),
    }

    logger.info(
        f"[SinglePass] Extracted: title='{title[:60]}', type={page_type}, "
        f"has_subtitle={subtitle is not None}, has_credibility={credibility is not None}, "
        f"confidence={confidence:.2f}"
    )

    # Crop logo/avatar if bounding box was detected
    primary_image_base64 = None
    if logo_bbox and isinstance(logo_bbox, dict):
        try:
            is_profile = data.get("is_individual_profile", False)
            primary_image_base64 = crop_region(pil_image, logo_bbox, is_profile_image=is_profile)
            if primary_image_base64:
                logger.info(f"[SinglePass] Cropped {'avatar' if is_profile else 'logo'} from bbox")
        except Exception as e:
            logger.warning(f"[SinglePass] Logo crop failed: {e}")

    # Build credibility items
    credibility_items = []
    if credibility:
        credibility_items.append({"type": "proof", "value": credibility})

    # Normalize page type to template type
    template_map = {
        "profile": "profile", "personal": "profile",
        "product": "product", "ecommerce": "product", "marketplace": "product",
        "blog": "article", "news": "article", "article": "article", "documentation": "article",
        "agency": "service", "portfolio": "service",
    }
    template_type = template_map.get(page_type, "landing")

    # Build blueprint
    blueprint = LayoutBlueprint(
        template_type=template_type,
        primary_color=palette["primary"],
        secondary_color=palette["secondary"],
        accent_color=palette["accent"],
        layout_reasoning=f"Single-pass extraction, page_type={page_type}",
        coherence_score=confidence,
        balance_score=confidence,
        clarity_score=confidence,
        overall_quality="excellent" if confidence >= 0.9 else "good" if confidence >= 0.7 else "fair",
    )

    processing_time = int((time.time() - start_time) * 1000)

    result = ReasonedPreview(
        regions=[],
        blueprint=blueprint,
        title=title,
        subtitle=subtitle,
        description=description,
        tags=tags,
        context_items=[],
        credibility_items=credibility_items,
        cta_text=cta_text,
        primary_image_base64=primary_image_base64,
        design_dna=design_dna,
        composition=composition,
        processing_time_ms=processing_time,
        reasoning_confidence=confidence,
        design_fidelity_score=confidence,
    )

    logger.info(
        f"[SinglePass] Done in {processing_time}ms: "
        f"template={template_type}, quality={blueprint.overall_quality}, "
        f"layout={composition.get('layout')}, title='{title[:50]}'"
    )

    return result

