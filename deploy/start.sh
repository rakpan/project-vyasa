#!/usr/bin/env bash
# deploy/start.sh - Master Ignition for Project Vyasa
set -euo pipefail

RED="\033[0;31m"
GREEN="\033[0;32m"
NC="\033[0m"

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"

# Pre-flight: .env
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}[ERROR] deploy/.env not found. Copy deploy/.env.example and set your values.${NC}" >&2
  exit 1
fi

# Pre-flight: Docker daemon
if ! docker info >/dev/null 2>&1; then
  echo -e "${RED}[ERROR] Docker is not running. Please start Docker and retry.${NC}" >&2
  exit 1
fi

# Launch stack
echo -e "${GREEN}Starting Project Vyasa stack...${NC}"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

# Wait for ArangoDB (vyasa-memory)
MEMORY_CONTAINER=${CONTAINER_MEMORY:-vyasa-memory}
ATTEMPTS=30
SLEEP_SECONDS=2

printf "Waiting for %s to become healthy" "$MEMORY_CONTAINER"
for i in $(seq 1 $ATTEMPTS); do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$MEMORY_CONTAINER" 2>/dev/null || echo "")
  if [[ "$STATUS" == "healthy" ]]; then
    echo -e "\n${GREEN}ArangoDB is healthy.${NC}"
    break
  fi
  printf "."
  sleep "$SLEEP_SECONDS"
  if [[ "$i" -eq "$ATTEMPTS" ]]; then
    echo -e "\n${RED}[ERROR] ArangoDB did not become healthy in time.${NC}" >&2
    exit 1
  fi
done

# Seed roles via orchestrator container
ORCH_CONTAINER=${CONTAINER_ORCHESTRATOR:-vyasa-orchestrator}
SEED_SCRIPT=/app/deploy/scripts/seed_roles.py
if docker exec "$ORCH_CONTAINER" test -f "$SEED_SCRIPT"; then
  echo -e "${GREEN}Seeding roles via orchestrator...${NC}"
  docker exec "$ORCH_CONTAINER" python3 "$SEED_SCRIPT"
else
  echo -e "${RED}[WARN] Seed script not found in orchestrator: $SEED_SCRIPT${NC}"
fi

# Output URLs
CONSOLE_PORT=${PORT_CONSOLE:-3000}
ARANGO_PORT=${PORT_MEMORY:-8529}

echo -e "${GREEN}Project Vyasa is starting up.${NC}"
echo "Console:  http://localhost:${CONSOLE_PORT}"
echo "ArangoDB: http://localhost:${ARANGO_PORT}"
