# ─────────────────────────────────────────────────────────────
#  OpenVassal — Makefile
# ─────────────────────────────────────────────────────────────

SHELL      := /bin/bash
PYTHON     := python3.13
VENV       := .venv313
BIN        := $(VENV)/bin
PIP        := $(BIN)/pip
APP        := $(BIN)/openvassal
PORT       := 8585

.DEFAULT_GOAL := help

# ── Setup ────────────────────────────────────────────────────

.PHONY: setup
setup: $(VENV) .env ## Create venv, install deps, and prepare .env
	@echo ""
	@echo "✅  Setup complete. Run 'make run' to start."

$(VENV): pyproject.toml
	@if [ ! -e $(BIN)/python3 ] && [ ! -e $(BIN)/python ]; then \
		$(PYTHON) -m venv $(VENV); \
		$(PIP) install --upgrade pip -q; \
		$(PIP) install -e ".[dev]" -q; \
		touch $(VENV); \
	fi

.env:
	@cp .env.example .env
	@echo "📝  Created .env from .env.example — add your API key(s)."

# ── Run ──────────────────────────────────────────────────────

.PHONY: run
run: $(VENV) ## Start the terminal chat
	$(APP)

.PHONY: ui
ui: $(VENV) ## Start the web UI (default port: 8585)
	$(APP) --setup --port $(PORT)

# ── Quality ──────────────────────────────────────────────────

.PHONY: test
test: $(VENV) ## Run tests
	$(BIN)/pytest tests/ -v

.PHONY: lint
lint: $(VENV) ## Run linter (ruff)
	$(BIN)/ruff check openvassal/ tests/

.PHONY: format
format: $(VENV) ## Auto-format code (ruff)
	$(BIN)/ruff format openvassal/ tests/

# ── Docker ───────────────────────────────────────────────────

.PHONY: docker
docker: .env ## Build and run with Docker Compose
	docker compose -f docker/docker-compose.yml up --build

.PHONY: docker-down
docker-down: ## Stop Docker containers
	docker compose -f docker/docker-compose.yml down

# ── Cleanup ──────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove venv, caches, and build artifacts
	rm -rf $(VENV) *.egg-info dist build .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹  Cleaned."

# ── Help ─────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
