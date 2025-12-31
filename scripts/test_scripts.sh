#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/env.sh"
load_env_defaults

if command -v shellcheck >/dev/null 2>&1; then
  echo "Running shellcheck..."
  shellcheck "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/run_stack.sh "$SCRIPT_DIR"/lib/env.sh || true
else
  echo "shellcheck not available; skipping lint."
fi

# Validate boolean parser
is_true "true" && echo "is_true(true)=0" || echo "is_true(true)=1"
is_true "false" && echo "is_true(false)=0" || echo "is_true(false)=1"

# Compose selection smoke
USE_OPIK=false
bash -c "$SCRIPT_DIR/run_stack.sh status >/dev/null 2>&1 || true"
echo "Script checks complete."
