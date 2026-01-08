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
Usage: $0 <start|stop|restart|up|down|logs|status|backup|verify> [--opik] [--firecrawl] [--vision-only] [--hot|--dev-console] [--detach] [service]

Optional Services:
  --opik                   Enable Opik observability services
  --firecrawl              Enable Firecrawl web scraping sidecar (requires FIRECRAWL_IMAGE)
  --vision-only            Start ONLY vision service (nothing else). Useful for testing or GPU memory management.

Hot Reload Options:
  --hot, --dev-console     Enable hot reload for console (mounts local source, auto-refresh on changes)
  CONSOLE_HOT_RELOAD=true   Set in deploy/.env for persistent hot reload (no flag needed)

Examples:
  $0 start                 # start Vyasa in detached mode
  $0 start --opik          # start Vyasa + Opik in detached mode
  $0 start --firecrawl     # start Vyasa + Firecrawl (requires FIRECRAWL_IMAGE)
  $0 start --opik --firecrawl  # start Vyasa + Opik + Firecrawl
  $0 start --vision-only   # start ONLY vision service (nothing else)
  $0 start --hot           # start Vyasa with console hot reload enabled
  $0 restart --hot         # restart with console hot reload
  $0 up --detach           # start Vyasa (explicit up)
  $0 up --opik --detach    # start Vyasa + Opik (explicit up)
  $0 stop                  # stop all Vyasa services (including vision if running)
  $0 down --opik           # stop all including Opik
  $0 logs --opik opik-api  # tail Opik API logs
  $0 backup                # run full backup (ArangoDB + Qdrant)
  $0 verify                # verify backups exist and are valid

Hot Reload:
  When enabled, changes to src/console/ are automatically detected and the page
  refreshes when you save files. No container rebuild needed!
EOF
}

COMMAND="${1:-}"
shift || true

USE_OPIK=false
USE_FIRECRAWL=false
USE_VISION_ONLY=false
DEV_CONSOLE=false
DETACH=""

# Check for hot reload environment variable (persistent setting)
if [ "${CONSOLE_HOT_RELOAD:-}" = "true" ] || [ "${CONSOLE_HOT_RELOAD:-}" = "1" ]; then
  DEV_CONSOLE=true
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --opik) USE_OPIK=true ;;
    --firecrawl) USE_FIRECRAWL=true ;;
    --vision-only) USE_VISION_ONLY=true ;;
    --dev-console|--hot|--dev) DEV_CONSOLE=true ;;
    --detach|-d) DETACH="-d" ;;
    *) break ;;
  esac
  shift
done

SERVICE="${1:-}"

compose_cmd() {
  # Ensure NETWORK_NAME is exported before compose commands
  export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
  
  local files=("-f" "$BASE_COMPOSE")
  if $USE_OPIK; then
    files+=("-f" "$OPIK_COMPOSE")
  fi
  if $DEV_CONSOLE; then
    files+=("-f" "$PROJECT_ROOT/deploy/docker-compose.dev-console.yml")
  fi
  # Pass env file explicitly to ensure NETWORK_NAME and other variables are available
  if [ -f "$ENV_FILE" ]; then
    files+=("--env-file" "$ENV_FILE")
  fi
  if [ -f "$SECRETS_FILE" ]; then
    files+=("--env-file" "$SECRETS_FILE")
  fi
  echo "${COMPOSE[@]}" "${files[@]}"
}

# Helper to get profile flags for compose commands
compose_profiles() {
  local profiles=()
  if $USE_FIRECRAWL; then
    profiles+=("--profile" "firecrawl")
  fi
  if $USE_VISION_ONLY; then
    profiles+=("--profile" "vision")
  fi
  echo "${profiles[@]}"
}

# Print dev console status
if $DEV_CONSOLE; then
  echo "🔥 Console hot reload enabled:"
  echo "  - Using Dockerfile.dev"
  echo "  - Mounting source: $PROJECT_ROOT/src/console"
  echo "  - Changes will auto-refresh in browser (no rebuild needed)"
  echo "  - To disable: remove --hot flag or set CONSOLE_HOT_RELOAD=false in deploy/.env"
  echo ""
