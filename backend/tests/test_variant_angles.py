"""Variants must be different arguments, not reworded copies.

The bug this replaces: variant C was a byte-for-byte copy of A, B was A cut to
150 characters, and all three shared one image — sold as an A/B feature on
Growth and above. A test that only checked "three variants exist" would have
passed on that, so these assert the thing that actually matters: distinctness.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.services.preview_reasoning import _parse_variants


MAIN = "Ship 10x faster with AI pair programming"


class TestParseVariants:
    def test_keeps_a_genuinely_different_angle(self):
        out = _parse_variants(
            [{"angle": "proof", "title": "Trusted by 50,000 engineering teams"}],
            main_title=MAIN,
        )
        assert len(out) == 1
        assert out[0]["angle"] == "proof"

    def test_drops_an_exact_copy_of_the_main_title(self):
        assert _parse_variants([{"title": MAIN}], main_title=MAIN) == []

    def test_drops_a_copy_differing_only_in_case_and_punctuation(self):
        assert _parse_variants(
            [{"title": "ship 10x faster with AI pair programming!"}], main_title=MAIN
        ) == []

    def test_drops_a_truncation_of_the_main_title(self):
        """Exactly what the old code produced for variant B."""
        assert _parse_variants([{"title": MAIN[:28]}], main_title=MAIN) == []

    def test_drops_a_duplicate_of_an_earlier_variant(self):
        out = _parse_variants(
            [
                {"angle": "proof", "title": "Trusted by 50,000 engineering teams"},
                {"angle": "benefit", "title": "Trusted by 50,000 engineering teams"},
            ],
            main_title=MAIN,
        )
        assert len(out) == 1

    def test_caps_at_two_alternatives(self):
        """Variant A is the main card, so B and C are all there is room for."""
        out = _parse_variants(
            [
                {"title": "Trusted by 50,000 engineering teams"},
                {"title": "Why your test suite slows every sprint"},
                {"title": "Cut code review time by half"},
            ],
            main_title=MAIN,
        )
        assert len(out) == 2

    @pytest.mark.parametrize("title", ["", "Short", "x" * 200])
    def test_drops_unusable_titles(self, title):
        assert _parse_variants([{"title": title}], main_title=MAIN) == []

    def test_unknown_angle_becomes_alternate(self):
        out = _parse_variants(
            [{"angle": "vibes", "title": "Why your test suite slows every sprint"}],
            main_title=MAIN,
        )
        assert out[0]["angle"] == "alternate"

    @pytest.mark.parametrize("raw", [None, "not a list", {}, 42])
    def test_malformed_payloads_yield_nothing(self, raw):
        assert _parse_variants(raw, main_title=MAIN) == []

    def test_non_dict_entries_are_skipped(self):
        out = _parse_variants(
            ["just a string", {"title": "Why your test suite slows every sprint"}],
            main_title=MAIN,
        )
        assert len(out) == 1

    def test_subtitle_is_carried_and_bounded(self):
        out = _parse_variants(
            [{"title": "Trusted by 50,000 engineering teams", "subtitle": "y" * 400}],
            main_title=MAIN,
        )
        assert len(out[0]["subtitle"]) <= 120


class TestPipelineVariants:
    """The rows the pipeline writes, given what the director returned."""

    def _write_variants(self, variants, spec=None, rerendered="https://r2/variant.png"):
        from backend.jobs import preview_pipeline

        db = MagicMock()
        preview = MagicMock(id=7)
        with patch.object(preview_pipeline, "PreviewVariantModel") as Model, \
                patch.object(preview_pipeline, "rerender_card",
                             return_value=(rerendered, "stat")):
            Model.side_effect = lambda **kw: kw
            preview_pipeline._replace_variants(
                db,
                preview=preview,
                main_title=MAIN,
                main_description="A description",
                main_image_url="https://r2/main.png",
                keywords="ai,devtools",
                variants=variants,
                render_spec=spec if spec is not None else {"composition": {"layout": "stat"}},
                url="https://acme.com",
            )
        return [call.args[0] for call in db.add.call_args_list]

    def test_variant_a_mirrors_the_main_card(self):
        rows = self._write_variants([])
        assert len(rows) == 1
        assert rows[0]["variant_key"] == "a"
        assert rows[0]["angle"] == "main"
        assert rows[0]["title"] == MAIN
        assert rows[0]["image_url"] == "https://r2/main.png"

    def test_each_alternative_gets_its_own_rendered_card(self):
        rows = self._write_variants([
            {"angle": "proof", "title": "Trusted by 50,000 engineering teams"},
            {"angle": "curiosity", "title": "Why your test suite slows every sprint"},
        ])
        assert [r["variant_key"] for r in rows] == ["a", "b", "c"]
        # The whole point: B and C are not the main image.
        assert rows[1]["image_url"] == "https://r2/variant.png"
        assert rows[2]["image_url"] == "https://r2/variant.png"

    def test_no_two_variants_share_a_title(self):
        rows = self._write_variants([
            {"angle": "proof", "title": "Trusted by 50,000 engineering teams"},
            {"angle": "curiosity", "title": "Why your test suite slows every sprint"},
        ])
        titles = [r["title"] for r in rows]
        assert len(set(titles)) == len(titles)

    def test_a_failed_render_falls_back_to_the_main_card(self):
        """Better the right copy on the main image than a broken image."""
        rows = self._write_variants(
            [{"angle": "proof", "title": "Trusted by 50,000 engineering teams"}],
            rerendered=None,
        )
        assert rows[1]["image_url"] == "https://r2/main.png"

    def test_old_variants_are_cleared_before_writing(self):
        """A regeneration produces new angles; stale rows would describe cards
        that no longer exist."""
        from backend.jobs import preview_pipeline

        db = MagicMock()
        with patch.object(preview_pipeline, "PreviewVariantModel"), \
                patch.object(preview_pipeline, "rerender_card", return_value=(None, None)):
            preview_pipeline._replace_variants(
                db, preview=MagicMock(id=7), main_title=MAIN, main_description="d",
                main_image_url="u", keywords=None, variants=[], render_spec={},
                url="https://acme.com",
            )
        db.query.return_value.filter.return_value.delete.assert_called_once()

    def test_titles_without_content_are_skipped(self):
        rows = self._write_variants([{"angle": "proof", "title": "   "}])
        assert len(rows) == 1  # main only
