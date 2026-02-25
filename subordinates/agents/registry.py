"""Agent registry — auto-discovers and loads agents from agents.yaml.

This is the plug-in system: add a new entry to agents.yaml → it's
automatically available to the Steward agent. Remove or disable it
→ it's gone.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from subordinates.agents.base import BaseAgent
from subordinates.config import settings
from subordinates.data.store import DataStore
from subordinates.models import AgentConfig

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Discovers, loads, and manages sub-agents from a YAML config.

    Usage::

        registry = AgentRegistry()
        registry.load()                # reads agents.yaml
        agents = registry.get_all()    # list of instantiated BaseAgent
        coding = registry.get("coding")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        data_store: DataStore | None = None,
    ):
        self._config_path = config_path or settings.agents_yaml
        self._data_store = data_store or DataStore()
        self._configs: list[AgentConfig] = []
        self._agents: dict[str, BaseAgent] = {}

    # ── Loading ───────────────────────────────────────────
    def load(self) -> None:
        """Parse agents.yaml and instantiate enabled agents."""
        self._configs = self._parse_yaml()
        for cfg in self._configs:
            if not cfg.enabled:
                logger.info("Agent '%s' is disabled — skipping", cfg.name)
                continue
            try:
                agent_instance = self._instantiate(cfg)
                self._agents[cfg.name] = agent_instance
                logger.info("Loaded agent '%s' (model=%s)", cfg.name, cfg.model)
            except Exception:
                logger.exception("Failed to load agent '%s'", cfg.name)

    def _parse_yaml(self) -> list[AgentConfig]:
        path = self._config_path
        if not path.exists():
            logger.warning("agents.yaml not found at %s — no agents loaded", path)
            return []
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        entries = raw.get("agents", [])
        return [AgentConfig(**entry) for entry in entries]

    def _instantiate(self, cfg: AgentConfig) -> BaseAgent:
        """Import the module and create an instance of the agent class."""
        module = importlib.import_module(cfg.module)
        cls: type[BaseAgent] = getattr(module, cfg.class_name)
        return cls(model=cfg.model or None, data_store=self._data_store)

    # ── Access ────────────────────────────────────────────
    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def get_all(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())

    @property
    def configs(self) -> list[AgentConfig]:
        return list(self._configs)

    # ── Mutations (plug-in / plug-out at runtime) ─────────
    def register(self, name: str, agent: BaseAgent) -> None:
        """Manually register an agent (e.g. for testing / runtime additions)."""
        self._agents[name] = agent
        logger.info("Manually registered agent '%s'", name)

    def unregister(self, name: str) -> bool:
        """Remove an agent from the registry."""
        if name in self._agents:
            del self._agents[name]
            logger.info("Unregistered agent '%s'", name)
            return True
        return False
