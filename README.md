# ⚡ OpenVassal

> **Local-first personal knowledge base** with multi-agent orchestration.  
> Powered by **CrewAI** + **mem0** — manually select agents, run pipelines, and share memory across all models.

---

## ✨ Features

- 🎯 **Manual Agent Selection** — you pick which LLM handles each task, no black-box routing
- 🔗 **Pipeline Orchestration** — chain agents into multi-step workflows (e.g. Plan → Code → Review)
- 🧠 **Unified Memory (mem0)** — all agents share persistent memory across sessions, auto-extracted from conversations
- 🌐 **Multi-LLM Support** — Claude, GPT, Gemini, Kimi — one-line config via CrewAI's LiteLLM
- 📦 **Local-first** — runs entirely on your machine, your data stays yours

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  User (CLI / Web UI)                                │
│  ↓  /use coder  |  /pipeline plan-code-review       │
├─────────────────────────────────────────────────────┤
│  Orchestrator — manual dispatch + pipeline engine    │
│  ┌──────────────┬──────────────┬──────────────────┐ │
│  │claude_planner│   coder      │  gemini_chat     │ │
│  │ Claude API   │  OpenAI API  │  Gemini API      │ │
│  └──────────────┴──────────────┴──────────────────┘ │
│  ┌──────────────┬──────────────────────────────────┐ │
│  │daily_assistant│  kimi_writer (Moonshot API)     │ │
│  └──────────────┴──────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│  mem0 Memory — shared across ALL agents & sessions   │
├─────────────────────────────────────────────────────┤
│  SQLite DataStore — tasks, notes, code snippets      │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/your-org/openvassal.git && cd openvassal
./setup.sh          # create venv, install deps, configure .env
make run            # start the terminal chat
```

> **Note:** Requires **Python 3.11–3.13** (CrewAI does not yet support Python 3.14).

---

## 🎮 CLI Commands

```
/use <agent>                Switch active agent (e.g. /use claude_planner)
/agents                     List all available agents
/pipeline <name> <desc>     Run a multi-step pipeline
/pipelines                  List available pipelines
/memory                     Show all stored memories
/memory search <query>      Semantic search through memories
/help                       Show all commands
/quit                       Exit
```

### Example Session

```
You → coder: Write a Python function to parse CSV files
coder is thinking…

coder:
Here's a robust CSV parser...

You → /use claude_planner
✔ Switched to claude_planner (Technical Architect & Code Reviewer)

You → claude_planner: Review the CSV parser for edge cases
claude_planner is thinking…
```

---

## 🤖 Default Agents

| Agent | Role | Model | Tools |
|---|---|---|---|
| `claude_planner` | Technical Architect & Code Reviewer | `anthropic/claude-sonnet-4-20250514` | — |
| `coder` | Senior Software Engineer | `openai/gpt-4o` | save/search code |
| `gemini_chat` | Knowledge Assistant | `gemini/gemini-2.5-flash` | — |
| `daily_assistant` | Productivity Assistant | `gemini/gemini-2.5-flash` | tasks, notes |
| `kimi_writer` | Chinese Technical Writer | `openai/moonshot-v1-32k` | — (disabled by default) |

> Agents are defined in `agents.yaml` — add, configure, or remove agents freely.

---

## 🔗 Pipelines

Predefined multi-step workflows in `agents.yaml`:

| Pipeline | Steps | Description |
|---|---|---|
| `plan-code-review` | Claude → GPT → Claude | Plan → Code → Review |
| `research-summarize` | Gemini → Claude | Research → Summarize |

### Running a Pipeline

```
/pipeline plan-code-review Build a REST API for user management
```

Each step's output is automatically passed as context to the next step.

---

## 🌐 Web UI

Start the web interface:

```bash
make ui    # Opens http://127.0.0.1:8585
```

| Page | Description |
|---|---|
| `/` | Settings — API keys, agent list, memory management |
| `/chat` | Chat — agent selector, conversation history, pipeline runner |

---

## ⚙️ Configuration

### 1. API Keys (`.env`)

```bash
OPENAI_API_KEY=sk-...              # Required for mem0 + coder
ANTHROPIC_API_KEY=sk-ant-...       # For claude_planner
GEMINI_API_KEY=...                 # For gemini_chat / daily_assistant
MOONSHOT_API_KEY=sk-...            # Optional, for kimi_writer
```

### 2. Agents (`agents.yaml`)

Each agent is configured with:

```yaml
- name: my_agent
  role: "What the agent does"
  goal: "What the agent aims to achieve"
  backstory: "Agent personality / expertise"
  model: "provider/model-name"     # LiteLLM format
  tools: [coding, daily_work]      # Optional tool groups
  enabled: true
```

### 3. Supported LLM Providers

| Provider | Model Format | Example |
|---|---|---|
| OpenAI | `openai/gpt-4o` | Standard |
| Anthropic | `anthropic/claude-sonnet-4-20250514` | Via LiteLLM |
| Google Gemini | `gemini/gemini-2.5-flash` | Via LiteLLM |
| Moonshot (Kimi) | `openai/moonshot-v1-32k` | OpenAI-compatible |
| Any LiteLLM provider | `provider/model` | [See LiteLLM docs](https://docs.litellm.ai/docs/providers) |

---

## 📁 Project Structure

```
openvassal/
├── agents.yaml              # Agent & pipeline configuration
├── .env                     # API keys (from .env.example)
├── pyproject.toml           # Dependencies & build config
├── Makefile                 # Dev commands
├── setup.sh                 # One-command bootstrap
├── openvassal/
│   ├── main.py              # CLI entry point (REPL)
│   ├── config.py            # Settings from .env
│   ├── memory.py            # mem0 integration
│   ├── models.py            # Pydantic data models
│   ├── orchestrator.py      # Manual dispatch + pipeline engine
│   ├── agents/
│   │   ├── registry.py      # Load agents from YAML → CrewAI
│   │   └── tools.py         # @tool functions (coding, daily_work)
│   ├── data/
│   │   ├── store.py         # SQLite data store
│   │   └── connectors.py    # Data importers
│   └── web/
│       ├── server.py        # FastAPI API + web server
│       └── static/          # HTML/CSS/JS for settings & chat UI
└── tests/
    ├── test_memory.py       # Memory manager tests
    ├── test_registry.py     # Agent registry tests
    ├── test_orchestrator.py # Orchestrator tests
    └── test_store.py        # Data store tests
```

---

## 🧪 Development

| Command | Description |
|---|---|
| `make setup` | Create venv, install deps, prepare `.env` |
| `make run` | Start the terminal chat |
| `make ui` | Start the web UI (port 8585) |
| `make test` | Run pytest |
| `make lint` | Run ruff linter |
| `make format` | Auto-format with ruff |
| `make docker` | Build & run with Docker Compose |
| `make clean` | Remove venv, caches, build artifacts |

```bash
# Run tests
make test

# Or directly
pytest tests/ -v
```

---

## 🧠 How Memory Works

OpenVassal uses **mem0** for persistent, cross-agent memory:

1. You chat with any agent → mem0 **auto-extracts** facts from conversations
2. On the next request, relevant memories are **semantically searched** and **injected** into the agent's context
3. All agents share the **same memory pool** — morning chat with Gemini is available to afternoon Claude session
4. Memory is stored locally (SQLite + vector embeddings)

---

## 📄 License

MIT
