"""Each stage, tested on its own.

The point of the decomposition was that a stage becomes a function between two
small objects. These tests are the proof: none of them starts a browser, calls a
model, or touches object storage, and every one of them would have needed all
three against the engine they replace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest

from backend.services.preview.budgets import StageBudget
from backend.services.preview.observability.job_trace import JobTrace
from backend.services.preview.observability.reason_codes import Degradation
from backend.services.preview.stages import (
    BrandResult,
    CaptureResult,
    CompositionSpec,
    PipelineState,
    ReasoningResult,
)


@dataclass
class FakeConfig:
    """The slice of engine config the stages actually read."""

    is_demo: bool = True
    enable_ai_reasoning: bool = True
    enable_cache: bool = False
    quality_threshold: float = 0.8
    max_quality_iterations: int = 2
    allow_soft_pass: bool = True
    min_soft_pass_overall: float = 0.6
    enforce_target_quality: bool = False
    brand_settings: Optional[Dict[str, Any]] = None
    progress_callback: Any = None
    timeout_seconds: int = 240


@pytest.fixture
def state():
    return PipelineState(
        url="https://example.com/product",
        config=FakeConfig(),
        trace=JobTrace(url="https://example.com/product"),
        budget=StageBudget(total_s=120.0),
    )


HTML = """
<html><head>
  <title>Acme — Ship faster</title>
  <meta property="og:title" content="Acme ships faster than anyone">
  <meta property="og:description" content="The workspace that keeps every team aligned across every project they run.">
  <meta property="og:image" content="https://acme.test/og.png">
  <link rel="apple-touch-icon" href="/icon-180.png">
  <link rel="icon" href="/favicon.ico">
</head><body>
  <header><img class="logo" src="/logo.svg" alt="Acme logo"></header>
</body></html>
"""


class TestContracts:
    """Each stage's output is a typed object, not a growing pile of locals."""

    def test_capture_without_a_screenshot_is_still_usable(self):
        """A page that refuses a browser but serves markup makes a real card."""
        capture = CaptureResult(url="https://x.test", html="<html></html>")
        assert capture.ok
        assert not capture.has_screenshot

    def test_capture_with_nothing_is_not_usable(self):
        assert not CaptureResult(url="https://x.test").ok

    def test_a_tiny_screenshot_does_not_count(self):
        assert not CaptureResult(url="https://x.test", screenshot_bytes=b"x" * 100).has_screenshot

    def test_reasoning_round_trips_through_the_legacy_shape(self):
        """Code not yet on the contract still gets the dict it expects."""
        original = ReasoningResult(
            title="Ship faster", subtitle="Together",
            tags=["saas"], composition={"layout": "split"},
            confidence=0.9,
        )
        restored = ReasoningResult.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.composition == original.composition
        assert restored.confidence == original.confidence

    def test_reasoning_without_a_title_is_not_ok(self):
        assert not ReasoningResult(title="   ").ok

    def test_a_composition_spec_is_exactly_the_renderer_call(self):
        spec = CompositionSpec(title="T", url="https://x.test", size="square")
        kwargs = spec.render_kwargs()
        assert kwargs["title"] == "T"
        assert kwargs["size"] == "square"
        # Anything the renderer does not take would raise at the call site.
        assert set(kwargs) <= {
            "title", "subtitle", "url", "brand_name", "colors", "composition",
            "logo_data_uri", "visual_data_uri", "hide_watermark", "proof",
            "cta_text", "size",
        }


class TestLogoResolution:
    def test_gathers_candidates_in_priority_order(self):
        """Priority is about which logo is better, not which matched first: an
        apple-touch-icon is a deliberate brand asset, a favicon is whatever fit
        in 16 pixels."""
        from backend.services.preview.extraction.logo_resolver import collect_candidates

        candidates = collect_candidates(HTML, "https://acme.test/product")
        tiers = [c.tier for c in candidates]
        assert tiers[0] == "highres_icon"
        assert "favicon" in tiers or "default_favicon" in tiers
        assert all(c.url.startswith("https://acme.test/") for c in candidates)

    def test_a_favicon_win_is_recorded_as_a_fallback(self):
        from backend.services.preview.extraction.logo_resolver import (
            LogoCandidate,
            logo_degradation,
        )

        code, _ = logo_degradation(
            "data:image/png;base64,AAAA",
            LogoCandidate("https://x/favicon.ico", "favicon"),
            [],
        )
        assert code == Degradation.BRAND_LOGO_FALLBACK_FAVICON

    def test_a_header_logo_win_is_not_a_fallback(self):
        from backend.services.preview.extraction.logo_resolver import (
            LogoCandidate,
            logo_degradation,
        )

        code, _ = logo_degradation(
            "data:image/png;base64,AAAA",
            LogoCandidate("https://x/logo.png", "header_img"),
            [],
        )
        assert code.is_healthy

    def test_no_logo_is_recorded_as_such(self):
        from backend.services.preview.extraction.logo_resolver import logo_degradation

        code, _ = logo_degradation(None, None, [])
        assert code == Degradation.BRAND_LOGO_NONE

    def test_lazy_loaded_srcs_are_found(self):
        """Reading only ``src`` finds a 1px spacer on a lot of modern sites."""
        from bs4 import BeautifulSoup

        from backend.services.preview.extraction.logo_resolver import _candidate_srcs

        tag = BeautifulSoup(
            '<img src="data:image/gif;base64,R0lGOD" data-src="/real-logo.png">',
            "html.parser",
        ).img
        assert "/real-logo.png" in _candidate_srcs(tag)

    def test_srcset_prefers_the_widest_asset(self):
        from bs4 import BeautifulSoup

        from backend.services.preview.extraction.logo_resolver import _candidate_srcs

        tag = BeautifulSoup(
            '<img srcset="/small.png 100w, /large.png 800w, /mid.png 400w">',
            "html.parser",
        ).img
        assert _candidate_srcs(tag)[0] == "/large.png"


