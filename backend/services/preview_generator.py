"""AI-powered preview generation service using OpenAI."""
import json
import re
import base64
from typing import Dict, Optional, List
import requests
from openai import OpenAI
from io import BytesIO
from PIL import Image
from backend.core.config import settings
from backend.schemas.brand import BrandSettings
from backend.services.metadata_extractor import extract_metadata_from_html
from backend.services.semantic_extractor import extract_semantic_structure
from backend.services.content_priority_extractor import extract_priority_content
from backend.services.playwright_screenshot import capture_screenshot


from backend.services.retry_utils import sync_retry
import requests.exceptions

@sync_retry(max_attempts=3, base_delay=1.0, retry_on=(requests.exceptions.RequestException,))
def fetch_page_html(url: str) -> str:
    """
    Fetch HTML content from a URL with retry logic.
    
    Args:
        url: The URL to fetch
        
    Returns:
        HTML content as string, or empty string on failure
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers, allow_redirects=True)  # Increased to 10s max
        response.raise_for_status()
        
        # Fix encoding issues: explicitly set UTF-8 encoding to prevent garbled characters
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        # Log error without exposing sensitive data
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching HTML from URL: {type(e).__name__}")
        return ""


def extract_basic_metadata(html: str) -> Dict[str, Optional[str]]:
    """
    Extract basic metadata from HTML using simple string operations.
    
    Args:
        html: HTML content as string
        
    Returns:
        Dictionary with title, description, og_image
    """
    metadata = {
        "title": None,
        "description": None,
        "og_image": None,
    }
    
    # Extract title from <title> tag
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()
    
    # Extract meta description
    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE
    )
    if desc_match:
        metadata["description"] = desc_match.group(1).strip()
    
    # Extract og:image
    og_image_match = re.search(
        r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE
    )
    if og_image_match:
        metadata["og_image"] = og_image_match.group(1).strip()
    
    return metadata


def _prepare_image_for_vision_api(screenshot_bytes: bytes) -> str:
    """
    Prepare screenshot image for OpenAI Vision API.
    Compresses and converts to base64.
    
    Args:
        screenshot_bytes: Raw PNG screenshot bytes
        
    Returns:
        Base64-encoded image string
    """
    try:
        # Open image
        image = Image.open(BytesIO(screenshot_bytes))
        
        # Convert to RGB if necessary (removes alpha channel)
        if image.mode in ('RGBA', 'LA', 'P'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = rgb_image
        
        # Resize if too large (max 2048px on longest side for API efficiency)
        max_size = 2048
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to base64
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return image_base64
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error preparing image for vision API: {type(e).__name__}")
        # Fallback: just encode original
        return base64.b64encode(screenshot_bytes).decode('utf-8')


def _analyze_screenshot_with_vision(screenshot_bytes: bytes, url: str, brand_settings: BrandSettings) -> Optional[Dict]:
    """
    Analyze screenshot using OpenAI Vision API to extract content based on visual design.
    
    Args:
        screenshot_bytes: Raw PNG screenshot bytes
        url: URL for context
        brand_settings: Brand settings for tone context
        
    Returns:
        Dictionary with extracted content or None if analysis fails
    """
    try:
        # Prepare image
        image_base64 = _prepare_image_for_vision_api(screenshot_bytes)
        
        # Derive brand tone
        brand_tone = _derive_brand_tone(brand_settings)
        
        # Parse URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path
        
        # Call Vision API
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("art_director")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "system",
                    "content": """You are a UI/UX expert and preview generation assistant. Analyze webpage screenshots to extract the most important content based on visual design hierarchy.

Your task is to identify what content is MOST VISUALLY PROMINENT and IMPORTANT on the page, then extract that content accurately.

Focus on:
- Visual hierarchy (largest, boldest, most prominent elements)
- Primary content (main headlines, titles, names)
- Key information (descriptions, bios, features, prices)
- Page type (profile, product, article, landing page)
- Important visual elements (images, icons, badges)

Return valid JSON only."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Analyze this webpage screenshot and extract the most important content based on visual design.

URL: {url}
Domain: {domain}
Path: {path}
Brand Tone: {brand_tone}

