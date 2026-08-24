"""
Design DNA Extractor - Core Design Intelligence Service.

This module extracts the DESIGN PHILOSOPHY of a webpage, not just its elements.
It understands WHY designers made choices and WHAT emotional message they convey.

The Design DNA includes:
- Design Philosophy: minimalist, maximalist, brutalist, luxurious, playful, etc.
- Typography DNA: personality, weight contrast, spacing character
- Color Psychology: emotional intent, strategy, saturation
- Spatial Intelligence: density, rhythm, whitespace intention
- Hero Element: the single most important visual element
- Brand Personality: adjectives, target feeling, confidence

This forms the foundation for creating previews that honor the original design's soul.
"""

import json
import base64
import logging
import time
from io import BytesIO
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from PIL import Image
from openai import OpenAI
from backend.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# DESIGN DNA SCHEMA
# =============================================================================

class DesignPhilosophyStyle(str, Enum):
    """Primary design style categories."""
    MINIMALIST = "minimalist"
    MAXIMALIST = "maximalist"
    BRUTALIST = "brutalist"
    ORGANIC = "organic"
    CORPORATE = "corporate"
    LUXURIOUS = "luxurious"
    PLAYFUL = "playful"
    TECHNICAL = "technical"
    EDITORIAL = "editorial"
    ARTISTIC = "artistic"


class VisualTension(str, Enum):
    """Visual energy level of the design."""
    CALM = "calm"
    BALANCED = "balanced"
    DYNAMIC = "dynamic"
    DRAMATIC = "dramatic"


class DesignEra(str, Enum):
    """Design era/aesthetic period."""
    CONTEMPORARY = "contemporary"
    CLASSIC = "classic"
    RETRO = "retro"
    FUTURISTIC = "futuristic"
    TIMELESS = "timeless"


class HeadlinePersonality(str, Enum):
    """Typography personality for headlines."""
    AUTHORITATIVE = "authoritative"
    FRIENDLY = "friendly"
    ELEGANT = "elegant"
    TECHNICAL = "technical"
    BOLD = "bold"
    SUBTLE = "subtle"
    EXPRESSIVE = "expressive"
    REFINED = "refined"


class ColorEmotion(str, Enum):
    """Primary emotional intent of color palette."""
    TRUST = "trust"
    ENERGY = "energy"
    CALM = "calm"
    SOPHISTICATION = "sophistication"
    WARMTH = "warmth"
    INNOVATION = "innovation"
    NATURE = "nature"
    LUXURY = "luxury"
    PLAYFULNESS = "playfulness"


class ColorStrategy(str, Enum):
    """Color palette strategy."""
    MONOCHROMATIC = "monochromatic"
    COMPLEMENTARY = "complementary"
    ANALOGOUS = "analogous"
    TRIADIC = "triadic"
    HIGH_CONTRAST = "high-contrast"
    MUTED = "muted"
    VIBRANT = "vibrant"


class SpatialDensity(str, Enum):
    """Content density approach."""
    COMPACT = "compact"
    BALANCED = "balanced"
    SPACIOUS = "spacious"
    ULTRA_MINIMAL = "ultra-minimal"


class SpatialRhythm(str, Enum):
    """Rhythm of spacing and layout."""
    EVEN = "even"
    DYNAMIC = "dynamic"
    PROGRESSIVE = "progressive"
    ASYMMETRIC = "asymmetric"


