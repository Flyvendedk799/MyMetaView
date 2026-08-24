"""
Brand extraction service for preview generation.

Extracts brand elements from websites:
- Logo (favicon or header logo) with AI-powered detection
- Primary brand colors
- Hero/featured images
- Brand name and tagline

ENHANCED with AI Logo Detection:
- Uses GPT-4o vision to locate logos in screenshots
- Falls back to HTML-based extraction
- Validates logo quality and prominence
"""
import base64
import colorsys
import json
import logging
import re
from collections import Counter
from io import BytesIO
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, urljoin
import requests
from PIL import Image
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# AI Logo Detection Integration
try:
    from openai import OpenAI
    from backend.core.config import settings
    AI_LOGO_DETECTION_AVAILABLE = True
except ImportError:
    AI_LOGO_DETECTION_AVAILABLE = False
    logger.warning("OpenAI not available for AI logo detection")

# PHASE 2: Error Recovery Integration
try:
    from backend.services.error_recovery import (
        classify_error,
        get_recovery_action,
        ErrorType,
        RecoveryAction,
        graceful_extract
    )
    ERROR_RECOVERY_AVAILABLE = True
except ImportError:
    ERROR_RECOVERY_AVAILABLE = False


# =============================================================================
# AI-POWERED LOGO DETECTION
# =============================================================================

# Logo detection prompt - loaded from backend/prompts/brand_extraction/system_brand.txt
def _get_logo_detection_prompt() -> str:
    try:
        from backend.prompts.loader import get_brand_extraction_prompt
        prompt = get_brand_extraction_prompt()
        if prompt:
            return prompt
    except ImportError:
        pass
    return "Analyze this webpage screenshot and locate the brand/company logo. Output valid JSON with logos_found and best_logo_index."


