# ⚡ OpenVassal

An open-source AI personal assistant powered by multiple agents, each with its own LLM.

## Quick Start

```bash
git clone https://github.com/your-org/openvassal.git && cd openvassal
./setup.sh          # one-command bootstrap (creates venv, installs deps, sets API key)
make run            # start chatting
```

Or use **Make** directly:

```bash
make setup          # create venv + install deps + prepare .env
make run            # terminal chat
make ui             # web UI at http://127.0.0.1:8585
```

## All Make Commands

| Command | Description |
|---|---|
| `make setup` | Create venv, install deps, prepare `.env` |
| `make run` | Start the terminal chat |
| `make ui` | Start the web UI (port 8585) |
| `make test` | Run pytest |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code with ruff |
| `make docker` | Build & run with Docker Compose |
| `make clean` | Remove venv, caches, build artifacts |
| `make help` | Show all available targets |

## Manual Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add your OPENAI_API_KEY
openvassal             # terminal chat
```

## How It Works

A **Steward** agent receives your messages and routes them to the right sub-agent:

```
You → Steward → Coding Agent      (code snippets, debugging)
              → Daily Work Agent   (tasks, notes, productivity)
              → ...more agents     (add your own)
```

All data is stored in a local **SQLite** database.

## Web UI

- **`/`** — Settings: API keys, models, agents, plans
- **`/chat`** — Chat with the Steward and see which agent responds

## Add a New Agent

1. Create `openvassal/agents/my_agent.py` (subclass `BaseAgent`)
2. Add an entry to `agents.yaml`
3. Restart — the Steward auto-discovers it

## Configuration

Edit `.env` for API keys and defaults, or use the web UI (`openvassal --setup`).

Supports **OpenAI**, **Anthropic** (Claude), **Google Gemini**, and any **OpenAI-compatible** API (DeepSeek, MiniMax, Kimi, Ollama, etc.) via custom providers + LiteLLM.

## Testing

```bash
pytest tests/ -v   # 20 tests
```

## License

MIT
