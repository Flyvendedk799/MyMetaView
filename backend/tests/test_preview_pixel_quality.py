"""The rendered PNG is the unit of quality — these tests hold that line.

Every failure asserted here is one that shipped: a gradient with no type on it,
a headline the same colour as its panel, copy running off the canvas, a logo
that is invisible where it was placed, a hero crop that grabbed the nav bar. All
of them passed the dict-level checks that came before, which is the whole
argument for measuring the artefact instead.
"""

from __future__ import annotations

import glob
from io import BytesIO

import pytest

from backend.services.preview.quality import (
    SoftPassPolicy,
    detect_gradient_only,
    evaluate_card,
    score_card,
)


def _font(size: int):
    from PIL import ImageFont

    paths = sorted(glob.glob("/usr/share/fonts/truetype/liberation/*Sans-Bold.ttf"))
    if not paths:
        pytest.skip("no TrueType font available to draw test cards")
    return ImageFont.truetype(paths[0], size)


def _png(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def real_card():
    """A card that looks like the product: dark panel, light type, an accent."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 630), (11, 59, 46))
    draw = ImageDraw.Draw(image)
    draw.text((70, 78), "EXAMPLE.COM / PRODUCT", font=_font(20), fill=(150, 170, 164))
    draw.text((70, 180), "Ship faster with", font=_font(64), fill=(251, 251, 249))
    draw.text((70, 262), "one shared source", font=_font(64), fill=(251, 251, 249))
    draw.rectangle([70, 372, 134, 377], fill=(232, 98, 44))
    draw.text((70, 402), "The workspace that keeps every team aligned",
              font=_font(24), fill=(150, 170, 164))
    return _png(image)


@pytest.fixture
def gradient_card():
    """The 6.5 regression: a handsome gradient with nothing written on it."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 630))
    draw = ImageDraw.Draw(image)
    for y in range(630):
        t = y / 630
        draw.line([(0, y), (1200, y)],
                  fill=(int(11 + t * 40), int(59 + t * 30), int(46 + t * 20)))
    return _png(image)


class TestGradientOnlyDetector:
    """The regression class that must never ship silently again."""

    def test_flags_a_gradient_with_no_content(self, gradient_card):
        assert detect_gradient_only(gradient_card) is True

    def test_flags_a_flat_panel_with_no_content(self):
        from PIL import Image

        assert detect_gradient_only(_png(Image.new("RGB", (1200, 630), (11, 59, 46)))) is True

    def test_does_not_flag_a_real_card(self, real_card):
        assert detect_gradient_only(real_card) is False

    def test_does_not_flag_a_deliberately_spare_card(self):
        """One huge word on a flat panel is a design, not a defect."""
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1200, 630), (11, 59, 46))
        ImageDraw.Draw(image).text((70, 250), "Notion", font=_font(64), fill=(251, 251, 249))
        assert detect_gradient_only(_png(image)) is False


class TestContrastMeasurement:
    def test_reads_real_contrast_on_a_dark_panel(self, real_card):
        score = score_card(real_card, expect_logo=False)
        # Near-white on deep green is ~13:1; anti-aliasing pulls it down a little.
        assert score.title_contrast > 8.0

    def test_finds_sparse_thin_type(self, real_card):
        """The eyebrow crosses ~1% of its band; a fixed decile misses it entirely
        and reports every card at the same wrong number."""
        score = score_card(real_card, expect_logo=False)
        assert 3.0 < score.eyebrow_contrast < 8.0

    def test_catches_invisible_text(self):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1200, 630), (251, 251, 249))
        ImageDraw.Draw(image).text((70, 250), "Invisible", font=_font(64), fill=(250, 250, 248))
        score = score_card(_png(image), expect_logo=False)
        assert score.title_contrast < 2.0
        assert score.passed is False


class TestOverflow:
    def test_clean_card_has_no_overflow(self, real_card):
        assert score_card(real_card, expect_logo=False).overflow_risk < 0.05

    def test_ink_at_the_edge_is_overflow(self):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1200, 630), (251, 251, 249))
        ImageDraw.Draw(image).rectangle([70, 200, 1199, 280], fill=(11, 31, 24))
        assert score_card(_png(image), expect_logo=False).overflow_risk > 0.2


