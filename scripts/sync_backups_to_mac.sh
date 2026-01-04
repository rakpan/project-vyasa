#!/usr/bin/env bash
set -euo pipefail

# Weekly backup sync script
# Syncs ArangoDB and Qdrant backups to a remote Mac (or other host) via rsync

# Configuration with defaults
: "${REMOTE_HOST:=}"
: "${REMOTE_USER:=}"
: "${REMOTE_BASE_DIR:=}"
: "${LOCAL_ARANGO_BACKUPS:=/raid/backups/arangodb}"
: "${LOCAL_QDRANT_BACKUPS:=/raid/backups/qdrant}"
: "${RSYNC_OPTS:=-avz --delete}"
: "${LOG_FILE:=/var/log/vyasa-backups.log}"

# Logging function
log() {
    local component="backup-sync"
    local status="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $component $status $message" | tee -a "$LOG_FILE"
}

# Ensure log file directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Validate required environment variables
if [ -z "$REMOTE_HOST" ]; then
    log "ERROR" "REMOTE_HOST is required"
    echo "ERROR: REMOTE_HOST must be set" >&2
    echo "Example: export REMOTE_HOST='mac-hostname.local'" >&2
    exit 1
fi

if [ -z "$REMOTE_USER" ]; then
    log "ERROR" "REMOTE_USER is required"
    echo "ERROR: REMOTE_USER must be set" >&2
    echo "Example: export REMOTE_USER='your-username'" >&2
    exit 1
fi

# Set default remote base directory if not provided
if [ -z "$REMOTE_BASE_DIR" ]; then
    REMOTE_BASE_DIR="/Users/${REMOTE_USER}/vyasa-backups"
fi

log "INFO" "Starting backup sync to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE_DIR}"

# Verify local backup directories exist
if [ ! -d "$LOCAL_ARANGO_BACKUPS" ]; then
    log "ERROR" "Local ArangoDB backup directory does not exist: $LOCAL_ARANGO_BACKUPS"
    exit 1
fi

if [ ! -d "$LOCAL_QDRANT_BACKUPS" ]; then
    log "ERROR" "Local Qdrant backup directory does not exist: $LOCAL_QDRANT_BACKUPS"
    exit 1
fi

# Test SSH connection
log "INFO" "Testing SSH connection to ${REMOTE_USER}@${REMOTE_HOST}"
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "${REMOTE_USER}@${REMOTE_HOST}" "echo 'SSH connection successful'" >/dev/null 2>&1; then
    log "ERROR" "SSH connection failed. Ensure passwordless SSH is configured."
    echo "ERROR: Cannot connect to ${REMOTE_USER}@${REMOTE_HOST}" >&2
    echo "Run: ssh-copy-id ${REMOTE_USER}@${REMOTE_HOST}" >&2
    exit 1
fi

# Create remote directories if they don't exist
log "INFO" "Ensuring remote directories exist"
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_BASE_DIR}/arangodb ${REMOTE_BASE_DIR}/qdrant" || {
    log "ERROR" "Failed to create remote directories"
    exit 1
}

# Sync ArangoDB backups
log "INFO" "Syncing ArangoDB backups..."
REMOTE_ARANGO="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE_DIR}/arangodb/"
if rsync $RSYNC_OPTS "$LOCAL_ARANGO_BACKUPS/" "$REMOTE_ARANGO" >/dev/null 2>&1; then
    log "SUCCESS" "ArangoDB backups synced successfully"
else
    log "ERROR" "Failed to sync ArangoDB backups"
    exit 1
fi

# Sync Qdrant backups
log "INFO" "Syncing Qdrant backups..."
REMOTE_QDRANT="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE_DIR}/qdrant/"
if rsync $RSYNC_OPTS "$LOCAL_QDRANT_BACKUPS/" "$REMOTE_QDRANT" >/dev/null 2>&1; then
    log "SUCCESS" "Qdrant backups synced successfully"
else
    log "ERROR" "Failed to sync Qdrant backups"
    exit 1
fi

log "SUCCESS" "All backups synced successfully to ${REMOTE_HOST}"
exit 0

