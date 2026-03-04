"""Agent registry — loads agents and pipelines from agents.yaml.

Agents are CrewAI Agent objects configured from YAML. No more dynamic
class imports — everything is defined declaratively.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, LLM

from openvassal.agents.tools import TOOL_FACTORIES, get_coding_tools, get_daily_work_tools
from openvassal.config import settings
from openvassal.data.store import DataStore
from openvassal.models import AgentConfig, PipelineConfig, PipelineStep

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Discovers, loads, and manages CrewAI agents from agents.yaml.

    Usage::

        registry = AgentRegistry()
        registry.load()                # reads agents.yaml
        agent = registry.get("coder") # get a CrewAI Agent
        names = registry.agent_names   # list of all agent names
    """

    def __init__(
        self,
        config_path: Path | None = None,
        data_store: DataStore | None = None,
    ):
        self._config_path = config_path or settings.agents_yaml
        self._data_store = data_store or DataStore()
        self._configs: list[AgentConfig] = []
        self._agents: dict[str, Agent] = {}
        self._agent_configs: dict[str, AgentConfig] = {}
        self._pipelines: list[PipelineConfig] = []

    # ── Loading ───────────────────────────────────────────
    def load(self) -> None:
        """Parse agents.yaml and instantiate enabled agents."""
        raw = self._parse_yaml()
        self._configs = raw["agents"]
        self._pipelines = raw["pipelines"]

        for cfg in self._configs:
            if not cfg.enabled:
                logger.info("Agent '%s' is disabled — skipping", cfg.name)
                continue
            try:
                agent = self._build_agent(cfg)
                self._agents[cfg.name] = agent
                self._agent_configs[cfg.name] = cfg
                logger.info("Loaded agent '%s' (model=%s)", cfg.name, cfg.model)
            except Exception:
                logger.exception("Failed to load agent '%s'", cfg.name)

    def _parse_yaml(self) -> dict[str, list]:
        path = self._config_path
        if not path.exists():
            logger.warning("agents.yaml not found at %s — no agents loaded", path)
            return {"agents": [], "pipelines": []}

        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        # Parse agent configs
        agents = []
        for entry in raw.get("agents", []):
            agents.append(AgentConfig(**entry))

        # Parse pipeline configs
        pipelines = []
        for entry in raw.get("pipelines", []):
            steps = [PipelineStep(**s) for s in entry.get("steps", [])]
            pipelines.append(PipelineConfig(
                name=entry["name"],
                description=entry.get("description", ""),
                steps=steps,
            ))

        return {"agents": agents, "pipelines": pipelines}

    def _build_agent(self, cfg: AgentConfig) -> Agent:
        """Build a CrewAI Agent from config."""
        # Resolve tools
        tools = self._resolve_tools(cfg.tools)

        # Build LLM
        llm = LLM(model=cfg.model) if cfg.model else None

        agent = Agent(
            role=cfg.role or cfg.name,
            goal=cfg.goal or f"Help the user with {cfg.name} tasks",
            backstory=cfg.backstory or f"You are a helpful {cfg.name} assistant.",
            llm=llm,
            tools=tools,
            verbose=cfg.verbose,
        )
        return agent

    def _resolve_tools(self, tool_names: list[str]) -> list:
        """Resolve tool names from config to actual tool instances."""
        if not tool_names:
            return []

        tools = []
        seen_groups: set[str] = set()
        for name in tool_names:
            # Check for group names first (coding, daily_work)
            if name in ("coding", "daily_work") and name not in seen_groups:
                seen_groups.add(name)
                if name == "coding":
                    tools.extend(get_coding_tools(self._data_store))
                elif name == "daily_work":
                    tools.extend(get_daily_work_tools(self._data_store))
            elif name in TOOL_FACTORIES and name not in seen_groups:
                factory = TOOL_FACTORIES[name]
                result = factory(self._data_store)
                if isinstance(result, list):
                    tools.extend(result)
                else:
                    tools.append(result)
                seen_groups.add(name)
        return tools

    # ── Access ────────────────────────────────────────────
    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def get_config(self, name: str) -> AgentConfig | None:
        return self._agent_configs.get(name)

    def get_all(self) -> dict[str, Agent]:
        return dict(self._agents)

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())

    @property
    def configs(self) -> list[AgentConfig]:
        return list(self._configs)

    @property
    def pipelines(self) -> list[PipelineConfig]:
        return list(self._pipelines)

    def get_pipeline(self, name: str) -> PipelineConfig | None:
        for p in self._pipelines:
            if p.name == name:
                return p
        return None

    # ── Mutations ─────────────────────────────────────────
    def register(self, name: str, agent: Agent, config: AgentConfig | None = None) -> None:
        """Manually register an agent (e.g. for testing / runtime additions)."""
        self._agents[name] = agent
        if config:
            self._agent_configs[name] = config
        logger.info("Manually registered agent '%s'", name)

    def unregister(self, name: str) -> bool:
        if name in self._agents:
            del self._agents[name]
            self._agent_configs.pop(name, None)
            logger.info("Unregistered agent '%s'", name)
            return True
        return False
