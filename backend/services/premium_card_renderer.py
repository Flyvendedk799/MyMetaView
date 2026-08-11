"""Premium share-card renderer.

The "AI template" (a composition spec the marketing brain authors) is rendered
here into a crisp PNG. Instead of compositing with PIL, we lay the card out in
real HTML/CSS and rasterize it with the same headless Chromium the screenshot
pipeline already runs — so we get real Bricolage/Plex typography, true kerning,
and pixel-clean edges.

The design language is MetaView's (restraint, one accent as a signal, mono
labels, generous whitespace). The *colors* are the target page's own brand, so a
Stripe card feels like Stripe and a Notion card feels like Notion — MetaView's
craft, the site's palette, the AI's story.

LAYOUTS. The art director picks one per page; each is a genuinely different
shape, not a recolour of the same card:

  typographic  headline-led, no imagery. Text-first software/professional pages.
  split        headline beside a hero visual panel. Visual-identity brands.
  stat         the page's proof number as the hero element. Needs a real metric.
  profile      circular avatar + name + role. Individual people.
  editorial    kicker, long headline, hairline rule, deck. Articles and essays.
  product      product visual + a price/CTA chip. Commerce.

Every layout degrades rather than fails: one that needs data it did not get
(``stat`` without a metric, ``profile`` without an avatar) falls back to a shape
that works with what is present. ``resolve_layout`` owns that decision, so the
engine can record which layout actually rendered.

SIZES. Cards render at whatever aspect the caller asks for — the same spec is
re-rendered per platform rather than cropped, so a square Instagram card is
composed as a square instead of being a chopped-up wide card.

Public entry point: ``render_premium_card(...) -> bytes`` (PNG).
"""

from __future__ import annotations

import html as _html
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from string import Template
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Canonical OG size. We render at 2× and downscale for anti-aliased edges.
CARD_W, CARD_H = 1200, 630
_SCALE = 2


# ---------------------------------------------------------------------------
# Sizes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CardSize:
    """A render target. Copy limits shrink with the space actually available."""
    key: str
    width: int
    height: int
    title_limit: int
    subtitle_limit: int

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def is_tall(self) -> bool:
        """Too tall for side-by-side columns — split layouts stack instead."""
        return self.aspect < 1.4


# The wide card is the OG/Twitter/LinkedIn/Slack link preview; those all sit
# within a hair of 1.91:1, so one render serves them. Square and portrait are
# the genuinely different shapes, and they are composed as such rather than
# cropped out of the wide card.
CARD_SIZES: Dict[str, CardSize] = {
    "wide": CardSize("wide", 1200, 630, title_limit=80, subtitle_limit=96),
    "square": CardSize("square", 1080, 1080, title_limit=96, subtitle_limit=130),
    "portrait": CardSize("portrait", 1080, 1350, title_limit=96, subtitle_limit=150),
}
DEFAULT_SIZE = CARD_SIZES["wide"]


def get_card_size(key: Optional[str]) -> CardSize:
    return CARD_SIZES.get(str(key or "wide").lower(), DEFAULT_SIZE)


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------

LAYOUTS = ("typographic", "split", "stat", "profile", "editorial", "product")

# Layouts that cannot render without imagery of some kind.
_NEEDS_VISUAL = {"split", "product", "profile"}

# Of those, the ones that put the imagery in a side/top panel. `profile` needs a
# visual but frames it as an avatar inside the text block — giving it a panel too
# would show the same face twice.
_PANEL_LAYOUTS = {"split", "product"}


