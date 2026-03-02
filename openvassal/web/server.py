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
class CustomProvider(BaseModel):
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class EnvConfig(BaseModel):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    default_model: str = "gpt-4o"
    database_path: str = "./data/openvassal.db"
    log_level: str = "INFO"
    custom_providers: list[CustomProvider] = []


class AgentEntry(BaseModel):
    name: str
    module: str
    class_name: str  # "class" in YAML
    description: str = ""
    model: str = ""
    enabled: bool = True


class AgentsConfig(BaseModel):
    agents: list[AgentEntry]


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None


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


def _parse_custom_providers(env: dict[str, str]) -> list[dict]:
    """Extract CUSTOM_<NAME>_* entries from env into a list of providers."""
    providers: dict[str, dict] = {}
    for key, val in env.items():
        if key.startswith("CUSTOM_") and key.count("_") >= 2:
            # Split by first two underscores: CUSTOM, NAME, FIELD...
            parts = key.split("_", 2)
            name = parts[1]
            # Since the name itself might have had spaces replaced by underscores, 
            # we need to be careful. The original code just took parts[1].
            # A better approach: find the last known suffix (_API_KEY, _BASE_URL, _MODEL)
            if key.endswith("_API_KEY"):
                name = key[len("CUSTOM_"):-len("_API_KEY")]
                field = "api_key"
            elif key.endswith("_BASE_URL"):
                name = key[len("CUSTOM_"):-len("_BASE_URL")]
                field = "base_url"
            elif key.endswith("_MODEL"):
                name = key[len("CUSTOM_"):-len("_MODEL")]
                field = "model"
            else:
                continue
            if name not in providers:
                providers[name] = {"name": name, "api_key": "", "base_url": "", "model": ""}
            if "api_key" in field:
                providers[name]["api_key"] = val
            elif "base_url" in field:
                providers[name]["base_url"] = val
            elif "model" in field:
                providers[name]["model"] = val
    return list(providers.values())


def _write_env(data: dict[str, str]) -> None:
    """Write dict as .env file, preserving comments from .env.example.

    Old CUSTOM_* entries in the existing .env are stripped first so that
    deleted custom providers don't linger.
    """
    example_path = settings.project_root / ".env.example"
    env_path = _env_path()
    lines: list[str] = []
    written_keys: set[str] = set()

    # Use .env.example as template if available
    if example_path.exists():
        for line in example_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, _ = stripped.partition("=")
                key = key.strip()
                if key in data:
                    lines.append(f"{key}={data[key]}")
                    written_keys.add(key)
                    continue
            lines.append(line)
    else:
        for k, v in data.items():
            lines.append(f"{k}={v}")
            written_keys.add(k)

    # Append any keys not covered by .env.example (e.g. custom providers)
    extra = {k: v for k, v in data.items() if k not in written_keys}
    if extra:
        lines.append("")
        lines.append("# --- Custom Providers (auto-generated) --------------------")
        for k, v in extra.items():
            lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


# ── Lazy-loaded Steward + Memory for chat ─────────────────
_steward_agent = None
_data_store = None
_memory_manager = None


def _get_memory_manager():
    global _memory_manager
    if _memory_manager is None:
        from openvassal.memory import MemoryManager
        _memory_manager = MemoryManager()
        logger.info("MemoryManager initialized")
    return _memory_manager


def _get_steward():
    global _steward_agent, _data_store
    if _steward_agent is None:
        from openvassal.agents.registry import AgentRegistry
        from openvassal.agents.steward import build_steward
        from openvassal.data.store import DataStore

        _data_store = DataStore()
        registry = AgentRegistry(data_store=_data_store)
        registry.load()
        memory_mgr = _get_memory_manager()
        _steward_agent = build_steward(registry, memory_manager=memory_mgr)
        logger.info("Chat: Steward agent initialized with agents: %s", registry.agent_names)
    return _steward_agent