@dataclass
class DesignPhilosophy:
    """Core design philosophy of the page."""
    primary_style: str
    secondary_style: Optional[str] = None
    visual_tension: str = "balanced"
    formality: float = 0.5  # 0 = casual, 1 = formal
    design_era: str = "contemporary"
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TypographyDNA:
    """Typography personality and characteristics."""
    headline_personality: str
    body_personality: str = "neutral"
    weight_contrast: str = "medium"  # high, medium, subtle
    case_strategy: str = "mixed"  # mixed, uppercase-accent, lowercase-casual
    spacing_character: str = "balanced"  # tight-dense, balanced, generous-luxury
    font_mood: str = ""
    recommended_weights: List[str] = field(default_factory=lambda: ["bold", "regular"])
    letter_spacing: str = "normal"  # tight, normal, wide, very-wide
    line_height: str = "normal"  # tight, normal, relaxed, very-relaxed
    font_size_hierarchy: str = ""  # Description of size relationships
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ColorPsychology:
    """Color psychology and emotional intent."""
    dominant_emotion: str
    color_strategy: str
    saturation_character: str = "balanced"  # vivid, muted, desaturated
    light_dark_balance: float = 0.5  # 0 = dark, 1 = light
    accent_usage: str = ""
    primary_hex: str = "#2563EB"
    secondary_hex: str = "#1E40AF"
    accent_hex: str = "#F59E0B"
    background_hex: str = "#FFFFFF"
    text_hex: str = "#111827"
    color_usage_pattern: str = ""  # How colors are used in the design
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpatialIntelligence:
    """Spatial relationships and layout rhythm."""
    density: str
    rhythm: str
    alignment_philosophy: str = "strict-grid"  # strict-grid, organic, mixed
    whitespace_intention: str = ""
    padding_scale: str = "medium"  # compact, medium, generous, luxurious
    grid_system: str = "8px-grid"  # 8px-grid, 12-column, 16-column, organic, none
    spacing_pattern: str = ""  # Description of spacing rhythm
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeroElement:
    """The single most important visual element."""
    element_type: str  # headline, image, logo, video, illustration, product
    content: str
    why_important: str
    how_to_honor: str
    visual_weight: float = 1.0  # 0-1, how dominant
    placement: str = "center"  # center, left, right, top, bottom
    size_relative_to_page: str = "medium"  # small, medium, large, dominant
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrandPersonality:
    """Brand personality traits."""
    adjectives: List[str]
    target_feeling: str
    voice_tone: str = "professional"  # professional, casual, authoritative, friendly
    design_confidence: float = 0.8
    industry_context: str = ""
    unique_visual_signature: str = ""  # What makes this brand visually unique
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UIComponents:
    """UI component styles and patterns."""
    button_style: str = "flat"  # flat, raised, outlined, ghost, gradient, glassmorphic, neumorphic
    button_shape: str = "rounded"  # rounded, sharp, pill, custom
    button_border_radius: str = "medium"  # none, small, medium, large, pill
    card_style: str = "flat"  # flat, elevated, bordered, glassmorphic, neumorphic
    card_shadow: str = "subtle"  # none, subtle, medium, dramatic
    form_style: str = "outlined"  # minimal, outlined, filled, underlined
    navigation_style: str = "minimal"  # minimal, bold, transparent, solid
    component_patterns: str = ""  # Description of unique UI patterns
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualEffects:
    """Visual effects and styling patterns."""
    shadows: str = "subtle"  # none, subtle, medium, dramatic
    gradients: str = "none"  # none, subtle, moderate, vibrant
    gradient_direction: str = "horizontal"  # horizontal, vertical, diagonal, radial
    borders: str = "thin"  # none, thin, medium, thick
    border_style: str = "solid"  # solid, dashed, dotted, gradient
    effects: List[str] = field(default_factory=list)  # glassmorphism, neumorphism, backdrop-blur, etc.
    visual_textures: List[str] = field(default_factory=list)  # smooth, grainy, paper, fabric
    overlay_patterns: str = "none"  # none, dots, grid, lines, geometric
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LayoutPatterns:
    """Layout structure and content organization."""
    content_structure: str = "centered"  # centered, left-aligned, full-width, asymmetric
    section_spacing: str = "normal"  # tight, normal, generous, very-generous
    content_width: str = "medium"  # narrow, medium, wide, full
    visual_hierarchy: str = ""  # Description of how content is organized
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DesignDNA:
    """Complete Design DNA profile."""
    philosophy: DesignPhilosophy
    typography: TypographyDNA
    color_psychology: ColorPsychology
    spatial: SpatialIntelligence
    hero_element: HeroElement
    brand_personality: BrandPersonality
    ui_components: UIComponents
    visual_effects: VisualEffects
    layout_patterns: LayoutPatterns
    
    # Metadata
    confidence: float = 0.0
    processing_time_ms: int = 0
    model_used: str = "gpt-4o"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "philosophy": self.philosophy.to_dict(),
            "typography": self.typography.to_dict(),
            "color_psychology": self.color_psychology.to_dict(),
            "spatial": self.spatial.to_dict(),
            "hero_element": self.hero_element.to_dict(),
            "brand_personality": self.brand_personality.to_dict(),
            "ui_components": self.ui_components.to_dict(),
            "visual_effects": self.visual_effects.to_dict(),
            "layout_patterns": self.layout_patterns.to_dict(),
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used
        }
    
    def get_template_recommendation(self) -> str:
        """Recommend a template style based on Design DNA."""
        style = self.philosophy.primary_style.lower()
        
        if style in ["minimalist", "luxurious"]:
            return "minimal-luxury"
        elif style in ["maximalist", "playful"]:
            return "bold-expressive"
        elif style in ["technical", "corporate"]:
            return "professional-clean"
        elif style in ["editorial", "artistic"]:
            return "editorial-creative"
        elif style == "brutalist":
            return "brutalist-stark"
        elif style == "organic":
            return "organic-natural"
        else:
            return "adaptive-balanced"
    
    def get_visual_effects(self) -> List[str]:
        """Recommend visual effects based on Design DNA."""
        effects = []
        style = self.philosophy.primary_style.lower()
        tension = self.philosophy.visual_tension.lower()
        
        # Effects based on style
        if style in ["minimalist", "luxurious"]:
            effects.extend(["subtle-shadow", "refined-gradient"])
        elif style in ["maximalist", "playful"]:
            effects.extend(["vibrant-gradient", "bold-shadow"])
        elif style == "technical":
            effects.extend(["sharp-edges", "grid-overlay"])
        elif style == "brutalist":
            effects.extend(["harsh-contrast", "no-decoration"])
        elif style == "organic":
            effects.extend(["soft-blur", "natural-gradient"])
        
        # Effects based on tension
        if tension == "dramatic":
            effects.append("high-contrast")
        elif tension == "calm":
            effects.append("subtle-transitions")
        
        # Effects based on era
        if self.philosophy.design_era == "futuristic":
            effects.append("glassmorphism")
        elif self.philosophy.design_era == "retro":
            effects.append("grain-texture")
        
        return list(set(effects))