def resolve_layout(
    requested: Optional[str],
    *,
    has_visual: bool,
    has_proof: bool,
) -> str:
    """The layout we can actually render, given the assets we ended up with.

    The art director picks from a screenshot and cannot know whether the focal
    crop succeeded or whether the proof survived validation, so its choice is a
    request. Degrading here — rather than rendering an empty panel or a blank
    stat — is what keeps a missing asset from turning into a broken card.
    """
    layout = str(requested or "typographic").lower().strip()
    if layout not in LAYOUTS:
        return "typographic"
    if layout in _NEEDS_VISUAL and not has_visual:
        # No visual: an editorial request degrades better than a bare headline
        # for long copy, but everything else reads fine as typographic.
        return "typographic"
    if layout == "stat" and not has_proof:
        return "typographic"
    return layout


# A proof string is usually "<number> <words>" — "50,000+ teams", "4.9★ from
# 2,847 reviews", "Featured in TechCrunch". The stat layout sets the number as
# the hero, so we split the leading quantity off the descriptive tail.
_STAT_HEAD_RE = re.compile(
    r"^\s*(?:[a-zA-Z]+\s+(?:by|in|from)\s+)?"        # "Trusted by", "Featured in"
    r"([€$£]?\d[\d,.\s]*[%+kKmMbB]?\+?\s*[★☆/]?\s*(?:\d+(?:[.,]\d+)?)?)"
    r"\s*(.*)$"
)


