# ⚡ OpenVassal

An open-source AI personal assistant powered by multiple agents, each with its own LLM.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add your OPENAI_API_KEY
```

## Usage

```bash
openvassal --setup     # web UI at http://127.0.0.1:8585
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

Supports **OpenAI**, **Anthropic** (Claude), and **Google Gemini** via LiteLLM.

## Testing

```bash
pytest tests/ -v   # 20 tests
```

## License

MIT
