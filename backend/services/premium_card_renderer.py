"""Premium share-card renderer.

The "AI template" (a composition spec the marketing brain authors) is rendered
here into a crisp 1200×630 PNG. Instead of compositing with PIL, we lay the card
out in real HTML/CSS and rasterize it with the same headless Chromium the
screenshot pipeline already runs — so we get real Bricolage/Plex typography,
true kerning, and pixel-clean edges.

The design language is MetaView's (restraint, one accent as a signal, mono
labels, generous whitespace, a single card recipe). The *colors* are the target
page's own brand, so a Stripe card feels like Stripe and a Notion card feels
like Notion — MetaView's craft, the site's palette, the AI's story.

Public entry point: ``render_premium_card(...) -> bytes`` (PNG, 1200×630).
"""

from __future__ import annotations

import html as _html
import logging
import re
from io import BytesIO
from string import Template
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Canonical OG size. We render at 2× and downscale for anti-aliased edges.
CARD_W, CARD_H = 1200, 630
_SCALE = 2

_GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&"
    "family=IBM+Plex+Mono:wght@500;600&"
    "family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)

# Fonts are embedded as base64 @font-face so rasterizing never blocks on (or
# fails because of) a network fetch inside the worker container — the whole
# reason the first live render fell back to the legacy generator. Loaded once
# and cached. If the asset is somehow missing, we fall back to the Google link
# (a network dep, but better than no display font).
import os as _os

_FONTS_CSS_PATH = _os.path.join(_os.path.dirname(__file__), "assets", "premium_fonts.css")
_FONT_HEAD_CACHE: Optional[str] = None


