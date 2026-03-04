"""Tests for the CrewAI agent registry."""

import tempfile
from pathlib import Path

import yaml
import pytest

from openvassal.data.store import DataStore


def _make_store() -> DataStore:
    tmp = tempfile.mktemp(suffix=".db")
    return DataStore(db_path=Path(tmp))


def _make_yaml(content: dict, tmp_dir: Path) -> Path:
    path = tmp_dir / "agents.yaml"
    path.write_text(yaml.dump(content, default_flow_style=False), encoding="utf-8")
    return path


def test_load_agents_from_yaml(tmp_path):
    """Test that agents are loaded correctly from YAML config."""
    config = {
        "agents": [
            {
                "name": "test_agent",
                "role": "Test Role",
                "goal": "Test Goal",
                "backstory": "Test Backstory",
                "model": "openai/gpt-4o",
                "tools": [],
                "enabled": True,
            },
        ],
        "pipelines": [],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert "test_agent" in registry.agent_names
    assert len(registry.get_all()) == 1

    agent = registry.get("test_agent")
    assert agent is not None
    assert agent.role == "Test Role"
    assert agent.goal == "Test Goal"


def test_disabled_agent_not_loaded(tmp_path):
    """Test that disabled agents are skipped."""
    config = {
        "agents": [
            {
                "name": "disabled_agent",
                "role": "Test",
                "goal": "Test",
                "model": "openai/gpt-4o",
                "enabled": False,
            },
        ],
        "pipelines": [],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert "disabled_agent" not in registry.agent_names
    assert len(registry.get_all()) == 0


def test_multiple_agents(tmp_path):
    """Test loading multiple agents."""
    config = {
        "agents": [
            {
                "name": "agent_a",
                "role": "Role A",
                "goal": "Goal A",
                "model": "openai/gpt-4o",
                "enabled": True,
            },
            {
                "name": "agent_b",
                "role": "Role B",
                "goal": "Goal B",
                "model": "anthropic/claude-sonnet-4-20250514",
                "enabled": True,
            },
        ],
        "pipelines": [],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert len(registry.agent_names) == 2
    assert "agent_a" in registry.agent_names
    assert "agent_b" in registry.agent_names


def test_pipeline_loading(tmp_path):
    """Test that pipelines are loaded from YAML."""
    config = {
        "agents": [
            {"name": "planner", "role": "Planner", "goal": "Plan", "model": "openai/gpt-4o", "enabled": True},
            {"name": "coder", "role": "Coder", "goal": "Code", "model": "openai/gpt-4o", "enabled": True},
        ],
        "pipelines": [
            {
                "name": "plan-code",
                "description": "Plan then code",
                "steps": [
                    {"agent": "planner", "task": "Create a plan"},
                    {"agent": "coder", "task": "Write the code"},
                ],
            }
        ],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert len(registry.pipelines) == 1
    pipeline = registry.get_pipeline("plan-code")
    assert pipeline is not None
    assert pipeline.description == "Plan then code"
    assert len(pipeline.steps) == 2
    assert pipeline.steps[0].agent == "planner"
    assert pipeline.steps[1].agent == "coder"


def test_missing_yaml_file(tmp_path):
    """Test graceful handling of missing YAML file."""
    missing_path = tmp_path / "nonexistent.yaml"

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=missing_path, data_store=_make_store())
    registry.load()

    assert len(registry.get_all()) == 0
    assert len(registry.pipelines) == 0


def test_get_returns_none_for_unknown(tmp_path):
    """Test that get() returns None for unknown agents."""
    yaml_path = _make_yaml({"agents": [], "pipelines": []}, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    assert registry.get("unknown") is None
    assert registry.get_pipeline("unknown") is None


def test_manual_register_and_unregister(tmp_path):
    """Test manual agent registration."""
    yaml_path = _make_yaml({"agents": [], "pipelines": []}, tmp_path)

    from crewai import Agent
    from openvassal.agents.registry import AgentRegistry

    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    agent = Agent(role="Test", goal="Test", backstory="Test")
    registry.register("custom", agent)
    assert "custom" in registry.agent_names

    registry.unregister("custom")
    assert "custom" not in registry.agent_names


def test_agent_with_tools(tmp_path):
    """Test loading agents with tool groups."""
    config = {
        "agents": [
            {
                "name": "coder",
                "role": "Coder",
                "goal": "Code",
                "model": "openai/gpt-4o",
                "tools": ["coding"],
                "enabled": True,
            },
        ],
        "pipelines": [],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    agent = registry.get("coder")
    assert agent is not None
    # Agent should have tools from the "coding" group
    assert len(agent.tools) > 0


def test_get_config(tmp_path):
    """Test getting agent config."""
    config = {
        "agents": [
            {
                "name": "test",
                "role": "Test Role",
                "goal": "Test Goal",
                "model": "openai/gpt-4o",
                "enabled": True,
            },
        ],
        "pipelines": [],
    }
    yaml_path = _make_yaml(config, tmp_path)

    from openvassal.agents.registry import AgentRegistry
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()

    cfg = registry.get_config("test")
    assert cfg is not None
    assert cfg.role == "Test Role"
    assert cfg.model == "openai/gpt-4o"