fi

# Validate Firecrawl configuration if enabled
if $USE_FIRECRAWL; then
  # Load FIRECRAWL_IMAGE from .env if not already set
  if [ -z "${FIRECRAWL_IMAGE:-}" ] && [ -f "$ENV_FILE" ]; then
    set +u
    # shellcheck source=/dev/null
    source "$ENV_FILE" 2>/dev/null || true
    set -u
  fi
  
  if [ -z "${FIRECRAWL_IMAGE:-}" ]; then
    echo "Error: --firecrawl flag requires FIRECRAWL_IMAGE to be set in deploy/.env" >&2
    echo "       Example: FIRECRAWL_IMAGE=firecrawl:local" >&2
    echo "       Build Firecrawl: git clone https://github.com/firecrawl/firecrawl.git && docker build -t firecrawl:local ." >&2
    exit 1
  fi
  
  # Verify image exists locally (warning only, not fatal)
  if ! docker image inspect "${FIRECRAWL_IMAGE}" >/dev/null 2>&1; then
    echo "Warning: FIRECRAWL_IMAGE=${FIRECRAWL_IMAGE} not found locally." >&2
    echo "         Firecrawl container will fail to start." >&2
    echo "         Build it: git clone https://github.com/firecrawl/firecrawl.git && docker build -t ${FIRECRAWL_IMAGE} ." >&2
  fi
fi

# Print config summary (check USE_OPIK and USE_FIRECRAWL flags)
if $USE_OPIK || $USE_FIRECRAWL; then
  echo "Config summary:"
  echo "  Vyasa: compose=deploy/docker-compose.yml"
  if $USE_OPIK; then
    echo "  Opik: enabled (--opik flag)"
  fi
  if $USE_FIRECRAWL; then
    echo "  Firecrawl: enabled (--firecrawl flag, image: ${FIRECRAWL_IMAGE:-not set})"
  fi
else
  print_config_summary
fi

# Ensure NETWORK_NAME is set before docker-compose validation
# Load NETWORK_NAME from .env if available, otherwise default to vyasa-net
if [ -f "$PROJECT_ROOT/deploy/.env" ]; then
  # Source .env to get NETWORK_NAME (if set)
  set +u  # Temporarily allow unset variables
  export $(grep -E '^NETWORK_NAME=' "$PROJECT_ROOT/deploy/.env" | xargs) 2>/dev/null || true
  set -u
fi
export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"

# Ensure network exists (required by both main compose and Opik compose)
# This must happen before any compose command that validates the file
# Network must exist before Docker Compose validates compose files
export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
  echo "Creating network $NETWORK_NAME..."
  docker network create "$NETWORK_NAME" || true
  # Give Docker a moment to register the network
  sleep 1
fi

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

# Ensure ARANGO_ROOT_PASSWORD is set (auto-generate if missing)
# This password is used by both the graph container (for initialization) and orchestrator (for connection)
ensure_arango_password() {
  local var_name="ARANGO_ROOT_PASSWORD"
  local comment="ArangoDB root password (used by graph container and orchestrator)"
  
  # Check if variable is already set in environment
  eval "local current_value=\${${var_name}:-}"
  if [ -n "$current_value" ]; then
    return 0
  fi
  
  # Check if it exists in .env file (uncommented)
  if [ -f "$ENV_FILE" ]; then
    local file_line
    file_line=$(grep -E "^[[:space:]]*${var_name}=" "$ENV_FILE" | head -1 || true)
    if [ -n "$file_line" ]; then
      # Variable exists in file - extract and export it
      local file_value
      file_value=$(echo "$file_line" | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr -d '"' | tr -d "'" || true)
      if [ -n "$file_value" ]; then
        eval "export ${var_name}=\"${file_value}\""
        return 0
      fi
    fi
  fi
  
  # Need to generate it
  if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl not found. Cannot auto-generate ${var_name}." >&2
    echo "       Please set ${var_name} in deploy/.env or deploy/.secrets.env" >&2
    return 1
  fi
  
  echo "Auto-generating ${var_name} (will be saved to deploy/.env)..."
  local generated_value
  generated_value=$(openssl rand -hex 16)
  
  # Append to .env file
  if [ -f "$ENV_FILE" ]; then
    echo "" >> "$ENV_FILE"
    echo "# ${comment} (auto-generated)" >> "$ENV_FILE"
    echo "${var_name}=${generated_value}" >> "$ENV_FILE"
    echo "  ✓ Saved to $ENV_FILE"
  else
    # Create .env file
    echo "# ${comment} (auto-generated)" > "$ENV_FILE"
    echo "${var_name}=${generated_value}" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "  ✓ Created $ENV_FILE with ${var_name}"
  fi
  
  eval "export ${var_name}=\"${generated_value}\""
  return 0
}

