#!/usr/bin/env bash
set -euo pipefail

# ==========================================
# PROJECT VYASA - INITIALIZATION SCRIPT
# ==========================================
# Sets up local Python environment and seeds core roles.
# Requires Python 3.11+ and Docker stack running (ArangoDB available).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "--> Initializing Project Vyasa environment at $PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi

python3 - <<'PY'
import sys
import platform
major, minor = sys.version_info[:2]
if major < 3 or (major == 3 and minor < 11):
    print(f"[ERROR] Python 3.11+ required, found {platform.python_version()}", file=sys.stderr)
    sys.exit(1)
PY

echo "--> Creating virtual environment ($VENV_DIR)..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "--> Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$REQ_FILE"

echo "--> Seeding roles into ArangoDB (requires stack running)..."
if python -m src.scripts.seed_roles; then
  echo "✓ Seeded roles successfully."
else
  echo "[WARN] Seeding failed. Ensure ArangoDB is running via deploy/start.sh, then rerun: source .venv/bin/activate && python -m src.scripts.seed_roles" >&2
fi

echo ""
echo "=========================================="
echo "PROJECT VYASA SETUP COMPLETE"
echo "=========================================="
echo "Virtualenv: $VENV_DIR"
echo "Next steps:"
echo "1) source .venv/bin/activate"
echo "2) ./deploy/start.sh (to start stack)"
echo "3) pytest (to validate)"
