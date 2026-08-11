"""Brand tone rewriting service using OpenAI."""
import json
import re
from typing import Dict
from openai import OpenAI
from backend.core.config import settings
from backend.schemas.brand import BrandSettings


def rewrite_to_brand_voice(text: str, brand_settings: BrandSettings) -> str:
    """
    Rewrite text to match brand voice using GPT-4o.

    Args:
        text: Original text to rewrite
        brand_settings: Brand settings for voice context

    Returns:
        Rewritten text matching brand voice
    """
    if not text or len(text.strip()) < 10:
        return text

    # Derive brand voice from settings
    brand_voice = _derive_brand_voice(brand_settings)
    brand_context = _brand_context(brand_settings)

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""Rewrite the following text to match this brand voice: {brand_voice}
{brand_context}
Original text:
{text}

Requirements:
- Maintain the core meaning and key information
- Match the brand voice tone exactly
- Keep the same length (±10%)
- Do not add emojis unless the brand voice is playful/fun
- Ensure professional quality
- Never invent claims the original text doesn't make

Return ONLY the rewritten text, no explanations or markdown."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a brand voice rewriting assistant. Return only the rewritten text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=300,
        )
        
        rewritten = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        rewritten = re.sub(r'^```\s*', '', rewritten)
        rewritten = re.sub(r'```\s*$', '', rewritten)
        
        return rewritten
        
    except Exception as e:
        print(f"Error rewriting to brand voice: {e}")
        # Return original text on error
        return text


# The tone presets a user can pick on the Brand & identity page, spelled out for
# the model. Anything not listed here falls back to the colour/type heuristic.
VOICE_DESCRIPTIONS = {
    "professional": "professional, precise and trustworthy",
    "confident": "confident and direct — short sentences, no hedging",
    "friendly": "warm, plain-spoken and approachable",
    "technical": "technical and specific — concrete nouns, no marketing fluff",
    "playful": "playful and energetic, with a light touch of wit",
    "luxury": "understated and premium — restrained, elegant phrasing",
}


def _brand_context(brand_settings: BrandSettings) -> str:
    """Block of the user's own words about their brand, for the rewrite prompt.

    Empty when nothing has been filled in, which leaves the original behaviour
    (voice only) untouched.
    """
    lines = []
    name = (getattr(brand_settings, "brand_name", None) or "").strip()
    description = (getattr(brand_settings, "brand_description", None) or "").strip()
    audience = (getattr(brand_settings, "audience", None) or "").strip()
    if name:
        lines.append(f"Brand: {name}")
    if description:
        lines.append(f"What they do: {description}")
    if audience:
        lines.append(f"Written for: {audience}")
    if not lines:
        return ""
    return "\nContext about the brand (do not quote it verbatim):\n" + "\n".join(lines) + "\n"


def _derive_brand_voice(brand_settings: BrandSettings) -> str:
    """
    Derive brand voice description from brand settings.

    An explicitly chosen voice wins; "auto" (or an unknown value) falls back to
    inferring one from the brand's colours and type.

    Returns a voice description string.
    """
    chosen = (getattr(brand_settings, "voice", None) or "auto").strip().lower()
    if chosen in VOICE_DESCRIPTIONS:
        return VOICE_DESCRIPTIONS[chosen]

    # Analyze colors for voice hints
    primary = brand_settings.primary_color.lower()
    secondary = brand_settings.secondary_color.lower()
    accent = brand_settings.accent_color.lower()
    
    voice_hints = []
    
    # Color analysis
    if any(c in primary for c in ['ff', 'f00', 'e00']):  # Red tones
        voice_hints.append("bold and energetic")
    if any(c in primary for c in ['00f', '009', '006']):  # Blue tones
        voice_hints.append("professional and trustworthy")
    if any(c in primary for c in ['0f0', '0a0', '090']):  # Green tones
        voice_hints.append("natural and approachable")
    if any(c in accent for c in ['ff', 'f00']):  # Bright accents
        voice_hints.append("vibrant")
    
    # Font analysis
    font_lower = brand_settings.font_family.lower()
    if 'serif' in font_lower or 'times' in font_lower:
        voice_hints.append("traditional and authoritative")
    elif 'mono' in font_lower or 'code' in font_lower:
        voice_hints.append("technical and precise")
    elif 'sans' in font_lower or 'inter' in font_lower or 'roboto' in font_lower:
        voice_hints.append("modern and clean")
    
    # Default voice
    if not voice_hints:
        return "clean, modern, minimalistic"
    
    # Combine hints
    unique_hints = list(set(voice_hints))
    if len(unique_hints) == 1:
        return unique_hints[0]
    else:
        return ", ".join(unique_hints[:2])

