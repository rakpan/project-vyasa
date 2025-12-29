#!/usr/bin/env bash
# deploy/stop.sh - Shutdown for Project Vyasa
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[WARN] deploy/.env not found. Continuing without env file."
  ENV_ARGS=()
else
  ENV_ARGS=(--env-file "$ENV_FILE")
fi

echo "Stopping Project Vyasa stack..."
docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" down

echo -n "Do you want to delete all data volumes? (y/N): "
read -r CONFIRM
if [[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]]; then
  echo "Removing containers and volumes..."
  docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" down -v
else
  echo "Volumes preserved."
fi
