"""Shared Pydantic data models used across the system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Data categories (breaking data barriers) ──────────────
class DataCategory(str, Enum):
    """Categories of personal data the system can integrate."""
    CHAT = "chat"
    HEALTH = "health"
    FINANCIAL = "financial"
    DAILY = "daily"
    CONTACTS = "contacts"
    FILES = "files"
    MEMORY = "memory"


# ── Core data record ──────────────────────────────────────
class DataRecord(BaseModel):
    """A single record in the unified personal data store."""
    id: str | None = None
    category: DataCategory
    source: str = Field(description="Where this data came from (e.g. 'apple_health', 'bank_csv')")
    timestamp: datetime = Field(default_factory=datetime.now)
    title: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── User profile ──────────────────────────────────────────
class UserProfile(BaseModel):
    """Basic user profile for personalization."""
    name: str = "User"
    email: str = ""
    timezone: str = "America/New_York"
    preferences: dict[str, Any] = Field(default_factory=dict)


# ── Plan / subscription model ─────────────────────────────
class PlanTier(BaseModel):
    """A single plan tier (base or per-agent add-on)."""
    name: str
    description: str = ""
    monthly_cost: float = 0.0
    included_agents: list[str] = Field(default_factory=list)
    usage_limits: dict[str, int] = Field(
        default_factory=dict,
        description="e.g. {'messages_per_day': 100, 'api_calls_per_day': 50}",
    )


class UserSubscription(BaseModel):
    """The user's current subscription = base plan + add-on agent plans."""
    base_plan: str = "free"
    active_agent_plans: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)


# ── Agent configuration (from agents.yaml) ────────────────
class AgentConfig(BaseModel):
    """Configuration for a single agent, loaded from agents.yaml."""
    name: str
    module: str
    class_name: str = Field(alias="class")
    description: str = ""
    model: str = ""
    enabled: bool = True
    plan_tier: str = ""

    model_config = {"populate_by_name": True}