def _rebuild_steward():
    """Force rebuild the Steward (e.g. after new facts are learned)."""
    global _steward_agent
    _steward_agent = None
    return _get_steward()


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
    """Send a message to the Steward agent and get a response.

    If session_id is provided, continues that conversation.
    If not, creates a new one automatically.
    """
    from agents import Runner

    steward = _get_steward()
    memory_mgr = _get_memory_manager()

    # Resolve or create the session
    if msg.session_id:
        session_id = msg.session_id
        # Touch the conversation timestamp
        memory_mgr.touch_conversation(session_id)
    else:
        # Auto-create a new conversation
        conv = memory_mgr.create_conversation()
        session_id = conv["id"]

    session = memory_mgr.get_or_create_session(session_id)

    try:
        result = await Runner.run(steward, input=msg.message, session=session)

        # The user wants Steward to control everything silently, so we always
        # return 'Steward' as the agent name, hiding the backend routing.
        agent_name = "Steward"

        response_text = result.final_output

        # Auto-title the conversation from the first message
        conv_meta = memory_mgr.get_conversation(session_id)
        if conv_meta and conv_meta.get("title") == "New Chat":
            # Use the first ~50 chars of the user's message as the title
            title = msg.message[:50].strip()
            if len(msg.message) > 50:
                title += "…"
            memory_mgr.update_conversation_title(session_id, title)

        # Extract user facts (non-blocking background task)
        asyncio.create_task(_extract_facts_background(
            memory_mgr, msg.message, response_text, session_id
        ))

        return {
            "response": response_text,
            "agent": agent_name,
            "session_id": session_id,
        }
    except Exception as exc:
        logger.exception("Chat error")
        # Provide user-friendly error messages
        err_str = str(exc).lower()
        if "api_key" in err_str or "authentication" in err_str or "401" in err_str:
            friendly = (
                "🔑 **Authentication failed.** Your API key may be invalid or missing. "
                "Please check your API keys in the Setup page."
            )
        elif "not found" in err_str or "404" in err_str:
            friendly = (
                "🔍 **Model not found.** The selected model may no longer be available. "
                "Please try a different model from the Setup page dropdown."
            )
        elif "connection" in err_str or "ssl" in err_str:
            friendly = (
                "🌐 **Connection error.** Could not reach the API provider. "
                "Please check your internet connection and the base URL in Setup."
            )
        else:
            friendly = (
                f"⚠️ Something went wrong while processing your request. "
                f"Please check your configuration in Setup."
            )
        logger.info("User-friendly error: %s (original: %s)", friendly, exc)
        return {
            "response": friendly,
            "agent": "System",
            "session_id": session_id,
        }


async def _extract_facts_background(
    memory_mgr, user_message: str, assistant_response: str, session_id: str
):
    """Background task to extract and save facts, then rebuild Steward."""
    try:
        count = await memory_mgr.extract_and_save_facts(
            user_message=user_message,
            assistant_response=assistant_response,
            session_id=session_id,
        )
        if count > 0:
            _rebuild_steward()
    except Exception:
        logger.debug("Background fact extraction failed (non-critical)", exc_info=True)


# ── Conversation management endpoints ────────────────────
@app.get("/api/conversations")
async def list_conversations():
    """List all conversations."""
    memory_mgr = _get_memory_manager()
    return {"conversations": memory_mgr.list_conversations()}


