#!/usr/bin/env bash
# deploy/deploy.sh - Pre-flight checks and stack launch for Project Vyasa
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Ensure critical directories exist with writable permissions
for dir in /raid/telemetry /raid/datasets; do
  mkdir -p "$dir"
  chmod 0755 "$dir" 2>/dev/null || true
done
chown "$(id -u):$(id -g)" /raid/telemetry /raid/datasets 2>/dev/null || true

# GPU check
if ! nvidia-smi >/dev/null 2>&1; then
  echo "[ERROR] nvidia-smi not responsive. Verify drivers before deployment." >&2
  exit 1
fi

# Delegate to start.sh
"$SCRIPT_DIR/start.sh"
