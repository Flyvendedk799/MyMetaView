"""Tests for preview_engine 400% optimization: parallelization, caching, early exits."""

import pytest
from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig


class TestHasRichOgMetadata:
    """Tests for OG-rich early exit detection."""

    def test_detects_rich_og_metadata(self):
        """Pages with og:title, og:description, og:image trigger fast path."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        html = """
        <html><head>
        <meta property="og:title" content="My Great Product - Best in Class">
        <meta property="og:description" content="This is a comprehensive description that has at least forty characters in it for the threshold.">
        <meta property="og:image" content="https://example.com/image.png">
        </head></html>
        """
        assert engine._has_rich_og_metadata(html) is True

    def test_rejects_short_title(self):
        """Short og:title does not qualify."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        html = """
        <html><head>
        <meta property="og:title" content="Short">
        <meta property="og:description" content="This is a comprehensive description that has at least forty characters in it for the threshold.">
        <meta property="og:image" content="https://example.com/image.png">
        </head></html>
        """
        assert engine._has_rich_og_metadata(html) is False

    def test_rejects_short_description(self):
        """Short og:description does not qualify."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        html = """
        <html><head>
        <meta property="og:title" content="My Great Product - Best in Class">
        <meta property="og:description" content="Too short">
        <meta property="og:image" content="https://example.com/image.png">
        </head></html>
        """
        assert engine._has_rich_og_metadata(html) is False

    def test_rejects_missing_image(self):
        """Missing og:image does not qualify."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        html = """
        <html><head>
        <meta property="og:title" content="My Great Product - Best in Class">
        <meta property="og:description" content="This is a comprehensive description that has at least forty characters in it for the threshold.">
        </head></html>
        """
        assert engine._has_rich_og_metadata(html) is False

    def test_handles_content_before_property_order(self):
        """Alternate meta order content=... property=... is supported."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        html = """
        <html><head>
        <meta content="My Great Product - Best in Class" property="og:title">
        <meta content="This is a comprehensive description that has at least forty characters in it for the threshold." property="og:description">
        <meta content="https://example.com/image.png" property="og:image">
        </head></html>
        """
        assert engine._has_rich_og_metadata(html) is True

    def test_empty_html_returns_false(self):
        """Empty or minimal HTML returns False."""
        config = PreviewEngineConfig(is_demo=True)
        engine = PreviewEngine(config)
        assert engine._has_rich_og_metadata("") is False
        assert engine._has_rich_og_metadata("<html></html>") is False


class TestOrchestratorResultIsUsable:
    """The multi-agent orchestrator may only skip the art director when it
    actually replaces it.

    The card is only page-specific because the art director hands the renderer a
    composition — layout, whether to use a visual, which colour carries the
    panel. A result without one renders from neutral defaults, which is the same
    card for every site: the "it just looks like a template" bug.
    """

    def test_rejects_result_with_no_composition_spec(self):
        assert PreviewEngine._orchestrator_result_is_usable({
            "title": "Acme — Ship Faster",
            "composition": {},
        }) is False

    def test_rejects_result_missing_composition_entirely(self):
        assert PreviewEngine._orchestrator_result_is_usable({
            "title": "Acme — Ship Faster",
        }) is False

    def test_rejects_composition_that_is_not_a_dict(self):
        assert PreviewEngine._orchestrator_result_is_usable({
            "title": "Acme — Ship Faster",
            "composition": "split",
        }) is False

    def test_rejects_placeholder_title(self):
        assert PreviewEngine._orchestrator_result_is_usable({
            "title": "Untitled",
            "composition": {"layout": "split", "use_visual": True},
        }) is False

    def test_accepts_a_complete_result(self):
        assert PreviewEngine._orchestrator_result_is_usable({
            "title": "Acme — Ship Faster",
            "composition": {"layout": "split", "use_visual": True},
        }) is True


class TestMultiAgentIsOffByDefault:
    def test_default_config_does_not_enable_the_orchestrator(self):
        """Production reached it only by inheriting a True default."""
        assert PreviewEngineConfig().enable_multi_agent is False

    def test_default_config_keeps_ai_reasoning_on(self):
        assert PreviewEngineConfig().enable_ai_reasoning is True
