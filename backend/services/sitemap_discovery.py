"""Discover a site's page URLs from its sitemap(s).

Used by the authenticated "cover your whole site" flow: given a verified domain,
find the URLs worth generating previews for by reading robots.txt + sitemap.xml
(following sitemap-index files one level deep). Best-effort and defensive — a site
with no sitemap simply returns an empty list, never an error.
"""
import logging
from typing import List, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_COMMON_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
]
_USER_AGENT = "MetaViewBot/1.0 (+https://mymetaview.com)"
_MAX_SITEMAPS = 40  # hard stop on how many sitemap documents we'll fetch


def _norm_host(host: str) -> str:
    """Normalise a host for same-site comparison (strip a leading www.)."""
    return (host or "").lower().lstrip(".").removeprefix("www.")


def _fetch(url: str, timeout: int = 8) -> str | None:
    """GET a URL, returning its text body on a 200, else None. Never raises."""
    try:
        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": _USER_AGENT}, allow_redirects=True
        )
        if resp.status_code == 200 and resp.text:
            return resp.text
    except requests.RequestException as e:
        logger.info("sitemap fetch failed for %s: %s", url, e)
    return None


def _parse_sitemap(xml_text: str) -> Tuple[List[str], List[str]]:
    """Parse a sitemap document.

    Returns (child_sitemap_urls, page_urls). A sitemap-index yields child sitemaps;
    a urlset yields page URLs.
    """
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return [], []

    tag = root.tag.lower()
    child_sitemaps: List[str] = []
    page_urls: List[str] = []

    if tag.endswith("sitemapindex"):
        for sm in root.findall(f"{_SITEMAP_NS}sitemap"):
            loc = sm.find(f"{_SITEMAP_NS}loc")
            if loc is not None and loc.text:
                child_sitemaps.append(loc.text.strip())
    else:  # urlset (or namespaced variant)
        for url_el in root.findall(f"{_SITEMAP_NS}url"):
            loc = url_el.find(f"{_SITEMAP_NS}loc")
            if loc is not None and loc.text:
                page_urls.append(loc.text.strip())
        # Fallback for documents without the standard namespace
        if not page_urls:
            for loc in root.iter():
                if loc.tag.lower().endswith("loc") and loc.text:
                    page_urls.append(loc.text.strip())

    return child_sitemaps, page_urls


def discover_sitemap_urls(domain: str, max_urls: int = 200) -> List[str]:
    """Return up to ``max_urls`` same-site page URLs discovered for ``domain``.

    Reads robots.txt for ``Sitemap:`` directives, then falls back to common
    sitemap paths, following one level of sitemap-index. Only URLs on the same
    host as ``domain`` are returned. Best-effort: returns [] if nothing is found.
    """
    base = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
    target_host = _norm_host(urlparse(base).netloc or domain)

    queue: List[str] = []

    # 1. robots.txt Sitemap: directives take priority (authoritative location)
    robots = _fetch(urljoin(base, "/robots.txt"))
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                loc = line.split(":", 1)[1].strip()
                if loc:
                    queue.append(loc)

    # 2. Common conventional paths as a fallback
    for path in _COMMON_PATHS:
        queue.append(urljoin(base, path))

    seen_sitemaps: set[str] = set()
    urls: List[str] = []
    seen_urls: set[str] = set()

    while queue and len(urls) < max_urls and len(seen_sitemaps) < _MAX_SITEMAPS:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        xml_text = _fetch(sitemap_url)
        if not xml_text:
            continue

        children, pages = _parse_sitemap(xml_text)
        for child in children:
            if child not in seen_sitemaps:
                queue.append(child)

        for page in pages:
            if _norm_host(urlparse(page).netloc) != target_host:
                continue
            if page in seen_urls:
                continue
            seen_urls.add(page)
            urls.append(page)
            if len(urls) >= max_urls:
                break

    logger.info("sitemap discovery for %s found %d urls (%d sitemaps read)",
                domain, len(urls), len(seen_sitemaps))
    return urls[:max_urls]
