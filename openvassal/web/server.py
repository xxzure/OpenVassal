"""FastAPI server for OpenVassal — config + chat UI.

Start with:  openvassal --setup
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from openvassal.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenVassal", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic request models ──────────────────────────────
class ChatMessage(BaseModel):
    message: str
    agent_name: str
    session_id: str | None = None


class PipelineRequest(BaseModel):
    pipeline_name: str
    description: str


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10


class EnvConfig(BaseModel):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    moonshot_api_key: str = ""
    default_agent: str = ""
    mem0_user_id: str = "default_user"
    database_path: str = "./data/openvassal.db"
    log_level: str = "INFO"


class AgentEntry(BaseModel):
    name: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    model: str = ""
    tools: list[str] = []
    enabled: bool = True


class AgentsConfig(BaseModel):
    agents: list[AgentEntry]


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
    env_path = _env_path()
    lines: list[str] = []
    written_keys: set[str] = set()

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

    extra = {k: v for k, v in data.items() if k not in written_keys}
    if extra:
        lines.append("")
        for k, v in extra.items():
            lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_agents_yaml() -> dict:
    """Read agents.yaml."""
    path = _agents_yaml_path()
    if not path.exists():
        return {"agents": [], "pipelines": []}
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return {
        "agents": raw.get("agents", []),
        "pipelines": raw.get("pipelines", []),
    }


def _write_agents_yaml(data: dict) -> None:
    """Write agents.yaml with header comments."""
    path = _agents_yaml_path()
    content = (
        "# ──────────────────────────────────────────────────────────\n"
        "#  Agent Registry Configuration (CrewAI)\n"
        "#  Each agent is a CrewAI Agent with role, goal, backstory, model.\n"
        "#  Pipelines define multi-step workflows between agents.\n"
        "# ──────────────────────────────────────────────────────────\n\n"
    )
    content += yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    path.write_text(content, encoding="utf-8")


# ── Lazy-loaded orchestrator components ───────────────────
_orchestrator = None
_memory_manager = None
_registry = None


def _get_memory_manager():
    global _memory_manager
    if _memory_manager is None:
        from openvassal.memory import MemoryManager
        _memory_manager = MemoryManager()
        logger.info("MemoryManager initialized")
    return _memory_manager


def _get_registry():
    global _registry
    if _registry is None:
        from openvassal.agents.registry import AgentRegistry
        _registry = AgentRegistry()
        _registry.load()
        logger.info("Registry loaded: %s", _registry.agent_names)
    return _registry


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from openvassal.orchestrator import Orchestrator
        _orchestrator = Orchestrator(_get_registry(), _get_memory_manager())
        logger.info("Orchestrator initialized")
    return _orchestrator


def _rebuild():
    """Force rebuild all components (e.g. after config change)."""
    global _orchestrator, _memory_manager, _registry
    _orchestrator = None
    _memory_manager = None
    _registry = None


# ── API Routes ────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    html_path = Path(__file__).parent / "static" / "chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── Chat ──────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Send a message to a specific agent (manual selection)."""
    orchestrator = _get_orchestrator()
    memory_mgr = _get_memory_manager()

    # Resolve or create the session
    session_id = msg.session_id
    if not session_id:
        conv = memory_mgr.create_conversation(agent_name=msg.agent_name)
        session_id = conv["id"]
    else:
        memory_mgr.touch_conversation(session_id)

    try:
        response = orchestrator.run_single(msg.agent_name, msg.message)

        # Auto-title from first message
        conv_meta = memory_mgr.get_conversation(session_id)
        if conv_meta and conv_meta.get("title") == "New Chat":
            title = msg.message[:50].strip()
            if len(msg.message) > 50:
                title += "…"
            memory_mgr.update_conversation_title(session_id, title)

        return {
            "response": response,
            "agent": msg.agent_name,
            "session_id": session_id,
        }
    except Exception as exc:
        logger.exception("Chat error")
        return {
            "response": f"⚠️ Error: {exc}",
            "agent": "System",
            "session_id": session_id,
        }