# Ensure ARANGO_ROOT_PASSWORD is set (generate if needed)
if ! ensure_arango_password; then
  exit 1
fi

# Ensure QDRANT_API_KEY is set (auto-generate if missing)
# This API key is used by the vector container (for authentication) and orchestrator/console (for connection)
ensure_qdrant_api_key() {
  local var_name="QDRANT_API_KEY"
  local comment="Qdrant API key (used by vector container and orchestrator/console)"
  
  # Check if variable is already set in environment
  eval "local current_value=\${${var_name}:-}"
  if [ -n "$current_value" ]; then
    return 0
  fi
  
  # Check if it exists in .env file (uncommented)
  if [ -f "$ENV_FILE" ]; then
    local file_line
    file_line=$(grep -E "^[[:space:]]*${var_name}=" "$ENV_FILE" | head -1 || true)
    if [ -n "$file_line" ]; then
      # Variable exists in file - extract and export it
      local file_value
      file_value=$(echo "$file_line" | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr -d '"' | tr -d "'" || true)
      if [ -n "$file_value" ]; then
        eval "export ${var_name}=\"${file_value}\""
        return 0
      fi
    fi
  fi
  
  # Need to generate it
  if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl not found. Cannot auto-generate ${var_name}." >&2
    echo "       Please set ${var_name} in deploy/.env or deploy/.secrets.env" >&2
    return 1
  fi
  
  echo "Auto-generating ${var_name} (will be saved to deploy/.env)..."
  local generated_value
  generated_value=$(openssl rand -hex 16)
  
  # Append to .env file
  if [ -f "$ENV_FILE" ]; then
    echo "" >> "$ENV_FILE"
    echo "# ${comment} (auto-generated)" >> "$ENV_FILE"
    echo "${var_name}=${generated_value}" >> "$ENV_FILE"
    echo "  ✓ Saved to $ENV_FILE"
  else
    # Create .env file
    echo "# ${comment} (auto-generated)" > "$ENV_FILE"
    echo "${var_name}=${generated_value}" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "  ✓ Created $ENV_FILE with ${var_name}"
  fi
  
  eval "export ${var_name}=\"${generated_value}\""
  return 0
}

# Ensure QDRANT_API_KEY is set (generate if needed)
if ! ensure_qdrant_api_key; then
  exit 1
fi

