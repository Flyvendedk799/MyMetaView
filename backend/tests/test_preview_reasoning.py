"""Tests for preview_reasoning.py - prompt output parsing and stage orchestration."""
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _closed_breaker():
    """The reasoning breaker is now shared across stages and processes.

    A test that simulates a failure would otherwise leave it open and every
    later test in the file would skip its model call and take the fallback.
    """
    from backend.services.reasoning_client import reasoning_breaker

    reasoning_breaker().reset()
    yield
    reasoning_breaker().reset()


class TestStage123OutputParsing:
    """Test that Stage 1-2-3 outputs are correctly parsed."""

    def test_parses_valid_json_response(self, sample_screenshot_bytes, sample_stage_1_2_3_response):
        """Stage 1-2-3 should parse a valid JSON response correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_stage_1_2_3_response)

        with patch('backend.services.preview_reasoning.get_client') as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            from backend.services.preview_reasoning import run_stages_1_2_3
            regions, palette, page_type, confidence, highlights, design_dna = run_stages_1_2_3(sample_screenshot_bytes)

        assert page_type == "saas"
        assert confidence == 0.92
        assert highlights["the_hook"] == "Build Better Software"
        assert highlights["social_proof_found"] == "Trusted by 50,000+ developers worldwide"
        assert highlights["key_benefit"] == "Ship 10x faster with AI-powered development tools"
        assert len(regions) == 2
        assert design_dna["style"] == "minimalist"

    def test_handles_json_in_code_block(self, sample_screenshot_bytes, sample_stage_1_2_3_response):
        """Should extract JSON from markdown code blocks."""
        wrapped = f"```json\n{json.dumps(sample_stage_1_2_3_response)}\n```"
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = wrapped

        with patch('backend.services.preview_reasoning.get_client') as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            from backend.services.preview_reasoning import run_stages_1_2_3
            regions, palette, page_type, confidence, highlights, design_dna = run_stages_1_2_3(sample_screenshot_bytes)

        assert page_type == "saas"
        assert highlights["the_hook"] == "Build Better Software"

    def test_handles_malformed_json_gracefully(self, sample_screenshot_bytes):
        """Should return fallback structure for invalid JSON."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not JSON at all"

        with patch('backend.services.preview_reasoning.get_client') as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            from backend.services.preview_reasoning import run_stages_1_2_3
            regions, palette, page_type, confidence, highlights, design_dna = run_stages_1_2_3(sample_screenshot_bytes)

        assert page_type == "unknown"
        assert confidence == 0.3

    def test_backward_compatible_field_names(self, sample_screenshot_bytes):
        """New field names (primary_headline) should map to old names (the_hook)."""
        response_data = {
            "page_type": "saas",
            "primary_headline": "New Field Name",
            "credibility_signals": "Trust data",
            "value_statement": "Value data",
            "regions": [],
            "detected_palette": {"primary": "#000", "secondary": "#fff", "accent": "#f00"},
            "detected_logo": {},
            "design_dna": {},
            "analysis_confidence": 0.8
        }
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)

        with patch('backend.services.preview_reasoning.get_client') as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            from backend.services.preview_reasoning import run_stages_1_2_3
            _, _, _, _, highlights, _ = run_stages_1_2_3(sample_screenshot_bytes)

        assert highlights["the_hook"] == "New Field Name"
        assert highlights["social_proof_found"] == "Trust data"
        assert highlights["key_benefit"] == "Value data"


class TestStage456MergedOutput:
    """Test merged stages 4-5-6 output parsing."""

    def test_parses_merged_layout_and_quality(self):
        """Merged stage should return both layout and quality scores."""
        response_data = {
            "composition_decisions": [
                {"region_id": "r1", "include": True, "slot_assignment": "headline", "decision_reasoning": "Main title"},
            ],
            "layout": {
                "template_style": "professional",
                "headline_slot": "r1",
                "visual_slot": None,
                "proof_slot": None,
                "benefit_slot": None,
                "cta_slot": None,
            },
            "layout_reasoning": "Clean professional layout",
            "preview_strength": "moderate",
            "accuracy_score": 0.85,
            "clarity_score": 0.80,
            "engagement_score": 0.70,
            "design_fidelity_score": 0.75,
            "overall_quality": "good",
            "improvement_suggestions": ["Add social proof"]
        }
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)

        with patch('backend.services.preview_reasoning.get_client') as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            from backend.services.preview_reasoning import run_stages_4_5_6, _extract_quality_from_merged
            regions = [{"id": "r1", "raw_content": "Test", "visual_weight": "hero"}]
            result = run_stages_4_5_6(regions, "saas", {"primary": "#000", "secondary": "#fff", "accent": "#f00"})

        # Layout should be normalized with backward compat
        assert "identity_slot" in result["layout"]
        assert result["layout"]["identity_slot"] == "r1"

        # Quality extraction
        quality = _extract_quality_from_merged(result)
        assert quality["coherence_score"] == 0.85
        assert quality["clarity_score"] == 0.80
        assert quality["design_fidelity_score"] == 0.75
        assert quality["overall_quality"] == "good"


class TestPurposeNormalization:
    """Test purpose string normalization."""

    def test_normalizes_new_purpose_values(self):
        from backend.services.preview_reasoning import _normalize_purpose, RegionPurpose

        assert _normalize_purpose("headline") == RegionPurpose.VALUE_PROP
        assert _normalize_purpose("credibility") == RegionPurpose.CREDIBILITY
        assert _normalize_purpose("value") == RegionPurpose.VALUE_PROP
        assert _normalize_purpose("identity") == RegionPurpose.IDENTITY
        assert _normalize_purpose("filler") == RegionPurpose.DECORATION
        assert _normalize_purpose("action") == RegionPurpose.ACTION

    def test_handles_old_purpose_values(self):
        from backend.services.preview_reasoning import _normalize_purpose, RegionPurpose

        assert _normalize_purpose("hook") == RegionPurpose.VALUE_PROP
        assert _normalize_purpose("proof") == RegionPurpose.CREDIBILITY
        assert _normalize_purpose("benefit") == RegionPurpose.VALUE_PROP
        assert _normalize_purpose("decoration") == RegionPurpose.DECORATION

    def test_handles_unknown_purpose(self):
        from backend.services.preview_reasoning import _normalize_purpose, RegionPurpose

        assert _normalize_purpose("unknown_value") == RegionPurpose.DECORATION


class TestSmartTruncation:
    """Test smart text truncation."""

    def test_preserves_short_text(self):
        from backend.services.preview_reasoning import smart_truncate_text

        assert smart_truncate_text("Short text", 100) == "Short text"

    def test_truncates_at_sentence_boundary(self):
        from backend.services.preview_reasoning import smart_truncate_text

        text = "First sentence. Second sentence. Third sentence is very long."
        result = smart_truncate_text(text, 40)
        assert "First sentence." in result or len(result) <= 43

    def test_handles_none_input(self):
        from backend.services.preview_reasoning import smart_truncate_text

        assert smart_truncate_text(None, 100) is None
        assert smart_truncate_text("", 100) == ""
