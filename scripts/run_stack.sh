#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/deploy/.env"
SECRETS_FILE="$PROJECT_ROOT/deploy/.secrets.env"
. "$SCRIPT_DIR/lib/env.sh"

load_env_defaults
require_cmd docker

# Load deploy/.env and deploy/.secrets.env if present (without mutating them)
load_env_file() {
  local file="$1"
  if [ -f "$file" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$file"
    set +a
  fi
}

load_env_file "$ENV_FILE"
load_env_file "$SECRETS_FILE"

# Detect compose (plugin or standalone)
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  echo "Error: Docker Compose not found (install docker-compose or enable docker compose plugin)" >&2
  exit 1
fi

BASE_COMPOSE="$PROJECT_ROOT/deploy/docker-compose.yml"
OPIK_COMPOSE="$PROJECT_ROOT/deploy/docker-compose.opik.yml"

usage() {
  cat <<EOF
Usage: $0 <start|stop|up|down|logs|status> [--opik] [--detach] [service]
Examples:
  $0 start                 # start Vyasa in detached mode
  $0 start --opik          # start Vyasa + Opik in detached mode
  $0 up --detach           # start Vyasa (explicit up)
  $0 up --opik --detach    # start Vyasa + Opik (explicit up)
  $0 stop                  # stop all Vyasa services
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
  echo "${COMPOSE[@]}" "${files[@]}"
}

print_config_summary

# Check for port conflicts before starting
check_port_conflict() {
  local port=$1
  local service=$2
  
  # Check if port is in use by a Docker container
  if docker ps --format '{{.Names}}' | grep -q "^${service}$" 2>/dev/null; then
    echo "Warning: Container '${service}' is already running and may be using port ${port}." >&2
    return 1
  fi
  
  # Check if port is in use (using ss, netstat, or lsof)
  if command -v ss >/dev/null 2>&1; then
    if ss -tuln 2>/dev/null | grep -q ":${port} "; then
      echo "Error: Port ${port} is already in use." >&2
      echo "       This will prevent the ${service} container from starting." >&2
      return 1
    fi
  elif command -v netstat >/dev/null 2>&1; then
    if netstat -tuln 2>/dev/null | grep -q ":${port} "; then
      echo "Error: Port ${port} is already in use." >&2
      echo "       This will prevent the ${service} container from starting." >&2
      return 1
    fi
  fi
  
  return 0
}

# Load port configuration from .env if available
if [ -f "$PROJECT_ROOT/deploy/.env" ]; then
  set +u
  export $(grep -E '^PORT_' "$PROJECT_ROOT/deploy/.env" | xargs) 2>/dev/null || true
  set -u
fi

# Check critical ports (best effort - may not catch all conflicts)
PORT_DRAFTER="${PORT_DRAFTER:-11435}"
if ! check_port_conflict "$PORT_DRAFTER" "drafter"; then
  echo "" >&2
  echo "Resolution options:" >&2
  echo "  1. Stop the conflicting container:" >&2
  echo "     docker stop ollama-compose" >&2
  echo "  2. Or use a different port by setting PORT_DRAFTER in deploy/.env" >&2
  echo "     Example: PORT_DRAFTER=11436" >&2
  echo "  3. Or remove the conflicting container if not needed:" >&2
  echo "     docker rm -f ollama-compose" >&2
  echo "" >&2
  # Don't exit - let Docker Compose handle the error with a clearer message
fi

# Validate Opik environment variables and setup if Opik is enabled
if $USE_OPIK; then
  # Check for required Opik environment variables
  if [ -z "${OPIK_POSTGRES_PASSWORD:-}" ]; then
    echo "Error: OPIK_POSTGRES_PASSWORD is required when using --opik flag." >&2
    echo "       Set it in deploy/.env or deploy/.secrets.env" >&2
    exit 1
  fi
  
  if [ -z "${OPIK_SECRET_KEY:-}" ]; then
    echo "Error: OPIK_SECRET_KEY is required when using --opik flag." >&2
    echo "       Set it in deploy/.env or deploy/.secrets.env" >&2
    echo "       Use a strong random value (e.g., openssl rand -hex 32)" >&2
    exit 1
  fi
  
  # Warn if placeholder values are detected
  if [ "${OPIK_SECRET_KEY:-}" = "changeme-opik" ] || [ "${OPIK_SECRET_KEY:-}" = "changeme" ]; then
    echo "Warning: OPIK_SECRET_KEY appears to be a placeholder value." >&2
    echo "         Please set a strong random secret before deploying." >&2
  fi

  # Ensure network exists (Opik compose requires external network)
  # Load NETWORK_NAME from .env if available, otherwise default to vyasa-net
  if [ -f "$PROJECT_ROOT/deploy/.env" ]; then
    # Source .env to get NETWORK_NAME (if set)
    set +u  # Temporarily allow unset variables
    export $(grep -E '^NETWORK_NAME=' "$PROJECT_ROOT/deploy/.env" | xargs) 2>/dev/null || true
    set -u
  fi
  NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
  if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "Creating external network $NETWORK_NAME (required by Opik)..."
    docker network create "$NETWORK_NAME" || true
  fi
  
  # Check Opik data directories (Docker will create them if missing, but we check for better UX)
  OPIK_DATA_DIR="/raid/vyasa/opik_data"
  
  # Best-effort: Try to create directories if they don't exist (no sudo required)
  # If we can't create them, Docker will create them when containers start
  if [ ! -d "$OPIK_DATA_DIR" ]; then
    # Try to create parent directory first
    if [ ! -d "/raid/vyasa" ]; then
      mkdir -p "/raid/vyasa" 2>/dev/null || true
    fi
    
    # Try to create Opik data directories
    for subdir in postgres redis opik; do
      dir="$OPIK_DATA_DIR/$subdir"
      if [ ! -d "$dir" ]; then
        mkdir -p "$dir" 2>/dev/null || true
      fi
    done
  fi
  
  # Verify directories exist (either we created them or they already existed)
  if [ ! -d "$OPIK_DATA_DIR/postgres" ] || [ ! -d "$OPIK_DATA_DIR/redis" ] || [ ! -d "$OPIK_DATA_DIR/opik" ]; then
    echo "Note: Opik data directories will be created by Docker when containers start." >&2
    echo "      If you encounter permission issues, check container logs." >&2
  fi
fi

case "$COMMAND" in
  start)
    DETACH="-d"
    $(compose_cmd) up $DETACH
    
    # Wait for Opik services to be ready (if Opik is enabled)
    if $USE_OPIK && [ -n "$DETACH" ]; then
      echo "Waiting for Opik services to be ready..."
      max_attempts=30
      attempt=0
      
      while [ $attempt -lt $max_attempts ]; do
        if $(compose_cmd) ps opik-api 2>/dev/null | grep -q "Up" && \
           $(compose_cmd) ps opik-postgres 2>/dev/null | grep -q "Up" && \
           $(compose_cmd) ps opik-redis 2>/dev/null | grep -q "Up"; then
          echo "Opik services are running."
          # Give opik-api a moment to initialize (migrations, etc.)
          sleep 3
          break
        fi
        attempt=$((attempt + 1))
        sleep 2
      done
      
      if [ $attempt -eq $max_attempts ]; then
        echo "Warning: Opik services may not be fully ready. Check logs with: $(compose_cmd) logs opik-api" >&2
      fi
    fi
    ;;
  up)
    $(compose_cmd) up $DETACH
    
    # Wait for Opik services to be ready (if Opik is enabled and detached)
    if $USE_OPIK && [ -n "$DETACH" ]; then
      echo "Waiting for Opik services to be ready..."
      max_attempts=30
      attempt=0
      
      while [ $attempt -lt $max_attempts ]; do
        if $(compose_cmd) ps opik-api 2>/dev/null | grep -q "Up" && \
           $(compose_cmd) ps opik-postgres 2>/dev/null | grep -q "Up" && \
           $(compose_cmd) ps opik-redis 2>/dev/null | grep -q "Up"; then
          echo "Opik services are running."
          sleep 3
          break
        fi
        attempt=$((attempt + 1))
        sleep 2
      done
      
      if [ $attempt -eq $max_attempts ]; then
        echo "Warning: Opik services may not be fully ready. Check logs with: $(compose_cmd) logs opik-api" >&2
      fi
    fi
    ;;
  stop)
    $(compose_cmd) down
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