def _font_head() -> str:
    global _FONT_HEAD_CACHE
    if _FONT_HEAD_CACHE is not None:
        return _FONT_HEAD_CACHE
    try:
        with open(_FONTS_CSS_PATH, "r", encoding="utf-8") as fh:
            css = fh.read()
        _FONT_HEAD_CACHE = f"<style>{css}</style>"
    except Exception as e:  # pragma: no cover
        logger.warning(f"premium_fonts.css unavailable ({e}); using network font link")
        _FONT_HEAD_CACHE = (
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link href="{_GOOGLE_FONTS}" rel="stylesheet">'
        )
    return _FONT_HEAD_CACHE


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _norm_hex(value: Optional[str], fallback: str) -> str:
    if not value or not isinstance(value, str):
        return fallback
    v = value.strip()
    m = _HEX_RE.match(v)
    if not m:
        return fallback
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"#{h.lower()}"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(hex_color: str) -> float:
    """Relative luminance (0=black, 1=white), WCAG-ish."""
    r, g, b = (c / 255.0 for c in _rgb(hex_color))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    a, b = _rgb(hex_a), _rgb(hex_b)
    r = round(a[0] + (b[0] - a[0]) * t)
    g = round(a[1] + (b[1] - a[1]) * t)
    bl = round(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def _text_on(bg_hex: str) -> str:
    """Legible text color for a given panel: near-white or near-ink."""
    return "#FBFBF9" if _luminance(bg_hex) < 0.45 else "#0B1F18"


def _panel_color(colors: Dict[str, str], role: str) -> str:
    """Resolve the panel background from the brand palette + requested role."""
    primary = _norm_hex(colors.get("primary_color") or colors.get("primary"), "#0B3B2E")
    secondary = _norm_hex(colors.get("secondary_color") or colors.get("secondary"), primary)
    role = (role or "primary").lower()
    if role == "light":
        return "#FBFBF9"
    if role == "dark":
        # A deep, slightly desaturated version of the brand primary reads premium.
        return _mix(primary, "#05100C", 0.55)
    if role == "secondary":
        return secondary
    # "primary": if the brand primary is very light, darken it so text sits well.
    return primary if _luminance(primary) < 0.62 else _mix(primary, "#05100C", 0.35)


# ---------------------------------------------------------------------------
# Copy helpers
# ---------------------------------------------------------------------------

def _clean(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    if len(t) > limit:
        t = t[: limit - 1].rstrip(" ,.;:-–—") + "…"
    return t


def _headline_size(title: str) -> int:
    """Fit the headline: shorter lines get a bigger, more confident size (px)."""
    n = len(title or "")
    if n <= 22:
        return 82
    if n <= 34:
        return 72
    if n <= 48:
        return 62
    if n <= 64:
        return 54
    return 46


def _url_label(url: str) -> str:
    try:
        p = urlparse(url if "://" in url else f"https://{url}")
        host = (p.netloc or "").replace("www.", "")
        path = (p.path or "").strip("/")
        seg = path.split("/")[0] if path else ""
        return f"{host} / {seg}" if seg else host
    except Exception:
        return url


def _esc(text: str) -> str:
    return _html.escape(text or "", quote=True)


def _logo_usable(data_uri: str) -> bool:
    """True only for a logo crop worth showing.

    A tiny, near-empty, or near-uniform crop scaled to 34px reads as a faint
    smudge in the corner and cheapens the card — better to fall back to the clean
    text wordmark. Rejects crops that are too small, mostly transparent, or almost
    a single flat color. Never blocks on a decode error.
    """
    try:
        import base64
        from PIL import Image
        b64 = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        img = Image.open(BytesIO(base64.b64decode(b64)))
        w, h = img.size
        if w < 44 or h < 14:
            return False
        small = img.convert("RGBA").resize((16, 16))
        px = list(small.getdata())
        if sum(1 for p in px if p[3] < 24) > len(px) * 0.82:
            return False  # mostly transparent
        def _var(xs):
            m = sum(xs) / len(xs)
            return sum((x - m) ** 2 for x in xs) / len(xs)
        spread = _var([p[0] for p in px]) + _var([p[1] for p in px]) + _var([p[2] for p in px])
        return spread >= 80  # reject near-uniform smudges
    except Exception:
        return True


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CARD_TEMPLATE = Template(
    """<!doctype html>
<html><head><meta charset="utf-8"/>
${font_head}
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:${card_w}px; height:${card_h}px; }
  .card {
    width:${card_w}px; height:${card_h}px; position:relative; overflow:hidden;
    background:${panel}; color:${ink}; display:flex;
    font-family:'IBM Plex Sans', system-ui, sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .accent-shape {
    position:absolute; top:-160px; right:-120px; width:420px; height:420px;
    border-radius:9999px; background:${accent}; opacity:0.14;
  }
  .text {
    position:relative; width:${text_col_w}; height:100%;
    padding:72px 76px; display:flex; flex-direction:column; justify-content:space-between;
  }
  .top { display:flex; align-items:center; justify-content:space-between; gap:24px; }
  .eyebrow {
    font-family:'IBM Plex Mono', monospace; font-weight:500; font-size:19px;
    letter-spacing:0.14em; text-transform:uppercase; color:${dim};
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  .logo { height:46px; max-width:250px; object-fit:contain; opacity:0.98; }
  .wordmark {
    font-family:'Bricolage Grotesque', sans-serif; font-weight:600; font-size:22px;
    letter-spacing:-0.01em; color:${ink};
  }
  .headline-wrap { display:flex; flex-direction:column; gap:22px; }
  .headline {
    font-family:'Bricolage Grotesque', sans-serif; font-weight:600;
    font-size:${hsize}px; line-height:1.05; letter-spacing:-0.025em;
    color:${ink}; max-width:${headline_mw};
  }
  .accent-bar { width:64px; height:5px; border-radius:3px; background:${accent}; }
  .subtitle {
    font-size:23px; line-height:1.4; color:${dim}; max-width:${subtitle_mw};
    font-weight:400;
  }
  .footer {
    display:flex; align-items:center; gap:14px;
    font-family:'IBM Plex Mono', monospace; font-size:15px; letter-spacing:0.06em;
    color:${dim}; text-transform:uppercase;
  }
  .dot { width:8px; height:8px; border-radius:9999px; background:${accent}; }
  .visual {
    position:relative; width:42%; height:100%; overflow:hidden;
    border-left:1px solid ${hline};
  }
  .visual img { width:100%; height:100%; object-fit:cover; object-position:center top; }
</style></head>
<body>
  <div class="card">
    ${accent_shape_html}
    <div class="text">
      <div class="top">
        <span class="eyebrow">${url_label}</span>
        ${logo_html}
      </div>
      <div class="headline-wrap">
        <div class="headline">${title}</div>
        <div class="accent-bar"></div>
        ${subtitle_html}
      </div>
      <div class="footer"><span class="dot"></span><span>metaview preview</span></div>
    </div>
    ${visual_html}
  </div>
</body></html>"""
)


def _build_html(
    *,
    title: str,
    subtitle: str,
    url_label: str,
    brand_name: str,
    panel: str,
    accent: str,
    ink: str,
    logo_data_uri: Optional[str],
    visual_data_uri: Optional[str],
    layout: str,
    mood: str,
    accent_moment: str = "bar",
) -> str:
    is_split = layout in {"split", "product", "editorial"} and bool(visual_data_uri)
    hsize = _headline_size(title)
    if is_split:
        hsize = min(hsize, 58)  # narrower text column

    # The corner mark: a cropped logo if we have one, else a text wordmark —
    # but only when the wordmark ADDS something. On profiles the brand_name is
    # the person's name, which is already the headline, so showing it twice reads
    # as a bug; suppress the wordmark when it's a substring of the title.
    _t = (title or "").strip().lower()
    _b = (brand_name or "").strip().lower()
    # Only show a wordmark that is actually a NAME. Brand extraction sometimes
    # returns a tagline/sentence as brand_name; a truncated sentence in the
    # corner looks broken, so require it to be short and few-worded.
    show_wordmark = (
        bool(_b) and len(_b) <= 22 and len(_b.split()) <= 3
        and _b not in _t and _t not in _b
    )
    if logo_data_uri:
        logo_html = f'<img class="logo" src="{logo_data_uri}" alt="" />'
    elif show_wordmark:
        logo_html = f'<span class="wordmark">{_esc(brand_name)}</span>'
    else:
        logo_html = ""
    subtitle_html = f'<div class="subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    visual_html = (
        f'<div class="visual"><img src="{_esc(visual_data_uri)}" alt="" /></div>'
        if is_split and visual_data_uri else ""
    )

    # The corner accent is the one variable "signal". When the director asks for
    # a "bar", the headline rule carries the accent alone (cleanest). A "shape"
    # is a soft wash; a "dot" is a smaller, more saturated mark. On split layouts
    # the visual already fills the right, so we drop the corner shape.
    moment = (accent_moment or "bar").lower()
    if is_split or moment == "bar":
        accent_shape_html = ""
    elif moment == "dot":
        accent_shape_html = (
            '<div class="accent-shape" style="width:220px;height:220px;'
            'opacity:0.22;top:-90px;right:-70px;"></div>'
        )
    else:  # "shape" (or anything else) → the soft corner circle
        accent_shape_html = '<div class="accent-shape"></div>'

    return _CARD_TEMPLATE.substitute(
        font_head=_font_head(),
        card_w=str(CARD_W),
        card_h=str(CARD_H),
        panel=panel,
        ink=ink,
        accent=accent,
        dim=_mix(ink, panel, 0.42),      # muted on-panel text
        hline=_mix(ink, panel, 0.80),    # faint hairline
        hsize=str(hsize),
        text_col_w="58%" if is_split else "100%",
        headline_mw="16ch" if is_split else "20ch",
        subtitle_mw="24ch" if is_split else "34ch",
        url_label=_esc(url_label),
        title=_esc(title),
        logo_html=logo_html,
        subtitle_html=subtitle_html,
        visual_html=visual_html,
        accent_shape_html=accent_shape_html,
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_premium_card(
    *,
    title: str,
    subtitle: Optional[str] = None,
    url: str = "",
    brand_name: Optional[str] = None,
    colors: Optional[Dict[str, str]] = None,
    composition: Optional[Dict[str, Any]] = None,
    logo_data_uri: Optional[str] = None,
    visual_data_uri: Optional[str] = None,
) -> bytes:
    """Render an on-identity premium share card to PNG bytes (1200×630).

    Raises on failure so the caller can fall back to the legacy generators.
    """
    colors = colors or {}
    composition = composition or {}

    # Drop a weak logo crop so the clean wordmark shows instead.
    if logo_data_uri and not _logo_usable(logo_data_uri):
        logo_data_uri = None

    title_c = _clean(title, 80) or (brand_name or _url_label(url))
    subtitle_c = _clean(subtitle, 96)
    accent = _norm_hex(colors.get("accent_color") or colors.get("accent"), "#E8622C")

    panel = _panel_color(colors, composition.get("panel_color_role", "primary"))
    ink = _text_on(panel)
    # If the accent has poor contrast on the panel, nudge it toward legible.
    if abs(_luminance(accent) - _luminance(panel)) < 0.12:
        accent = _mix(accent, ink, 0.35)

    layout = str(composition.get("layout", "typographic")).lower()
    use_visual = bool(composition.get("use_visual")) and bool(visual_data_uri)
    if not use_visual:
        visual_data_uri = None
        if layout in {"split", "product", "editorial"}:
            layout = "typographic"

    doc = _build_html(
        title=title_c,
        subtitle=subtitle_c,
        url_label=_url_label(url),
        brand_name=_clean(brand_name, 28),
        panel=panel,
        accent=accent,
        ink=ink,
        logo_data_uri=logo_data_uri,
        visual_data_uri=visual_data_uri,
        layout=layout,
        mood=str(composition.get("mood", "confident")),
        accent_moment=str(composition.get("accent_moment", "bar")),
    )

    png = _rasterize(doc)
    return _downscale(png)


def _rasterize(doc: str) -> bytes:
    """Render HTML to a 2× PNG on a dedicated thread that owns its Playwright.

    The screenshot pipeline's shared BrowserPool binds its Playwright to whichever
    thread created it — usually a ThreadPoolExecutor worker from the parallel
    capture/extraction stage, which has already exited by the time we composite.
    Reusing that browser from the main thread raises
    ``greenlet.error: cannot switch to a different thread (which happens to have
    exited)``. To be bulletproof we do the entire launch → shoot → close on one
    fresh thread with its own ``sync_playwright`` instance, so every Playwright
    call happens on the thread that created it.
    """
    from backend.services.playwright_screenshot import BrowserPool
    import threading

    box: Dict[str, Any] = {}

    def _run() -> None:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(args=BrowserPool.BROWSER_ARGS, headless=True)
                try:
                    box["png"] = _shoot(browser, doc)
                finally:
                    browser.close()
        except Exception as exc:  # re-raised on the caller thread below
            box["err"] = exc

    t = threading.Thread(target=_run, name="premium-card-render", daemon=True)
    t.start()
    t.join(timeout=60)
    if "png" in box:
        return box["png"]
    if "err" in box:
        raise box["err"]
    raise RuntimeError("premium card render timed out after 60s")


def _shoot(browser, doc: str) -> bytes:
    page = browser.new_page(
        viewport={"width": CARD_W, "height": CARD_H},
        device_scale_factor=_SCALE,
    )
    try:
        # domcontentloaded (not "load"): fonts are embedded as data: URIs, so
        # there are no external resources to wait for — this can't hang on the
        # network the way "load" + a Google Fonts link did.
        page.set_content(doc, wait_until="domcontentloaded", timeout=15000)
        # Bounded wait for font faces to parse/apply (embedded → near-instant),
        # capped so it can never hang.
        try:
            page.evaluate(
                "() => Promise.race(["
                "  (document.fonts ? document.fonts.ready : Promise.resolve()),"
                "  new Promise(r => setTimeout(r, 2500))"
                "])"
            )
        except Exception:
            pass
        page.wait_for_timeout(120)
        return page.screenshot(type="png", full_page=False)
    finally:
        page.close()


def _downscale(png_2x: bytes) -> bytes:
    """Downscale the 2× render to exactly 1200×630 for crisp, anti-aliased edges."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(png_2x)).convert("RGB")
        if img.size != (CARD_W, CARD_H):
            img = img.resize((CARD_W, CARD_H), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return png_2x