class TestVerdicts:
    def test_a_good_card_passes(self, real_card):
        verdict = evaluate_card(real_card, policy=SoftPassPolicy(threshold=0.75),
                                expect_logo=False)
        assert verdict.decision == "pass"
        assert verdict.shippable

    def test_a_broken_card_retries_when_there_is_budget(self, gradient_card):
        verdict = evaluate_card(gradient_card, policy=SoftPassPolicy(),
                                attempts_left=1, expect_logo=False)
        assert verdict.decision == "retry"
        assert not verdict.shippable

    def test_a_broken_card_is_rejected_when_there_is_not(self, gradient_card):
        verdict = evaluate_card(gradient_card, policy=SoftPassPolicy(),
                                attempts_left=0, expect_logo=False)
        assert verdict.decision == "reject"

    def test_a_weak_but_whole_card_soft_passes(self, real_card):
        """Below target but not broken: a real card beats a generic fallback."""
        verdict = evaluate_card(
            real_card,
            policy=SoftPassPolicy(threshold=0.99, min_soft_pass_overall=0.5),
            expect_logo=False,
        )
        assert verdict.decision == "soft_pass"
        assert verdict.shippable

    def test_a_broken_card_never_soft_passes(self, gradient_card):
        """No threshold argues an unreadable card into acceptability."""
        verdict = evaluate_card(
            gradient_card,
            policy=SoftPassPolicy(threshold=0.0, min_soft_pass_overall=0.0),
            expect_logo=False,
        )
        assert not verdict.shippable


class TestLogoContrast:
    """A white logo on a white panel is a real failure this card used to ship."""

    def _logo(self, rgb):
        import base64

        from PIL import Image

        return "data:image/png;base64," + base64.b64encode(
            _png(Image.new("RGB", (120, 40), rgb))
        ).decode()

    def test_swaps_the_panel_when_the_mark_would_vanish(self):
        from backend.services.preview.assets import resolve_logo_contrast

        fix = resolve_logo_contrast(
            self._logo((255, 255, 255)),
            panel_hex="#FBFBF9", panel_color_role="light",
            alternate_panel_hex="#0B3B2E", alternate_role="primary",
        )
        assert fix.changed
        assert fix.panel_color_role == "primary"
        assert fix.logo_data_uri is not None  # the mark is kept, the panel moves

    def test_leaves_a_visible_mark_alone(self):
        from backend.services.preview.assets import resolve_logo_contrast

        fix = resolve_logo_contrast(
            self._logo((255, 255, 255)),
            panel_hex="#0B3B2E", panel_color_role="primary",
            alternate_panel_hex="#FBFBF9",
        )
        assert not fix.changed
        assert fix.ratio > 2.0

    def test_falls_back_to_a_plate_when_no_panel_works(self):
        from backend.services.preview.assets import resolve_logo_contrast

        # A mid-grey mark against two panels it reads poorly on.
        fix = resolve_logo_contrast(
            self._logo((128, 132, 130)),
            panel_hex="#7A7E7C", panel_color_role="primary",
            alternate_panel_hex="#8A8E8C", alternate_role="secondary",
        )
        assert fix.needs_plate
        assert fix.plate_color in ("#FBFBF9", "#0B1F18")

    def test_a_missing_logo_is_not_a_contrast_problem(self):
        from backend.services.preview.assets import resolve_logo_contrast

        fix = resolve_logo_contrast(None, panel_hex="#0B3B2E")
        assert fix.logo_data_uri is None
        assert not fix.changed


class TestFocalCropQA:
    """The art director's focus box is a request, not a fact."""

    @pytest.fixture
    def page(self):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1400, 2000), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, 1400, 90], fill=(245, 245, 247))     # flat nav
        for i in range(18):                                          # busy hero
            draw.rectangle([200 + i * 55, 400 + (i % 5) * 70,
                            240 + i * 55, 600 + (i % 5) * 70],
                           fill=(30 + i * 10, 90, 200 - i * 8))
        draw.text((200, 300), "Real hero content", font=_font(40), fill=(10, 10, 10))
        return _png(image)

    def test_accepts_a_genuine_hero_region(self, page):
        from backend.services.preview.assets import crop_focus

        result = crop_focus(page, {"x": 0.12, "y": 0.15, "width": 0.76, "height": 0.30})
        assert result.accepted
        assert result.data_uri

    def test_rejects_a_nav_bar(self, page):
        from backend.services.preview.assets import crop_focus

        result = crop_focus(page, {"x": 0.0, "y": 0.0, "width": 1.0, "height": 0.045})
        assert not result.accepted
        assert "chrome" in result.reason or "small" in result.reason

    def test_rejects_empty_background(self, page):
        from backend.services.preview.assets import crop_focus

        result = crop_focus(page, {"x": 0.05, "y": 0.85, "width": 0.9, "height": 0.12})
        assert not result.accepted

    def test_accepts_absolute_pixel_boxes(self, page):
        """The model returns either convention and rejecting one silently
        disabled the split layout."""
        from backend.services.preview.assets import crop_focus

        assert crop_focus(page, {"x": 200, "y": 300, "width": 800, "height": 500}).accepted

    def test_missing_inputs_do_not_raise(self):
        from backend.services.preview.assets import crop_focus

        assert not crop_focus(None, {"x": 0, "y": 0, "width": 1, "height": 1}).accepted
        assert not crop_focus(b"not an image", {"x": 0, "y": 0, "width": 1, "height": 1}).accepted
