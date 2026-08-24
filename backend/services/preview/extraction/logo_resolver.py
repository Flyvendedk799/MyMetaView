"""Finding a page's logo — in parallel, guarded, and with SVG included.

The old resolver walked a ladder of CSS selectors and downloaded each candidate
one at a time, waiting up to five seconds per miss. A page offering a dozen
icons therefore cost a minute in the worst case, inside a stage with a deadline;
and every SVG candidate was discarded outright because PIL cannot decode one,
which is why sites with a perfectly good vector wordmark fell back to text.

Same ladder, three changes: candidates are gathered first and fetched
concurrently, every URL goes through the SSRF guard, and SVG is rasterized
rather than skipped. The ladder's *order* is preserved exactly — the first
usable candidate in priority order wins, so behaviour is unchanged for pages
where the old code already found something.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from backend.services.preview.assets.logo import logo_is_usable, normalize_logo
from backend.services.preview.net import fetch_many
from backend.services.preview.observability.reason_codes import Degradation

logger = logging.getLogger(__name__)


# Priority order. Earlier tiers are better logos, not merely earlier matches:
# an apple-touch-icon is a deliberate, square, high-res brand asset, while a
# favicon is whatever fit in 16px.
_HIGHRES_ICON_SELECTORS = (
    'link[rel="apple-touch-icon"]',
    'link[rel="apple-touch-icon-precomposed"]',
    'link[rel="icon"][sizes="192x192"]',
    'link[rel="icon"][sizes="180x180"]',
    'link[rel="icon"][sizes="128x128"]',
    'link[rel="icon"][sizes="96x96"]',
)

_LOGO_IMG_SELECTORS = (
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
)

_FAVICON_SELECTORS = (
    'link[rel="icon"][sizes]',
    'link[rel="icon"]',
    'link[rel="shortcut icon"]',
)

# Fetching every candidate a busy page offers would be its own denial of
# service; the ladder's useful signal is all in the first couple of dozen.
MAX_CANDIDATES = 24


@dataclass
class LogoCandidate:
    """One possible logo and where in the ladder it came from."""

    url: str
    tier: str          # highres_icon | header_img | favicon | default_favicon
    selector: str = ""

    @property
    def degradation(self) -> Optional[Degradation]:
        """Which fallback, if any, using this candidate represents."""
        if self.tier in ("favicon", "default_favicon"):
            return Degradation.BRAND_LOGO_FALLBACK_FAVICON
        return None


def _candidate_srcs(img_tag) -> List[str]:
    """Every src an ``<img>`` might really be using.

    Lazy-loading frameworks leave ``src`` as a placeholder and put the real
    asset in a data attribute or a srcset, so reading only ``src`` finds a 1px
    spacer on a large share of modern sites.
    """
    out: List[str] = []
    for attribute in ("src", "data-src", "data-lazy-src", "data-original"):
        value = (img_tag.get(attribute) or "").strip()
        if value and not value.startswith("data:image/gif"):
            out.append(value)

    srcset = (img_tag.get("srcset") or img_tag.get("data-srcset") or "").strip()
    if srcset:
        # Widest descriptor first — the biggest asset makes the crispest mark.
        entries = []
        for part in srcset.split(","):
            bits = part.strip().split()
            if not bits:
                continue
            width = 0
            if len(bits) > 1 and bits[1].endswith("w"):
                try:
                    width = int(bits[1][:-1])
                except ValueError:
                    width = 0
            entries.append((width, bits[0]))
        out.extend(src for _, src in sorted(entries, reverse=True))

    seen = set()
    return [s for s in out if not (s in seen or seen.add(s))]


def collect_candidates(html: str, url: str) -> List[LogoCandidate]:
    """Gather every logo candidate the page offers, in priority order.

    Gathering before fetching is the whole change: the list is known up front,
    so the downloads can run at once instead of the ladder blocking on each miss.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html or "", "html.parser")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Logo candidate parse failed: %s", exc)
        return []

    parsed = urlparse(url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    candidates: List[LogoCandidate] = []
    seen: set = set()

    def add(raw: str, tier: str, selector: str) -> None:
        if not raw or len(candidates) >= MAX_CANDIDATES:
            return
        absolute = urljoin(base, raw.strip())
        if absolute in seen:
            return
        seen.add(absolute)
        candidates.append(LogoCandidate(absolute, tier, selector))

    for selector in _HIGHRES_ICON_SELECTORS:
        icon = soup.select_one(selector)
        if icon and icon.get("href"):
            add(icon["href"], "highres_icon", selector)

    for selector in _LOGO_IMG_SELECTORS:
        for tag in soup.select(selector)[:3]:
            for src in _candidate_srcs(tag):
                add(src, "header_img", selector)

    for selector in _FAVICON_SELECTORS:
        icon = soup.select_one(selector)
        if icon and icon.get("href"):
            add(icon["href"], "favicon", selector)

    add("/favicon.ico", "default_favicon", "default")
    return candidates


def resolve_logo(
    html: str,
    url: str,
    *,
    timeout: float = 6.0,
) -> Tuple[Optional[str], Optional[LogoCandidate], List[str]]:
    """Best usable logo for the page.

    Returns ``(data_uri, winning_candidate, notes)``. Candidates are fetched
    concurrently but *selected* in ladder order, so parallelism buys latency
    without changing which logo wins.
    """
    candidates = collect_candidates(html, url)
    if not candidates:
        return None, None, ["no logo candidates in markup"]

    notes: List[str] = []
    results = fetch_many([c.url for c in candidates], timeout=timeout)

    svg_seen = False
    for candidate, result in zip(candidates, results):
        if not result.ok:
            if result.refused:
                notes.append(f"refused {candidate.url[:60]}: {result.error}")
            continue

        is_svg = "svg" in (result.content_type or "").lower() or result.content[:200].lstrip().startswith(b"<svg")
        data_uri = normalize_logo(result.content, content_type=result.content_type)
        if not data_uri:
            if is_svg:
                svg_seen = True
                notes.append(f"svg candidate not rasterizable: {candidate.url[:60]}")
            continue
        if not logo_is_usable(data_uri):
            notes.append(f"candidate too weak to show: {candidate.url[:60]}")
            continue

        if is_svg:
            notes.append("rasterized SVG logo")
        return data_uri, candidate, notes

    if svg_seen:
        notes.append("all usable candidates were SVG and no rasterizer is installed")
    return None, None, notes


def logo_degradation(
    data_uri: Optional[str],
    candidate: Optional[LogoCandidate],
    notes: List[str],
) -> Tuple[Degradation, str]:
    """Which degradation code describes how the logo hunt ended."""
    if not data_uri:
        if any("svg" in note for note in notes):
            return Degradation.BRAND_LOGO_SVG_SKIPPED, "; ".join(notes[:2])
        return Degradation.BRAND_LOGO_NONE, "; ".join(notes[:2]) or "no usable logo found"

    if any("rasterized SVG" in note for note in notes):
        return Degradation.BRAND_LOGO_SVG_RASTERIZED, f"from {candidate.tier if candidate else 'unknown'}"

    specific = candidate.degradation if candidate else None
    if specific:
        return specific, f"{candidate.tier}: {candidate.url[:80]}"
    return Degradation.BRAND_OK, f"{candidate.tier if candidate else 'unknown'} logo"
