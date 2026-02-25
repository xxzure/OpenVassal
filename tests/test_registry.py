"""Tests for the agent registry."""

import tempfile
from pathlib import Path

import yaml

from subordinates.agents.base import BaseAgent
from subordinates.agents.registry import AgentRegistry
from subordinates.data.store import DataStore


def _make_store() -> DataStore:
    tmp = tempfile.mktemp(suffix=".db")
    return DataStore(db_path=Path(tmp))


def _make_agents_yaml(agents_config: list[dict], tmp_dir: Path) -> Path:
    path = tmp_dir / "agents.yaml"
    path.write_text(yaml.dump({"agents": agents_config}), encoding="utf-8")
    return path


def test_load_enabled_agents(tmp_path):
    config = [
        {
            "name": "coding",
            "module": "subordinates.agents.coding",
            "class": "CodingAgent",
            "description": "Coding agent",
            "model": "gpt-4o",
            "enabled": True,
            "plan_tier": "coding",
        },
        {
            "name": "daily_work",
            "module": "subordinates.agents.daily_work",
            "class": "DailyWorkAgent",
            "description": "Daily work agent",
            "model": "gpt-4o-mini",
            "enabled": True,
            "plan_tier": "daily_work",
        },
    ]
    yaml_path = _make_agents_yaml(config, tmp_path)
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert "coding" in registry.agent_names
    assert "daily_work" in registry.agent_names
    assert len(registry.get_all()) == 2


def test_disabled_agent_not_loaded(tmp_path):
    config = [
        {
            "name": "coding",
            "module": "subordinates.agents.coding",
            "class": "CodingAgent",
            "enabled": False,
            "plan_tier": "coding",
        },
    ]
    yaml_path = _make_agents_yaml(config, tmp_path)
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert "coding" not in registry.agent_names
    assert len(registry.get_all()) == 0


def test_manual_register_and_unregister(tmp_path):
    yaml_path = _make_agents_yaml([], tmp_path)
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    # Create a dummy agent
    from subordinates.agents.coding import CodingAgent
    agent = CodingAgent(data_store=_make_store())
    registry.register("my_custom_agent", agent)
    assert "my_custom_agent" in registry.agent_names

    registry.unregister("my_custom_agent")
    assert "my_custom_agent" not in registry.agent_names


def test_missing_yaml_file(tmp_path):
    missing_path = tmp_path / "nonexistent.yaml"
    registry = AgentRegistry(config_path=missing_path, data_store=_make_store())
    registry.load()
    assert len(registry.get_all()) == 0


def test_get_returns_none_for_unknown():
    registry = AgentRegistry(config_path=Path("/nonexistent"), data_store=_make_store())
    assert registry.get("unknown") is None
