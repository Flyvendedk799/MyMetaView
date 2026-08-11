"""Quick benchmark for adaptive demo quality mode selection."""

from __future__ import annotations

from statistics import mean

from backend.services.quality_profiles import get_quality_profile, resolve_quality_mode


SAMPLE_URLS = [
    "https://acme.com",
    "https://acme.com/pricing",
    "https://acme.com/features",
    "https://acme.com/about",
    "https://acme.com/blog/launching-our-platform",
    "https://acme.com/blog/engineering/how-we-scaled",
    "https://acme.com/docs/api",
    "https://acme.com/docs/platform/integrations/slack",
    "https://acme.com/docs/platform/integrations/salesforce?tab=setup&region=eu",
    "https://acme.com/enterprise",
    "https://acme.com/solutions/fintech",
    "https://acme.com/product/analytics-dashboard?plan=pro&annual=true",
]


def run() -> None:
    baseline_iterations = [4 for _ in SAMPLE_URLS]  # previous default was ultra everywhere
    adaptive_iterations = []
    adaptive_modes = []

    for url in SAMPLE_URLS:
        mode = resolve_quality_mode("auto", url=url)
        profile = get_quality_profile(mode, url=url)
        adaptive_modes.append(mode)
        adaptive_iterations.append(profile.iterations)

    baseline_avg = mean(baseline_iterations)
    adaptive_avg = mean(adaptive_iterations)
    reduction = ((baseline_avg - adaptive_avg) / baseline_avg) * 100.0

    # Relative latency proxy: iterations are a major contributor in quality-loop stages.
    # We keep this explicit as a proxy, not a wall-clock benchmark.
    print("Adaptive demo profile benchmark")
    print("--------------------------------")
    print(f"sample_count={len(SAMPLE_URLS)}")
    print(f"baseline_mode=ultra")
    print(f"baseline_avg_iterations={baseline_avg:.2f}")
    print(f"adaptive_avg_iterations={adaptive_avg:.2f}")
    print(f"iteration_reduction_pct={reduction:.2f}")
    print(f"mode_distribution={{'fast': {adaptive_modes.count('fast')}, 'balanced': {adaptive_modes.count('balanced')}, 'ultra': {adaptive_modes.count('ultra')}}}")


if __name__ == "__main__":
    run()
