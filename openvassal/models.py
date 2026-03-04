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
    source: str = Field(description="Where this data came from (e.g. 'coding_agent', 'csv')")
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


# ── Agent configuration (from agents.yaml) ────────────────
class AgentConfig(BaseModel):
    """Configuration for a single agent, loaded from agents.yaml."""
    name: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    model: str = ""
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True
    verbose: bool = False


# ── Pipeline configuration ────────────────────────────────
class PipelineStep(BaseModel):
    """A single step in a pipeline."""
    agent: str = Field(description="Name of the agent to use for this step")
    task: str = Field(description="Task description template for this step")


class PipelineConfig(BaseModel):
    """Configuration for a multi-step pipeline."""
    name: str
    description: str = ""
    steps: list[PipelineStep] = Field(default_factory=list)