def extract_logo_with_ai(screenshot_bytes: bytes, url: str = "") -> Optional[Dict[str, Any]]:
    """
    Use GPT-4o vision to detect and locate logos in a screenshot.
    
    This is the primary logo detection method, providing accurate bounding boxes
    for logo extraction from screenshots.
    
    Args:
        screenshot_bytes: Screenshot bytes
        url: URL for context
        
    Returns:
        Dict with logo info including bbox, or None if detection fails
    """
    if not AI_LOGO_DETECTION_AVAILABLE:
        logger.debug("AI logo detection not available")
        return None
    
    logger.info(f"🤖 Running AI logo detection for: {url[:50] if url else 'unknown'}...")
    
    try:
        # Prepare image for API
        image = Image.open(BytesIO(screenshot_bytes))
        original_width, original_height = image.size
        
        # Resize if too large (max 2048px)
        max_dim = 2048
        if image.width > max_dim or image.height > max_dim:
            ratio = min(max_dim / image.width, max_dim / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed
        if image.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            if image.mode in ('RGBA', 'LA'):
                background.paste(image, mask=image.split()[-1])
            image = background
        
        # Encode to base64
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Call GPT-4o vision
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.reasoning_client import get_client

        spec = spec_for("logo_detection")
        client = get_client(timeout=spec.timeout_s)
        
        response = client.chat.completions.create(
            **spec.request_kwargs_without_tokens(),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at detecting brand logos in webpage screenshots. Output valid JSON only."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _get_logo_detection_prompt()},
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
            max_tokens=1000,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        # Validate result
        logos_found = result.get("logos_found", [])
        best_index = result.get("best_logo_index", -1)
        
        if not logos_found or best_index < 0 or best_index >= len(logos_found):
            logger.info("🤖 AI logo detection: No suitable logo found")
            return None
        
        best_logo = logos_found[best_index]
        
        # Validate confidence
        if best_logo.get("confidence", 0) < 0.6:
            logger.info(f"🤖 AI logo detection: Logo confidence too low ({best_logo.get('confidence', 0):.2f})")
            return None
        
        logger.info(
            f"✅ AI logo detected: {best_logo.get('location', 'unknown')} "
            f"({best_logo.get('type', 'unknown')}) "
            f"confidence={best_logo.get('confidence', 0):.2f}"
        )
        
        return {
            "bbox": best_logo.get("bbox"),
            "confidence": best_logo.get("confidence"),
            "location": best_logo.get("location"),
            "type": best_logo.get("type"),
            "description": best_logo.get("description"),
            "original_width": original_width,
            "original_height": original_height
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"🤖 AI logo detection: JSON parse error: {e}")
        return None
    except Exception as e:
        logger.warning(f"🤖 AI logo detection failed: {e}")
        return None


def crop_logo_from_screenshot(screenshot_bytes: bytes, logo_info: Dict[str, Any]) -> Optional[str]:
    """
    Crop the logo from screenshot using AI-detected bounding box.
    
    Args:
        screenshot_bytes: Screenshot bytes
        logo_info: Logo info dict with bbox from AI detection
        
    Returns:
        Base64-encoded logo image or None
    """
    try:
        bbox = logo_info.get("bbox")
        if not bbox:
            return None
        
        image = Image.open(BytesIO(screenshot_bytes))
        width, height = image.size
        
        # Convert normalized coordinates to pixels
        x = int(bbox.get("x", 0) * width)
        y = int(bbox.get("y", 0) * height)
        w = int(bbox.get("width", 0.1) * width)
        h = int(bbox.get("height", 0.1) * height)
        
        # Add small padding (5% of dimensions)
        padding_x = int(w * 0.05)
        padding_y = int(h * 0.05)
        
        # Calculate crop box with padding
        left = max(0, x - padding_x)
        top = max(0, y - padding_y)
        right = min(width, x + w + padding_x)
        bottom = min(height, y + h + padding_y)
        
        # Validate crop dimensions
        if right <= left or bottom <= top:
            logger.warning("Invalid crop dimensions for logo")
            return None
        
        crop_width = right - left
        crop_height = bottom - top
        
        # Minimum size validation
        if crop_width < 30 or crop_height < 30:
            logger.warning(f"Logo crop too small: {crop_width}x{crop_height}")
            return None
        
        # Crop the logo
        logo_image = image.crop((left, top, right, bottom))
        if max(logo_image.size) > _LOGO_MAX_DIM:
            ratio = _LOGO_MAX_DIM / max(logo_image.size)
            logo_image = logo_image.resize(
                (max(1, int(logo_image.width * ratio)), max(1, int(logo_image.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        
        # Convert to RGBA to handle transparency
        if logo_image.mode != 'RGBA':
            logo_image = logo_image.convert('RGBA')
        
        # Save as PNG to preserve quality
        buffer = BytesIO()
        logo_image.save(buffer, format='PNG', optimize=True)
        logo_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        logger.info(f"✅ Logo cropped successfully: {crop_width}x{crop_height}px")
        return logo_base64
        
    except Exception as e:
        logger.warning(f"Failed to crop logo from screenshot: {e}")
        return None


# Some CDNs (Cloudflare, Akamai) refuse the default python-requests UA with a
# 403, which silently downgraded us to the favicon fallback on those sites.
_IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
}

# Logos are corner marks, not hero art: anything past this edge length only
# bloats the Redis cache and the demo payload without adding a pixel on screen.
_LOGO_MAX_DIM = 512
_MAX_LOGO_DOWNLOAD_BYTES = 5 * 1024 * 1024  # matches the brand-logo upload cap


def _looks_like_svg(content: bytes, content_type: str = "") -> bool:
    if "svg" in (content_type or "").lower():
        return True
    head = content[:512].lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)


def _trim_logo_padding(img: Image.Image) -> Image.Image:
    """Trim fully transparent margins so the logo renders at its optical size.

    Exported logo files often ship inside a much larger transparent canvas;
    untrimmed, the visible mark shrinks to a fraction of the height the card
    gives it. Trims only via the alpha channel — never content — and keeps a
    small breathing margin.
    """
    try:
        if img.mode != 'RGBA':
            return img
        bbox = img.split()[-1].getbbox()
        if not bbox:
            return img  # fully transparent; caller's validation handles it
        left, top, right, bottom = bbox
        if (right - left) >= img.width * 0.9 and (bottom - top) >= img.height * 0.9:
            return img  # nothing meaningful to trim
        pad_x = max(2, (right - left) // 25)
        pad_y = max(2, (bottom - top) // 25)
        return img.crop((
            max(0, left - pad_x), max(0, top - pad_y),
            min(img.width, right + pad_x), min(img.height, bottom + pad_y),
        ))
    except Exception:
        return img


def _process_logo_image(img: Image.Image) -> str:
    """Normalize a validated logo to trimmed, bounded, base64 PNG."""
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    img = _trim_logo_padding(img)
    if max(img.size) > _LOGO_MAX_DIM:
        ratio = _LOGO_MAX_DIM / max(img.size)
        img = img.resize(
            (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buffered = BytesIO()
    img.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def _download_and_validate_image(img_url: str, min_width: int = 32, min_height: int = 32) -> Optional[str]:
    """Download image, validate dimensions, return base64 PNG or None."""
    try:
        response = requests.get(img_url, timeout=5, headers=_IMAGE_REQUEST_HEADERS)
        if response.status_code != 200 or not response.content:
            return None
        if len(response.content) > _MAX_LOGO_DOWNLOAD_BYTES:
            return None
        if _looks_like_svg(response.content, response.headers.get("content-type", "")):
            # PIL can't rasterize SVG and the frontend renders logo_base64 as
            # PNG; skip so the next candidate (usually a raster icon) wins.
            logger.debug(f"Skipping SVG logo candidate (no rasterizer): {img_url}")
            return None
        img = Image.open(BytesIO(response.content))
        img.load()
        if img.width < min_width or img.height < min_height:
            return None
        # Filter decorative images (1x1 pixels, tracking pixels)
        if img.width <= 2 or img.height <= 2:
            return None
        return _process_logo_image(img)
    except Exception:
        return None


def _candidate_img_srcs(img_tag) -> List[str]:
    """All plausible source URLs of an <img>, lazy-load attributes included.

    Lazy-loaded sites put a 1px placeholder (or nothing) in `src` and the real
    file in data-src/data-lazy-src/srcset; reading only `src` made us fall
    through to the favicon on exactly the sites with the nicest logos.
    """
    srcs: List[str] = []
    for attr in ('src', 'data-src', 'data-lazy-src', 'data-original'):
        value = (img_tag.get(attr) or "").strip()
        if value and not value.startswith('data:'):
            srcs.append(value)
    srcset = img_tag.get('srcset') or img_tag.get('data-srcset') or ""
    for candidate in srcset.split(','):
        value = candidate.strip().split(' ')[0]
        if value and not value.startswith('data:'):
            srcs.append(value)
            break  # first srcset entry is enough
    # De-duplicate, preserving order
    return list(dict.fromkeys(srcs))


def extract_brand_logo(html_content: str, url: str, screenshot_bytes: bytes) -> Optional[str]:
    """
    Extract brand logo from website.

    Priority order (HTML-first for speed, AI as fallback):
    1. apple-touch-icon / high-res favicon (fast, reliable)
    2. <img> in <header>/<nav> with logo-related attributes
    3. AI-powered logo detection from screenshot
    4. Standard favicon
    5. Screenshot crop fallback

    Args:
        html_content: HTML content of the page
        url: URL of the website
        screenshot_bytes: Screenshot for AI logo detection

    Returns:
        Base64-encoded logo image or None
    """
    logger.info(f"Starting logo extraction for: {url}")

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # =================================================================
        # PRIORITY 1: apple-touch-icon and high-res icons (best quality, no AI needed)
        # =================================================================
        highres_icon_selectors = [
            'link[rel="apple-touch-icon"]',
            'link[rel="apple-touch-icon-precomposed"]',
            'link[rel="icon"][sizes="192x192"]',
            'link[rel="icon"][sizes="180x180"]',
            'link[rel="icon"][sizes="128x128"]',
            'link[rel="icon"][sizes="96x96"]',
        ]

        for selector in highres_icon_selectors:
            icon = soup.select_one(selector)
            if icon and icon.get('href'):
                icon_url = urljoin(base_url, icon['href'])
                logo_base64 = _download_and_validate_image(icon_url, min_width=32, min_height=32)
                if logo_base64:
                    logger.info(f"Logo extracted from high-res icon: {selector}")
                    return logo_base64

        # =================================================================
        # PRIORITY 2: <img> in header/nav elements
        # =================================================================
        logo_selectors = [
            'header img[class*="logo" i]',
            'nav img[class*="logo" i]',
            'header img[alt*="logo" i]',
            'nav img[alt*="logo" i]',
            'img[class*="logo" i]',
            'img[id*="logo" i]',
            'img[alt*="logo" i]',
            'a[class*="logo" i] img',
            'header img',
            'nav img',
            '.navbar img',
            '.header img',
            '[class*="brand"] img',
            'a[href="/"] img',
            '.site-logo img',
            '#logo img',
        ]

        for selector in logo_selectors:
            # A selector's first hit can be a broken or placeholder image;
            # trying the next couple of matches beats skipping to the favicon.
            for logo_img in soup.select(selector)[:3]:
                for src in _candidate_img_srcs(logo_img):
                    logo_url = urljoin(base_url, src)
                    logo_base64 = _download_and_validate_image(logo_url, min_width=32, min_height=32)
                    if logo_base64:
                        logger.info(f"Logo extracted from HTML: {selector}")
                        return logo_base64

        # =================================================================
        # PRIORITY 3: AI-Powered Logo Detection (fallback for complex pages)
        # =================================================================
        if screenshot_bytes and AI_LOGO_DETECTION_AVAILABLE:
            logo_info = extract_logo_with_ai(screenshot_bytes, url)
            if logo_info:
                logo_base64 = crop_logo_from_screenshot(screenshot_bytes, logo_info)
                if logo_base64:
                    logger.info(f"Logo extracted via AI detection: {logo_info.get('location', 'unknown')}")
                    return logo_base64

        # =================================================================
        # PRIORITY 4: Standard favicon
        # =================================================================
        favicon_selectors = [
            'link[rel="icon"][sizes]',
            'link[rel="icon"]',
            'link[rel="shortcut icon"]',
        ]

        for selector in favicon_selectors:
            favicon = soup.select_one(selector)
            if favicon and favicon.get('href'):
                favicon_url = urljoin(base_url, favicon['href'])
                logo_base64 = _download_and_validate_image(favicon_url, min_width=32, min_height=32)
                if logo_base64:
                    logger.info(f"Logo extracted from favicon: {selector}")
                    return logo_base64

        # Try default favicon.ico
        default_favicon = f"{base_url}/favicon.ico"
        logo_base64 = _download_and_validate_image(default_favicon, min_width=16, min_height=16)
        if logo_base64:
            logger.info("Logo extracted from default favicon.ico")
            return logo_base64

        # =================================================================
        # PRIORITY 5: Screenshot crop fallback
        # =================================================================
        logo_base64 = _extract_logo_from_screenshot(screenshot_bytes)
        if logo_base64:
            logger.info("Logo extracted from screenshot (fallback crop)")
            return logo_base64

        logger.warning(f"No suitable logo found for: {url}")
        return None

    except Exception as e:
        logger.error(f"Logo extraction failed for {url}: {e}", exc_info=True)
        return None


def _extract_logo_from_screenshot(screenshot_bytes: bytes) -> Optional[str]:
    """
    Fallback method: Extract logo from screenshot by analyzing top-left region.
    
    This is a simple heuristic that crops the top-left region where logos typically appear.
    
    Args:
        screenshot_bytes: Screenshot bytes
        
    Returns:
        Base64-encoded logo image or None
    """
    try:
        screenshot = Image.open(BytesIO(screenshot_bytes)).convert('RGB')
        width, height = screenshot.size
        
        # Crop top-left region (typically where logos appear)
        # Use 20% of width and 15% of height
        crop_width = int(width * 0.2)
        crop_height = int(height * 0.15)
        
        logo_region = screenshot.crop((0, 0, crop_width, crop_height))

        # Check if region has meaningful content (not just background): a crop
        # of empty header shipped as "the logo" is worse than no logo at all —
        # it reaches the demo UI and the card renderer as a blank smudge.
        pixels = list(logo_region.resize((24, 24)).getdata())
        if len(pixels) < 100:  # Too small
            return None
        def _channel_variance(values):
            mean = sum(values) / len(values)
            return sum((v - mean) ** 2 for v in values) / len(values)
        spread = sum(
            _channel_variance([p[channel] for p in pixels]) for channel in range(3)
        )
        if spread < 80:
            logger.debug("  Screenshot logo extraction: region is near-uniform, skipping")
            return None

        logo_base64 = _process_logo_image(logo_region)

        logger.debug(f"  Screenshot logo extraction: cropped {crop_width}x{crop_height} from top-left")
        return logo_base64
        
    except Exception as e:
        logger.debug(f"  Screenshot logo extraction failed: {e}")
        return None


def fetch_uploaded_logo(logo_url: str) -> Optional[Dict[str, Optional[str]]]:
    """Download the customer's uploaded brand logo (Brand & identity page).

    Returns {"data_uri": ..., "png_base64": ...} or None if unreachable.
    `data_uri` keeps the original format (SVG included — the card renderer is
    real Chromium and draws it crisply); `png_base64` is the normalized raster
    for consumers that require PNG, and is None for SVG uploads.
    """
    if not logo_url:
        return None
    try:
        response = requests.get(logo_url, timeout=8, headers=_IMAGE_REQUEST_HEADERS)
        if response.status_code != 200 or not response.content:
            logger.warning(f"Uploaded logo unreachable ({response.status_code}): {logo_url}")
            return None
        if len(response.content) > _MAX_LOGO_DOWNLOAD_BYTES:
            logger.warning(f"Uploaded logo too large, ignoring: {logo_url}")
            return None

        if _looks_like_svg(response.content, response.headers.get("content-type", "")):
            data_uri = "data:image/svg+xml;base64," + base64.b64encode(response.content).decode('utf-8')
            return {"data_uri": data_uri, "png_base64": None}

        img = Image.open(BytesIO(response.content))
        img.load()
        if img.width < 8 or img.height < 8:
            return None
        png_base64 = _process_logo_image(img)
        return {"data_uri": f"data:image/png;base64,{png_base64}", "png_base64": png_base64}
    except Exception as e:
        logger.warning(f"Failed to fetch uploaded logo {logo_url}: {e}")
        return None


def _process_hero_image(img: Image.Image) -> str:
    """Resize and encode a hero image to base64 JPEG."""
    if img.width > 1200:
        ratio = 1200 / img.width
        new_size = (1200, int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    if img.mode in ('RGBA', 'LA', 'P'):
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode in ('RGBA', 'LA'):
            rgb_img.paste(img, mask=img.split()[-1])
        img = rgb_img
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def extract_hero_image(html_content: str, url: str) -> Optional[str]:
    """
    Extract hero/featured image from website.

    Priority order:
    1. og:image meta tag
    2. twitter:image meta tag
    3. Large images in hero/header sections
    4. CSS background-image on hero sections
    5. Largest non-decorative image in first 50% of HTML

    Args:
        html_content: HTML content of the page
        url: URL of the website

    Returns:
        Base64-encoded hero image or None
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # =================================================================
        # PRIORITY 1: og:image meta tag
        # =================================================================
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = urljoin(base_url, og_image['content'])
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    if img.width >= 200 and img.height >= 100:
                        logger.info("Extracted hero image from og:image")
                        return _process_hero_image(img)
            except Exception as e:
                logger.debug(f"Failed to download og:image: {e}")

        # =================================================================
        # PRIORITY 2: twitter:image meta tag
        # =================================================================
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'}) or soup.find('meta', property='twitter:image')
        if twitter_image and twitter_image.get('content'):
            image_url = urljoin(base_url, twitter_image['content'])
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    if img.width >= 200 and img.height >= 100:
                        logger.info("Extracted hero image from twitter:image")
                        return _process_hero_image(img)
            except Exception as e:
                logger.debug(f"Failed to download twitter:image: {e}")

        # =================================================================
        # PRIORITY 3: Hero section images
        # =================================================================
        hero_selectors = [
            '.hero img',
            '.banner img',
            'header img[class*="hero" i]',
            'section[class*="hero" i] img',
            '.jumbotron img',
            '[class*="hero-image"] img',
            '[class*="featured-image"] img',
            'main > section:first-child img',
        ]

        for selector in hero_selectors:
            hero_img = soup.select_one(selector)
            if hero_img and hero_img.get('src'):
                image_url = urljoin(base_url, hero_img['src'])
                try:
                    response = requests.get(image_url, timeout=5)
                    if response.status_code == 200:
                        img = Image.open(BytesIO(response.content))
                        if img.width >= 400 and img.height >= 200:
                            logger.info(f"Extracted hero image from: {selector}")
                            return _process_hero_image(img)
                except Exception:
                    continue

        # =================================================================
        # PRIORITY 4: CSS background-image on hero sections
        # =================================================================
        hero_bg_selectors = [
            '[class*="hero"]',
            '[class*="banner"]',
            '[class*="jumbotron"]',
            'header',
        ]
        for selector in hero_bg_selectors:
            element = soup.select_one(selector)
            if element:
                style = element.get('style', '')
                bg_match = re.search(r'background-image:\s*url\(["\']?([^"\')+]+)["\']?\)', style)
                if bg_match:
                    bg_url = urljoin(base_url, bg_match.group(1))
                    try:
                        response = requests.get(bg_url, timeout=5)
                        if response.status_code == 200:
                            img = Image.open(BytesIO(response.content))
                            if img.width >= 400:
                                logger.info(f"Extracted hero image from CSS background: {selector}")
                                return _process_hero_image(img)
                    except Exception:
                        continue

        # =================================================================
        # PRIORITY 5: Largest non-decorative image in first half of HTML
        # =================================================================
        all_images = soup.find_all('img', src=True)
        # Only consider first half of images (above the fold)
        half_count = max(1, len(all_images) // 2)
        candidates = []
        for img_tag in all_images[:half_count]:
            src = img_tag.get('src', '')
            # Skip decorative/tiny images
            if any(skip in src.lower() for skip in ['pixel', 'spacer', 'blank', 'tracking', '1x1', 'data:image/gif']):
                continue
            # Skip images with decorative role
            if img_tag.get('role') == 'presentation' or img_tag.get('aria-hidden') == 'true':
                continue
            # Check explicit dimensions
            width_attr = img_tag.get('width', '')
            height_attr = img_tag.get('height', '')
            try:
                w = int(width_attr) if width_attr and width_attr.isdigit() else 0
                h = int(height_attr) if height_attr and height_attr.isdigit() else 0
                if w > 0 and h > 0 and (w < 50 or h < 50):
                    continue
                candidates.append((img_tag, w * h if w > 0 and h > 0 else 0))
            except (ValueError, TypeError):
                candidates.append((img_tag, 0))

        # Sort by declared area (largest first), then try downloading
        candidates.sort(key=lambda x: x[1], reverse=True)
        for img_tag, _ in candidates[:5]:
            image_url = urljoin(base_url, img_tag['src'])
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    # Must be at least 400px wide and have reasonable aspect ratio
                    if img.width >= 400 and 0.3 < (img.height / img.width) < 3.0:
                        logger.info(f"Extracted hero image from largest page image")
                        return _process_hero_image(img)
            except Exception:
                continue

        logger.info("No suitable hero image found")
        return None

    except Exception as e:
        logger.error(f"Hero image extraction failed: {e}", exc_info=True)
        return None


def _calculate_luminance(rgb: tuple) -> float:
    """Calculate relative luminance of an RGB color (0-1 scale)."""
    def adjust(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [adjust(c) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _get_contrast_ratio(color1: tuple, color2: tuple) -> float:
    """Calculate WCAG contrast ratio between two RGB colors."""
    l1 = _calculate_luminance(color1)
    l2 = _calculate_luminance(color2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _colors_are_too_similar(colors: list, min_contrast: float = 2.0) -> bool:
    """Check if all extracted colors are too similar (low contrast potential)."""
    if len(colors) < 2:
        return True
    
    # Check all pairs for sufficient contrast
    for i, c1 in enumerate(colors):
        for c2 in colors[i+1:]:
            if _get_contrast_ratio(c1, c2) >= min_contrast:
                return False  # Found at least one good contrast pair
    return True  # All colors are too similar


def _darken_tuple(rgb: tuple, factor: float = 0.2) -> tuple:
    """Darken an RGB color tuple by a factor."""
    return tuple(max(0, int(c * (1 - factor))) for c in rgb)


def _extract_colors_from_image(image_bytes: bytes) -> Dict[str, str]:
    """
    Extract dominant colors from an image using PIL.
    
    ENHANCED: Now validates color contrast and uses fallbacks
    when all extracted colors are too similar (e.g., all white).
    
    Args:
        image_bytes: Image bytes
        
    Returns:
        Dict with primary, secondary, accent colors with guaranteed contrast
    """
    # Fallback colors with good contrast
    FALLBACK_COLORS = {
        "primary_color": "#1E293B",  # Dark slate (good for text)
        "secondary_color": "#FFFFFF",  # White (good for backgrounds)
        "accent_color": "#F97316"  # Orange (brand accent)
    }
    
    try:
        img = Image.open(BytesIO(image_bytes))
        # Resize for faster processing - larger sample for better accuracy
        img = img.resize((200, 200), Image.Resampling.LANCZOS)

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Get colors - sample more densely for better representation
        # Focus on upper 60% where brand colors tend to be (header, nav, hero)
        pixels = []
        width, height = img.size
        brand_zone_height = int(height * 0.6)
        for y in range(0, brand_zone_height, 3):
            for x in range(0, width, 3):
                pixels.append(img.getpixel((x, y)))
        # Also sample the rest at lower density
        for y in range(brand_zone_height, height, 6):
            for x in range(0, width, 6):
                pixels.append(img.getpixel((x, y)))
        
        # Get most common colors - get more to find contrasting ones
        color_counts = Counter(pixels)
        top_colors = color_counts.most_common(10)  # Get more colors to find contrast
        
        def rgb_to_hex(rgb):
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".upper()
        
        # Get the raw top 3 colors
        raw_colors = [c[0] for c in top_colors[:3]] if len(top_colors) >= 3 else []
        
        # Check if extracted colors have sufficient contrast
        if len(raw_colors) < 2 or _colors_are_too_similar(raw_colors):
            logger.warning(f"Extracted colors lack contrast: {[rgb_to_hex(c) for c in raw_colors]}, using enhanced extraction")
            
            # Try to find contrasting colors from the extended palette
            all_colors = [c[0] for c in top_colors]
            
            # Separate into light and dark colors
            light_colors = [c for c in all_colors if _calculate_luminance(c) > 0.5]
            dark_colors = [c for c in all_colors if _calculate_luminance(c) <= 0.5]
            
            if dark_colors and light_colors:
                # IMPORTANT: In the preview system, primary_color is used for BACKGROUNDS
                # We need to determine if this is a light or dark themed site
                
                # Calculate if the site is predominantly light or dark
                light_pixel_count = sum(1 for c in all_colors if _calculate_luminance(c) > 0.5)
                total_colors = len(all_colors)
                is_light_themed = light_pixel_count > total_colors * 0.6  # 60%+ light = light theme
                
                dark_colors.sort(key=lambda c: _calculate_luminance(c))
                light_colors.sort(key=lambda c: _calculate_luminance(c), reverse=True)
                
                if is_light_themed:
                    # LIGHT THEMED SITE: Use vibrant gradient for visual interest
                    # Primary should be a rich gradient-friendly color, not pure white
                    
                    # Find the most saturated/colorful color from the palette
                    def get_saturation(rgb):
                        max_c = max(rgb)
                        min_c = min(rgb)
                        if max_c == 0:
                            return 0
                        return (max_c - min_c) / max_c
                    
                    colorful_colors = sorted(all_colors, key=get_saturation, reverse=True)
                    
                    # Use a softer dark gradient for light-themed sites (not pitch black)
                    # This creates a visually appealing preview even for white sites
                    # FIXED: Use even lighter slate colors to avoid "too black" look
                    primary = (71, 85, 105)  # Slate-600 - much softer, professional
                    secondary = (51, 65, 85)  # Slate-700 - softer than before
                    
                    # Try to find a brand color for accent (must be colorful, not dark)
                    accent = None
                    for c in colorful_colors:
                        sat = get_saturation(c)
                        lum = _calculate_luminance(c)
                        # Must have color AND not be too dark (luminance > 0.3)
                        if sat > 0.3 and lum > 0.3:
                            accent = c
                            break
                    
                    # Fallback to vibrant orange if no colorful accent found
                    if not accent:
                        accent = (249, 115, 22)  # Orange-500 - vibrant and visible
                    
                    colors = {
                        "primary_color": rgb_to_hex(primary),
                        "secondary_color": rgb_to_hex(secondary),
                        "accent_color": rgb_to_hex(accent)
                    }
                    logger.info(f"Light-themed site: using dark gradient for visual appeal: {colors}")
                    return colors
                else:
                    # DARK THEMED SITE: Use the actual dark colors from the site
                    primary = dark_colors[0]
                    secondary = dark_colors[1] if len(dark_colors) > 1 else _darken_tuple(primary, 0.2)
                    
                    # Find an accent color
                    accent = None
                    for c in all_colors:
                        if c != primary and c != secondary:
                            if _get_contrast_ratio(c, primary) >= 3.0:
                                accent = c
                                break
                    
                    if not accent:
                        accent = (251, 191, 36)  # Amber fallback for dark themes
                    
                    colors = {
                        "primary_color": rgb_to_hex(primary),
                        "secondary_color": rgb_to_hex(secondary),
                        "accent_color": rgb_to_hex(accent)
                    }
                    logger.info(f"Dark-themed site: using extracted dark colors: {colors}")
                    return colors
            else:
                # No dark/light separation possible - all colors are same luminance
                # Use professional gradient fallback
                if light_colors:
                    # All light colors - use softer dark gradient (not pitch black)
                    return {
                        "primary_color": "#475569",  # Slate-600 - much softer, professional
                        "secondary_color": "#334155",  # Slate-700 - softer than before
                        "accent_color": "#F97316"  # Orange accent - vibrant
                    }
                elif dark_colors:
                    # All dark colors - use extracted dark with amber accent
                    return {
                        "primary_color": rgb_to_hex(dark_colors[0]),
                        "secondary_color": "#0F172A",  # Slate-900
                        "accent_color": "#FBBF24"  # Amber accent
                    }
                else:
                    return FALLBACK_COLORS
        
        # Original colors have sufficient contrast - use them
        primary = top_colors[0][0] if top_colors else (37, 99, 235)
        secondary = top_colors[1][0] if len(top_colors) > 1 else (30, 64, 175)
        accent = top_colors[2][0] if len(top_colors) > 2 else (245, 158, 11)

        # If primary is near-white (luminance > 0.9), swap with secondary or use dark gradient
        # White backgrounds make terrible gradient primaries
        if _calculate_luminance(primary) > 0.9:
            if _calculate_luminance(secondary) < 0.7:
                primary, secondary = secondary, primary  # Swap
                logger.info(f"Swapped near-white primary with secondary for better gradients")
            else:
                # Both are light - fall back to professional dark gradient
                primary = (71, 85, 105)   # Slate-600
                secondary = (51, 65, 85)   # Slate-700
                logger.info(f"Both colors near-white, using slate gradient fallback")

        # Ensure primary and secondary are sufficiently different
        # If too similar, derive secondary by darkening primary
        if _get_contrast_ratio(primary, secondary) < 1.5:
            # Shift hue by ~30 degrees in HSV space
            h, s, v = colorsys.rgb_to_hsv(primary[0]/255, primary[1]/255, primary[2]/255)
            h2 = (h + 0.08) % 1.0  # ~30 degree shift
            v2 = max(0.1, v * 0.7)  # Darken
            sr, sg, sb = colorsys.hsv_to_rgb(h2, min(1, s * 1.2), v2)
            secondary = (int(sr * 255), int(sg * 255), int(sb * 255))
            logger.info(f"Derived secondary from primary via hue shift: {rgb_to_hex(secondary)}")

        # Ensure accent is distinct from both primary and secondary
        if _get_contrast_ratio(accent, primary) < 2.0:
            # Use complementary hue for accent
            h, s, v = colorsys.rgb_to_hsv(primary[0]/255, primary[1]/255, primary[2]/255)
            h_accent = (h + 0.42) % 1.0  # ~150 degree shift (triadic)
            ar, ag, ab = colorsys.hsv_to_rgb(h_accent, max(0.6, s), max(0.6, v))
            accent = (int(ar * 255), int(ag * 255), int(ab * 255))
            logger.info(f"Derived accent via triadic hue shift: {rgb_to_hex(accent)}")

        colors = {
            "primary_color": rgb_to_hex(primary),
            "secondary_color": rgb_to_hex(secondary),
            "accent_color": rgb_to_hex(accent)
        }

        return colors
    except Exception as e:
        logger.warning(f"Failed to extract colors from image: {e}")
        return FALLBACK_COLORS


def extract_brand_colors(html_content: str, screenshot_bytes: Optional[bytes] = None) -> Dict[str, str]:
    """
    Extract brand colors from website with intelligent fallbacks.

    Priority:
    1. Screenshot color analysis (most accurate)
    2. CSS custom properties/variables
    3. Meta theme-color tag
    4. Branded MetaView fallback (not generic)

    Args:
        html_content: HTML content of the page
        screenshot_bytes: Optional screenshot for color extraction

    Returns:
        Dict with primary, secondary, accent colors
    """
    # Use branded MetaView fallback instead of generic blue
    colors = {
        "primary_color": "#F97316",  # MetaView orange (branded fallback)
        "secondary_color": "#1E293B",  # Dark gray
        "accent_color": "#FBBF24"  # MetaView amber
    }

    try:
        # Priority 1: Extract from screenshot if available (most accurate)
        if screenshot_bytes:
            palette = _extract_colors_from_image(screenshot_bytes)
            if palette:
                colors["primary_color"] = palette.get("primary_color", colors["primary_color"])
                colors["secondary_color"] = palette.get("secondary_color", colors["secondary_color"])
                colors["accent_color"] = palette.get("accent_color", colors["accent_color"])
                logger.info(f"Extracted colors from screenshot: {colors}")
                return colors

        # Priority 2: Parse CSS for common brand color patterns
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check for CSS variables (modern approach)
        style_tags = soup.find_all('style')
        for style in style_tags:
            if style.string:
                # Look for CSS custom properties (primary, brand, main colors)
                var_matches = re.findall(r'--(?:primary|brand|main)[-\w]*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|rgb\([^)]+\))', style.string)
                if var_matches:
                    colors["primary_color"] = var_matches[0]
                    logger.info(f"Extracted primary color from CSS variables: {colors['primary_color']}")
                    # Try to find secondary/accent in same style block
                    secondary_matches = re.findall(r'--(?:secondary|accent)[-\w]*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|rgb\([^)]+\))', style.string)
                    if len(secondary_matches) > 0:
                        colors["secondary_color"] = secondary_matches[0]
                    if len(secondary_matches) > 1:
                        colors["accent_color"] = secondary_matches[1]
                    break

        # Priority 3: Check meta theme-color tag
        theme_color = soup.find('meta', attrs={'name': 'theme-color'})
        if theme_color and theme_color.get('content'):
            theme_hex = theme_color['content'].strip()
            if re.match(r'^#[0-9a-fA-F]{6}$', theme_hex, re.IGNORECASE):
                colors["primary_color"] = theme_hex
                logger.info(f"Extracted primary color from theme-color meta: {colors['primary_color']}")

        return colors

    except Exception as e:
        logger.error(f"Color extraction failed: {e}", exc_info=True)
        # Return branded MetaView fallback, not generic blue
        return colors


def extract_brand_name(html_content: str, url: str) -> Optional[str]:
    """
    Extract brand name from website.

    Priority order:
    1. og:site_name meta tag
    2. <title> tag (cleaned)
    3. Domain name

    Args:
        html_content: HTML content of the page
        url: URL of the website

    Returns:
        Brand name or None
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Try og:site_name
        og_site_name = soup.find('meta', property='og:site_name')
        if og_site_name and og_site_name.get('content'):
            return og_site_name['content']

        # Try title tag (remove common suffixes)
        title = soup.find('title')
        if title and title.string:
            title_text = title.string.strip()
            # Remove common separators and everything after them
            for sep in [' | ', ' - ', ' – ', ' :: ']:
                if sep in title_text:
                    title_text = title_text.split(sep)[0]
                    break
            return title_text

        # Fallback: Use domain name
        domain = urlparse(url).netloc
        # Remove www. and TLD
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'\.[a-z]{2,}$', '', domain)
        return domain.capitalize()

    except Exception as e:
        logger.error(f"Brand name extraction failed: {e}", exc_info=True)
        return None


def extract_all_brand_elements(
    html_content: str,
    url: str,
    screenshot_bytes: bytes
) -> Dict[str, Any]:
    """
    Extract all brand elements from a website.

    Args:
        html_content: HTML content of the page
        url: URL of the website
        screenshot_bytes: Screenshot bytes

    Returns:
        Dict containing all brand elements
    """
    logger.info(f"Extracting brand elements for: {url}")

    brand_elements = {
        "brand_name": extract_brand_name(html_content, url),
        "logo_base64": extract_brand_logo(html_content, url, screenshot_bytes),
        "hero_image_base64": extract_hero_image(html_content, url),
        "colors": extract_brand_colors(html_content, screenshot_bytes),
    }

    logger.info(f"Brand extraction complete: name={brand_elements['brand_name']}, "
                f"has_logo={bool(brand_elements['logo_base64'])}, "
                f"has_hero={bool(brand_elements['hero_image_base64'])}")

    return brand_elements


def extract_colors_from_screenshot(screenshot_bytes: bytes) -> Optional[Dict[str, str]]:
    """Extract brand colors from a screenshot image only (no HTML needed)."""
    try:
        palette = _extract_colors_from_image(screenshot_bytes)
        if palette:
            return {
                "primary": palette.get("primary_color", "#2563EB"),
                "secondary": palette.get("secondary_color", "#1E40AF"),
                "accent": palette.get("accent_color", "#F59E0B"),
            }
    except Exception as e:
        logger.warning(f"extract_colors_from_screenshot failed: {e}")
    return None
