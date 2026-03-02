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


# ── Agent configuration (from agents.yaml) ────────────────
class AgentConfig(BaseModel):
    """Configuration for a single agent, loaded from agents.yaml."""
    name: str
    module: str
    class_name: str = Field(alias="class")
    description: str = ""
    model: str = ""
    enabled: bool = True

    model_config = {"populate_by_name": True}