class TestComposition:
    def test_the_minimal_spec_needs_no_model(self, state):
        """Degradation means a simpler spec into the same renderer — this is
        what makes that true rather than aspirational."""
        from backend.services.preview.composition.builder import build_minimal_spec

        capture = CaptureResult(url=state.url, html=HTML)
        spec = build_minimal_spec(state, capture, BrandResult(brand_name="Acme"))

        assert spec.minimal
        assert spec.title == "Acme ships faster than anyone"   # the page's own og:title
        assert spec.composition["layout"] == "typographic"
        assert Degradation.COMPOSITION_MINIMAL_SPEC.value in state.trace.degradation_codes()

    def test_the_minimal_spec_falls_back_to_the_domain(self, state):
        from backend.services.preview.composition.builder import build_minimal_spec

        spec = build_minimal_spec(state, CaptureResult(url=state.url), BrandResult())
        assert spec.title == "Example"

    def test_a_layout_needing_a_visual_it_did_not_get_drops_the_panel(self, state):
        """Rendering an empty panel is worse than rendering a typographic card."""
        from backend.services.preview.composition.builder import build_spec

        spec = build_spec(
            state,
            CaptureResult(url=state.url, html=HTML),   # no screenshot to crop
            BrandResult(colors={"primary_color": "#0B3B2E"}),
            ReasoningResult(
                title="Ship faster",
                composition={"layout": "split", "use_visual": True,
                             "visual_source": "screenshot",
                             "visual_focus": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.4}},
            ),
        )
        assert spec.visual_data_uri is None
        assert spec.composition["use_visual"] is False

    def test_customer_overrides_beat_the_art_director(self, state):
        state.config.brand_settings = {
            "preview_layout": "editorial",
            "preview_panel": "dark",
            "preview_accent": "dot",
        }
        from backend.services.preview.composition.builder import build_spec

        spec = build_spec(
            state, CaptureResult(url=state.url, html=HTML),
            BrandResult(colors={"primary_color": "#0B3B2E"}),
            ReasoningResult(title="Ship faster", composition={"layout": "stat"}),
        )
        assert spec.composition["layout"] == "editorial"
        assert spec.composition["panel_color_role"] == "dark"
        assert spec.composition["accent_moment"] == "dot"

    def test_auto_means_the_art_director_decides(self, state):
        state.config.brand_settings = {"preview_layout": "auto", "preview_panel": "auto"}
        from backend.services.preview.composition.builder import build_spec

        spec = build_spec(
            state, CaptureResult(url=state.url, html=HTML),
            BrandResult(), ReasoningResult(title="T", composition={"layout": "stat"}),
        )
        assert spec.composition["layout"] == "stat"


