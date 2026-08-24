"""The My Site brand, on its way to the card.

Branding is configured per connected domain and is meant to reach every preview
generated for that domain: the identity shapes the copy, the palette, mark and
font shape the card. These tests pin the three places that was leaking — the
result cache, the art director's brief, and the renderer's typography — plus the
per-preview opt-out the gallery offers when a page is not really the site's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from backend.services.preview.branding import (
    DISREGARD_KEY,
    brand_signature,
    disregarded,
    identity_brief,
    settings_of,
)

BRAND = {
    "brand_name": "Acme Analytics",
    "tagline": "Analytics without the setup",
    "brand_description": "We show SaaS teams which features drive retention.",
    "audience": "Product managers at B2B SaaS companies",
    "voice": "confident",
    "primary_color": "#2979FF",
    "secondary_color": "#0A1A3C",
    "accent_color": "#3FFFD3",
    "font_family": "IBM Plex Sans",
    "logo_url": "https://cdn.test/logo.png",
    "preview_layout": "split",
    "preview_panel": "dark",
    "preview_accent": "bar",
    "force_brand_colors": True,
    "hide_watermark": False,
}


@dataclass
class FakeConfig:
    brand_settings: Optional[Dict[str, Any]] = None


class TestBrandSignature:
    def test_no_settings_and_empty_settings_agree(self):
        """The demo has no brand, and its cache must behave as it always did."""
        assert brand_signature(None) == brand_signature({}) == "none"

    def test_two_brands_do_not_share_a_cached_card(self):
        other = {**BRAND, "primary_color": "#FF0000"}
        assert brand_signature(BRAND) != brand_signature(other)

    def test_changing_the_font_changes_the_signature(self):
        assert brand_signature(BRAND) != brand_signature({**BRAND, "font_family": "Inter"})

    def test_it_is_stable_across_key_order_and_casing(self):
        reordered = dict(reversed(list(BRAND.items())))
        recased = {**BRAND, "primary_color": "#2979ff"}
        assert brand_signature(BRAND) == brand_signature(reordered) == brand_signature(recased)

    def test_a_disregarded_preview_is_its_own_bucket(self):
        """Otherwise a branded card would be served for an unbranded request."""
        assert brand_signature({**BRAND, DISREGARD_KEY: True}) != brand_signature(BRAND)

    def test_fields_that_do_not_change_the_card_are_ignored(self):
        assert brand_signature({**BRAND, "id": 7, "updated_at": "now"}) == brand_signature(BRAND)


class TestIdentityBrief:
    def test_it_carries_what_the_user_typed(self):
        brief = identity_brief(BRAND)
        assert "Acme Analytics" in brief
        assert "Product managers at B2B SaaS companies" in brief
        assert "confident" in brief

    def test_an_empty_tab_briefs_nothing(self):
        """Blank fields mean "keep inferring from the page"."""
        assert identity_brief({"voice": "auto"}) == ""
        assert identity_brief({}) == ""
        assert identity_brief(None) == ""

    def test_colours_are_not_in_the_copy_brief(self):
        assert "#2979FF" not in identity_brief(BRAND)

    def test_a_disregarded_preview_gets_no_brief(self):
        assert identity_brief({**BRAND, DISREGARD_KEY: True}) == ""

    def test_it_changes_the_reasoning_cache_key(self):
        """The brief is part of the prompt, so copy cannot be shared brands."""
        from backend.services.preview.caching.layers import reasoning_fingerprint

        base = dict(url="https://acme.test/pricing", title="Pricing", text="<html/>")
        assert reasoning_fingerprint(**base, brand_brief=identity_brief(BRAND)) != \
               reasoning_fingerprint(**base)


class TestSettingsOf:
    def test_it_reads_the_engine_config(self):
        assert settings_of(FakeConfig(brand_settings=BRAND))["brand_name"] == "Acme Analytics"

    def test_a_config_without_settings_is_not_an_error(self):
        assert settings_of(FakeConfig()) == {}
        assert settings_of(object()) == {}

    def test_disregard_is_off_unless_asked_for(self):
        assert not disregarded(BRAND)
        assert not disregarded(None)
        assert disregarded({**BRAND, DISREGARD_KEY: True})


class TestTheResultCacheKnowsWhichBrandItHolds:
    """A cached card is only reusable for a request with the same branding.

    Result entries are keyed by URL, so before the signature travelled with the
    payload the same URL served one stored card to every brand — a customer's
    own card from before they changed their colours, or another account's card
    entirely.
    """

    @staticmethod
    def _state(brand, monkeypatch, stored):
        import json

        from backend.services import preview_cache
        from backend.services.preview.budgets import StageBudget
        from backend.services.preview.observability.job_trace import JobTrace
        from backend.services.preview.stages import PipelineState

        class FakeRedis:
            def get(self, key):
                return json.dumps(stored) if stored is not None else None

        monkeypatch.setattr(preview_cache, "get_redis_client", lambda: FakeRedis())
        url = "https://acme.test/pricing"
        return PipelineState(
            url=url,
            config=FakeConfig(brand_settings=brand),
            trace=JobTrace(url=url),
            budget=StageBudget(total_s=120.0),
        )

    def test_a_card_generated_for_this_brand_is_served(self, monkeypatch):
        from backend.services.preview.pipeline import _read_cache

        stored = {"title": "Cached", "brand_signature": brand_signature(BRAND)}
        state = self._state(BRAND, monkeypatch, stored)
        assert (_read_cache(state, "saas:preview:ai:") or {}).get("title") == "Cached"

    def test_a_card_generated_for_another_brand_is_a_miss(self, monkeypatch):
        from backend.services.preview.observability.reason_codes import Degradation
        from backend.services.preview.pipeline import _read_cache

        stored = {"title": "Someone else\u2019s card",
                  "brand_signature": brand_signature({**BRAND, "primary_color": "#FF0000"})}
        state = self._state(BRAND, monkeypatch, stored)
        assert _read_cache(state, "saas:preview:ai:") is None
        assert Degradation.RESULT_CACHE_BRAND_CHANGED.value in state.trace.degradation_codes()

    def test_an_entry_from_before_the_signature_existed_is_a_miss(self, monkeypatch):
        """Old entries carry no signature and were generated for some brand."""
        from backend.services.preview.pipeline import _read_cache

        state = self._state(BRAND, monkeypatch, {"title": "Legacy"})
        assert _read_cache(state, "saas:preview:ai:") is None

    def test_the_demo_still_reads_its_own_unbranded_entries(self, monkeypatch):
        from backend.services.preview.pipeline import _read_cache

        state = self._state(None, monkeypatch, {"title": "Demo card"})
        assert (_read_cache(state, "demo:preview:v3:ultra:") or {}).get("title") == "Demo card"


class TestBrandFontReachesTheCard:
    @pytest.mark.parametrize("font,expected", [
        ("IBM Plex Sans", "'IBM Plex Sans'"),
        ("Inter", "'Inter'"),
        ("System", "system-ui"),
        ("Bricolage Grotesque", "'Bricolage Grotesque'"),
    ])
    def test_each_choice_resolves_to_a_stack_that_leads_with_it(self, font, expected):
        from backend.services.premium_card_renderer import _font_stacks

        display, headline, body = _font_stacks(font)
        assert display.startswith(expected)
        assert headline.startswith(expected)
        assert body  # never empty — a card with no font stack renders in Times

    def test_an_unknown_font_falls_back_to_the_house_face(self):
        from backend.services.premium_card_renderer import _font_stacks

        assert _font_stacks("Comic Sans")[0].startswith("'Bricolage Grotesque'")
        assert _font_stacks(None)[0].startswith("'Bricolage Grotesque'")

    def test_the_headline_stack_keeps_its_script_fallbacks(self):
        """A headline is where non-Latin copy has to be drawn at size."""
        from backend.services.premium_card_renderer import _font_stacks

        assert "Noto Sans Arabic" in _font_stacks("Inter")[1]

    def test_the_chosen_font_is_what_the_card_html_asks_for(self):
        from backend.services.premium_card_renderer import _build_html

        doc = _build_html(
            title="Ship faster", subtitle="Together", url_label="acme.test",
            brand_name="Acme", panel="#0B3B2E", accent="#E8622C", ink="#ffffff",
            logo_data_uri=None, visual_data_uri=None, layout="typographic",
            mood="confident", font_family="IBM Plex Sans",
        )
        assert "font-family:'IBM Plex Sans'" in doc


class TestTheJobCarriesTheChoice:
    """What the gallery's toggle actually does to a generation."""

    @staticmethod
    def _run(ignore_site_branding: bool):
        """Run the production job far enough to capture the engine config."""
        from unittest.mock import MagicMock, patch

        from backend.jobs import preview_pipeline
        from backend.services.generation_lane import LaneDecision

        with patch.object(preview_pipeline, "PreviewEngine") as MockEngine, \
                patch.object(preview_pipeline, "SessionLocal") as MockSession, \
                patch.object(preview_pipeline, "brand_resolver") as mock_brand, \
                patch.object(preview_pipeline, "BrandSettingsSchema") as MockSchema, \
                patch.object(preview_pipeline, "resolve_lane") as mock_lane, \
                patch.object(preview_pipeline, "record_ai_generation"), \
                patch.object(preview_pipeline, "upsert_preview") as mock_upsert, \
                patch.object(preview_pipeline, "rewrite_to_brand_voice") as mock_voice, \
                patch.object(preview_pipeline, "log_activity"):
            MockSession.return_value = MagicMock()
            mock_brand.resolve.return_value = MagicMock()
            MockSchema.model_validate.return_value = MagicMock(
                primary_color="#2979FF", secondary_color="#0A1A3C",
                accent_color="#3FFFD3", font_family="IBM Plex Sans", logo_url=None,
            )
            mock_voice.return_value = "rewritten in the brand's voice"
            mock_lane.return_value = LaneDecision("ai", used=0, limit=None)
            MockEngine.return_value.generate.return_value = MagicMock(
                blueprint={"template_type": "landing"}, tags=[], title="T",
                description="the page's own description", message="m",
                composited_preview_image_url="u", screenshot_url="s",
            )

            preview_pipeline.generate_preview_job(
                1, 1, "https://acme.test/guest-post", "acme.test",
                ignore_site_branding=ignore_site_branding,
            )
            return MockEngine.call_args[0][0], mock_upsert.call_args.kwargs

    def test_by_default_the_site_brand_reaches_the_engine(self):
        config, upserted = self._run(False)
        assert config.brand_settings["primary_color"] == "#2979FF"
        assert config.brand_settings["font_family"] == "IBM Plex Sans"
        assert config.brand_settings[DISREGARD_KEY] is False
        assert upserted["description"] == "rewritten in the brand's voice"
        assert upserted["ignore_site_branding"] is False

    def test_disregarding_it_reaches_the_engine_too(self):
        """The flag travels with the settings so the trace can explain the card."""
        config, upserted = self._run(True)
        assert config.brand_settings[DISREGARD_KEY] is True
        assert disregarded(config.brand_settings)

    def test_a_disregarded_preview_keeps_the_pages_own_words(self):
        config, upserted = self._run(True)
        assert upserted["description"] == "the page's own description"

    def test_the_choice_is_stored_on_the_preview(self):
        """A re-roll has to run the same way, so it cannot live on the request."""
        _, upserted = self._run(True)
        assert upserted["ignore_site_branding"] is True
