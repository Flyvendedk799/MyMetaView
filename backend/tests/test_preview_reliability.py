"""Reliability: what the engine refuses, what it retries, what it gives up on.

Three policies that were previously implicit in exception strings and a single
600-second timeout, and are now decisions a test can make assertions about.
"""

from __future__ import annotations

import pytest

from backend.services.preview.budgets import StageBudget, run_with_deadline
from backend.services.preview.observability.reason_codes import (
    Degradation,
    FailureReason,
    PreviewLane,
    Stage,
    is_transient,
)
from backend.services.preview.retry import decide_retry, idempotency_key


class TestSSRFGuard:
    """The engine fetches URLs a user typed, from inside our network."""

    def test_refuses_loopback(self):
        from backend.services.preview.net import SSRFError, guard_url

        with pytest.raises(SSRFError):
            guard_url("http://127.0.0.1:8000/admin")

    def test_refuses_link_local_metadata(self):
        """The cloud metadata endpoint is the canonical SSRF target."""
        from backend.services.preview.net import SSRFError, guard_url

        with pytest.raises(SSRFError):
            guard_url("http://169.254.169.254/latest/meta-data/")

    def test_refuses_private_ranges(self):
        from backend.services.preview.net import SSRFError, guard_url

        for url in ("http://10.0.0.5/", "http://192.168.1.1/", "http://172.16.0.1/"):
            with pytest.raises(SSRFError):
                guard_url(url)

    def test_refuses_non_http_schemes(self):
        from backend.services.preview.net import SSRFError, guard_url

        for url in ("file:///etc/passwd", "gopher://x/", "ftp://x/"):
            with pytest.raises(SSRFError):
                guard_url(url)

    def test_refuses_service_ports(self):
        from backend.services.preview.net import SSRFError, guard_url

        with pytest.raises(SSRFError):
            guard_url("http://example.com:6379/")

    def test_allows_a_normal_public_url(self):
        from backend.services.preview.net import guard_url

        assert guard_url("https://example.com/page")

    def test_refuses_ipv6_loopback_and_mapped_v4(self):
        from backend.services.preview.net import SSRFError, guard_url

        with pytest.raises(SSRFError):
            guard_url("http://[::1]/")
        with pytest.raises(SSRFError):
            guard_url("http://[::ffff:127.0.0.1]/")

    def test_candidate_lists_drop_bad_entries_rather_than_failing(self):
        """One hostile icon href must not fail the whole logo hunt."""
        from backend.services.preview.net.ssrf import guard_all

        kept = guard_all([
            "https://example.com/logo.png",
            "http://127.0.0.1/logo.png",
            "file:///etc/passwd",
        ])
        assert kept == ["https://example.com/logo.png"]


class TestStageBudgets:
    def test_a_stage_cannot_exceed_what_is_left_of_the_total(self):
        """A slow capture eats the quality loop's iterations, not the deadline."""
        budget = StageBudget(total_s=25.0)
        assert budget.for_stage(Stage.REASONING) <= 25.0

    def test_the_fast_lane_gets_less_time(self):
        fast = StageBudget.for_lane(PreviewLane.FAST)
        deep = StageBudget.for_lane(PreviewLane.DEEP)
        assert fast.for_stage(Stage.REASONING) < deep.for_stage(Stage.REASONING)

    def test_records_what_each_stage_spent(self):
        budget = StageBudget(total_s=100.0)
        budget.record(Stage.CAPTURE, 4.2)
        budget.record(Stage.CAPTURE, 1.0)
        assert budget.summary()["capture"] == pytest.approx(5.2)

    def test_a_blown_deadline_degrades_instead_of_hanging(self):
        """The point of a budget: the pipeline stops waiting and records why."""
        import time

        from backend.services.preview.observability.job_trace import JobTrace

        trace = JobTrace(url="https://slow.test")
        budget = StageBudget(total_s=100.0, stage_budgets={Stage.RENDER: 0.2})

        result = run_with_deadline(
            lambda: (time.sleep(3), "never")[1],
            stage=Stage.RENDER, budget=budget, default="degraded", trace=trace,
        )
        assert result == "degraded"
        assert Degradation.BUDGET_STAGE_EXCEEDED.value in trace.degradation_codes()

    def test_work_that_finishes_in_time_returns_normally(self):
        budget = StageBudget(total_s=100.0)
        assert run_with_deadline(lambda: "done", stage=Stage.RENDER, budget=budget) == "done"


class TestRetryPolicy:
    """Retry what the world broke; never retry what the input broke."""

    def test_transient_reasons_retry_with_backoff(self):
        first = decide_retry(FailureReason.CAPTURE_TIMEOUT, attempt=0)
        second = decide_retry(FailureReason.CAPTURE_TIMEOUT, attempt=1)
        assert first.should_retry and second.should_retry
        assert second.delay_s > first.delay_s

    def test_permanent_reasons_never_retry(self):
        for reason in (
            FailureReason.CAPTURE_BLOCKED,
            FailureReason.CAPTURE_HTTP_ERROR,
            FailureReason.EXTRACTION_INVALID_PAYLOAD,
        ):
            assert not decide_retry(reason).should_retry

    def test_retries_are_bounded(self):
        assert not decide_retry(FailureReason.CAPTURE_TIMEOUT, attempt=2).should_retry

    def test_unknown_reasons_do_not_retry(self):
        """A failure we cannot classify is not evidence that retrying helps."""
        assert not decide_retry(None).should_retry
        assert not decide_retry("something_we_do_not_recognise").should_retry

    def test_transience_is_a_property_of_the_code_not_the_string(self):
        assert is_transient(FailureReason.EXTRACTION_AI_RATE_LIMIT)
        assert is_transient("capture_timeout")
        assert not is_transient("capture_blocked")


