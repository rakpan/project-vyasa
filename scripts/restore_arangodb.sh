#!/usr/bin/env bash
set -euo pipefail

# ArangoDB restore script
# Restores from arangodump output (directory or tar.gz)

# Default configuration
ARANGO_CONTAINER="${ARANGO_CONTAINER:-graph}"
ARANGO_ENDPOINT="${ARANGO_ENDPOINT:-tcp://127.0.0.1:8529}"
ARANGO_USER="${ARANGO_USER:-root}"
ARANGO_DATABASE="${ARANGO_DATABASE:-}"
OVERWRITE="${OVERWRITE:-true}"

# Parse command line arguments
INPUT_PATH=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            INPUT_PATH="$2"
            shift 2
            ;;
        --container)
            ARANGO_CONTAINER="$2"
            shift 2
            ;;
        --endpoint)
            ARANGO_ENDPOINT="$2"
            shift 2
            ;;
        --user)
            ARANGO_USER="$2"
            shift 2
            ;;
        --password)
            ARANGO_PASSWORD="$2"
            shift 2
            ;;
        --database)
            ARANGO_DATABASE="$2"
            shift 2
            ;;
        --overwrite)
            OVERWRITE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --input <backup_path> [options]"
            echo ""
            echo "Options:"
            echo "  --input <path>        Backup directory or tar.gz file (required)"
            echo "  --container <name>    Container name (default: graph)"
            echo "  --endpoint <url>      ArangoDB endpoint (default: tcp://127.0.0.1:8529)"
            echo "  --user <user>         ArangoDB user (default: root)"
            echo "  --password <pass>     ArangoDB password (required)"
            echo "  --database <db>       Target database (optional, restores all if not set)"
            echo "  --overwrite <true|false>  Overwrite existing data (default: true)"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Use --help for usage information" >&2
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$INPUT_PATH" ]; then
    echo "ERROR: --input is required" >&2
    echo "Use --help for usage information" >&2
    exit 1
fi

if [ -z "${ARANGO_PASSWORD:-}" ]; then
    # Try to load from .secrets.env
    if [ -f "deploy/.secrets.env" ]; then
        set +u
        source deploy/.secrets.env 2>/dev/null || true
        set -u
        ARANGO_PASSWORD="${ARANGO_ROOT_PASSWORD:-${ARANGO_PASSWORD:-}}"
    fi
fi

if [ -z "${ARANGO_PASSWORD:-}" ]; then
    echo "ERROR: --password is required or set ARANGO_PASSWORD/ARANGO_ROOT_PASSWORD" >&2
    exit 1
fi

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${ARANGO_CONTAINER}$"; then
    echo "ERROR: Container '$ARANGO_CONTAINER' is not running" >&2
    exit 1
fi

# Check if input path exists
if [ ! -e "$INPUT_PATH" ]; then
    echo "ERROR: Input path does not exist: $INPUT_PATH" >&2
    exit 1
fi

# Create temporary directory for extraction if needed
TEMP_DIR=""
RESTORE_DIR=""

if [ -f "$INPUT_PATH" ] && [[ "$INPUT_PATH" == *.tar.gz ]]; then
    echo "Extracting backup archive..."
    TEMP_DIR=$(mktemp -d)
    if ! tar -xzf "$INPUT_PATH" -C "$TEMP_DIR" >/dev/null 2>&1; then
        echo "ERROR: Failed to extract backup archive" >&2
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    # Find the dump directory (should be the only subdirectory)
    RESTORE_DIR=$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)
    if [ -z "$RESTORE_DIR" ]; then
        echo "ERROR: No dump directory found in archive" >&2
        rm -rf "$TEMP_DIR"
        exit 1
    fi
elif [ -d "$INPUT_PATH" ]; then
    RESTORE_DIR="$INPUT_PATH"
else
    echo "ERROR: Input must be a directory or .tar.gz file" >&2
    exit 1
fi

# Verify restore directory contains dump files
if [ ! -d "$RESTORE_DIR" ] || [ -z "$(find "$RESTORE_DIR" -name "*.structure.json" -o -name "*.data.json" 2>/dev/null | head -1)" ]; then
    echo "ERROR: Restore directory does not appear to contain a valid arangodump output" >&2
    [ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
    exit 1
fi

echo "Restoring from: $RESTORE_DIR"

# Copy restore directory into container
CONTAINER_RESTORE_PATH="/tmp/arangorestore"
echo "Copying restore data to container..."
docker exec "$ARANGO_CONTAINER" rm -rf "$CONTAINER_RESTORE_PATH" >/dev/null 2>&1 || true
if ! docker cp "$RESTORE_DIR" "${ARANGO_CONTAINER}:${CONTAINER_RESTORE_PATH}" >/dev/null 2>&1; then
    echo "ERROR: Failed to copy restore data to container" >&2
    [ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
    exit 1
fi

# Prepare arangorestore command
RESTORE_CMD="arangorestore"
RESTORE_ARGS=(
    "--server.endpoint" "$ARANGO_ENDPOINT"
    "--server.username" "$ARANGO_USER"
    "--server.password" "$ARANGO_PASSWORD"
    "--input-directory" "$CONTAINER_RESTORE_PATH"
    "--include-system-collections" "true"
)

# Add overwrite flag
if [ "$OVERWRITE" = "true" ] || [ "$OVERWRITE" = "1" ]; then
    RESTORE_ARGS+=("--overwrite" "true")
fi

# If specific database is requested, add it
if [ -n "$ARANGO_DATABASE" ]; then
    RESTORE_ARGS+=("--server.database" "$ARANGO_DATABASE")
fi

# Run arangorestore
echo "Running arangorestore..."
if ! docker exec "$ARANGO_CONTAINER" "$RESTORE_CMD" "${RESTORE_ARGS[@]}" >/dev/null 2>&1; then
    echo "ERROR: arangorestore failed" >&2
    docker exec "$ARANGO_CONTAINER" rm -rf "$CONTAINER_RESTORE_PATH" >/dev/null 2>&1 || true
    [ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
    exit 1
fi

# Clean up
echo "Cleaning up..."
docker exec "$ARANGO_CONTAINER" rm -rf "$CONTAINER_RESTORE_PATH" >/dev/null 2>&1 || true
[ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"

echo "Restore completed successfully"
exit 0

