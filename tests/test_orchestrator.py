"""Tests for the Orchestrator — agent dispatch and pipeline execution."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
import pytest

from openvassal.data.store import DataStore
from openvassal.memory import MemoryManager
from openvassal.orchestrator import Orchestrator


def _make_store() -> DataStore:
    tmp = tempfile.mktemp(suffix=".db")
    return DataStore(db_path=Path(tmp))


def _make_registry(config: dict, tmp_path: Path):
    """Create a registry from a config dict."""
    from openvassal.agents.registry import AgentRegistry

    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    registry = AgentRegistry(config_path=yaml_path, data_store=_make_store())
    registry.load()
    return registry


def _make_memory() -> MemoryManager:
    tmp = tempfile.mktemp(suffix=".db")
    mgr = MemoryManager(db_path=Path(tmp), user_id="test_user")
    # Mock mem0 to avoid external deps
    mgr._mem0 = MagicMock()
    mgr._mem0.search.return_value = {"results": []}
    mgr._mem0.get_all.return_value = {"results": []}
    return mgr


def test_run_single_unknown_agent(tmp_path):
    """Test running with an unknown agent returns an error message."""
    config = {"agents": [], "pipelines": []}
    registry = _make_registry(config, tmp_path)
    memory = _make_memory()
    orchestrator = Orchestrator(registry, memory)

    result = orchestrator.run_single("nonexistent", "hello")
    assert "not found" in result.lower()


def test_run_pipeline_unknown(tmp_path):
    """Test running an unknown pipeline returns an error."""
    config = {"agents": [], "pipelines": []}
    registry = _make_registry(config, tmp_path)
    memory = _make_memory()
    orchestrator = Orchestrator(registry, memory)

    results = orchestrator.run_pipeline("nonexistent", "hello")
    assert len(results) == 1
    assert "not found" in results[0]["output"].lower()


def test_get_available_agents(tmp_path):
    """Test listing available agents."""
    config = {
        "agents": [
            {"name": "a1", "role": "Role A", "goal": "Goal A", "model": "openai/gpt-4o", "enabled": True},
            {"name": "a2", "role": "Role B", "goal": "Goal B", "model": "gemini/gemini-2.5-flash", "enabled": True},
        ],
        "pipelines": [],
    }
    registry = _make_registry(config, tmp_path)
    memory = _make_memory()
    orchestrator = Orchestrator(registry, memory)

    agents = orchestrator.get_available_agents()
    assert len(agents) == 2
    names = [a["name"] for a in agents]
    assert "a1" in names
    assert "a2" in names


def test_get_available_pipelines(tmp_path):
    """Test listing available pipelines."""
    config = {
        "agents": [
            {"name": "a1", "role": "R", "goal": "G", "model": "openai/gpt-4o", "enabled": True},
        ],
        "pipelines": [
            {
                "name": "test-pipeline",
                "description": "A test pipeline",
                "steps": [
                    {"agent": "a1", "task": "Do something"},
                ],
            }
        ],
    }
    registry = _make_registry(config, tmp_path)
    memory = _make_memory()
    orchestrator = Orchestrator(registry, memory)

    pipelines = orchestrator.get_available_pipelines()
    assert len(pipelines) == 1
    assert pipelines[0]["name"] == "test-pipeline"
    assert len(pipelines[0]["steps"]) == 1


def test_run_pipeline_with_missing_agent(tmp_path):
    """Test pipeline with a missing agent step returns error for that step."""
    config = {
        "agents": [],
        "pipelines": [
            {
                "name": "broken",
                "description": "Pipeline with missing agent",
                "steps": [
                    {"agent": "nonexistent", "task": "Do something"},
                ],
            }
        ],
    }
    registry = _make_registry(config, tmp_path)
    memory = _make_memory()
    orchestrator = Orchestrator(registry, memory)

    results = orchestrator.run_pipeline("broken", "test")
    assert len(results) == 1
    assert "not found" in results[0]["output"].lower()
