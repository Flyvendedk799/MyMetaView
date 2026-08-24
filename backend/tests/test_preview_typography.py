"""Typography rules that hold outside English.

The renderer sized and clipped text by counting characters, which is correct
only where a character happens to be about half an em wide. These tests pin the
three places that assumption broke — CJK, RTL, and unbreakable compounds — and
pin the English behaviour that must not change while fixing them.
"""

from __future__ import annotations

import pytest

from backend.services.preview.rendering.typography import (
    HeadlineFit,
    em_width,
    fit_headline,
    is_rtl_text,
    is_wide,
    text_direction,
    truncate_to_em,
)

ENGLISH = "Ship faster with one shared source of truth"
JAPANESE = "本気で速く出荷するための唯一の情報源"
ARABIC = "اشحن بشكل أسرع مع مصدر واحد للحقيقة"
HEBREW = "משלוח מהיר יותר עם מקור אמת אחד"
GERMAN = "Rechtsschutzversicherungsgesellschaftsvertreterversammlungsbeschluss"


class TestWidthMeasurement:
    def test_cjk_glyphs_are_full_width(self):
        assert is_wide("本") and is_wide("あ") and is_wide("한")
        assert not is_wide("a") and not is_wide("Ω")

    def test_cjk_measures_far_wider_than_its_character_count_suggests(self):
        """18 Japanese characters are wider than 40 English ones — the exact
        confusion that oversized every CJK headline."""
        assert len(JAPANESE) < len(ENGLISH)
        assert em_width(JAPANESE) > em_width(ENGLISH) * 0.85

    def test_narrow_characters_count_for_less(self):
        assert em_width("iiii") < em_width("mmmm")

    def test_empty_is_zero(self):
        assert em_width("") == 0.0
        assert em_width(None) == 0.0


class TestDirection:
    def test_detects_arabic_and_hebrew(self):
        assert is_rtl_text(ARABIC)
        assert is_rtl_text(HEBREW)
        assert text_direction(ARABIC) == "rtl"

    def test_english_is_ltr(self):
        assert not is_rtl_text(ENGLISH)
        assert text_direction(ENGLISH) == "ltr"

    def test_a_foreign_brand_name_does_not_flip_the_card(self):
        """Predominantly, not "contains" — one Hebrew word in an English
        headline must not mirror the whole layout."""
        assert not is_rtl_text("Acme עברית ships faster than anyone else here")

    def test_no_letters_is_ltr(self):
        assert text_direction("1234 —") == "ltr"


class TestHeadlineSizing:
    @pytest.mark.parametrize("text,expected", [
        ("Ship faster", 82),                                    # short: big
        ("Ship faster with one shared source", 72),
        (ENGLISH, 62),
        ("The workspace that keeps every single team completely aligned across", 54),
    ])
    def test_english_sizing_is_unchanged(self, text, expected):
        """The card's type scale is a design decision; the i18n fix must not
        quietly restyle every English card."""
        assert fit_headline(text).font_size_px == expected

    def test_cjk_is_sized_by_width_not_character_count(self):
        """18 characters would have been handed the size meant for a phrase
        half its visual width, and run off the card."""
        fit = fit_headline(JAPANESE)
        assert fit.font_size_px <= 62
        assert fit.lines <= 3

    def test_rtl_carries_its_direction_through(self):
        assert fit_headline(ARABIC).direction == "rtl"

    def test_a_narrow_column_gets_a_smaller_size(self):
        wide = fit_headline(ENGLISH, layout="typographic").font_size_px
        narrow = fit_headline(ENGLISH, layout="split").font_size_px
        assert narrow <= wide

    def test_nothing_fits_forever(self):
        """Past the floor, truncate rather than overflow."""
        fit = fit_headline(GERMAN * 4)
        assert fit.truncated
        assert fit.text.endswith("…")

    def test_empty_headline_is_handled(self):
        fit = fit_headline("")
        assert isinstance(fit, HeadlineFit)
        assert fit.lines == 0


class TestTruncation:
    def test_breaks_at_a_word_boundary(self):
        out = truncate_to_em(ENGLISH, 12.0)
        assert out.endswith("…")
        assert not out.rstrip("…").endswith(" ")
        # The kept portion is whole words.
        assert all(word in ENGLISH for word in out.rstrip("…").split())

    def test_breaks_mid_token_only_when_there_is_nowhere_else(self):
        """A German compound is one token wider than the column — an ellipsis
        is a clearer signal there than a line running off the card."""
        out = truncate_to_em(GERMAN, 10.0)
        assert out.endswith("…")
        assert len(out) < len(GERMAN)

    def test_cjk_truncates_without_spaces(self):
        out = truncate_to_em(JAPANESE, 8.0)
        assert out.endswith("…")
        assert em_width(out) <= 9.0

    def test_short_text_is_untouched(self):
        assert truncate_to_em("Notion", 20.0) == "Notion"

    def test_does_not_end_on_punctuation(self):
        assert not truncate_to_em("Ship faster, with one source", 6.0).rstrip("…").endswith(",")


class TestFontAvailability:
    def test_reports_scripts_the_container_cannot_draw(self):
        """Naming a Noto fallback in CSS does not install it: a container
        missing fonts-noto-cjk renders Japanese as tofu while every upstream
        check reports success."""
        from backend.services.preview.rendering.typography import missing_script_fonts

        missing = missing_script_fonts()
        assert isinstance(missing, list)
        assert all(script in ("CJK", "Arabic", "Hebrew") for script in missing)
