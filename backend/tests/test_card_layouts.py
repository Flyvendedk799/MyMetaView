"""Layout resolution, proof parsing, and re-render direction.

These cover the decisions made *around* the rasterizer — the parts that decide
what a card becomes. Actually rasterizing needs Chromium and is exercised by
hand; what matters here is that a layout never renders a panel it cannot fill or
a stat it does not have.
"""
import pytest

from backend.services.card_rerender import (
    DIRECTABLE_ACCENTS,
    DIRECTABLE_LAYOUTS,
    DIRECTABLE_PANELS,
    apply_direction,
    spec_is_renderable,
)
from backend.services.premium_card_renderer import (
    CARD_SIZES,
    LAYOUTS,
    get_card_size,
    resolve_layout,
    split_proof,
)


class TestResolveLayout:
    """A layout the assets cannot support must degrade, never render empty."""

    @pytest.mark.parametrize("layout", ["split", "product", "profile"])
    def test_visual_layouts_degrade_without_a_visual(self, layout):
        assert resolve_layout(layout, has_visual=False, has_proof=True) == "typographic"

    @pytest.mark.parametrize("layout", ["split", "product", "profile"])
    def test_visual_layouts_survive_with_a_visual(self, layout):
        assert resolve_layout(layout, has_visual=True, has_proof=False) == layout

    def test_stat_degrades_without_a_number(self):
        assert resolve_layout("stat", has_visual=True, has_proof=False) == "typographic"

    def test_stat_survives_with_a_number(self):
        assert resolve_layout("stat", has_visual=False, has_proof=True) == "stat"

    def test_editorial_needs_nothing(self):
        assert resolve_layout("editorial", has_visual=False, has_proof=False) == "editorial"

    @pytest.mark.parametrize("bogus", ["hologram", "", None, "SPLIT ", "3d"])
    def test_unknown_layouts_fall_back(self, bogus):
        # " SPLIT " normalises; the rest are genuinely unknown.
        assert resolve_layout(bogus, has_visual=True, has_proof=True) in LAYOUTS

    def test_case_and_whitespace_are_normalised(self):
        assert resolve_layout("  Editorial ", has_visual=False, has_proof=False) == "editorial"


class TestSplitProof:
    """The stat layout only works when a real quantity leads the proof string."""

    @pytest.mark.parametrize("proof,value", [
        ("Trusted by 50,000+ teams", "50,000+"),
        ("4.9★ from 2,847 reviews", "4.9★"),
        ("Featured in 12 publications", "12"),
        ("$2.4B processed annually", "$2.4B"),
        ("98% retention after year one", "98%"),
    ])
    def test_extracts_the_leading_quantity(self, proof, value):
        got, _ = split_proof(proof)
        assert got == value

    @pytest.mark.parametrize("proof", [
        "Trusted by teams everywhere",
        "Featured in TechCrunch",
        "Award winning design",
        "", None,
    ])
    def test_rejects_proof_with_no_number(self, proof):
        assert split_proof(proof) == ("", "")

    def test_keeps_the_descriptive_tail(self):
        _, label = split_proof("Trusted by 50,000+ engineering teams")
        assert "engineering teams" in label

    def test_a_proof_without_a_number_cannot_carry_a_stat_layout(self):
        """The two rules have to agree or a stat card renders with a blank hero."""
        proof = "Loved by developers"
        has_proof = bool(split_proof(proof)[0])
        assert has_proof is False
        assert resolve_layout("stat", has_visual=False, has_proof=has_proof) == "typographic"


class TestCardSizes:
    def test_wide_is_the_default_for_unknown_keys(self):
        assert get_card_size("nonsense").key == "wide"
        assert get_card_size(None).key == "wide"

    def test_only_the_wide_card_uses_columns(self):
        """Square and portrait must stack, or a split card gets two thin strips."""
        assert CARD_SIZES["wide"].is_tall is False
        assert CARD_SIZES["square"].is_tall is True
        assert CARD_SIZES["portrait"].is_tall is True

    def test_taller_cards_allow_longer_copy(self):
        wide, portrait = CARD_SIZES["wide"], CARD_SIZES["portrait"]
        assert portrait.title_limit >= wide.title_limit
        assert portrait.subtitle_limit > wide.subtitle_limit


class TestApplyDirection:
    BASE = {
        "composition": {"layout": "typographic", "use_visual": False,
                        "panel_color_role": "dark", "accent_moment": "bar"},
        "colors": {"primary": "#123456"},
    }

    def test_layout_override_is_applied(self):
        out = apply_direction(self.BASE, layout="editorial")
        assert out["composition"]["layout"] == "editorial"

    def test_switching_to_a_panel_layout_requests_the_visual(self):
        for layout in ("split", "product"):
            out = apply_direction(self.BASE, layout=layout)
            assert out["composition"]["use_visual"] is True

    def test_switching_away_from_a_panel_layout_drops_the_visual(self):
        spec = {"composition": {**self.BASE["composition"], "layout": "split", "use_visual": True}}
        out = apply_direction(spec, layout="stat")
        assert out["composition"]["use_visual"] is False

    def test_unknown_values_are_ignored_not_rejected(self):
        out = apply_direction(self.BASE, layout="hologram", panel="chartreuse", accent="fireworks")
        assert out["composition"]["layout"] == "typographic"
        assert out["composition"]["panel_color_role"] == "dark"
        assert out["composition"]["accent_moment"] == "bar"

    def test_the_original_spec_is_not_mutated(self):
        """The caller still needs the old spec if the render fails."""
        before = dict(self.BASE["composition"])
        apply_direction(self.BASE, layout="split", panel="light")
        assert self.BASE["composition"] == before

    def test_omitted_fields_are_left_alone(self):
        out = apply_direction(self.BASE, panel="light")
        assert out["composition"]["layout"] == "typographic"
        assert out["composition"]["accent_moment"] == "bar"
        assert out["composition"]["panel_color_role"] == "light"

    def test_non_composition_fields_survive(self):
        out = apply_direction(self.BASE, layout="stat")
        assert out["colors"] == {"primary": "#123456"}


class TestDirectableChoices:
    """What the UI offers must be what the renderer accepts."""

    def test_every_directable_layout_is_a_real_layout(self):
        assert set(DIRECTABLE_LAYOUTS) == set(LAYOUTS)

    def test_panel_and_accent_choices_are_non_empty(self):
        assert DIRECTABLE_PANELS and DIRECTABLE_ACCENTS


class TestSpecIsRenderable:
    def test_a_spec_with_a_composition_is_renderable(self):
        assert spec_is_renderable({"composition": {"layout": "split"}}) is True

    @pytest.mark.parametrize("spec", [None, {}, {"colors": {}}, {"composition": {}}, "nope"])
    def test_anything_else_is_not(self, spec):
        assert spec_is_renderable(spec) is False
