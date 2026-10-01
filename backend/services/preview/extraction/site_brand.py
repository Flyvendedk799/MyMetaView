""""Fill from my site": read a domain's brand off its home page.

Every account starts with MetaView's stock palette and no identity, and the
My Site tab asked customers to type in what their own site already says. This
runs the engine's own extraction against the domain's home page and returns
suggestions for the form. Nothing is saved — the user reviews and saves.

It prefers what the engine already learned: the domain brand cache holds the
palette sampled from a real screenshot during an earlier generation, which is a
better read than the HTML-only pass a web request can afford.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.services.preview.caching.layers import BrandCache, domain_of
from backend.services.preview.extraction.brand import SYNTHETIC_SLATE_PRIMARIES

logger = logging.getLogger(__name__)

# The separators sites put between name and strapline in <title>.
_TITLE_SPLIT = re.compile(r"\s+[|\-–—·:•]\s+")

_REAL_PALETTE_SOURCES = {"sampled", "derived", "brand_settings"}


class SiteUnreachable(Exception):
    """The home page could not be fetched (down, refused, or not HTML)."""


def detect_site_brand(
    domain_name: str,
    *,
    organization_id: int,
    upload_logo: bool = True,
) -> Dict[str, Any]:
    """Suggestions for the My Site form, read from ``https://<domain>/``."""
    from backend.services.preview.net import fetch

    url = f"https://{domain_name}/"
    domain = domain_of(url)
    cached = BrandCache.get(domain) if domain else None

    page = fetch(url, timeout=10.0)
    html = page.text if page.ok else ""
    if not html and not cached:
        raise SiteUnreachable(page.error or f"HTTP {page.status}")

    out: Dict[str, Any] = {"source_url": url}

    meta = _metadata(html)
    name = (cached or {}).get("brand_name") or _brand_name(html, url)
    if name:
        out["brand_name"] = name[:80]
    tagline = _tagline(meta.get("title"), name)
    if tagline:
        out["tagline"] = tagline
    description = meta.get("og_description") or meta.get("description")
    if description and len(description) >= 20:
        out["brand_description"] = description.strip()[:500]

    colors, source = _palette(cached, html)
    if colors:
        out.update(colors)
        out["palette_source"] = source

    logo_uri = (cached or {}).get("logo_data_uri") or _logo(html, url)
    if logo_uri and upload_logo:
        stored = _store_logo(logo_uri, organization_id)
        if stored:
            out["logo_url"] = stored
    return out


def _metadata(html: str) -> Dict[str, Optional[str]]:
    if not html:
        return {}
    try:
        from backend.services.metadata_extractor import extract_metadata_from_html

        return extract_metadata_from_html(html) or {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Metadata extraction failed: %s", exc)
        return {}


def _brand_name(html: str, url: str) -> Optional[str]:
    if not html:
        return None
    try:
        from backend.services.brand_extractor import extract_brand_name

        return (extract_brand_name(html, url) or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Brand name extraction failed: %s", exc)
        return None


def _tagline(title: Optional[str], name: Optional[str]) -> Optional[str]:
    """The strapline half of "Acme — Analytics without the setup"."""
    if not title:
        return None
    parts = [p.strip() for p in _TITLE_SPLIT.split(title) if p.strip()]
    if len(parts) < 2:
        return None
    lowered = (name or "").strip().lower()
    for part in parts:
        if lowered and (part.lower() == lowered or lowered in part.lower()):
            continue
        if 8 <= len(part) <= 120 and part.lower() not in {"home", "homepage", "welcome"}:
            return part
    return None


def _palette(cached: Optional[Dict[str, Any]], html: str):
    """A real palette, or nothing — never the sampler's synthetic slate."""
    if cached and cached.get("palette_source") in _REAL_PALETTE_SOURCES:
        colors = _clean_colors(cached.get("colors") or {})
        if colors:
            return colors, cached.get("palette_source")
    if not html:
        return {}, None
    try:
        from backend.services.brand_extractor import extract_brand_colors

        colors = _clean_colors(extract_brand_colors(html, None) or {})
        return (colors, "derived") if colors else ({}, None)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Palette extraction failed: %s", exc)
        return {}, None


def _clean_colors(colors: Dict[str, Any]) -> Dict[str, str]:
    from backend.schemas.brand import normalize_hex

    primary = str(colors.get("primary_color") or "").lower()
    if not primary or primary in {c.lower() for c in SYNTHETIC_SLATE_PRIMARIES}:
        return {}
    out: Dict[str, str] = {}
    for key in ("primary_color", "secondary_color", "accent_color"):
        try:
            value = normalize_hex(colors.get(key)) if colors.get(key) else None
        except ValueError:
            value = None
        if value:
            out[key] = value
    return out if "primary_color" in out else {}


def _logo(html: str, url: str) -> Optional[str]:
    if not html:
        return None
    try:
        from backend.services.preview.extraction.logo_resolver import resolve_logo

        logo_uri, _candidate, _notes = resolve_logo(html, url)
        return logo_uri
    except Exception as exc:  # noqa: BLE001
        logger.debug("Logo resolution failed: %s", exc)
        return None


def _store_logo(data_uri: str, organization_id: int) -> Optional[str]:
    """Persist a detected mark so the form can hold it as an ordinary logo URL.

    Only marks the engine would actually draw are kept — a favicon-sized smudge
    suggested as "your logo" would be worse than suggesting nothing.
    """
    from backend.services.preview.assets.logo import logo_is_usable

    if not logo_is_usable(data_uri):
        return None
    try:
        header, payload = data_uri.split(",", 1)
        content = base64.b64decode(payload)
    except Exception:  # noqa: BLE001
        return None
    content_type = header[5:].split(";", 1)[0] or "image/png"
    ext = "svg" if "svg" in content_type else "png"
    try:
        from backend.services.r2_client import upload_file_to_r2

        return upload_file_to_r2(
            content, f"brand-logos/{organization_id}/detected-{uuid4()}.{ext}", content_type,
        ) or None
    except Exception as exc:  # noqa: BLE001
        logger.info("Detected logo could not be stored: %s", exc)
        return None