# Validate Opik environment variables and setup if Opik is enabled
if $USE_OPIK; then
  # Auto-generate Opik secrets if they don't exist
  # These secrets MUST be persistent - they're used to access existing database data
  # We generate them once and store them in .env so they persist across restarts
  
  # Helper function to ensure a variable is set, generating it if needed
  ensure_opik_secret() {
    local var_name="$1"
    local comment="$2"
    
    # Check if variable is already set in environment
    eval "local current_value=\${${var_name}:-}"
    if [ -n "$current_value" ]; then
      return 0
    fi
    
    # Check if it exists in .env file (uncommented)
    if [ -f "$ENV_FILE" ]; then
      local file_line
      file_line=$(grep -E "^[[:space:]]*${var_name}=" "$ENV_FILE" | head -1 || true)
      if [ -n "$file_line" ]; then
        # Variable exists in file - extract and export it
        local file_value
        file_value=$(echo "$file_line" | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr -d '"' | tr -d "'" || true)
        if [ -n "$file_value" ]; then
          eval "export ${var_name}=\"${file_value}\""
          return 0
        fi
      fi
    fi
    
    # Need to generate it
    if ! command -v openssl >/dev/null 2>&1; then
      echo "Error: openssl not found. Cannot auto-generate ${var_name}." >&2
      echo "       Please set ${var_name} in deploy/.env or deploy/.secrets.env" >&2
      return 1
    fi
    
    echo "Auto-generating ${var_name} (will be saved to deploy/.env)..."
    local generated_value
    generated_value=$(openssl rand -hex 32)
    
    # Append to .env file
    if [ -f "$ENV_FILE" ]; then
      echo "" >> "$ENV_FILE"
      echo "# ${comment} (auto-generated)" >> "$ENV_FILE"
      echo "${var_name}=${generated_value}" >> "$ENV_FILE"
      echo "  ✓ Saved to $ENV_FILE"
    else
      # Create .env file
      echo "# ${comment} (auto-generated)" > "$ENV_FILE"
      echo "${var_name}=${generated_value}" >> "$ENV_FILE"
      chmod 600 "$ENV_FILE"
      echo "  ✓ Created $ENV_FILE with ${var_name}"
    fi
    
    eval "export ${var_name}=\"${generated_value}\""
    return 0
  }
  
  # Ensure both secrets are set (generate if needed)
  if ! ensure_opik_secret "OPIK_POSTGRES_PASSWORD" "Opik PostgreSQL password"; then
    exit 1
  fi
  
  if ! ensure_opik_secret "OPIK_SECRET_KEY" "Opik API secret key"; then
    exit 1
  fi
  
  # Warn if placeholder values are detected (user should change them)
  if [ "${OPIK_SECRET_KEY:-}" = "changeme-opik" ] || [ "${OPIK_SECRET_KEY:-}" = "changeme" ]; then
    echo "Warning: OPIK_SECRET_KEY appears to be a placeholder value." >&2
    echo "         Please set a strong random secret before deploying." >&2
  fi
  if [ "${OPIK_POSTGRES_PASSWORD:-}" = "changeme" ] || [ "${OPIK_POSTGRES_PASSWORD:-}" = "changeme-opik" ]; then
    echo "Warning: OPIK_POSTGRES_PASSWORD appears to be a placeholder value." >&2
    echo "         Please set a secure password before deploying." >&2
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
    # Ensure network exists before compose validation
    export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
    if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
      echo "Creating network $NETWORK_NAME..."
      docker network create "$NETWORK_NAME" || true
    fi
    DETACH="-d"
    if $USE_VISION_ONLY; then
      # Start ONLY vision service
      echo "Starting vision service only..."
      $(compose_cmd) --profile vision up $DETACH cortex-vision
    else
      $(compose_cmd) up $DETACH $(compose_profiles)
    fi
    
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
    # Ensure network exists before compose validation
    export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
    if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
      echo "Creating network $NETWORK_NAME..."
      docker network create "$NETWORK_NAME" || true
    fi
    if $USE_VISION_ONLY; then
      # Start ONLY vision service
      echo "Starting vision service only..."
      $(compose_cmd) --profile vision up $DETACH cortex-vision
    else
      $(compose_cmd) up $DETACH $(compose_profiles)
    fi
    
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
    # Stop all services including vision if it exists
    # First stop main services
    $(compose_cmd) down --remove-orphans $(compose_profiles) 2>/dev/null || true
    # Also stop vision if it's running (even if not in profile)
    if docker ps --format '{{.Names}}' | grep -q "^.*cortex-vision$" 2>/dev/null; then
      echo "Stopping vision service..."
      $(compose_cmd) --profile vision stop cortex-vision 2>/dev/null || true
      $(compose_cmd) --profile vision rm -f cortex-vision 2>/dev/null || true
    fi
    ;;
  down)
    # Stop all services including vision if it exists
    # First stop main services
    $(compose_cmd) down --remove-orphans $(compose_profiles) 2>/dev/null || true
    # Also stop vision if it's running (even if not in profile)
    if docker ps --format '{{.Names}}' | grep -q "^.*cortex-vision$" 2>/dev/null; then
      echo "Stopping vision service..."
      $(compose_cmd) --profile vision stop cortex-vision 2>/dev/null || true
      $(compose_cmd) --profile vision rm -f cortex-vision 2>/dev/null || true
    fi
    ;;
  restart)
    # Stop services first (this will free up ports)
    echo "Stopping services..."
    # Use down with --remove-orphans to clean up properly
    $(compose_cmd) down --remove-orphans 2>/dev/null || true
    # Also stop vision if it's running
    if docker ps --format '{{.Names}}' | grep -q "^.*cortex-vision$" 2>/dev/null; then
      $(compose_cmd) --profile vision stop cortex-vision 2>/dev/null || true
      $(compose_cmd) --profile vision rm -f cortex-vision 2>/dev/null || true
    fi
    # Wait a moment for ports to be released and network to be cleaned up
    sleep 2
    # Ensure network exists before starting (compose validation requires it)
    # Network must exist as external network for compose validation
    if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
      echo "Creating network $NETWORK_NAME..."
      docker network create "$NETWORK_NAME" || true
    fi
    # Export NETWORK_NAME again to ensure it's available for compose
    export NETWORK_NAME="${NETWORK_NAME:-vyasa-net}"
    # Start services again
    echo "Starting services..."
    DETACH="${DETACH:--d}"
    if $USE_VISION_ONLY; then
      # Start ONLY vision service
      echo "Starting vision service only..."
      $(compose_cmd) --profile vision up $DETACH cortex-vision
    else
      $(compose_cmd) up $DETACH $(compose_profiles)
    fi
    
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
  logs)
    if $USE_VISION_ONLY; then
      $(compose_cmd) --profile vision logs -f cortex-vision
    else
      $(compose_cmd) logs -f $(compose_profiles) ${SERVICE:+$SERVICE}
    fi
    ;;
  status)
    if $USE_VISION_ONLY; then
      $(compose_cmd) --profile vision ps cortex-vision
    else
      $(compose_cmd) ps $(compose_profiles)
      # Also show vision status if it's running
      if docker ps --format '{{.Names}}' | grep -q "^.*cortex-vision$" 2>/dev/null; then
        echo ""
        echo "Vision service (running separately):"
        $(compose_cmd) --profile vision ps cortex-vision
      fi
    fi
    ;;
  backup)
    # Run full backup (ArangoDB + Qdrant)
    BACKUP_SCRIPT="$SCRIPT_DIR/backup_all.sh"
    if [ ! -f "$BACKUP_SCRIPT" ]; then
      echo "Error: Backup script not found: $BACKUP_SCRIPT" >&2
      exit 1
    fi
    if [ ! -x "$BACKUP_SCRIPT" ]; then
      echo "Error: Backup script is not executable: $BACKUP_SCRIPT" >&2
      exit 1
    fi
    echo "Running full backup (ArangoDB + Qdrant)..."
    cd "$PROJECT_ROOT"
    if ! "$BACKUP_SCRIPT"; then
      echo "Error: Backup failed. Check logs: /var/log/vyasa-backups.log" >&2
      exit 1
    fi
    echo "Backup completed successfully"
    ;;
  verify)
    # Verify backups exist and are valid
    VERIFY_SCRIPT="$SCRIPT_DIR/verify_backups.sh"
    if [ ! -f "$VERIFY_SCRIPT" ]; then
      echo "Error: Verification script not found: $VERIFY_SCRIPT" >&2
      exit 1
    fi
    if [ ! -x "$VERIFY_SCRIPT" ]; then
      echo "Error: Verification script is not executable: $VERIFY_SCRIPT" >&2
      exit 1
    fi
    echo "Verifying backups..."
    cd "$PROJECT_ROOT"
    if ! "$VERIFY_SCRIPT"; then
      echo "Error: Backup verification failed. Check logs: /var/log/vyasa-backups.log" >&2
      exit 1
    fi
    echo "All backups verified successfully"
    ;;
  *)
    usage
    exit 1
    ;;
esac
