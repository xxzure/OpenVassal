# Subordinates — AI Personal Assistant

A multi-agent AI personal assistant. A **Steward Agent** orchestrates pluggable
sub-agents — each specialized in a domain (coding, daily work, finances, health,
phone calls) — to manage your digital life.

## Quick start

```bash
# 1. Clone & install
git clone <repo-url> && cd subordinates
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env          # fill in your API keys

# 3. Run
subordinates                   # starts the interactive CLI
```

## Architecture

```
User ──▶ Steward Agent ──┬──▶ Coding Agent
                         ├──▶ Daily Work Agent
                         ├──▶ Financial Agent   (future)
                         ├──▶ Health Agent       (future)
                         └──▶ Telephone Agent    (future)
                              │
                         Data Layer (SQLite + connectors)
```

- **Plugin-based**: drop a new agent module in `subordinates/agents/` and register
  it in `agents.yaml` — it's automatically available.
- **Multi-LLM**: each agent can use a different model (OpenAI, Anthropic, Gemini, …)
  via [LiteLLM](https://docs.litellm.ai/docs/providers).
- **Insurance-style plans**: base subscription + per-agent add-ons.

## Project structure

```
subordinates/
├── subordinates/
│   ├── agents/          # pluggable agent modules
│   │   ├── base.py      # BaseAgent interface
│   │   ├── registry.py  # auto-discovery & registration
│   │   ├── steward.py   # orchestrator
│   │   ├── coding.py    # coding sub-agent
│   │   └── daily_work.py
│   ├── data/            # unified data layer
│   ├── plans/           # cost / plan management
│   ├── config.py        # settings
│   └── main.py          # CLI entry point
├── tests/
├── agents.yaml          # agent registry config
├── pyproject.toml
└── .env.example
```

## License

MIT