class TestIdempotency:
    def test_the_same_work_produces_the_same_key(self):
        args = dict(url="https://a.test/x", organization_id=7, lane="ai")
        assert idempotency_key(**args) == idempotency_key(**args)

    def test_different_lanes_are_different_work(self):
        """Otherwise a template-lane retry could take over an AI-lane job."""
        assert idempotency_key(url="https://a.test", organization_id=1, lane="ai") != \
               idempotency_key(url="https://a.test", organization_id=1, lane="template")

    def test_different_orgs_are_different_work(self):
        assert idempotency_key(url="https://a.test", organization_id=1) != \
               idempotency_key(url="https://a.test", organization_id=2)

    def test_a_retry_inherits_the_original_identity(self):
        """A retry that generates a fresh key is a duplicate, not a retry."""
        original = idempotency_key(url="https://a.test", organization_id=1)
        assert idempotency_key(url="https://b.test", attempt_of=original) == original


class TestDegradationTaxonomy:
    def test_healthy_and_unhealthy_codes_are_distinguishable(self):
        assert Degradation.PREMIUM_RENDER_OK.is_healthy
        assert not Degradation.PREMIUM_RENDER_FAILED.is_healthy

    def test_a_trace_reads_as_a_story(self):
        from backend.services.preview.observability.job_trace import JobTrace

        trace = JobTrace(url="https://x.test")
        trace.degrade(Degradation.CAPTURE_OK, Stage.CAPTURE)
        trace.degrade(Degradation.BRAND_LOGO_FALLBACK_FAVICON, Stage.EXTRACTION, "header img 403")
        trace.degrade(Degradation.PREMIUM_RENDER_OK, Stage.RENDER)

        assert trace.degradation_trail() == (
            "capture_ok → brand_logo_fallback_favicon → premium_render_ok"
        )
        assert trace.unhealthy_degradations() == ["brand_logo_fallback_favicon"]

    def test_a_finished_job_with_fallbacks_is_reported_as_degraded(self):
        """Otherwise it is indistinguishable from a clean run, which is the
        whole reason 'why is this card generic?' was unanswerable."""
        from backend.services.preview.observability.diagnosis import diagnose
        from backend.services.preview.observability.job_trace import JobTrace

        trace = JobTrace(url="https://x.test")
        trace.degrade(Degradation.REASONING_FALLBACK_HTML, Stage.REASONING, "model timed out")
        trace.finalize_success()

        result = diagnose(trace.to_dict())
        assert result["verdict"] == "degraded"
        assert result["explanation"][0]["says"]

    def test_a_clean_job_is_reported_as_success(self):
        from backend.services.preview.observability.diagnosis import diagnose
        from backend.services.preview.observability.job_trace import JobTrace

        trace = JobTrace(url="https://x.test")
        trace.degrade(Degradation.CAPTURE_OK, Stage.CAPTURE)
        trace.degrade(Degradation.PREMIUM_RENDER_OK, Stage.RENDER)
        trace.finalize_success()

        assert diagnose(trace.to_dict())["verdict"] == "success"


class TestCostAccounting:
    def test_spend_is_attributed_to_the_open_stage(self):
        from backend.services.preview.observability.job_trace import JobTrace, StageTiming

        trace = JobTrace(url="https://x.test")
        trace.open_stage(Stage.REASONING)
        trace.record_ai_usage(9000, 800, cost_usd=0.03)
        trace.add_stage(trace.attach_pending_usage(
            StageTiming("reasoning", 0.0, 1.0, 1000.0)
        ))

        payload = trace.to_dict()
        assert payload["ai_cost_usd"] == pytest.approx(0.03)
        assert payload["stage_timings"][0]["ai_cost_usd"] == pytest.approx(0.03)

    def test_tiering_makes_utility_calls_far_cheaper(self):
        """Vision reasoning needs the flagship; classifying a page does not,
        and paying flagship rates for it was most of the per-preview cost."""
        from backend.services.preview.reasoning.models import spec_for

        flagship = spec_for("art_director").cost_usd(10_000, 2_000)
        utility = spec_for("classification").cost_usd(10_000, 2_000)
        assert utility < flagship / 10

    def test_the_gateways_rejected_parameter_is_simply_not_sent(self):
        """The temperature incident becomes config, not an SDK monkey-patch."""
        from backend.services.preview.reasoning.models import spec_for

        assert "temperature" not in spec_for("art_director").request_kwargs()

    def test_a_model_migration_is_an_env_variable(self, monkeypatch):
        from backend.services.preview.reasoning.models import spec_for

        monkeypatch.setenv("PREVIEW_MODEL_ART_DIRECTOR", "gpt-4.1")
        assert spec_for("art_director").model == "gpt-4.1"
