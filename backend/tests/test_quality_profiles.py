"""Tests for adaptive demo quality profile selection."""

from backend.services.quality_profiles import (
    estimate_url_complexity,
    get_cache_prefix_for_mode,
    get_quality_profile,
    resolve_quality_mode,
)


def test_explicit_mode_is_respected():
    assert resolve_quality_mode("fast", url="https://example.com/pricing") == "fast"
    assert resolve_quality_mode("balanced", url="https://example.com") == "balanced"
    assert resolve_quality_mode("ultra", url="https://example.com") == "ultra"


def test_auto_mode_selects_fast_for_simple_homepage():
    mode = resolve_quality_mode("auto", url="https://example.com")
    assert mode == "fast"
    assert get_cache_prefix_for_mode("auto", "https://example.com") == "demo:preview:v3:fast:"


def test_auto_mode_selects_balanced_for_medium_complexity_page():
    url = "https://example.com/about/services?utm_source=campaign"
    mode = resolve_quality_mode("auto", url=url)
    assert mode == "balanced"


def test_auto_mode_selects_ultra_for_high_complexity_page():
    url = "https://example.com/docs/platform/integrations/enterprise?tab=api&region=eu&lang=en#advanced"
    mode = resolve_quality_mode("auto", url=url)
    assert mode == "ultra"


def test_invalid_mode_falls_back_to_ultra():
    assert resolve_quality_mode("invalid", url="https://example.com") == "ultra"


def test_profile_shape_is_consistent():
    profile = get_quality_profile("balanced", url="https://example.com/features")
    assert profile.quality_mode == "balanced"
    assert profile.iterations == 3
    assert profile.threshold == 0.82


def test_complexity_heuristics_are_monotonic_enough_for_demo_selection():
    simple = estimate_url_complexity("https://example.com")
    medium = estimate_url_complexity("https://example.com/services/about")
    complex_url = "https://example.com/docs/platform/integrations/enterprise?tab=api&region=eu&lang=en"
    complex_score = estimate_url_complexity(complex_url)

    assert simple < medium
    assert medium <= complex_score