# =============================================================================
# AI PROMPTS
# =============================================================================

DESIGN_DNA_SYSTEM_PROMPT = """You are a senior design director with 20+ years of experience at agencies like Pentagram, IDEO, and Apple.

Your expertise is understanding the SOUL of a design - not just what you see, but WHY the designers made those choices and WHAT emotional message they're conveying.

You think like a designer, not a content extractor. You understand:
- Visual hierarchy and how it guides the eye
- Color psychology and emotional resonance
- Typography personality and brand voice
- Spatial relationships and their meaning
- How design creates feeling

OUTPUT STRICT JSON matching the schema. No markdown, no explanations outside JSON."""


DESIGN_DNA_USER_PROMPT = """Analyze this webpage as a design director. Your goal is to understand its COMPLETE DESIGN DNA - the underlying philosophy, visual patterns, UI components, and emotional intent.

URL Context: {url}

CRITICAL: Extract EVERY visual detail that makes this brand unique. Don't just describe what you see - capture HOW it's designed so we can recreate its exact "vibe" in a preview.

OUTPUT JSON:
{{
    "design_philosophy": {{
        "primary_style": "<minimalist|maximalist|brutalist|organic|corporate|luxurious|playful|technical|editorial|artistic>",
        "secondary_style": "<optional secondary style or null>",
        "visual_tension": "<calm|balanced|dynamic|dramatic>",
        "formality": <0.0-1.0, where 0=casual/friendly, 1=formal/serious>,
        "design_era": "<contemporary|classic|retro|futuristic|timeless>",
        "reasoning": "2-3 sentences explaining why this design philosophy was chosen and what message it conveys"
    }},
    
    "typography_dna": {{
        "headline_personality": "<authoritative|friendly|elegant|technical|bold|subtle|expressive|refined>",
        "body_personality": "<neutral|warm|technical|editorial|casual>",
        "weight_contrast": "<high|medium|subtle>",
        "case_strategy": "<mixed|uppercase-accent|lowercase-casual|sentence-case>",
        "spacing_character": "<tight-dense|balanced|generous-luxury>",
        "font_mood": "One sentence describing the emotional quality of the typography",
        "recommended_weights": ["<weights to use, e.g., 'black', 'bold', 'medium', 'regular', 'light'>"],
        "letter_spacing": "<tight|normal|wide|very-wide>",
        "line_height": "<tight|normal|relaxed|very-relaxed>",
        "font_size_hierarchy": "Describe the size relationships (e.g., 'headlines are 3x body, subheadings are 1.5x body')"
    }},
    
    "color_psychology": {{
        "dominant_emotion": "<trust|energy|calm|sophistication|warmth|innovation|nature|luxury|playfulness>",
        "color_strategy": "<monochromatic|complementary|analogous|triadic|high-contrast|muted|vibrant>",
        "saturation_character": "<vivid|balanced|muted|desaturated>",
        "light_dark_balance": <0.0-1.0, where 0=dark theme, 1=light theme>,
        "accent_usage": "How accent colors create emphasis and guide attention",
        "primary_hex": "<main brand color hex - extract EXACT color from logo/branding>",
        "secondary_hex": "<secondary/supporting color hex - extract from UI>",
        "accent_hex": "<accent/CTA color hex - extract from buttons/links>",
        "background_hex": "<main background color hex>",
        "text_hex": "<main text color hex>",
        "color_usage_pattern": "How colors are used (e.g., 'primary for CTAs, secondary for backgrounds, accent for highlights')"
    }},
    
    "spatial_intelligence": {{
        "density": "<compact|balanced|spacious|ultra-minimal>",
        "rhythm": "<even|dynamic|progressive|asymmetric>",
        "alignment_philosophy": "<strict-grid|organic|mixed>",
        "whitespace_intention": "What the whitespace communicates about the brand",
        "padding_scale": "<compact|medium|generous|luxurious>",
        "grid_system": "<8px-grid|12-column|16-column|organic|none>",
        "spacing_pattern": "Describe spacing rhythm (e.g., '8px base unit, 16px for sections, 32px for major breaks')"
    }},
    
    "ui_components": {{
        "button_style": "<flat|raised|outlined|ghost|gradient|glassmorphic|neumorphic>",
        "button_shape": "<rounded|sharp|pill|custom>",
        "button_border_radius": "<none|small|medium|large|pill>",
        "card_style": "<flat|elevated|bordered|glassmorphic|neumorphic>",
        "card_shadow": "<none|subtle|medium|dramatic>",
        "form_style": "<minimal|outlined|filled|underlined>",
        "navigation_style": "<minimal|bold|transparent|solid>",
        "component_patterns": "Describe unique UI patterns (e.g., 'rounded cards with subtle shadows', 'sharp edges with high contrast')"
    }},
    
    "visual_effects": {{
        "shadows": "<none|subtle|medium|dramatic>",
        "gradients": "<none|subtle|moderate|vibrant>",
        "gradient_direction": "<horizontal|vertical|diagonal|radial>",
        "borders": "<none|thin|medium|thick>",
        "border_style": "<solid|dashed|dotted|gradient>",
        "effects": ["<glassmorphism|neumorphism|backdrop-blur|text-shadow|box-shadow|none>"],
        "visual_textures": ["<smooth|grainy|paper|fabric|none>"],
        "overlay_patterns": "<none|dots|grid|lines|geometric>"
    }},
    
    "hero_element": {{
        "element_type": "<headline|image|logo|video|illustration|product|profile|testimonial>",
        "content": "The actual content/text of the hero element",
        "why_important": "Why this element dominates the visual hierarchy",
        "how_to_honor": "How to preserve this element's importance in a preview",
        "visual_weight": <0.0-1.0, how dominant this element is>,
        "placement": "<center|left|right|top|bottom>",
        "size_relative_to_page": "<small|medium|large|dominant>"
    }},
    
    "brand_personality": {{
        "adjectives": ["3-5 words describing the brand personality"],
        "target_feeling": "How should a viewer FEEL after seeing this design?",
        "voice_tone": "<professional|casual|authoritative|friendly|playful|sophisticated|warm|innovative>",
        "design_confidence": <0.0-1.0, how confident/polished is the design execution>,
        "industry_context": "What industry/sector this appears to be for",
        "unique_visual_signature": "What makes this brand visually unique? (e.g., 'bold gradients with sharp corners', 'minimalist with generous whitespace')"
    }},
    
    "layout_patterns": {{
        "content_structure": "<centered|left-aligned|full-width|asymmetric>",
        "section_spacing": "<tight|normal|generous|very-generous>",
        "content_width": "<narrow|medium|wide|full>",
        "visual_hierarchy": "Describe how content is organized (e.g., 'hero at top, features in grid below', 'sidebar navigation with main content')"
    }},
    
    "analysis_confidence": <0.0-1.0>
}}

ANALYSIS PRINCIPLES:
1. INTENT > APPEARANCE: Focus on WHY, not just WHAT
2. EMOTIONAL TRUTH: What feeling does this design create?
3. DESIGNER'S EYE: How would you describe this to a fellow designer?
4. BRAND ESSENCE: What makes this design uniquely theirs?
5. PRACTICAL APPLICATION: How should we honor this in a preview?
6. VISUAL FIDELITY: Extract EXACT visual details - colors, spacing, effects, component styles
7. PATTERN RECOGNITION: Identify repeating visual patterns that define the brand

CRITICAL EXTRACTION REQUIREMENTS:
- Extract EXACT brand colors from logo/branding elements (not generic colors)
- Identify UI component styles (button shapes, card styles, shadows)
- Capture visual effects (gradients, shadows, borders, textures)
- Note typography specifics (letter spacing, line height, size hierarchy)
- Document layout patterns (grid systems, spacing rhythm)
- Identify unique visual signatures that make this brand distinct

Look beyond the obvious. A minimalist design isn't just "simple" - it's a deliberate choice to create clarity, focus, and sophistication. Extract EVERY visual detail that contributes to the brand's unique "vibe"."""


