#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ClickML Pro — Quickstart
# One command to install everything and launch the dashboard.
#
#   curl -sSL https://raw.githubusercontent.com/AnantaXe/ClickML-Pro/main/quickstart.sh | bash
#   # or
#   chmod +x quickstart.sh && ./quickstart.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}[INFO]${RESET}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${RESET}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${RESET}  %s\n" "$*"; }
fail()  { printf "${RED}[FAIL]${RESET}  %s\n" "$*"; exit 1; }

# ── Banner ───────────────────────────────────────────────────────────────────
echo ""
printf "${BOLD}${CYAN}"
cat << 'EOF'
   _____ _ _      _    __  __ _       ____
  / ____| (_)    | |  |  \/  | |     |  _ \
 | |    | |_  ___| | _| \  / | |     | |_) |_ __ ___
 | |    | | |/ __| |/ / |\/| | |     |  __/| '__/ _ \
 | |____| | | (__|   <| |  | | |____ | |   | | | (_) |
  \_____|_|_|\___|_|\_\_|  |_|______||_|   |_|  \___/
EOF
printf "${RESET}\n"
echo "  Enterprise MLOps & Data Engineering Platform"
echo "  ─────────────────────────────────────────────"
echo ""

# ── Detect project root ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    cd "$SCRIPT_DIR"
else
    # Running via curl pipe — clone if not already in the repo
    if [[ ! -f "pyproject.toml" ]]; then
        info "Cloning ClickML-Pro repository…"
        git clone https://github.com/AnantaXe/ClickML-Pro.git
        cd ClickML-Pro
    fi
fi

PROJECT_ROOT="$(pwd)"
info "Project root: $PROJECT_ROOT"

# ── Check prerequisites ─────────────────────────────────────────────────────
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        fail "$1 is required but not found. Please install it first."
    fi
}

info "Checking prerequisites…"

check_cmd python3
check_cmd pip
check_cmd node
check_cmd npm

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 10) )); then
    fail "Python >= 3.10 is required (found $PYTHON_VERSION)"
fi

NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
if (( NODE_MAJOR < 16 )); then
    fail "Node.js >= 16 is required (found $(node -v))"
fi

ok "Python $PYTHON_VERSION  |  Node $(node -v)  |  npm $(npm -v)"

# ── Virtual environment ─────────────────────────────────────────────────────
VENV_DIR="$PROJECT_ROOT/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment…"
    python3 -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "Virtual environment activated ($VENV_DIR)"

# ── Install Python package ──────────────────────────────────────────────────
info "Installing ClickML Pro (pip install -e \".[dev]\")…"
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet
ok "Python package installed"

# ── .env file ───────────────────────────────────────────────────────────────
if [[ ! -f "$PROJECT_ROOT/.env" ]] && [[ -f "$PROJECT_ROOT/.env.example" ]]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    ok "Created .env from .env.example"
fi

# ── Build React dashboard ───────────────────────────────────────────────────
DASHBOARD_DIR="$PROJECT_ROOT/clickml_pro/ui/dashboard"

info "Installing dashboard dependencies (npm install)…"
(cd "$DASHBOARD_DIR" && npm install --silent)

info "Building dashboard (npm run build)…"
(cd "$DASHBOARD_DIR" && npm run build --silent)
ok "Dashboard built → $DASHBOARD_DIR/dist/"

# ── Run tests ────────────────────────────────────────────────────────────────
info "Running tests…"
if python -m pytest tests/ -q -p no:twisted --tb=short 2>/dev/null; then
    ok "All tests passed"
else
    warn "Some tests failed — the server may still work"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  ${GREEN}${BOLD}✔ ClickML Pro is ready!${RESET}\n"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Quick commands:"
echo ""
printf "    ${CYAN}clickml ui${RESET}              Launch dashboard + API (http://localhost:8000)\n"
printf "    ${CYAN}clickml ui --dev${RESET}        Vite dev server with hot-reload (port 5173)\n"
printf "    ${CYAN}clickml serve${RESET}           API server only\n"
printf "    ${CYAN}clickml serve --reload${RESET}  API server with auto-reload\n"
printf "    ${CYAN}clickml --help${RESET}          See all commands\n"
echo ""
printf "    ${CYAN}API docs${RESET}   → http://localhost:8000/docs\n"
printf "    ${CYAN}Dashboard${RESET}  → http://localhost:8000\n"
echo ""

# ── Optional: auto-launch ───────────────────────────────────────────────────
read -rp "Start the dashboard now? [Y/n] " answer
answer="${answer:-Y}"
if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo ""
    info "Starting ClickML Pro on http://localhost:8000 …"
    exec clickml ui
fi