# ── Pipeline ─────────────────────────────────────────────
@app.post("/api/pipeline")
async def run_pipeline(req: PipelineRequest):
    """Run a multi-step pipeline."""
    orchestrator = _get_orchestrator()
    results = orchestrator.run_pipeline(req.pipeline_name, req.description)
    return {"results": results}


# ── Agents ───────────────────────────────────────────────
@app.get("/api/agents")
async def get_agents():
    """Get available agents."""
    orchestrator = _get_orchestrator()
    return {"agents": orchestrator.get_available_agents()}


@app.get("/api/agents/config")
async def get_agents_config():
    """Get raw agents.yaml config."""
    data = _read_agents_yaml()
    return data


@app.post("/api/agents/config")
async def save_agents_config(config: AgentsConfig):
    """Save agents configuration."""
    data = _read_agents_yaml()
    agents_data = []
    for agent in config.agents:
        entry = {
            "name": agent.name,
            "role": agent.role,
            "goal": agent.goal,
            "backstory": agent.backstory,
            "model": agent.model,
            "tools": agent.tools,
            "enabled": agent.enabled,
        }
        agents_data.append(entry)
    data["agents"] = agents_data
    _write_agents_yaml(data)
    _rebuild()
    return {"status": "saved"}


# ── Pipelines ────────────────────────────────────────────
@app.get("/api/pipelines")
async def get_pipelines():
    orchestrator = _get_orchestrator()
    return {"pipelines": orchestrator.get_available_pipelines()}


# ── Conversations ────────────────────────────────────────
@app.get("/api/conversations")
async def list_conversations():
    memory_mgr = _get_memory_manager()
    return {"conversations": memory_mgr.list_conversations()}


@app.post("/api/conversations")
async def create_conversation():
    memory_mgr = _get_memory_manager()
    conv = memory_mgr.create_conversation()
    return conv


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(session_id: str):
    memory_mgr = _get_memory_manager()
    deleted = memory_mgr.delete_conversation(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


# ── Memory ───────────────────────────────────────────────
@app.get("/api/memory")
async def get_memories():
    """Get all memories from mem0."""
    memory_mgr = _get_memory_manager()
    return {"memories": memory_mgr.get_all_memories()}


@app.post("/api/memory/search")
async def search_memories(req: MemorySearchRequest):
    """Search memories via mem0."""
    memory_mgr = _get_memory_manager()
    results = memory_mgr.search_memory(req.query, limit=req.limit)
    return {"results": results}


@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory."""
    memory_mgr = _get_memory_manager()
    deleted = memory_mgr.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


# ── Data / Records ───────────────────────────────────────
@app.get("/api/data/recent")
async def get_recent_data():
    from openvassal.data.store import DataStore
    store = DataStore()
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


# ── Config / Env ─────────────────────────────────────────
@app.get("/api/env")
async def get_env():
    env = _read_env()
    return EnvConfig(
        openai_api_key=env.get("OPENAI_API_KEY", ""),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
        gemini_api_key=env.get("GEMINI_API_KEY", ""),
        moonshot_api_key=env.get("MOONSHOT_API_KEY", ""),
        default_agent=env.get("DEFAULT_AGENT", ""),
        mem0_user_id=env.get("MEM0_USER_ID", "default_user"),
        database_path=env.get("DATABASE_PATH", "./data/openvassal.db"),
        log_level=env.get("LOG_LEVEL", "INFO"),
    )


@app.post("/api/env")
async def save_env(config: EnvConfig):
    data = {
        "OPENAI_API_KEY": config.openai_api_key,
        "ANTHROPIC_API_KEY": config.anthropic_api_key,
        "GEMINI_API_KEY": config.gemini_api_key,
        "MOONSHOT_API_KEY": config.moonshot_api_key,
        "DEFAULT_AGENT": config.default_agent,
        "MEM0_USER_ID": config.mem0_user_id,
        "DATABASE_PATH": config.database_path,
        "LOG_LEVEL": config.log_level,
    }
    _write_env(data)
    _rebuild()
    settings.reload()
    logger.info("Config saved. Components will be rebuilt on next request.")
    return {"status": "saved"}


def start_server(host: str = "127.0.0.1", port: int = 8585) -> None:
    """Start the config + chat UI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