Extract:
1. Page type (profile, product, article, landing, unknown)
2. Primary title/name (the most prominent heading or name on the page)
3. Primary description (the main text content, bio, or description)
4. Key attributes (for profiles: name, competencies/skills, location, rating; for products: name, price, features; etc.)
5. Visual elements (important images, icons, badges visible)

Return as JSON:
{{
    "page_type": "profile|product|article|landing|unknown",
    "primary_title": "extracted title/name",
    "primary_description": "extracted description/bio",
    "key_attributes": {{
        "name": "...",
        "location": "...",
        "competencies": ["..."],
        "rating": "...",
        "price": "...",
        "features": ["..."]
    }},
    "visual_elements": ["description of important visual elements"],
    "confidence": 0.0-1.0
}}

Be accurate - extract exactly what you see, don't make assumptions."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"  # High detail for accurate analysis
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'^```\s*', '', content)
            content = re.sub(r'```\s*$', '', content)
        
        vision_data = json.loads(content)
        return vision_data
        
    except json.JSONDecodeError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error parsing vision API response: {type(e).__name__}")
        return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error calling vision API: {type(e).__name__}")
        return None


def generate_ai_preview(url: str, brand_settings: BrandSettings, html_content: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Generate AI-enhanced preview data using OpenAI Vision API to analyze visual design.
    
    Flow:
    1. Capture screenshot of viewport
    2. Send to OpenAI Vision API
    3. AI detects design and extracts important content
    4. Generate preview based on what AI sees
    5. Return to user
    
    Args:
        url: The URL to generate preview for
        brand_settings: User's brand settings for context
        html_content: Optional pre-fetched HTML content (if None, will fetch)
        
    Returns:
        Dictionary with title, description, keywords, tone, type, reasoning, image_url,
        variant_a, variant_b, variant_c, rewritten_text
    """
    # Step 1: Capture screenshot of viewport (PRIMARY METHOD)
    vision_analysis = None
    screenshot_bytes = None
    try:
        screenshot_bytes = capture_screenshot(url)
        vision_analysis = _analyze_screenshot_with_vision(screenshot_bytes, url, brand_settings)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Screenshot capture or vision analysis failed: {type(e).__name__}, falling back to HTML parsing")
    
    # Step 2: Fallback to HTML parsing if vision analysis failed
    if html_content is None:
        html_content = fetch_page_html(url)
    
    # Step 3: Extract metadata from HTML (as fallback/supplement)
    metadata = extract_metadata_from_html(html_content)
    semantic = extract_semantic_structure(html_content)
    priority_content = extract_priority_content(html_content, url)
    
    # Step 4: Use vision analysis if available, otherwise use HTML-based priority content
    if vision_analysis:
        # Vision analysis takes precedence - it sees what users actually see
        primary_title = vision_analysis.get('primary_title') or priority_content.get('primary_title')
        primary_description = vision_analysis.get('primary_description') or priority_content.get('primary_description')
        page_type = vision_analysis.get('page_type') or priority_content.get('page_type', 'unknown')
        key_attributes = vision_analysis.get('key_attributes', {})
        visual_elements = vision_analysis.get('visual_elements', [])
        confidence = vision_analysis.get('confidence', 0.0)
    else:
        # Fallback to HTML-based extraction
        primary_title = priority_content.get('primary_title')
        primary_description = priority_content.get('primary_description')
        page_type = priority_content.get('page_type', 'unknown')
        key_attributes = priority_content.get('key_attributes', {})
        visual_elements = priority_content.get('visual_elements', [])
        confidence = priority_content.get('content_priority_score', 0.0)
    
    # Step 5: Parse URL for domain and path
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path
    
    # Step 6: Derive brand tone from brand settings
    brand_tone = _derive_brand_tone(brand_settings)
    
    # Step 7: Prepare enhanced prompt for OpenAI with vision analysis (if available)
    analysis_source = "Vision API (screenshot analysis)" if vision_analysis else "HTML parsing"
    
    prompt = f"""You are a world-class preview generation assistant. Generate high-quality, accurate previews with multiple variants based on the analyzed content.

URL: {url}
Domain: {domain}
Path: {path}

CONTENT ANALYSIS ({analysis_source}):
- Detected Page Type: {page_type}
- Primary Title: {primary_title or 'Not found'}
- Primary Description: {primary_description or 'Not found'}
- Key Attributes: {key_attributes}
- Visual Elements: {', '.join(visual_elements[:3]) if visual_elements else 'None'}
- Confidence: {confidence:.2f}

SEMANTIC CONTENT ANALYSIS:
- Intent: {semantic.get('intent', 'unknown')}
- Sentiment: {semantic.get('sentiment', 'neutral')}
- Primary Content: {semantic.get('primary_content', '')[:500]}
- Topic Keywords: {', '.join(semantic.get('topic_keywords', [])[:10])}
- Named Entities: {', '.join(semantic.get('named_entities', [])[:5])}

EXTRACTED METADATA (fallback if priority content unavailable):
- Title (priority): {metadata.get('priority_title', 'Not found')}
  - OG Title: {metadata.get('og_title', 'Not found')}
  - HTML Title: {metadata.get('title', 'Not found')}
  - H1: {metadata.get('h1', 'Not found')}
- Description (priority): {metadata.get('priority_description', 'Not found')}
  - OG Description: {metadata.get('og_description', 'Not found')}
  - Meta Description: {metadata.get('description', 'Not found')}
  - Text Summary: {metadata.get('text_summary', 'Not found')[:200] if metadata.get('text_summary') else 'Not found'}
- OG Image: {metadata.get('og_image', 'Not found')}
- Canonical URL: {metadata.get('canonical_url', 'Not found')}

BRAND CONTEXT:
- Primary Color: {brand_settings.primary_color}
- Secondary Color: {brand_settings.secondary_color}
- Accent Color: {brand_settings.accent_color}
- Font Family: {brand_settings.font_family}
- Brand Tone: {brand_tone}

COMPETITOR-GRADE SEO GUIDELINES:
- Titles should be 50-60 characters, include primary keyword, be compelling
- Descriptions should be 150-160 characters, include call-to-action, be persuasive
- Keywords should be relevant, searchable, and match user intent
- Tone should match brand voice and content sentiment

YOUR TASK:
1. Generate MAIN preview (title, description) based on semantic analysis + metadata
2. Generate VARIANT A: More concise, action-oriented version
3. Generate VARIANT B: More descriptive, benefit-focused version
4. Generate VARIANT C: More emotional, story-driven version
5. Extract 5-7 relevant keywords from semantic analysis
6. Determine tone that matches brand voice and content sentiment
7. Predict type based on intent and content structure
8. Provide detailed reasoning for all choices

CRITICAL INSTRUCTIONS:
1. Use the Content Analysis above as PRIMARY SOURCE - it represents what users actually see on the page
2. For PROFILE pages: Focus on the person/expert name, their competencies/skills, location, and what they offer
3. For PRODUCT pages: Focus on product name, key features, and price
4. For ARTICLE pages: Focus on article title and main topic
5. NEVER use generic site-wide descriptions - always use the SPECIFIC content extracted
6. Each variant must be unique but accurate to the content
7. Variants should test different messaging angles (concise vs descriptive vs emotional)
8. Keep titles 50-60 chars, descriptions 150-160 chars
9. Keywords must be relevant and searchable
10. Tone must align with brand voice: {brand_tone}

Return your response as valid JSON with these exact keys:
{{
    "title": "string (main, 50-60 chars)",
    "description": "string (main, 150-160 chars)",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "tone": "professional | fun | bold | casual | technical | creative | neutral",
    "type": "product | blog | landing | unknown",
    "variant_a": {{
        "title": "string (concise, action-oriented, 50-60 chars)",
        "description": "string (150-160 chars)"
    }},
    "variant_b": {{
        "title": "string (descriptive, benefit-focused, 50-60 chars)",
        "description": "string (150-160 chars)"
    }},
    "variant_c": {{
        "title": "string (emotional, story-driven, 50-60 chars)",
        "description": "string (150-160 chars)"
    }},
    "reasoning": "detailed explanation of semantic analysis, variant strategies, and choices"
}}
"""
    
    # Step 4: Call OpenAI Chat Completions API
    try:
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("art_director")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "system",
                    "content": "You are a preview generation assistant. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500,
        )
        
        # Parse JSON response
        content = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'^```\s*', '', content)
            content = re.sub(r'```\s*$', '', content)
        
        ai_data = json.loads(content)
        
        # Step 8: Return AI result with variants
        # Use vision analysis or priority content as fallback
        final_title = ai_data.get("title") or primary_title or metadata.get("priority_title") or "Untitled Page"
        final_description = ai_data.get("description") or primary_description or metadata.get("priority_description")
        final_type = page_type if page_type != "unknown" else ai_data.get("type", "unknown")
        
        return {
            "title": final_title,
            "description": final_description,
            "keywords": ai_data.get("keywords", []),
            "tone": ai_data.get("tone", "neutral"),
            "type": final_type,
            "reasoning": ai_data.get("reasoning", f"Generated from {analysis_source}"),
            "variant_a": ai_data.get("variant_a", {}),
            "variant_b": ai_data.get("variant_b", {}),
            "variant_c": ai_data.get("variant_c", {}),
            "image_url": metadata.get("og_image") or "",  # Image will be handled by screenshot generation
        }
        
    except json.JSONDecodeError as e:
        # Log error without exposing sensitive data
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error parsing AI response: {type(e).__name__}")
        # Fallback to extracted metadata
        fallback_title = metadata.get("priority_title") or "Untitled Page"
        fallback_desc = metadata.get("priority_description") or ""
        return {
            "title": fallback_title,
            "description": fallback_desc,
            "keywords": semantic.get("topic_keywords", [])[:5],
            "tone": "neutral",
            "type": semantic.get("intent", "unknown").replace(" page", "").replace(" article", ""),
            "reasoning": f"Fallback: Used semantic intent '{semantic.get('intent')}' and extracted metadata",
            "variant_a": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "variant_b": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "variant_c": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "image_url": metadata.get("og_image") or "",
        }
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        # Fallback to extracted metadata
        fallback_title = metadata.get("priority_title") or "Untitled Page"
        fallback_desc = metadata.get("priority_description") or ""
        return {
            "title": fallback_title,
            "description": fallback_desc,
            "keywords": semantic.get("topic_keywords", [])[:5],
            "tone": "neutral",
            "type": semantic.get("intent", "unknown").replace(" page", "").replace(" article", ""),
            "reasoning": f"Error fallback: {str(e)}",
            "variant_a": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "variant_b": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "variant_c": {"title": fallback_title[:60], "description": fallback_desc[:160]},
            "image_url": metadata.get("og_image") or "",
        }


def _derive_brand_tone(brand_settings: BrandSettings) -> str:
    """
    Derive brand tone from brand settings (colors, font).
    
    Returns a tone description string.
    """
    # Analyze colors for tone hints
    primary = brand_settings.primary_color.lower()
    secondary = brand_settings.secondary_color.lower()
    accent = brand_settings.accent_color.lower()
    
    tone_hints = []
    
    # Color analysis
    if any(c in primary for c in ['ff', 'f00', 'e00']):  # Red tones
        tone_hints.append("bold")
    if any(c in primary for c in ['00f', '009', '006']):  # Blue tones
        tone_hints.append("professional")
    if any(c in primary for c in ['0f0', '0a0', '090']):  # Green tones
        tone_hints.append("natural")
    if any(c in accent for c in ['ff', 'f00']):  # Bright accents
        tone_hints.append("energetic")
    
    # Font analysis
    font_lower = brand_settings.font_family.lower()
    if 'serif' in font_lower or 'times' in font_lower:
        tone_hints.append("traditional")
    elif 'mono' in font_lower or 'code' in font_lower:
        tone_hints.append("technical")
    elif 'sans' in font_lower or 'inter' in font_lower or 'roboto' in font_lower:
        tone_hints.append("modern")
    
    # Default tone
    if not tone_hints:
        return "clean, modern, minimalistic"
    
    # Combine hints
    unique_hints = list(set(tone_hints))
    if len(unique_hints) == 1:
        return unique_hints[0]
    else:
        return ", ".join(unique_hints[:2])

