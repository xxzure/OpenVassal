"""FastAPI config + chat server for OpenVassal.

Start with:  openvassal --setup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from openvassal.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenVassal", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic request models ──────────────────────────────
class EnvConfig(BaseModel):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    default_model: str = "gpt-4o"
    database_path: str = "./data/openvassal.db"
    log_level: str = "INFO"


class AgentEntry(BaseModel):
    name: str
    module: str
    class_name: str  # "class" in YAML
    description: str = ""
    model: str = ""
    enabled: bool = True
    plan_tier: str = ""


class AgentsConfig(BaseModel):
    agents: list[AgentEntry]


class ChatMessage(BaseModel):
    message: str


# ── Helpers ───────────────────────────────────────────────
def _env_path() -> Path:
    return settings.project_root / ".env"


def _agents_yaml_path() -> Path:
    return settings.agents_yaml


def _read_env() -> dict[str, str]:
    """Parse .env file into dict."""
    path = _env_path()
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def _write_env(data: dict[str, str]) -> None:
    """Write dict as .env file, preserving comments from .env.example."""
    example_path = settings.project_root / ".env.example"
    lines: list[str] = []

    if example_path.exists():
        for line in example_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, _ = stripped.partition("=")
                key = key.strip()
                if key in data:
                    lines.append(f"{key}={data[key]}")
                    continue
            lines.append(line)
    else:
        for k, v in data.items():
            lines.append(f"{k}={v}")

    _env_path().write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_agents_yaml() -> list[dict]:
    """Read agents.yaml."""
    path = _agents_yaml_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return raw.get("agents", []) if raw else []


def _write_agents_yaml(agents: list[dict]) -> None:
    """Write agents.yaml."""
    path = _agents_yaml_path()
    content = (
        "# ──────────────────────────────────────────────────────────\n"
        "#  Agent Registry Configuration\n"
        "#  Add / remove agents by editing this file.\n"
        "#  The Steward agent discovers sub-agents from this list.\n"
        "# ──────────────────────────────────────────────────────────\n\n"
    )
    content += yaml.dump({"agents": agents}, default_flow_style=False, sort_keys=False)
    path.write_text(content, encoding="utf-8")


# ── Lazy-loaded Steward for chat ──────────────────────────
_steward_agent = None
_data_store = None


def _get_steward():
    global _steward_agent, _data_store
    if _steward_agent is None:
        from openvassal.agents.registry import AgentRegistry
        from openvassal.agents.steward import build_steward
        from openvassal.data.store import DataStore

        _data_store = DataStore()
        registry = AgentRegistry(data_store=_data_store)
        registry.load()
        _steward_agent = build_steward(registry)
        logger.info("Chat: Steward agent initialized with agents: %s", registry.agent_names)
    return _steward_agent


def _get_data_store():
    global _data_store
    if _data_store is None:
        from openvassal.data.store import DataStore
        _data_store = DataStore()
    return _data_store


# ── API Routes ────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the config UI."""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Serve the chat UI."""
    html_path = Path(__file__).parent / "static" / "chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Send a message to the Steward agent and get a response."""
    from agents import Runner

    steward = _get_steward()

    try:
        result = await Runner.run(steward, input=msg.message)

        # Determine which agent responded
        agent_name = "Steward"
        if hasattr(result, "last_agent") and result.last_agent:
            agent_name = result.last_agent.name

        return {
            "response": result.final_output,
            "agent": agent_name,
        }
    except Exception as exc:
        logger.exception("Chat error")
        return {
            "response": f"⚠️ Error: {exc}",
            "agent": "System",
        }


@app.get("/api/data/recent")
async def get_recent_data():
    """Get recent data records for the work results panel."""
    store = _get_data_store()
    records = store.query(limit=30)
    return {
        "records": [
            {
                "id": r.id,
                "category": r.category.value,
                "source": r.source,
                "timestamp": r.timestamp.isoformat(),
                "title": r.title,
                "content": r.content[:300],
                "metadata": r.metadata,
            }
            for r in records
        ],
        "stats": store.stats,
    }


@app.get("/api/env")
async def get_env():
    """Get current .env config values."""
    env = _read_env()
    return EnvConfig(
        openai_api_key=env.get("OPENAI_API_KEY", ""),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
        gemini_api_key=env.get("GEMINI_API_KEY", ""),
        default_model=env.get("DEFAULT_MODEL", "gpt-4o"),
        database_path=env.get("DATABASE_PATH", "./data/openvassal.db"),
        log_level=env.get("LOG_LEVEL", "INFO"),
    )


@app.post("/api/env")
async def save_env(config: EnvConfig):
    """Save .env config."""
    _write_env({
        "OPENAI_API_KEY": config.openai_api_key,
        "ANTHROPIC_API_KEY": config.anthropic_api_key,
        "GEMINI_API_KEY": config.gemini_api_key,
        "DEFAULT_MODEL": config.default_model,
        "DATABASE_PATH": config.database_path,
        "LOG_LEVEL": config.log_level,
    })
    return {"status": "saved"}


@app.get("/api/agents")
async def get_agents():
    """Get current agents configuration."""
    agents = _read_agents_yaml()
    return {"agents": agents}


@app.post("/api/agents")
async def save_agents(config: AgentsConfig):
    """Save agents configuration."""
    agents_data = []
    for agent in config.agents:
        entry = {
            "name": agent.name,
            "module": agent.module,
            "class": agent.class_name,
            "description": agent.description,
            "model": agent.model,
            "enabled": agent.enabled,
            "plan_tier": agent.plan_tier,
        }
        agents_data.append(entry)
    _write_agents_yaml(agents_data)
    return {"status": "saved"}


@app.get("/api/models")
async def get_available_models():
    """Return a curated list of popular models."""
    return {
        "models": [
            {"provider": "OpenAI", "id": "gpt-4o", "label": "GPT-4o"},
            {"provider": "OpenAI", "id": "gpt-4o-mini", "label": "GPT-4o Mini"},
            {"provider": "OpenAI", "id": "gpt-4.1", "label": "GPT-4.1"},
            {"provider": "OpenAI", "id": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
            {"provider": "OpenAI", "id": "gpt-4.1-nano", "label": "GPT-4.1 Nano"},
            {"provider": "Anthropic", "id": "litellm/anthropic/claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
            {"provider": "Anthropic", "id": "litellm/anthropic/claude-3-5-sonnet-20241022", "label": "Claude 3.5 Sonnet"},
            {"provider": "Anthropic", "id": "litellm/anthropic/claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku"},
            {"provider": "Google", "id": "litellm/gemini/gemini-2.5-flash-preview-05-20", "label": "Gemini 2.5 Flash"},
            {"provider": "Google", "id": "litellm/gemini/gemini-2.5-pro-preview-05-06", "label": "Gemini 2.5 Pro"},
            {"provider": "Google", "id": "litellm/gemini/gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
        ]
    }


@app.get("/api/plans")
async def get_plans():
    """Return available plan tiers."""
    from openvassal.plans.manager import PLAN_CATALOG
    return {
        "plans": {
            name: {
                "name": plan.name,
                "description": plan.description,
                "monthly_cost": plan.monthly_cost,
                "included_agents": plan.included_agents,
                "usage_limits": plan.usage_limits,
            }
            for name, plan in PLAN_CATALOG.items()
        }
    }


def start_server(host: str = "127.0.0.1", port: int = 8585) -> None:
    """Start the config UI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