class TestBrandExtraction:
    def test_a_typed_in_brand_name_beats_whatever_we_scraped(self, state):
        """They filled it in so we would stop guessing."""
        from backend.services.preview.extraction.brand import _apply_brand_settings

        state.config.brand_settings = {"brand_name": "Acme Corp"}
        result = _apply_brand_settings(state, BrandResult(brand_name="acme.test"))
        assert result.brand_name == "Acme Corp"

    def test_a_blank_brand_name_still_means_keep_inferring(self, state):
        from backend.services.preview.extraction.brand import _apply_brand_settings

        state.config.brand_settings = {"brand_name": "   "}
        result = _apply_brand_settings(state, BrandResult(brand_name="Scraped"))
        assert result.brand_name == "Scraped"

    def test_forced_brand_colors_are_recorded_as_an_override(self, state):
        from backend.services.preview.extraction.brand import _apply_brand_settings

        state.config.brand_settings = {
            "force_brand_colors": True, "primary_color": "#FF0000",
        }
        result = _apply_brand_settings(state, BrandResult(colors={"primary_color": "#0B3B2E"}))
        assert result.colors["primary_color"] == "#FF0000"
        assert Degradation.COMPOSITION_BRAND_OVERRIDES_APPLIED.value in \
               state.trace.degradation_codes()

    def test_the_legacy_dict_shape_is_preserved(self):
        """The rest of the app still passes brand_elements around."""
        from backend.services.preview.extraction.brand import to_legacy_dict

        legacy = to_legacy_dict(BrandResult(
            brand_name="Acme",
            logo_data_uri="data:image/png;base64,AAAA",
            colors={"primary_color": "#0B3B2E"},
        ))
        assert legacy["brand_name"] == "Acme"
        assert legacy["logo_base64"] == "AAAA"   # base64 payload, no data: prefix
        assert legacy["colors"]["primary_color"] == "#0B3B2E"


class TestReasoningFallback:
    def test_metadata_beats_a_placeholder_dict(self, state):
        """The stub that used to sit here is why every page rendered the same
        card; the page's own og: tags are real, specific copy."""
        from backend.services.preview.reasoning.stage import _from_page_metadata

        result = _from_page_metadata(state, CaptureResult(url=state.url, html=HTML),
                                     source="html")
        assert result.title == "Acme ships faster than anyone"
        assert result.subtitle.startswith("The workspace")
        assert result.source == "html"

    def test_metadata_copy_does_not_outrank_an_ai_read(self, state):
        """Real but not authored — the confidence has to say so."""
        from backend.services.preview.reasoning.stage import _from_page_metadata

        fallback = _from_page_metadata(state, CaptureResult(url=state.url, html=HTML),
                                       source="html")
        assert fallback.confidence < 0.5

    def test_the_template_lane_skips_the_model_entirely(self, state):
        from backend.services.preview.reasoning.stage import run_reasoning

        state.config.enable_ai_reasoning = False
        result = run_reasoning(state, CaptureResult(url=state.url, html=HTML))

        assert result.source == "template"
        assert result.title == "Acme ships faster than anyone"
        assert Degradation.REASONING_SKIPPED_TEMPLATE_LANE.value in \
               state.trace.degradation_codes()


class TestEngineSurface:
    def test_the_coordinator_stayed_small(self):
        """The acceptance bar was 500 lines; the file was 4,094."""
        from pathlib import Path

        import backend.services.preview_engine as engine

        lines = Path(engine.__file__).read_text().count("\n")
        assert lines < 500, f"preview_engine.py grew back to {lines} lines"

    def test_a_fallback_result_is_never_cached(self):
        """Caching one bad generation turns it into a day of bad generations."""
        from backend.services.preview_engine import (
            PreviewEngine,
            PreviewEngineConfig,
            PreviewEngineResult,
        )

        engine = PreviewEngine(PreviewEngineConfig(enforce_target_quality=True))
        result = PreviewEngineResult(
            url="https://x.test", title="T",
            quality_scores={"is_fallback": True, "overall": 0.95},
        )
        assert engine._is_cache_eligible_result(result) is False

    def test_a_below_target_result_is_not_cached_in_strict_mode(self):
        from backend.services.preview_engine import (
            PreviewEngine,
            PreviewEngineConfig,
            PreviewEngineResult,
        )

        engine = PreviewEngine(PreviewEngineConfig(
            enforce_target_quality=True, quality_threshold=0.88,
        ))
        result = PreviewEngineResult(
            url="https://x.test", title="T", quality_scores={"overall": 0.81},
        )
        assert engine._is_cache_eligible_result(result) is False

    def test_a_good_result_is_cached(self):
        from backend.services.preview_engine import (
            PreviewEngine,
            PreviewEngineConfig,
            PreviewEngineResult,
        )

        engine = PreviewEngine(PreviewEngineConfig(
            enforce_target_quality=True, quality_threshold=0.88,
        ))
        result = PreviewEngineResult(
            url="https://x.test", title="T",
            quality_scores={"overall": 0.92, "gate_status": "pass"},
        )
        assert engine._is_cache_eligible_result(result) is True

    def test_the_result_carries_its_degradation_trail(self):
        from backend.services.preview_engine import PreviewEngineResult

        result = PreviewEngineResult.from_payload({
            "url": "https://x.test", "title": "T",
            "_trace": {
                "job_id": "abc",
                "degradation_trail": "capture_ok → brand_logo_fallback_favicon",
            },
        })
        assert result.job_id == "abc"
        assert result.degradations == ["capture_ok", "brand_logo_fallback_favicon"]
