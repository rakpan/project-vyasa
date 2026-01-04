#!/usr/bin/env bash
set -euo pipefail

# ArangoDB backup script
# Creates dated backups using arangodump and rotates old backups

# Configuration with defaults
: "${ARANGO_CONTAINER:=graph}"
: "${ARANGO_ENDPOINT:=tcp://127.0.0.1:8529}"
: "${ARANGO_USER:=root}"
: "${ARANGO_DATABASE:=}"
: "${BACKUP_ROOT:=/raid/backups/arangodb}"
: "${RETENTION_DAYS:=14}"
: "${COMPRESS:=true}"
: "${LOG_FILE:=/var/log/vyasa-backups.log}"

# Load ARANGO_PASSWORD from environment or .secrets.env
if [ -z "${ARANGO_PASSWORD:-}" ]; then
    if [ -f "deploy/.secrets.env" ]; then
        # Source .secrets.env and extract ARANGO_ROOT_PASSWORD or ARANGO_PASSWORD
        set +u
        source deploy/.secrets.env 2>/dev/null || true
        set -u
        ARANGO_PASSWORD="${ARANGO_ROOT_PASSWORD:-${ARANGO_PASSWORD:-}}"
    fi
fi

if [ -z "${ARANGO_PASSWORD:-}" ]; then
    echo "ERROR: ARANGO_PASSWORD or ARANGO_ROOT_PASSWORD must be set" >&2
    exit 1
fi

# Logging function
log() {
    local component="arangodb-backup"
    local status="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $component $status $message" | tee -a "$LOG_FILE"
}

# Ensure log file directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Create dated backup directory
BACKUP_DATE=$(date +"%Y-%m-%d")
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DATE"
mkdir -p "$BACKUP_DIR"

log "INFO" "Starting backup to $BACKUP_DIR"

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${ARANGO_CONTAINER}$"; then
    log "ERROR" "Container '$ARANGO_CONTAINER' is not running"
    exit 1
fi

# Prepare arangodump command
DUMP_CMD="arangodump"
DUMP_ARGS=(
    "--server.endpoint" "$ARANGO_ENDPOINT"
    "--server.username" "$ARANGO_USER"
    "--server.password" "$ARANGO_PASSWORD"
    "--include-system-collections" "true"
    "--output-directory" "/tmp/arangodump"
)

# If specific database is requested, add it
if [ -n "$ARANGO_DATABASE" ]; then
    DUMP_ARGS+=("--server.database" "$ARANGO_DATABASE")
fi

# Run arangodump inside container
log "INFO" "Running arangodump in container $ARANGO_CONTAINER"
if ! docker exec "$ARANGO_CONTAINER" "$DUMP_CMD" "${DUMP_ARGS[@]}" >/dev/null 2>&1; then
    log "ERROR" "arangodump failed"
    exit 1
fi

# Copy dump from container to host
log "INFO" "Copying dump from container to $BACKUP_DIR"
if ! docker cp "${ARANGO_CONTAINER}:/tmp/arangodump" "$BACKUP_DIR/." >/dev/null 2>&1; then
    log "ERROR" "Failed to copy dump from container"
    exit 1
fi

# Clean up temporary dump in container
docker exec "$ARANGO_CONTAINER" rm -rf /tmp/arangodump >/dev/null 2>&1 || true

# Compress if requested
if [ "$COMPRESS" = "true" ] || [ "$COMPRESS" = "1" ]; then
    log "INFO" "Compressing backup"
    cd "$BACKUP_DIR"
    if tar -czf "../${BACKUP_DATE}.tar.gz" . >/dev/null 2>&1; then
        rm -rf "$BACKUP_DIR"
        BACKUP_DIR="$BACKUP_ROOT"
        BACKUP_FILE="${BACKUP_DATE}.tar.gz"
        log "INFO" "Backup compressed to $BACKUP_FILE"
    else
        log "ERROR" "Compression failed"
        exit 1
    fi
fi

# Rotate old backups
log "INFO" "Rotating backups older than $RETENTION_DAYS days"
CUTOFF_DATE=$(date -d "$RETENTION_DAYS days ago" +"%Y-%m-%d" 2>/dev/null || date -v-${RETENTION_DAYS}d +"%Y-%m-%d" 2>/dev/null || echo "")

if [ -n "$CUTOFF_DATE" ]; then
    # Remove old directories
    find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]" | while read -r dir; do
        dirname=$(basename "$dir")
        if [ "$dirname" \< "$CUTOFF_DATE" ]; then
            log "INFO" "Removing old backup directory: $dirname"
            rm -rf "$dir"
        fi
    done
    
    # Remove old tarballs
    find "$BACKUP_ROOT" -maxdepth 1 -type f -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].tar.gz" | while read -r file; do
        filename=$(basename "$file" .tar.gz)
        if [ "$filename" \< "$CUTOFF_DATE" ]; then
            log "INFO" "Removing old backup tarball: $filename.tar.gz"
            rm -f "$file"
        fi
    done
fi

log "SUCCESS" "Backup completed successfully"
exit 0

