# OpenVassal — AI Personal Assistant

> A multi-agent AI personal assistant with a steward/sub-agent architecture.
> Each agent is a plug-in that can use its own LLM. Break data barriers by
> merging all your personal data into one unified store.

## Quick Start

```bash
git clone <repo-url> && cd openvassal
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # add your API key(s)
openvassal --setup             # launch the config UI
openvassal                     # starts the interactive CLI
```

## Architecture

```
You ──▶ Steward Agent ──┬──▶ Coding Agent
                        ├──▶ Daily Work Agent
                        └──▶ … (plug-in more)
                             │
                        SQLite (unified data store)
```

## Key Features

- **Multi-LLM**: each agent picks its own model (OpenAI / Anthropic / Gemini)
- **Plugin-based**: drop a new agent module in `openvassal/agents/` and register
  it in `agents.yaml` — done
- **Insurance-style plans**: base subscription + per-agent add-ons
- **Local-first**: SQLite database, runs anywhere
- **Web UI**: config dashboard + chat interface at `http://127.0.0.1:8585`

## Project Layout

```
openvassal/             ← Python package
├── agents/             ← plug-in sub-agents
├── data/               ← unified data store & connectors
├── plans/              ← cost / subscription logic
├── web/                ← FastAPI server + chat & config UI
└── main.py             ← CLI entry point
docker/                 ← Dockerfile & Compose
tests/                  ← pytest unit tests
agents.yaml             ← agent registry
```
