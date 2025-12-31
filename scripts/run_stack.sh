#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$SCRIPT_DIR/lib/env.sh"

load_env_defaults
require_cmd docker
require_cmd docker-compose || true
require_cmd docker compose || true

BASE_COMPOSE="$PROJECT_ROOT/deploy/docker-compose.yml"
OPIK_COMPOSE="$PROJECT_ROOT/deploy/docker-compose.opik.yml"

usage() {
  cat <<EOF
Usage: $0 <up|down|logs|status> [--opik] [--detach] [service]
Examples:
  $0 up --detach           # start Vyasa only
  $0 up --opik --detach    # start Vyasa + Opik
  $0 down --opik           # stop all including Opik
  $0 logs --opik opik-api  # tail Opik API logs
EOF
}

COMMAND="${1:-}"
shift || true

USE_OPIK=false
DETACH=""

while [ $# -gt 0 ]; do
  case "$1" in
    --opik) USE_OPIK=true ;;
    --detach|-d) DETACH="-d" ;;
    *) break ;;
  esac
  shift
done

SERVICE="${1:-}"

compose_cmd() {
  local files=("-f" "$BASE_COMPOSE")
  if $USE_OPIK; then
    files+=("-f" "$OPIK_COMPOSE")
  fi
  echo docker compose "${files[@]}"
}

print_config_summary

case "$COMMAND" in
  up)
    $(compose_cmd) up $DETACH
    ;;
  down)
    $(compose_cmd) down
    ;;
  logs)
    $(compose_cmd) logs -f ${SERVICE:+$SERVICE}
    ;;
  status)
    $(compose_cmd) ps
    ;;
  *)
    usage
    exit 1
    ;;
esac
