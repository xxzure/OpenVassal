"""Plan manager — insurance-style cost model.

Base plan gives access to the Steward agent.
Each sub-agent is an add-on plan (like adding coverage to an insurance policy).
"""

from __future__ import annotations

from subordinates.models import PlanTier, UserSubscription


# ── Available plan tiers ──────────────────────────────────
PLAN_CATALOG: dict[str, PlanTier] = {
    "free": PlanTier(
        name="free",
        description="Basic — Steward agent only",
        monthly_cost=0.0,
        included_agents=["steward"],
        usage_limits={"messages_per_day": 20},
    ),
    "base": PlanTier(
        name="base",
        description="Core plan — Steward + essential routing",
        monthly_cost=9.99,
        included_agents=["steward"],
        usage_limits={"messages_per_day": 200},
    ),
    "coding": PlanTier(
        name="coding",
        description="Add-on: Coding Agent",
        monthly_cost=4.99,
        included_agents=["coding"],
        usage_limits={"messages_per_day": 100, "code_generations": 50},
    ),
    "daily_work": PlanTier(
        name="daily_work",
        description="Add-on: Daily Work Agent",
        monthly_cost=2.99,
        included_agents=["daily_work"],
        usage_limits={"messages_per_day": 100},
    ),
    "telephone": PlanTier(
        name="telephone",
        description="Add-on: Telephone Agent",
        monthly_cost=2.99,
        included_agents=["telephone"],
        usage_limits={"messages_per_day": 50, "call_summaries": 20},
    ),
    "financial": PlanTier(
        name="financial",
        description="Add-on: Financial Agent",
        monthly_cost=3.99,
        included_agents=["financial"],
        usage_limits={"messages_per_day": 100},
    ),
    "health": PlanTier(
        name="health",
        description="Add-on: Health Agent",
        monthly_cost=2.99,
        included_agents=["health"],
        usage_limits={"messages_per_day": 80},
    ),
}


class PlanManager:
    """Manages user subscriptions and checks access to agents."""

    def __init__(self, subscription: UserSubscription | None = None):
        self.subscription = subscription or UserSubscription()

    # ── Queries ───────────────────────────────────────────
    @property
    def allowed_agents(self) -> set[str]:
        """All agent names the user has access to."""
        agents: set[str] = set()
        # Base plan agents
        base = PLAN_CATALOG.get(self.subscription.base_plan)
        if base:
            agents.update(base.included_agents)
        # Add-on agent plans
        for plan_name in self.subscription.active_agent_plans:
            plan = PLAN_CATALOG.get(plan_name)
            if plan:
                agents.update(plan.included_agents)
        return agents

    def can_use_agent(self, agent_name: str) -> bool:
        """Check whether the user's subscription covers *agent_name*."""
        return agent_name in self.allowed_agents

    @property
    def monthly_total(self) -> float:
        """Total monthly cost."""
        total = 0.0
        base = PLAN_CATALOG.get(self.subscription.base_plan)
        if base:
            total += base.monthly_cost
        for plan_name in self.subscription.active_agent_plans:
            plan = PLAN_CATALOG.get(plan_name)
            if plan:
                total += plan.monthly_cost
        return round(total, 2)

    # ── Mutations ─────────────────────────────────────────
    def add_agent_plan(self, plan_name: str) -> bool:
        """Subscribe to an agent add-on."""
        if plan_name not in PLAN_CATALOG:
            return False
        if plan_name in self.subscription.active_agent_plans:
            return True  # already active
        self.subscription.active_agent_plans.append(plan_name)
        return True

    def remove_agent_plan(self, plan_name: str) -> bool:
        """Unsubscribe from an agent add-on."""
        if plan_name in self.subscription.active_agent_plans:
            self.subscription.active_agent_plans.remove(plan_name)
            return True
        return False

    def summary(self) -> str:
        """Human-readable subscription summary."""
        lines = [
            f"Plan: {self.subscription.base_plan}",
            f"Add-ons: {', '.join(self.subscription.active_agent_plans) or 'none'}",
            f"Active agents: {', '.join(sorted(self.allowed_agents))}",
            f"Monthly cost: ${self.monthly_total:.2f}",
        ]
        return "\n".join(lines)
