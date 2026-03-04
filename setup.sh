#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  OpenVassal — One-command bootstrap
#  Usage:  ./setup.sh          (local clone)
#          curl -sSL <url> | bash   (remote)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${CYAN}▸${RESET} $*"; }
ok()    { echo -e "${GREEN}✔${RESET} $*"; }

# ── Pre-flight checks ───────────────────────────────────────

if ! command -v python3 &>/dev/null; then
    echo "❌  python3 is required but not found. Please install Python 3.11+."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "❌  Python 3.11+ required (found $PY_VERSION)."
    exit 1
fi

echo ""
echo -e "${BOLD}${CYAN}⚡ OpenVassal Setup${RESET}"
echo -e "${DIM}  CrewAI + mem0 Personal Knowledge Base${RESET}"
echo -e "${DIM}───────────────────────────────────────${RESET}"
echo ""

# ── Virtual environment ─────────────────────────────────────

if [ -d ".venv" ] && ! .venv/bin/python3 --version &>/dev/null; then
    info "Existing venv is broken (repo may have moved). Recreating..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv .venv
    ok "Virtual environment created"
else
    ok "Virtual environment exists"
fi

source .venv/bin/activate

# ── Dependencies ─────────────────────────────────────────────

info "Installing dependencies (crewai, mem0, ...)..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q
ok "Dependencies installed"

# ── Environment file ─────────────────────────────────────────

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Created .env from .env.example"

    echo ""
    echo -e "${BOLD}🔑  API Key Setup${RESET}"
    read -rp "Enter your OpenAI API key (required for mem0, or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${api_key}|" .env
        else
            sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${api_key}|" .env
        fi
        ok "API key saved to .env"
    else
        echo -e "  ${DIM}Skipped — edit .env later to add your keys.${RESET}"
    fi
else
    ok ".env already exists"
fi

# ── Done ─────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}✅  All set!${RESET}"
echo ""
echo -e "  ${CYAN}make run${RESET}    Start the terminal chat"
echo -e "  ${CYAN}make ui${RESET}     Start the web UI"
echo -e "  ${CYAN}make test${RESET}   Run tests"
echo -e "  ${CYAN}make help${RESET}   Show all commands"
echo ""
