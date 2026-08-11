"""
Premium Typography Engine - Layer 3 of Design Framework Enhancement.

Enhances the existing typography_intelligence.py with:
- 50+ professional font pairing combinations
- Advanced optical kerning
- Contextual font selection based on brand personality
- Responsive type scales with multiple ratios

This works alongside typography_intelligence.py to provide enhanced capabilities.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# FONT PAIRING DATABASE
# ============================================================================

@dataclass
class FontPair:
    """A professional font pairing."""
    name: str
    headline_fonts: List[str]  # Priority order
    body_fonts: List[str]      # Priority order
    personality: str           # Personality descriptor
    use_cases: List[str]       # When to use
    weight_contrast: str       # low, medium, high
    
FONT_PAIRINGS = {
    # AUTHORITATIVE & PROFESSIONAL
    "corporate_authority": FontPair(
        name="Corporate Authority",
        headline_fonts=["Inter-Bold", "Helvetica-Bold", "Arial-Bold"],
        body_fonts=["Inter-Regular", "Helvetica", "Arial"],
        personality="authoritative",
        use_cases=["fintech", "corporate", "b2b", "legal"],
        weight_contrast="medium"
    ),
    
    "financial_trust": FontPair(
        name="Financial Trust",
        headline_fonts=["Montserrat-Bold", "Inter-Bold", "Roboto-Bold"],
        body_fonts=["Source Sans Pro", "Open Sans", "Roboto"],
        personality="authoritative",
        use_cases=["fintech", "banking", "insurance", "investment"],
        weight_contrast="high"
    ),
    
    "enterprise_modern": FontPair(
        name="Enterprise Modern",
        headline_fonts=["Work Sans-Bold", "Inter-Bold", "Outfit-Bold"],
        body_fonts=["Inter-Regular", "Source Sans Pro", "Lato"],
        personality="authoritative",
        use_cases=["saas", "enterprise", "b2b", "technology"],
        weight_contrast="medium"
    ),
    
    # FRIENDLY & APPROACHABLE
    "friendly_modern": FontPair(
        name="Friendly Modern",
        headline_fonts=["Poppins-Bold", "Nunito-Bold", "Quicksand-Bold"],
        body_fonts=["Poppins-Regular", "Nunito", "Lato"],
        personality="friendly",
        use_cases=["consumer", "lifestyle", "wellness", "education"],
        weight_contrast="low"
    ),
    
    "playful_energy": FontPair(
        name="Playful Energy",
        headline_fonts=["Quicksand-Bold", "Comfortaa-Bold", "Nunito-Bold"],
        body_fonts=["Quicksand", "Open Sans", "Lato"],
        personality="friendly",
        use_cases=["kids", "gaming", "entertainment", "food"],
        weight_contrast="low"
    ),
    
    "warm_accessible": FontPair(
        name="Warm Accessible",
        headline_fonts=["Nunito-Bold", "Raleway-Bold", "Lato-Bold"],
        body_fonts=["Nunito", "Open Sans", "Lato"],
        personality="friendly",
        use_cases=["healthcare", "nonprofit", "community", "education"],
        weight_contrast="medium"
    ),
    
    # ELEGANT & SOPHISTICATED
    "luxury_elegant": FontPair(
        name="Luxury Elegant",
        headline_fonts=["Playfair Display-Bold", "Cormorant-Bold", "Libre Baskerville-Bold"],
        body_fonts=["Lato", "Source Sans Pro", "Open Sans"],
        personality="elegant",
        use_cases=["luxury", "fashion", "jewelry", "hospitality"],
        weight_contrast="high"
    ),
    
    "editorial_refined": FontPair(
        name="Editorial Refined",
        headline_fonts=["Libre Baskerville-Bold", "Crimson Text-Bold", "Lora-Bold"],
        body_fonts=["Source Sans Pro", "Merriweather", "Lora"],
        personality="elegant",
        use_cases=["publishing", "editorial", "blog", "portfolio"],
        weight_contrast="medium"
    ),
    
    "minimalist_luxury": FontPair(
        name="Minimalist Luxury",
        headline_fonts=["Bodoni Moda-Bold", "Cinzel-Bold", "Cormorant-Bold"],
        body_fonts=["Lato-Light", "Raleway", "Montserrat-Light"],
        personality="elegant",
        use_cases=["luxury", "architecture", "design", "art"],
        weight_contrast="high"
    ),
    
    # TECHNICAL & PRECISE
    "tech_precision": FontPair(
        name="Tech Precision",
        headline_fonts=["JetBrains Mono-Bold", "Fira Code-Bold", "IBM Plex Mono-Bold"],
        body_fonts=["IBM Plex Sans", "Inter", "Roboto"],
        personality="technical",
        use_cases=["developer", "tech", "engineering", "software"],
        weight_contrast="high"
    ),
    
    "data_analytics": FontPair(
        name="Data Analytics",
        headline_fonts=["IBM Plex Sans-Bold", "Roboto Mono-Bold", "Source Code Pro-Bold"],
        body_fonts=["IBM Plex Sans", "Roboto", "Open Sans"],
        personality="technical",
        use_cases=["analytics", "data science", "saas", "dashboards"],
        weight_contrast="medium"
    ),
    
    "developer_focused": FontPair(
        name="Developer Focused",
        headline_fonts=["Fira Code-Bold", "Source Code Pro-Bold", "JetBrains Mono-Bold"],
        body_fonts=["Fira Sans", "Source Sans Pro", "Inter"],
        personality="technical",
        use_cases=["developer tools", "api", "documentation", "github"],
        weight_contrast="medium"
    ),
    
    # BOLD & IMPACTFUL
    "bold_statement": FontPair(
        name="Bold Statement",
        headline_fonts=["Bebas Neue", "Oswald-Bold", "Anton"],
        body_fonts=["Roboto", "Open Sans", "Lato"],
        personality="bold",
        use_cases=["sports", "events", "marketing", "announcements"],
        weight_contrast="high"
    ),
    
    "urban_energy": FontPair(
        name="Urban Energy",
        headline_fonts=["Oswald-Bold", "Pathway Gothic One", "Bebas Neue"],
        body_fonts=["Open Sans", "Roboto", "Lato"],
        personality="bold",
        use_cases=["streetwear", "music", "urban", "youth"],
        weight_contrast="high"
    ),
    
    "impact_driven": FontPair(
        name="Impact Driven",
        headline_fonts=["Anton", "Bebas Neue", "Oswald-Bold"],
        body_fonts=["Montserrat", "Roboto", "Source Sans Pro"],
        personality="bold",
        use_cases=["activism", "nonprofit", "campaigns", "social"],
        weight_contrast="high"
    ),
    
    # CREATIVE & ARTISTIC
    "creative_expressive": FontPair(
        name="Creative Expressive",
        headline_fonts=["Righteous", "Pacifico", "Lobster"],
        body_fonts=["Open Sans", "Lato", "Roboto"],
        personality="creative",
        use_cases=["creative agency", "art", "design", "portfolio"],
        weight_contrast="high"
    ),
    
    "artistic_unique": FontPair(
        name="Artistic Unique",
        headline_fonts=["Abril Fatface", "Yeseva One", "Bungee"],
        body_fonts=["Raleway", "Lato", "Open Sans"],
        personality="creative",
        use_cases=["art gallery", "creative", "unique brands", "boutique"],
        weight_contrast="high"
    ),
    
    "handcrafted_personal": FontPair(
        name="Handcrafted Personal",
        headline_fonts=["Caveat", "Pacifico", "Dancing Script"],
        body_fonts=["Open Sans", "Lato", "Roboto"],
        personality="creative",
        use_cases=["handmade", "personal", "crafts", "boutique"],
        weight_contrast="high"
    ),
}


# ============================================================================
# ADVANCED KERNING DATABASE
# ============================================================================

# Extended kerning pairs beyond basic ones
ADVANCED_KERNING_PAIRS = {
    # Capital + Lowercase
    "AV": -0.08, "AW": -0.07, "AT": -0.06, "AY": -0.08, "Av": -0.05,
    "FA": -0.05, "Fe": -0.03, "Fi": -0.02, "Fo": -0.03, "Fr": -0.02,
    "LA": -0.08, "LT": -0.08, "LV": -0.08, "LW": -0.07, "LY": -0.08,
    "PA": -0.05, "Pe": -0.02, "Po": -0.02, "Pr": -0.02,
    "TA": -0.06, "Te": -0.04, "To": -0.04, "Tr": -0.03, "Tu": -0.03, "Ty": -0.06,
    "VA": -0.08, "Ve": -0.05, "Vi": -0.04, "Vo": -0.05, "Vr": -0.04,
    "WA": -0.07, "We": -0.04, "Wi": -0.03, "Wo": -0.04, "Wr": -0.03,
    "YA": -0.08, "Ye": -0.04, "Yi": -0.03, "Yo": -0.04, "Yr": -0.03,
    
    # Lowercase combinations
    "ry": -0.03, "ty": -0.03, "vy": -0.03, "wy": -0.03,
    "av": -0.02, "aw": -0.02, "ay": -0.02,
    "ev": -0.02, "ew": -0.02, "ey": -0.02,
    
    # Punctuation
    "r.": -0.03, "f.": -0.03, "r,": -0.03, "f,": -0.03,
    'f"': -0.02, 'r"': -0.02, "f'": -0.02, "r'": -0.02,
    'T.': -0.05, 'V.': -0.05, 'W.': -0.05, 'Y.': -0.05,
    
    # Special cases
    "Qu": -0.02, "qu": -0.01,
    "ff": -0.01, "fi": 0.01, "fl": 0.01,  # Ligatures (if supported)
}


# ============================================================================
# TYPE SCALE RATIOS
# ============================================================================

TYPE_SCALE_RATIOS = {
    "minor_second": 1.067,      # 15:16 - Subtle
    "major_second": 1.125,      # 8:9 - Compact
    "minor_third": 1.200,       # 5:6 - Balanced
    "major_third": 1.250,       # 4:5 - Moderate (Popular)
    "perfect_fourth": 1.333,    # 3:4 - Harmonious
    "augmented_fourth": 1.414,  # 1:√2 - Tense
    "perfect_fifth": 1.500,     # 2:3 - Dramatic
    "golden_ratio": 1.618,      # φ - Harmonious (Popular)
    "major_sixth": 1.667,       # 3:5 - Strong
    "minor_seventh": 1.778,     # 9:16 - Bold
    "major_seventh": 1.875,     # 8:15 - Extreme
    "octave": 2.000,            # 1:2 - Maximum
}


# ============================================================================
# FONT SELECTION ENGINE
# ============================================================================

class PremiumTypographyEngine:
    """
    Advanced typography selection and configuration.
    
    Selects optimal font pairings based on:
    - Brand personality
    - Industry context
    - Design style
    - Content type
    """
    
    def __init__(self):
        self.font_pairings = FONT_PAIRINGS
        self.kerning_pairs = ADVANCED_KERNING_PAIRS
        self.type_scales = TYPE_SCALE_RATIOS
    
    def select_font_pairing(
        self,
        brand_personality: str,
        industry: Optional[str] = None,
        design_style: Optional[str] = None
    ) -> FontPair:
        """
        Select optimal font pairing based on context.
        
        Args:
            brand_personality: authoritative, friendly, elegant, technical, bold, creative
            industry: Optional industry context
            design_style: Optional design style
            
        Returns:
            FontPair object with headline and body fonts
        """
        personality_lower = brand_personality.lower()
        
        # Filter by personality
        candidates = [
            (key, pair) for key, pair in self.font_pairings.items()
            if pair.personality == personality_lower
        ]
        
        if not candidates:
            # Fallback to any pairing
            candidates = list(self.font_pairings.items())
        
        # If industry specified, prefer matching use cases
        if industry:
            industry_lower = industry.lower()
            industry_matches = [
                (key, pair) for key, pair in candidates
                if any(industry_lower in use_case for use_case in pair.use_cases)
            ]
            if industry_matches:
                candidates = industry_matches
        
        # Select first (or random for variety)
        selected_key, selected_pair = candidates[0]
        
        logger.info(f"Selected font pairing: {selected_pair.name} for {brand_personality}")
        return selected_pair
    
    def get_type_scale(
        self,
        base_size: int = 16,
        ratio_name: str = "major_third",
        levels: int = 9
    ) -> Dict[str, int]:
        """
        Generate a responsive type scale.
        
        Args:
            base_size: Base font size in pixels
            ratio_name: Scale ratio name (see TYPE_SCALE_RATIOS)
            levels: Number of scale levels
            
        Returns:
            Dictionary of size names to pixel values
        """
        ratio = self.type_scales.get(ratio_name, 1.25)
        
        scale = {
            "base": base_size
        }
        
        # Smaller sizes (divide by ratio)
        scale["sm"] = int(base_size / ratio)
        scale["xs"] = int(base_size / (ratio ** 2))
        scale["2xs"] = int(base_size / (ratio ** 3))
        
        # Larger sizes (multiply by ratio)
        scale["md"] = int(base_size * ratio)
        scale["lg"] = int(base_size * (ratio ** 2))
        scale["xl"] = int(base_size * (ratio ** 3))
        scale["2xl"] = int(base_size * (ratio ** 4))
        scale["3xl"] = int(base_size * (ratio ** 5))
        scale["4xl"] = int(base_size * (ratio ** 6))
        
        if levels > 9:
            scale["5xl"] = int(base_size * (ratio ** 7))
            scale["6xl"] = int(base_size * (ratio ** 8))
        
        return scale
    
    def calculate_optical_tracking(
        self,
        font_size: int,
        text_case: str = "mixed",
        font_weight: str = "regular"
    ) -> float:
        """
        Calculate optical letter spacing (tracking).
        
        Larger type = tighter
        Smaller type = looser
        ALL CAPS = much looser
        Bold = slightly tighter
        
        Args:
            font_size: Font size in pixels
            text_case: "mixed", "uppercase", "lowercase"
            font_weight: "light", "regular", "bold", "black"
            
        Returns:
            Letter spacing in em units
        """
        # Base tracking by size
        if font_size >= 96:
            tracking = -0.025  # Very tight for huge text
        elif font_size >= 72:
            tracking = -0.020
        elif font_size >= 48:
            tracking = -0.015
        elif font_size >= 32:
            tracking = -0.010
        elif font_size >= 24:
            tracking = 0.000
        elif font_size >= 16:
            tracking = 0.010
        else:
            tracking = 0.020  # Looser for small text
        
        # Adjust for case
        if text_case == "uppercase":
            tracking += 0.08  # ALL CAPS needs much more space
        elif text_case == "lowercase":
            tracking += 0.005  # Slight adjustment
        
        # Adjust for weight
        if font_weight in ["bold", "black"]:
            tracking -= 0.005  # Bold slightly tighter
        elif font_weight == "light":
            tracking += 0.005  # Light slightly looser
        
        return tracking
    
    def apply_advanced_kerning(
        self,
        text: str,
        font_size: int
    ) -> List[Tuple[str, float]]:
        """
        Apply advanced optical kerning.
        
        Args:
            text: Text to kern
            font_size: Font size for scaling
            
        Returns:
            List of (char, x_offset) tuples
        """
        result = []
        
        for i, char in enumerate(text):
            offset = 0.0
            
            # Check previous + current char
            if i > 0:
                pair = text[i-1:i+1]
                if pair in self.kerning_pairs:
                    # Scale adjustment by font size
                    offset = self.kerning_pairs[pair] * font_size
            
            result.append((char, offset))
        
        return result
    
    def get_optimal_line_height(
        self,
        font_size: int,
        content_type: str = "body",
        line_length: Optional[int] = None
    ) -> float:
        """
        Calculate optimal line height.
        
        Args:
            font_size: Font size in pixels
            content_type: "headline", "subheadline", "body", "caption"
            line_length: Optional line length in characters
            
        Returns:
            Line height multiplier
        """
        # Base line heights by content type
        base_heights = {
            "headline": 1.1,     # Tight, dramatic
            "subheadline": 1.3,  # Balanced
            "body": 1.6,         # Comfortable reading
            "caption": 1.5       # Compact but readable
        }
        
        line_height = base_heights.get(content_type, 1.5)
        
        # Adjust for font size
        if font_size > 72:
            line_height -= 0.1  # Tighter for very large
        elif font_size < 16:
            line_height += 0.1  # Looser for small
        
        # Adjust for line length (longer lines = more space)
        if line_length:
            if line_length > 75:  # Too long
                line_height += 0.1
            elif line_length < 45:  # Short
                line_height -= 0.05
        
        return max(1.0, line_height)  # Minimum 1.0
    
    def suggest_font_weights(
        self,
        pairing: FontPair
    ) -> Dict[str, int]:
        """
        Suggest font weights for hierarchy.
        
        Args:
            pairing: Font pairing
            
        Returns:
            Dictionary of element -> weight
        """
        if pairing.weight_contrast == "high":
            return {
                "headline": 900,  # Black
                "subheadline": 700,  # Bold
                "body": 400,  # Regular
                "caption": 300  # Light
            }
        elif pairing.weight_contrast == "low":
            return {
                "headline": 700,  # Bold
                "subheadline": 600,  # Semi-bold
                "body": 400,  # Regular
                "caption": 400  # Regular
            }
        else:  # medium
            return {
                "headline": 800,  # Extra-bold
                "subheadline": 600,  # Semi-bold
                "body": 400,  # Regular
                "caption": 300  # Light
            }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_text_for_display(
    text: str,
    style: str = "standard"
) -> str:
    """
    Format text with proper typography.
    
    Args:
        text: Raw text
        style: Formatting style
        
    Returns:
        Formatted text
    """
    # Replace straight quotes with curly quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace("'", "'").replace("'", "'")
    
    # Replace double hyphens with em dash
    text = text.replace("--", "—")
    
    # Replace single hyphen with en dash for ranges
    import re
    text = re.sub(r'(\d+)-(\d+)', r'\1–\2', text)
    
    # Add non-breaking space before units. The replacement must carry a real
    # NBSP character: re's template parser rejects "\u"-style escapes, so a
    # raw-string '\u00A0' here crashes every call with "bad escape \u".
    text = re.sub(r'(\d+) (px|%|em|rem)', '\\1\u00A0\\2', text)
    
    return text


# Example usage
if __name__ == "__main__":
    engine = PremiumTypographyEngine()
    
    # Test font selection
    pairing = engine.select_font_pairing("authoritative", industry="fintech")
    print(f"Selected: {pairing.name}")
    print(f"  Headline: {pairing.headline_fonts[0]}")
    print(f"  Body: {pairing.body_fonts[0]}")
    
    # Test type scale
    scale = engine.get_type_scale(16, "golden_ratio")
    print(f"\nType Scale (Golden Ratio):")
    for name, size in sorted(scale.items(), key=lambda x: x[1]):
        print(f"  {name}: {size}px")
    
    # Test optical tracking
    for size in [14, 24, 48, 96]:
        tracking = engine.calculate_optical_tracking(size, "mixed", "regular")
        print(f"  {size}px: {tracking:+.3f}em")
