"""The card's typefaces actually load.

``premium_fonts.css`` embeds Bricolage Grotesque, IBM Plex Sans and IBM Plex
Mono as data URIs. Every rule in it once read ``format('woff2')
format('woff2')`` — an invalid ``src`` descriptor, so Chromium registered no
face at all and every card, demo and app, was drawn in whatever system sans the
container had. Nothing failed: the CSS parsed, the fallbacks rendered, and the
"premium design language" simply never shipped. These tests make that loud.
"""
from __future__ import annotations

import base64
import os
import re

import pytest

CSS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "services", "assets", "premium_fonts.css"
)
RULE_RE = re.compile(r"@font-face\s*\{([^}]*)\}")


def _rules():
    with open(CSS_PATH, encoding="utf-8") as fh:
        return RULE_RE.findall(fh.read())


def test_every_family_the_renderer_names_is_embedded():
    families = {re.search(r"font-family:\s*'([^']+)'", r).group(1) for r in _rules()}
    assert {"Bricolage Grotesque", "IBM Plex Sans", "IBM Plex Mono"} <= families


@pytest.mark.parametrize("index", range(14))
def test_each_face_has_one_valid_woff2_source(index):
    rules = _rules()
    if index >= len(rules):
        pytest.skip("fewer faces embedded")
    # The url() carries a ";" of its own (data:font/woff2;base64), so the
    # descriptor runs from url( to the first ";" after its closing paren.
    src = re.search(r"src:\s*(url\([^)]*\)[^;]*);", rules[index]).group(1)
    # Exactly one url() and one format() — a repeated format() voids the rule.
    assert len(re.findall(r"url\(", src)) == 1, src[:80]
    assert len(re.findall(r"format\(", src)) == 1, re.sub(r"base64,[^)]+", "…", src)
    payload = re.search(r"base64,([A-Za-z0-9+/=]+)", src).group(1)
    assert base64.b64decode(payload)[:4] == b"wOF2"


def test_chromium_registers_the_faces():
    """The real check, where a browser is available (the render container)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from backend.services.premium_card_renderer import _font_head

    doc = f"<!doctype html><html><head>{_font_head()}</head><body></body></html>"
    try:
        with sync_api.sync_playwright() as p:
            from backend.services.playwright_screenshot import chromium_launch_kwargs

            browser = p.chromium.launch(**chromium_launch_kwargs())
            try:
                page = browser.new_page()
                page.set_content(doc, wait_until="domcontentloaded")
                loaded = page.evaluate(
                    "async () => (await document.fonts.load(\"600 40px 'Bricolage Grotesque'\")).length"
                )
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — no browser here is not a failure
        pytest.skip(f"Chromium unavailable: {exc}")
    assert loaded > 0