@app.post("/api/conversations")
async def create_conversation():
    """Create a new conversation."""
    memory_mgr = _get_memory_manager()
    conv = memory_mgr.create_conversation()
    return conv


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation and its history."""
    memory_mgr = _get_memory_manager()
    deleted = memory_mgr.delete_conversation(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@app.get("/api/conversations/{session_id}/messages")
async def get_conversation_messages(session_id: str):
    """Get all messages for a specific conversation."""
    memory_mgr = _get_memory_manager()
    session = memory_mgr.get_or_create_session(session_id)
    # get_items() is an async method on SQLiteSession
    try:
        items = await session.get_items()
    except Exception as e:
        logger.exception("Failed to get session items")
        raise HTTPException(status_code=500, detail=str(e))

    # Convert TResponseInputItem to simple dicts for the UI
    messages = []
    for item in items:
        # TResponseInputItem has a 'type' field which is usually 'message', and 'role'
        if getattr(item, "type", None) == "message" or isinstance(item, dict) and item.get("type") == "message":
            role = getattr(item, "role", None) or (item.get("role") if isinstance(item, dict) else "assistant")
            
            # Content can be a string or a list of parts
            content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "")
            
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Extract text parts
                text_parts = []
                for part in content:
                    part_type = getattr(part, "type", None) or (part.get("type") if isinstance(part, dict) else "")
                    if part_type == "text":
                        part_text = getattr(part, "text", None) or (part.get("text") if isinstance(part, dict) else "")
                        if part_text:
                            text_parts.append(part_text)
                text = "\n".join(text_parts)
                
            if text:
                messages.append({
                    "role": role,
                    "content": text
                })
                
    return {"messages": messages}


# ── Memory / Facts endpoints ─────────────────────────────
@app.get("/api/memory/facts")
async def get_facts():
    """Get all remembered user facts."""
    memory_mgr = _get_memory_manager()
    return {"facts": memory_mgr.get_all_facts()}


@app.delete("/api/memory/facts/{fact_id}")
async def delete_fact(fact_id: str):
    """Delete a specific user fact."""
    memory_mgr = _get_memory_manager()
    deleted = memory_mgr.delete_fact(fact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    # Rebuild steward with updated facts
    _rebuild_steward()
    return {"status": "deleted"}


# ── Data endpoints ────────────────────────────────────────
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
        custom_providers=[CustomProvider(**p) for p in _parse_custom_providers(env)],
    )


@app.post("/api/env")
async def save_env(config: EnvConfig):
    """Save .env config."""
    global _steward_agent
    data = {
        "OPENAI_API_KEY": config.openai_api_key,
        "ANTHROPIC_API_KEY": config.anthropic_api_key,
        "GEMINI_API_KEY": config.gemini_api_key,
        "DEFAULT_MODEL": config.default_model,
        "DATABASE_PATH": config.database_path,
        "LOG_LEVEL": config.log_level,
    }
    # Serialize custom providers
    for cp in config.custom_providers:
        safe_name = cp.name.upper().replace(" ", "_").replace("-", "_")
        prefix = f"CUSTOM_{safe_name}"
        data[f"{prefix}_API_KEY"] = cp.api_key
        if cp.base_url:
            data[f"{prefix}_BASE_URL"] = cp.base_url
        if cp.model:
            data[f"{prefix}_MODEL"] = cp.model
    _write_env(data)
    # Invalidate cached steward so next chat uses updated config
    _steward_agent = None
    # Reload settings from .env
    settings.reload()
    logger.info("Config saved. Steward will be rebuilt on next chat.")
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
        }
        agents_data.append(entry)
    _write_agents_yaml(agents_data)
    return {"status": "saved"}


@app.get("/api/models")
async def get_available_models():
    """Return a curated list of popular models, including custom providers."""
    models = [
        {"provider": "OpenAI", "id": "gpt-4o", "label": "GPT-4o"},
        {"provider": "OpenAI", "id": "gpt-4o-mini", "label": "GPT-4o Mini"},
        {"provider": "OpenAI", "id": "gpt-4.1", "label": "GPT-4.1"},
        {"provider": "OpenAI", "id": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
        {"provider": "OpenAI", "id": "gpt-4.1-nano", "label": "GPT-4.1 Nano"},
        {"provider": "Anthropic", "id": "litellm/anthropic/claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
        {"provider": "Anthropic", "id": "litellm/anthropic/claude-3-5-sonnet-20241022", "label": "Claude 3.5 Sonnet"},
        {"provider": "Anthropic", "id": "litellm/anthropic/claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku"},
        {"provider": "Google", "id": "litellm/gemini/gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
        {"provider": "Google", "id": "litellm/gemini/gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
        {"provider": "Google", "id": "litellm/gemini/gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
    ]

    # Append models from custom providers defined in .env
    env = _read_env()
    for cp in _parse_custom_providers(env):
        if cp.get("model"):
            provider_name = cp["name"].title()
            # Support comma-separated models
            for model_id in cp["model"].split(","):
                model_id = model_id.strip()
                if model_id:
                    from openvassal.config import settings
                    resolved_model = settings.resolve_model(model_id)
                    # resolved_model can be a string or a LitellmModel object.
                    # For the UI dropdown, we just need the string representation of the ID.
                    resolved_id = getattr(resolved_model, "model", resolved_model)
                    models.append({
                        "provider": provider_name,
                        "id": resolved_id,
                        "label": model_id,
                    })

    return {"models": models}
def start_server(host: str = "127.0.0.1", port: int = 8585) -> None:
    """Start the config UI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
