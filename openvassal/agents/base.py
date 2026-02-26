"""Base agent interface — all sub-agents inherit from this.

To create a new agent:
  1. Subclass BaseAgent
  2. Implement build_agent() → agents.Agent
  3. Add an entry to agents.yaml
  4. Done — the registry auto-discovers it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agents import Agent

from openvassal.config import settings
from openvassal.data.store import DataStore


class BaseAgent(ABC):
    """Contract for every pluggable sub-agent.

    Subclasses must implement ``build_agent()`` which returns an
    ``agents.Agent`` instance from the OpenAI Agents SDK.
    """

    # Human-friendly display name
    name: str = "Unnamed Agent"
    description: str = ""

    def __init__(
        self,
        model: str | None = None,
        data_store: DataStore | None = None,
        **kwargs: Any,
    ):
        raw_model = model or settings.default_model
        self.model = settings.resolve_model(raw_model)
        self.data_store = data_store or DataStore()
        self._extra = kwargs

    @abstractmethod
    def build_agent(self) -> Agent:
        """Construct and return the ``agents.Agent`` for this sub-agent.

        The returned Agent will be plugged into the Steward via handoff
        or as_tool(), depending on the orchestration mode.
        """
        ...

    def get_tools(self) -> list:
        """Return extra tools (function_tools) for this agent.

        Override in subclasses to add per-agent tools.
        """
        return []