# =============================================================================
# IMAGE PREPARATION
# =============================================================================

def prepare_image_for_dna_analysis(screenshot_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Prepare image for Design DNA analysis with high quality.
    
    Returns:
        Tuple of (base64_string, preparation_info)
    """
    image = Image.open(BytesIO(screenshot_bytes))
    original_size = image.size
    
    # Use higher resolution for design analysis (we need to see details)
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
    
    # High quality JPEG for better analysis
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=95)
    
    info = {
        "original_size": original_size,
        "processed_size": image.size,
        "compressed_bytes": buffer.tell()
    }
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8'), info


# =============================================================================
# CORE EXTRACTION
# =============================================================================

def extract_design_dna(
    screenshot_bytes: bytes,
    url: str = "",
    timeout: int = 60
) -> DesignDNA:
    """
    Extract complete Design DNA from a webpage screenshot.
    
    This is the primary function for understanding a page's design philosophy.
    
    Args:
        screenshot_bytes: Raw PNG screenshot bytes
        url: URL for context
        timeout: API timeout in seconds
        
    Returns:
        DesignDNA with complete design analysis
    """
    start_time = time.time()
    
    # Prepare image
    image_base64, prep_info = prepare_image_for_dna_analysis(screenshot_bytes)
    logger.info(f"🧬 Extracting Design DNA for: {url[:50]}...")
    
    try:
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("design_dna")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "system",
                    "content": DESIGN_DNA_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": DESIGN_DNA_USER_PROMPT.format(url=url)
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
            max_tokens=2500,
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        
        # Build DesignDNA
        dna = _build_design_dna(data, elapsed_ms)
        
        logger.info(
            f"✅ Design DNA extracted: style={dna.philosophy.primary_style}, "
            f"tension={dna.philosophy.visual_tension}, "
            f"emotion={dna.color_psychology.dominant_emotion}, "
            f"confidence={dna.confidence:.2f}, time={elapsed_ms}ms"
        )
        
        return dna
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Design DNA JSON: {e}")
        return _get_fallback_dna(url, str(e))
    except Exception as e:
        logger.error(f"Design DNA extraction failed: {e}")
        return _get_fallback_dna(url, str(e))


def _build_design_dna(data: Dict[str, Any], processing_time_ms: int) -> DesignDNA:
    """Build DesignDNA from parsed JSON data."""
    
    # Philosophy
    phil_data = data.get("design_philosophy", {})
    philosophy = DesignPhilosophy(
        primary_style=phil_data.get("primary_style", "corporate"),
        secondary_style=phil_data.get("secondary_style"),
        visual_tension=phil_data.get("visual_tension", "balanced"),
        formality=float(phil_data.get("formality", 0.5)),
        design_era=phil_data.get("design_era", "contemporary"),
        reasoning=phil_data.get("reasoning", "")
    )
    
    # Typography
    typo_data = data.get("typography_dna", {})
    typography = TypographyDNA(
        headline_personality=typo_data.get("headline_personality", "bold"),
        body_personality=typo_data.get("body_personality", "neutral"),
        weight_contrast=typo_data.get("weight_contrast", "medium"),
        case_strategy=typo_data.get("case_strategy", "mixed"),
        spacing_character=typo_data.get("spacing_character", "balanced"),
        font_mood=typo_data.get("font_mood", ""),
        recommended_weights=typo_data.get("recommended_weights", ["bold", "regular"]),
        letter_spacing=typo_data.get("letter_spacing", "normal"),
        line_height=typo_data.get("line_height", "normal"),
        font_size_hierarchy=typo_data.get("font_size_hierarchy", "")
    )
    
    # Color Psychology
    color_data = data.get("color_psychology", {})
    color_psychology = ColorPsychology(
        dominant_emotion=color_data.get("dominant_emotion", "trust"),
        color_strategy=color_data.get("color_strategy", "complementary"),
        saturation_character=color_data.get("saturation_character", "balanced"),
        light_dark_balance=float(color_data.get("light_dark_balance", 0.7)),
        accent_usage=color_data.get("accent_usage", ""),
        primary_hex=color_data.get("primary_hex", "#2563EB"),
        secondary_hex=color_data.get("secondary_hex", "#1E40AF"),
        accent_hex=color_data.get("accent_hex", "#F59E0B"),
        background_hex=color_data.get("background_hex", "#FFFFFF"),
        text_hex=color_data.get("text_hex", "#111827"),
        color_usage_pattern=color_data.get("color_usage_pattern", "")
    )
    
    # Spatial Intelligence
    spatial_data = data.get("spatial_intelligence", {})
    spatial = SpatialIntelligence(
        density=spatial_data.get("density", "balanced"),
        rhythm=spatial_data.get("rhythm", "even"),
        alignment_philosophy=spatial_data.get("alignment_philosophy", "strict-grid"),
        whitespace_intention=spatial_data.get("whitespace_intention", ""),
        padding_scale=spatial_data.get("padding_scale", "medium"),
        grid_system=spatial_data.get("grid_system", "8px-grid"),
        spacing_pattern=spatial_data.get("spacing_pattern", "")
    )
    
    # Hero Element
    hero_data = data.get("hero_element", {})
    hero_element = HeroElement(
        element_type=hero_data.get("element_type", "headline"),
        content=hero_data.get("content", ""),
        why_important=hero_data.get("why_important", ""),
        how_to_honor=hero_data.get("how_to_honor", ""),
        visual_weight=float(hero_data.get("visual_weight", 1.0)),
        placement=hero_data.get("placement", "center"),
        size_relative_to_page=hero_data.get("size_relative_to_page", "medium")
    )
    
    # Brand Personality
    brand_data = data.get("brand_personality", {})
    brand_personality = BrandPersonality(
        adjectives=brand_data.get("adjectives", ["professional", "modern"]),
        target_feeling=brand_data.get("target_feeling", "Trust and confidence"),
        voice_tone=brand_data.get("voice_tone", "professional"),
        design_confidence=float(brand_data.get("design_confidence", 0.8)),
        industry_context=brand_data.get("industry_context", ""),
        unique_visual_signature=brand_data.get("unique_visual_signature", "")
    )
    
    # UI Components
    ui_data = data.get("ui_components", {})
    ui_components = UIComponents(
        button_style=ui_data.get("button_style", "flat"),
        button_shape=ui_data.get("button_shape", "rounded"),
        button_border_radius=ui_data.get("button_border_radius", "medium"),
        card_style=ui_data.get("card_style", "flat"),
        card_shadow=ui_data.get("card_shadow", "subtle"),
        form_style=ui_data.get("form_style", "outlined"),
        navigation_style=ui_data.get("navigation_style", "minimal"),
        component_patterns=ui_data.get("component_patterns", "")
    )
    
    # Visual Effects
    effects_data = data.get("visual_effects", {})
    visual_effects = VisualEffects(
        shadows=effects_data.get("shadows", "subtle"),
        gradients=effects_data.get("gradients", "none"),
        gradient_direction=effects_data.get("gradient_direction", "horizontal"),
        borders=effects_data.get("borders", "thin"),
        border_style=effects_data.get("border_style", "solid"),
        effects=effects_data.get("effects", []),
        visual_textures=effects_data.get("visual_textures", []),
        overlay_patterns=effects_data.get("overlay_patterns", "none")
    )
    
    # Layout Patterns
    layout_data = data.get("layout_patterns", {})
    layout_patterns = LayoutPatterns(
        content_structure=layout_data.get("content_structure", "centered"),
        section_spacing=layout_data.get("section_spacing", "normal"),
        content_width=layout_data.get("content_width", "medium"),
        visual_hierarchy=layout_data.get("visual_hierarchy", "")
    )
    
    return DesignDNA(
        philosophy=philosophy,
        typography=typography,
        color_psychology=color_psychology,
        spatial=spatial,
        hero_element=hero_element,
        brand_personality=brand_personality,
        ui_components=ui_components,
        visual_effects=visual_effects,
        layout_patterns=layout_patterns,
        confidence=float(data.get("analysis_confidence", 0.7)),
        processing_time_ms=processing_time_ms
    )


def _get_fallback_dna(url: str, error: str) -> DesignDNA:
    """Get a fallback Design DNA when extraction fails."""
    logger.warning(f"Using fallback Design DNA due to: {error}")
    
    return DesignDNA(
        philosophy=DesignPhilosophy(
            primary_style="corporate",
            visual_tension="balanced",
            formality=0.6,
            design_era="contemporary",
            reasoning=f"Fallback DNA due to extraction error: {error[:100]}"
        ),
        typography=TypographyDNA(
            headline_personality="bold",
            body_personality="neutral",
            weight_contrast="medium",
            case_strategy="mixed",
            spacing_character="balanced",
            font_mood="Professional and clear",
            letter_spacing="normal",
            line_height="normal",
            font_size_hierarchy="Standard hierarchy"
        ),
        color_psychology=ColorPsychology(
            dominant_emotion="trust",
            color_strategy="complementary",
            saturation_character="balanced",
            light_dark_balance=0.7,
            accent_usage="Standard accent for CTAs",
            color_usage_pattern="Standard color usage"
        ),
        spatial=SpatialIntelligence(
            density="balanced",
            rhythm="even",
            alignment_philosophy="strict-grid",
            whitespace_intention="Standard breathing room",
            padding_scale="medium",
            grid_system="8px-grid",
            spacing_pattern="Standard spacing"
        ),
        hero_element=HeroElement(
            element_type="headline",
            content="Content from " + url[:50],
            why_important="Primary message",
            how_to_honor="Use as main title",
            visual_weight=1.0,
            placement="center",
            size_relative_to_page="medium"
        ),
        brand_personality=BrandPersonality(
            adjectives=["professional", "modern", "trustworthy"],
            target_feeling="Confidence and trust",
            voice_tone="professional",
            design_confidence=0.5,
            industry_context="General",
            unique_visual_signature="Standard professional design"
        ),
        ui_components=UIComponents(
            button_style="flat",
            button_shape="rounded",
            button_border_radius="medium",
            card_style="flat",
            card_shadow="subtle",
            form_style="outlined",
            navigation_style="minimal",
            component_patterns="Standard UI components"
        ),
        visual_effects=VisualEffects(
            shadows="subtle",
            gradients="none",
            gradient_direction="horizontal",
            borders="thin",
            border_style="solid",
            effects=[],
            visual_textures=[],
            overlay_patterns="none"
        ),
        layout_patterns=LayoutPatterns(
            content_structure="centered",
            section_spacing="normal",
            content_width="medium",
            visual_hierarchy="Standard hierarchy"
        ),
        confidence=0.3
    )


# =============================================================================
# QUICK ANALYSIS (Lightweight version)
# =============================================================================

def extract_quick_dna(
    screenshot_bytes: bytes,
    url: str = ""
) -> Dict[str, Any]:
    """
    Extract a quick/lightweight Design DNA for faster processing.
    
    Uses a simpler prompt for speed while still capturing essential DNA.
    Returns a dictionary instead of full DesignDNA object.
    """
    start_time = time.time()
    
    image_base64, _ = prepare_image_for_dna_analysis(screenshot_bytes)
    
    quick_prompt = """Quickly analyze this webpage's design DNA. Output JSON only:
{
    "style": "<minimalist|maximalist|corporate|luxurious|playful|technical>",
    "mood": "<calm|energetic|sophisticated|friendly|bold>",
    "colors": {
        "primary": "<hex>",
        "secondary": "<hex>",
        "accent": "<hex>",
        "is_dark_theme": <true|false>
    },
    "typography": "<bold|elegant|technical|friendly|minimal>",
    "spacing": "<compact|balanced|spacious>",
    "brand_feel": ["2-3 adjectives"],
    "hero_focus": "<headline|image|product|profile>"
}"""
    
    try:
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("design_dna")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": quick_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "low"  # Low detail for speed
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        data["processing_time_ms"] = int((time.time() - start_time) * 1000)
        
        logger.info(f"⚡ Quick DNA extracted: style={data.get('style')}, mood={data.get('mood')}")
        return data
        
    except Exception as e:
        logger.warning(f"Quick DNA extraction failed: {e}")
        return {
            "style": "corporate",
            "mood": "balanced",
            "colors": {"primary": "#2563EB", "secondary": "#1E40AF", "accent": "#F59E0B", "is_dark_theme": False},
            "typography": "bold",
            "spacing": "balanced",
            "brand_feel": ["professional", "modern"],
            "hero_focus": "headline",
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "fallback": True
        }


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def dna_to_blueprint_colors(dna: DesignDNA) -> Dict[str, str]:
    """Convert Design DNA color psychology to blueprint colors."""
    return {
        "primary_color": dna.color_psychology.primary_hex,
        "secondary_color": dna.color_psychology.secondary_hex,
        "accent_color": dna.color_psychology.accent_hex,
        "background_color": dna.color_psychology.background_hex,
        "text_color": dna.color_psychology.text_hex
    }


def dna_to_template_config(dna: DesignDNA) -> Dict[str, Any]:
    """Convert Design DNA to template configuration."""
    return {
        "template_style": dna.get_template_recommendation(),
        "visual_effects": dna.get_visual_effects(),
        "typography": {
            "headline_style": dna.typography.headline_personality,
            "weight_contrast": dna.typography.weight_contrast,
            "spacing": dna.typography.spacing_character,
            "recommended_weights": dna.typography.recommended_weights
        },
        "spatial": {
            "density": dna.spatial.density,
            "padding_scale": dna.spatial.padding_scale,
            "alignment": dna.spatial.alignment_philosophy
        },
        "mood": {
            "formality": dna.philosophy.formality,
            "tension": dna.philosophy.visual_tension,
            "emotion": dna.color_psychology.dominant_emotion
        },
        "brand_adjectives": dna.brand_personality.adjectives
    }

