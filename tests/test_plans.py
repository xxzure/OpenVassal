"""Tests for the plan manager."""

from subordinates.models import UserSubscription
from subordinates.plans.manager import PLAN_CATALOG, PlanManager


def test_free_plan_includes_steward():
    mgr = PlanManager(UserSubscription(base_plan="free"))
    assert "steward" in mgr.allowed_agents
    assert mgr.monthly_total == 0.0


def test_base_plan_cost():
    mgr = PlanManager(UserSubscription(base_plan="base"))
    assert mgr.monthly_total == 9.99


def test_add_agent_plan():
    mgr = PlanManager(UserSubscription(base_plan="base"))
    assert mgr.can_use_agent("coding") is False

    mgr.add_agent_plan("coding")
    assert mgr.can_use_agent("coding") is True
    assert mgr.monthly_total == 9.99 + 4.99


def test_remove_agent_plan():
    mgr = PlanManager(UserSubscription(base_plan="base", active_agent_plans=["coding"]))
    assert mgr.can_use_agent("coding") is True

    mgr.remove_agent_plan("coding")
    assert mgr.can_use_agent("coding") is False


def test_multiple_addons():
    mgr = PlanManager(UserSubscription(base_plan="base"))
    mgr.add_agent_plan("coding")
    mgr.add_agent_plan("daily_work")
    mgr.add_agent_plan("health")

    assert mgr.can_use_agent("coding")
    assert mgr.can_use_agent("daily_work")
    assert mgr.can_use_agent("health")
    assert mgr.monthly_total == 9.99 + 4.99 + 2.99 + 2.99


def test_add_invalid_plan():
    mgr = PlanManager(UserSubscription(base_plan="base"))
    result = mgr.add_agent_plan("nonexistent_plan")
    assert result is False


def test_summary_output():
    mgr = PlanManager(UserSubscription(base_plan="base", active_agent_plans=["coding"]))
    summary = mgr.summary()
    assert "base" in summary
    assert "coding" in summary
    assert "$14.98" in summary


def test_plan_catalog_has_all_tiers():
    expected = {"free", "base", "coding", "daily_work", "telephone", "financial", "health"}
    assert set(PLAN_CATALOG.keys()) == expected