def split_proof(proof: Optional[str]) -> tuple[str, str]:
    """Split a proof string into (hero quantity, descriptive tail).

    Returns ("", "") when there is no leading quantity — the caller treats that
    as "this proof cannot carry a stat layout".
    """
    text = _clean(proof, 90)
    if not text:
        return "", ""
    m = _STAT_HEAD_RE.match(text)
    if not m:
        return "", ""
    value = (m.group(1) or "").strip(" ,.;:")
    label = (m.group(2) or "").strip(" ,.;:")
    if not value or not any(ch.isdigit() for ch in value):
        return "", ""
    return value, label

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
    background:${panel}; color:${ink}; display:flex; flex-direction:${card_dir};
    font-family:'IBM Plex Sans', system-ui, sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .accent-shape {
    position:absolute; top:${shape_off}px; right:${shape_off}px;
    width:${shape_sz}px; height:${shape_sz}px;
    border-radius:9999px; background:${accent}; opacity:0.14;
  }
  .text {
    position:relative; width:${text_col_w}; height:${text_col_h}; flex:${text_flex};
    padding:${pad_y}px ${pad_x}px; display:flex; flex-direction:column;
    justify-content:space-between; gap:${pad_y}px;
  }
  .top { display:flex; align-items:center; justify-content:space-between; gap:24px; }
  .eyebrow {
    font-family:'IBM Plex Mono', monospace; font-weight:500; font-size:${eyebrow_sz}px;
    letter-spacing:0.14em; text-transform:uppercase; color:${dim};
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  .logo { height:${logo_h}px; max-width:250px; object-fit:contain; opacity:0.98; }
  .wordmark {
    font-family:'Bricolage Grotesque', sans-serif; font-weight:600; font-size:22px;
    letter-spacing:-0.01em; color:${ink};
  }
  .headline-wrap { display:flex; flex-direction:column; gap:${gap}px; }
  .headline {
    font-family:'Bricolage Grotesque', sans-serif; font-weight:600;
    font-size:${hsize}px; line-height:1.05; letter-spacing:-0.025em;
    color:${ink}; max-width:${headline_mw};
  }
  .accent-bar { width:64px; height:5px; border-radius:3px; background:${accent}; flex:none; }
  .subtitle {
    font-size:${sub_sz}px; line-height:1.4; color:${dim}; max-width:${subtitle_mw};
    font-weight:400;
  }
  .footer {
    display:flex; align-items:center; gap:14px;
    font-family:'IBM Plex Mono', monospace; font-size:15px; letter-spacing:0.06em;
    color:${dim}; text-transform:uppercase;
  }
  .dot { width:8px; height:8px; border-radius:9999px; background:${accent}; }
  .visual {
    position:relative; width:${visual_w}; height:${visual_h}; overflow:hidden;
    border-left:${vborder_l}; border-bottom:${vborder_b}; flex:none;
  }
  .visual-bg {
    position:absolute; inset:-40px; width:calc(100% + 80px); height:calc(100% + 80px);
    object-fit:cover; object-position:center center;
    /* Heavy blur turns the hero into abstract brand-coloured texture — keeps the
       energy but removes any recognisable text/logo that would echo the centered
       mark. Over-sized + clipped so the blurred edges never show the panel. */
    filter:blur(24px); transform:scale(1.03);
  }
  .visual-scrim { position:absolute; inset:0; background:${scrim}; }
  .visual-logo {
    position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
    max-width:76%; max-height:56%; width:auto; height:auto; object-fit:contain;
    filter: drop-shadow(0 8px 24px rgba(0,0,0,0.5));
  }
  .visual-solo { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center center; }

  /* --- stat: the proof number is the hero, the headline supports it --- */
  .stat-value {
    font-family:'Bricolage Grotesque', sans-serif; font-weight:700;
    font-size:${stat_sz}px; line-height:0.92; letter-spacing:-0.04em; color:${ink};
  }
  .stat-label {
    font-family:'IBM Plex Mono', monospace; font-size:${eyebrow_sz}px; font-weight:500;
    letter-spacing:0.12em; text-transform:uppercase; color:${accent};
    max-width:24ch;
  }
  .stat-headline {
    font-size:${stat_head_sz}px; font-weight:600; letter-spacing:-0.02em;
    color:${dim}; max-width:32ch; line-height:1.15;
  }

  /* --- profile: the person leads, framed --- */
  .profile-row { display:flex; align-items:center; gap:${gap}px; }
  .avatar {
    width:${avatar_sz}px; height:${avatar_sz}px; border-radius:9999px; flex:none;
    object-fit:cover; object-position:center top;
    border:4px solid ${accent}; background:${hline};
  }

  /* --- editorial: kicker, rule, deck — an article, not an ad --- */
  .rule { width:100%; height:1px; background:${hline}; }
  .kicker {
    font-family:'IBM Plex Mono', monospace; font-weight:600; font-size:${eyebrow_sz}px;
    letter-spacing:0.16em; text-transform:uppercase; color:${accent};
  }
  .deck { font-size:${sub_sz}px; line-height:1.45; color:${dim}; max-width:44ch; }

  /* --- product: a price/action chip anchors the offer --- */
  .chip {
    display:inline-flex; align-items:center; align-self:flex-start; gap:10px;
    padding:12px 22px; border-radius:9999px; background:${accent};
    color:${on_accent}; font-family:'IBM Plex Mono', monospace; font-weight:600;
    font-size:17px; letter-spacing:0.06em; text-transform:uppercase;
  }
</style></head>
<body>
  <div class="card">
    ${accent_shape_html}
    ${body_html}
  </div>
</body></html>"""
)


def _visual_panel(
    *,
    visual_data_uri: str,
    logo_data_uri: Optional[str],
    blurred: bool,
) -> str:
    """The imagery panel.

    ``blurred`` sets the hero behind a scrim as brand-coloured texture with the
    logo centred on top — right when the point is the brand, wrong when the
    point is the thing itself. Product shots and avatars render clean.
    """
    if blurred and logo_data_uri:
        return (
            '<div class="visual">'
            f'<img class="visual-bg" src="{_esc(visual_data_uri)}" alt="" />'
            '<div class="visual-scrim"></div>'
            f'<img class="visual-logo" src="{_esc(logo_data_uri)}" alt="" />'
            '</div>'
        )
    return (
        f'<div class="visual"><img class="visual-solo" src="{_esc(visual_data_uri)}" alt="" /></div>'
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
    hide_watermark: bool = False,
    proof: Optional[str] = None,
    cta_text: Optional[str] = None,
    size: CardSize = DEFAULT_SIZE,
) -> str:
    # Columns only work when there is width to divide. On square and portrait
    # cards the visual stacks above the text instead.
    stacked = size.is_tall
    is_split = layout in _PANEL_LAYOUTS and bool(visual_data_uri)
    k = size.width / 1200.0  # geometry scales with the card

    hsize = _headline_size(title)
    if is_split and not stacked:
        hsize = min(hsize, 58)  # narrower text column
    if stacked:
        hsize = int(hsize * 0.92)
    hsize = max(30, int(hsize * k))

    # Scrim = the panel colour at ~0.66 opacity: it dims the hero photo into a
    # cohesive, subdued backdrop (muting any of the site's own overlaid text) and
    # ties the visual panel to the card's colour, so the centered logo pops.
    _pr, _pg, _pb = _rgb(panel)
    scrim = (
        f"linear-gradient(rgba({_pr},{_pg},{_pb},0.55), rgba({_pr},{_pg},{_pb},0.8))"
    )

    # The corner mark: a cropped logo if we have one, else a text wordmark —
    # but only when it ADDS something.
    #  - On SPLIT cards the visual panel already shows the brand (often the logo
    #    itself), so a corner logo would DUPLICATE it — suppress it entirely.
    #  - On profiles the brand_name is the person's name = the headline, so
    #    showing it twice reads as a bug; suppress the wordmark when it's a
    #    substring of the title. Brand extraction also sometimes returns a
    #    tagline as brand_name, so a wordmark must be short and name-like.
    _t = (title or "").strip().lower()
    _b = (brand_name or "").strip().lower()
    show_wordmark = (
        bool(_b) and len(_b) <= 22 and len(_b.split()) <= 3
        and _b not in _t and _t not in _b
    )
    if is_split:
        logo_html = ""
    elif logo_data_uri:
        logo_html = f'<img class="logo" src="{logo_data_uri}" alt="" />'
    elif show_wordmark:
        logo_html = f'<span class="wordmark">{_esc(brand_name)}</span>'
    else:
        logo_html = ""
    subtitle_html = f'<div class="subtitle">{_esc(subtitle)}</div>' if subtitle else ""

    # A product shot or a face is the subject; a hero backdrop is texture behind
    # the brand mark. Only the latter gets blurred and overlaid.
    visual_html = ""
    if is_split and visual_data_uri:
        visual_html = _visual_panel(
            visual_data_uri=visual_data_uri,
            logo_data_uri=logo_data_uri,
            blurred=layout == "split",
        )

    top_html = (
        f'<div class="top"><span class="eyebrow">{_esc(url_label)}</span>{logo_html}</div>'
    )
    footer_html = (
        "" if hide_watermark
        else '<div class="footer"><span class="dot"></span><span>metaview preview</span></div>'
    )

    # --- the middle block: this is what actually differs between layouts ---
    if layout == "stat":
        stat_value, stat_label = split_proof(proof)
        middle = (
            '<div class="headline-wrap">'
            f'<div class="stat-value">{_esc(stat_value)}</div>'
            + (f'<div class="stat-label">{_esc(stat_label)}</div>' if stat_label else "")
            + '<div class="accent-bar"></div>'
            f'<div class="headline stat-headline">{_esc(title)}</div>'
            '</div>'
        )
    elif layout == "profile":
        avatar = (
            f'<img class="avatar" src="{_esc(visual_data_uri)}" alt="" />'
            if visual_data_uri else ""
        )
        middle = (
            '<div class="profile-row">'
            f'{avatar}'
            '<div class="headline-wrap">'
            f'<div class="headline">{_esc(title)}</div>'
            '<div class="accent-bar"></div>'
            f'{subtitle_html}'
            '</div></div>'
        )
    elif layout == "editorial":
        # The kicker carries the topic; the URL already sits in the eyebrow, so
        # repeating the domain here would just be noise.
        kicker = _clean(proof, 40) or _clean(brand_name, 40)
        middle = (
            '<div class="headline-wrap">'
            + (f'<div class="kicker">{_esc(kicker)}</div>' if kicker else "")
            + '<div class="rule"></div>'
            f'<div class="headline">{_esc(title)}</div>'
            + (f'<div class="deck">{_esc(subtitle)}</div>' if subtitle else "")
            + '</div>'
        )
    elif layout == "product":
        chip = _clean(cta_text, 28) or _clean(proof, 28)
        middle = (
            '<div class="headline-wrap">'
            f'<div class="headline">{_esc(title)}</div>'
            '<div class="accent-bar"></div>'
            f'{subtitle_html}'
            + (f'<div class="chip">{_esc(chip)}</div>' if chip else "")
            + '</div>'
        )
    else:  # typographic and split share the headline block
        middle = (
            '<div class="headline-wrap">'
            f'<div class="headline">{_esc(title)}</div>'
            '<div class="accent-bar"></div>'
            f'{subtitle_html}'
            '</div>'
        )

    text_html = f'<div class="text">{top_html}{middle}{footer_html}</div>'
    # Stacked cards lead with the image; wide cards read text-first, left to right.
    body_html = (visual_html + text_html) if stacked else (text_html + visual_html)

    # The corner accent is the one variable "signal". When the director asks for
    # a "bar", the headline rule carries the accent alone (cleanest). A "shape"
    # is a soft wash; a "dot" is a smaller, more saturated mark. On layouts with
    # a visual the panel already fills the frame, so we drop the corner shape.
    moment = (accent_moment or "bar").lower()
    shape_sz, shape_off = int(420 * k), int(-160 * k)
    if is_split or moment == "bar":
        accent_shape_html = ""
    elif moment == "dot":
        shape_sz, shape_off = int(220 * k), int(-90 * k)
        accent_shape_html = '<div class="accent-shape" style="opacity:0.22;"></div>'
    else:  # "shape" (or anything else) → the soft corner circle
        accent_shape_html = '<div class="accent-shape"></div>'

    # The stat number is the largest thing on the card; long values must not
    # overflow, so it shrinks with its own length.
    stat_len = len(split_proof(proof)[0]) if layout == "stat" else 0
    stat_sz = int((186 if stat_len <= 6 else 148 if stat_len <= 9 else 112) * k)

    return _CARD_TEMPLATE.substitute(
        font_head=_font_head(),
        card_w=str(size.width),
        card_h=str(size.height),
        card_dir="column" if stacked else "row",
        panel=panel,
        ink=ink,
        accent=accent,
        on_accent=_text_on(accent),      # legible text inside an accent chip
        dim=_mix(ink, panel, 0.42),      # muted on-panel text
        hline=_mix(ink, panel, 0.80),    # faint hairline
        scrim=scrim,                     # panel-tinted dim over the hero photo

        pad_x=str(int(76 * k)),
        pad_y=str(int(72 * k)),
        gap=str(int(22 * k)),
        hsize=str(hsize),
        sub_sz=str(max(15, int(23 * k))),
        eyebrow_sz=str(max(13, int(19 * k))),
        logo_h=str(max(30, int(46 * k))),
        avatar_sz=str(int(190 * k)),
        stat_sz=str(stat_sz),
        stat_head_sz=str(max(20, int(30 * k))),
        shape_sz=str(shape_sz),
        shape_off=str(shape_off),

        text_col_w="100%" if (stacked or not is_split) else "58%",
        text_col_h="auto" if stacked else "100%",
        # Stacked cards need the text block to claim the leftover height, or
        # `space-between` has nothing to distribute and the footer floats mid-card.
        text_flex="1 1 auto" if stacked else "none",
        visual_w="100%" if stacked else "42%",
        visual_h="44%" if stacked else "100%",
        vborder_l="none" if stacked else f"1px solid {_mix(ink, panel, 0.80)}",
        vborder_b=f"1px solid {_mix(ink, panel, 0.80)}" if stacked else "none",
        headline_mw="16ch" if (is_split and not stacked) else "20ch",
        subtitle_mw="24ch" if (is_split and not stacked) else "34ch",

        accent_shape_html=accent_shape_html,
        body_html=body_html,
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
    hide_watermark: bool = False,
    proof: Optional[str] = None,
    cta_text: Optional[str] = None,
    size: str = "wide",
) -> bytes:
    """Render an on-identity premium share card to PNG bytes.

    ``size`` names an entry in ``CARD_SIZES`` — the card is composed at that
    aspect rather than cropped down from the wide one.

    Raises on failure so the caller can fall back to the legacy generators.
    """
    return render_premium_card_detailed(
        title=title, subtitle=subtitle, url=url, brand_name=brand_name,
        colors=colors, composition=composition, logo_data_uri=logo_data_uri,
        visual_data_uri=visual_data_uri, hide_watermark=hide_watermark,
        proof=proof, cta_text=cta_text, size=size,
    )[0]


def render_premium_card_detailed(
    *,
    title: str,
    subtitle: Optional[str] = None,
    url: str = "",
    brand_name: Optional[str] = None,
    colors: Optional[Dict[str, str]] = None,
    composition: Optional[Dict[str, Any]] = None,
    logo_data_uri: Optional[str] = None,
    visual_data_uri: Optional[str] = None,
    hide_watermark: bool = False,
    proof: Optional[str] = None,
    cta_text: Optional[str] = None,
    size: str = "wide",
) -> tuple[bytes, str]:
    """As ``render_premium_card``, but also returns the layout that rendered.

    The art director's pick and the layout that survives asset resolution are
    not always the same, and the engine records what actually shipped.
    """
    colors = colors or {}
    composition = composition or {}
    card_size = get_card_size(size)

    # Drop a weak logo crop so the clean wordmark shows instead.
    if logo_data_uri and not _logo_usable(logo_data_uri):
        logo_data_uri = None

    title_c = _clean(title, card_size.title_limit) or (brand_name or _url_label(url))
    subtitle_c = _clean(subtitle, card_size.subtitle_limit)
    accent = _norm_hex(colors.get("accent_color") or colors.get("accent"), "#E8622C")

    panel = _panel_color(colors, composition.get("panel_color_role", "primary"))
    ink = _text_on(panel)
    # If the accent has poor contrast on the panel, nudge it toward legible.
    if abs(_luminance(accent) - _luminance(panel)) < 0.12:
        accent = _mix(accent, ink, 0.35)

    # `use_visual` is the director's intent; the crop actually existing is the
    # fact. Only both together count as having a visual.
    if not bool(composition.get("use_visual")):
        visual_data_uri = None
    layout = resolve_layout(
        composition.get("layout"),
        has_visual=bool(visual_data_uri),
        has_proof=bool(split_proof(proof)[0]),
    )
    if layout not in _NEEDS_VISUAL:
        visual_data_uri = None

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
        hide_watermark=hide_watermark,
        proof=proof,
        cta_text=cta_text,
        size=card_size,
    )

    png = _rasterize(doc, card_size)
    return _downscale(png, card_size), layout


def _rasterize(doc: str, size: CardSize = DEFAULT_SIZE) -> bytes:
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
                    box["png"] = _shoot(browser, doc, size)
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


def _shoot(browser, doc: str, size: CardSize = DEFAULT_SIZE) -> bytes:
    page = browser.new_page(
        viewport={"width": size.width, "height": size.height},
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


def _downscale(png_2x: bytes, size: CardSize = DEFAULT_SIZE) -> bytes:
    """Downscale the 2× render to the card's exact size for crisp, anti-aliased edges."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(png_2x)).convert("RGB")
        if img.size != (size.width, size.height):
            img = img.resize((size.width, size.height), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return png_2x
