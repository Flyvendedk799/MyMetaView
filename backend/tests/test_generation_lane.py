"""Which lane a generation runs on, and that both surfaces run the same engine.

The bug these guard against: the signed-in app and the public demo configured
the engine separately, the app drifted onto weaker settings plus the multi-agent
orchestrator, and customers' previews came out looking like generic templates
while the demo stayed sharp.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.services.generation_lane import (
    AI_GENERATION_ACTION,
    LaneDecision,
    month_start,
    resolve_lane,
)
from backend.services.quality_profiles import get_quality_profile


@dataclass
class FakeOrg:
    """Minimal stand-in for an Organization as core.plans reads it."""
    id: int = 1
    subscription_status: str = "active"
    subscription_plan: str = "free"
    trial_ends_at: datetime = None


def _db_counting(count: int) -> MagicMock:
    """A session whose activity-log query reports `count` AI generations."""
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = count
    return db


class TestLaneSelection:
    def test_free_plan_uses_ai_until_its_allowance_is_spent(self):
        # Free is 5 AI previews/month.
        decision = resolve_lane(_db_counting(4), FakeOrg(subscription_plan="free"))
        assert decision.lane == "ai"
        assert decision.remaining == 1

    def test_free_plan_falls_back_to_templates_once_spent(self):
        decision = resolve_lane(_db_counting(5), FakeOrg(subscription_plan="free"))
        assert decision.lane == "template"
        assert decision.remaining == 0

    def test_overspend_does_not_go_negative(self):
        decision = resolve_lane(_db_counting(11), FakeOrg(subscription_plan="free"))
        assert decision.lane == "template"
        assert decision.remaining == 0

    def test_paid_plan_has_a_bigger_allowance(self):
        # 5 generations exhausts free but is nothing on growth.
        assert resolve_lane(_db_counting(5), FakeOrg(subscription_plan="growth")).lane == "ai"

    def test_unlimited_plan_never_falls_back(self):
        decision = resolve_lane(_db_counting(10_000), FakeOrg(subscription_plan="agency"))
        assert decision.lane == "ai"
        assert decision.limit is None
        assert decision.remaining is None

    def test_counting_failure_does_not_block_generation(self):
        """A broken usage query must not cost the customer their AI preview."""
        db = MagicMock()
        db.query.side_effect = RuntimeError("activity_logs unavailable")
        assert resolve_lane(db, FakeOrg(subscription_plan="free")).lane == "ai"


class TestUsageWindow:
    def test_quota_window_starts_at_the_first_of_the_month(self):
        start = month_start(datetime(2026, 3, 17, 14, 30, 5))
        assert start == datetime(2026, 3, 1, 0, 0, 0, 0)

    def test_usage_query_is_scoped_to_org_action_and_month(self):
        """Spend must not leak across organizations or across months."""
        db = _db_counting(0)
        resolve_lane(db, FakeOrg(id=42, subscription_plan="free"))

        filters = db.query.return_value.filter.call_args[0]
        rendered = " ".join(str(f) for f in filters)
        assert "organization_id" in rendered
        assert "action" in rendered
        assert "created_at" in rendered


class TestQualityProfiles:
    def test_no_profile_uses_the_multi_agent_orchestrator(self):
        """It returns no composition spec, so every card renders the same."""
        for mode in ("template", "fast", "balanced", "ultra"):
            assert get_quality_profile(mode).multi_agent is False

    def test_only_the_template_profile_skips_ai_reasoning(self):
        assert get_quality_profile("template").ai_reasoning is False
        for mode in ("fast", "balanced", "ultra"):
            assert get_quality_profile(mode).ai_reasoning is True

    def test_template_lane_is_cheap_and_forgiving(self):
        """It cannot retry into quality it structurally cannot reach."""
        template = get_quality_profile("template")
        assert template.iterations == 1
        assert template.allow_soft_pass is True
        assert template.enforce_target_quality is False


class TestDemoAndAppParity:
    """The app must generate exactly as well as the demo the customer saw."""

    def _engine_config(self, lane: str):
        """Run the production job far enough to capture the engine config."""
        from backend.jobs import preview_pipeline

        with patch.object(preview_pipeline, "PreviewEngine") as MockEngine, \
                patch.object(preview_pipeline, "SessionLocal") as MockSession, \
                patch.object(preview_pipeline, "brand_resolver") as mock_brand, \
                patch.object(preview_pipeline, "BrandSettingsSchema") as MockSchema, \
                patch.object(preview_pipeline, "resolve_lane") as mock_lane, \
                patch.object(preview_pipeline, "record_ai_generation"), \
                patch.object(preview_pipeline, "upsert_preview"), \
                patch.object(preview_pipeline, "rewrite_to_brand_voice", return_value="desc"), \
                patch.object(preview_pipeline, "log_activity"):
            MockSession.return_value = MagicMock()
            mock_brand.resolve.return_value = MagicMock()
            MockSchema.model_validate.return_value = MagicMock(
                primary_color="#2563EB", secondary_color="#1E40AF",
                accent_color="#F59E0B", font_family="Inter", logo_url=None,
            )
            mock_lane.return_value = LaneDecision(lane, used=0, limit=None)
            MockEngine.return_value.generate.return_value = MagicMock(
                blueprint={"template_type": "landing"}, tags=[], title="T",
                description="d", message="m", composited_preview_image_url="u",
                screenshot_url="s",
            )

            preview_pipeline.generate_preview_job(1, 1, "https://example.com", "example.com")
            return MockEngine.call_args[0][0]

    def test_app_generates_at_the_demo_s_top_quality_profile(self):
        config = self._engine_config("ai")
        ultra = get_quality_profile("ultra")

        assert config.enable_ai_reasoning is True
        assert config.enable_multi_agent is False
        assert config.quality_threshold == ultra.threshold
        assert config.max_quality_iterations == ultra.iterations
        assert config.enforce_target_quality == ultra.enforce_target_quality
        assert config.min_soft_pass_overall == ultra.min_soft_pass_overall
        assert config.min_soft_pass_fidelity == ultra.min_soft_pass_fidelity

    def test_template_lane_makes_no_ai_calls(self):
        config = self._engine_config("template")
        assert config.enable_ai_reasoning is False
        assert config.enable_multi_agent is False
        assert config.enable_ui_element_extraction is False

    def test_lanes_do_not_share_a_cache_namespace(self):
        """Otherwise upgrading keeps serving the template card they paid to escape."""
        from backend.jobs import preview_pipeline

        prefixes = {}
        for lane in ("ai", "template"):
            with patch.object(preview_pipeline, "PreviewEngine") as MockEngine, \
                    patch.object(preview_pipeline, "SessionLocal"), \
                    patch.object(preview_pipeline, "brand_resolver"), \
                    patch.object(preview_pipeline, "BrandSettingsSchema"), \
                    patch.object(preview_pipeline, "resolve_lane") as mock_lane, \
                    patch.object(preview_pipeline, "record_ai_generation"), \
                    patch.object(preview_pipeline, "upsert_preview"), \
                    patch.object(preview_pipeline, "rewrite_to_brand_voice", return_value="d"), \
                    patch.object(preview_pipeline, "log_activity"):
                mock_lane.return_value = LaneDecision(lane, used=0, limit=None)
                MockEngine.return_value.generate.return_value = MagicMock(
                    blueprint={"template_type": "landing"}, tags=[], title="T",
                    description="d", message="m", composited_preview_image_url="u",
                    screenshot_url="s",
                )
                preview_pipeline.generate_preview_job(1, 1, "https://example.com", "example.com")
                prefixes[lane] = MockEngine.return_value.generate.call_args.kwargs["cache_key_prefix"]

        assert prefixes["ai"] != prefixes["template"]


class TestAiSpendIsRecorded:
    def test_ai_lane_spends_one_generation_before_running(self):
        from backend.jobs import preview_pipeline

        with patch.object(preview_pipeline, "PreviewEngine") as MockEngine, \
                patch.object(preview_pipeline, "SessionLocal"), \
                patch.object(preview_pipeline, "brand_resolver"), \
                patch.object(preview_pipeline, "BrandSettingsSchema"), \
                patch.object(preview_pipeline, "resolve_lane") as mock_lane, \
                patch.object(preview_pipeline, "record_ai_generation") as mock_record, \
                patch.object(preview_pipeline, "upsert_preview"), \
                patch.object(preview_pipeline, "rewrite_to_brand_voice", return_value="d"), \
                patch.object(preview_pipeline, "log_activity"):
            mock_lane.return_value = LaneDecision("ai", used=0, limit=5)
            MockEngine.return_value.generate.return_value = MagicMock(
                blueprint={"template_type": "landing"}, tags=[], title="T",
                description="d", message="m", composited_preview_image_url="u",
                screenshot_url="s",
            )
            preview_pipeline.generate_preview_job(1, 1, "https://example.com", "example.com")

        assert mock_record.call_count == 1

    def test_template_lane_spends_nothing(self):
        from backend.jobs import preview_pipeline

        with patch.object(preview_pipeline, "PreviewEngine") as MockEngine, \
                patch.object(preview_pipeline, "SessionLocal"), \
                patch.object(preview_pipeline, "brand_resolver"), \
                patch.object(preview_pipeline, "BrandSettingsSchema"), \
                patch.object(preview_pipeline, "resolve_lane") as mock_lane, \
                patch.object(preview_pipeline, "record_ai_generation") as mock_record, \
                patch.object(preview_pipeline, "upsert_preview"), \
                patch.object(preview_pipeline, "rewrite_to_brand_voice", return_value="d"), \
                patch.object(preview_pipeline, "log_activity"):
            mock_lane.return_value = LaneDecision("template", used=5, limit=5)
            MockEngine.return_value.generate.return_value = MagicMock(
                blueprint={"template_type": "landing"}, tags=[], title="T",
                description="d", message="m", composited_preview_image_url="u",
                screenshot_url="s",
            )
            preview_pipeline.generate_preview_job(1, 1, "https://example.com", "example.com")

        mock_record.assert_not_called()

    def test_the_recorded_action_is_what_usage_counts(self):
        """Writer and reader must agree on the action string."""
        import inspect
        from backend.services import generation_lane

        source = inspect.getsource(generation_lane.record_ai_generation)
        assert "AI_GENERATION_ACTION" in source
        assert AI_GENERATION_ACTION == "preview.ai_generation.spent"
