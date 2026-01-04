#!/usr/bin/env bash
set -euo pipefail

# Master backup script that runs both ArangoDB and Qdrant backups
# Intended for use with cron/systemd timer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Logging function
log() {
    local component="backup-all"
    local status="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local log_file="${LOG_FILE:-/var/log/vyasa-backups.log}"
    echo "[$timestamp] $component $status $message" | tee -a "$log_file"
}

log "INFO" "Starting full backup (ArangoDB + Qdrant)"

# Run ArangoDB backup
log "INFO" "Running ArangoDB backup"
if ! "$SCRIPT_DIR/backup_arangodb.sh"; then
    log "ERROR" "ArangoDB backup failed"
    exit 1
fi

# Run Qdrant backup
log "INFO" "Running Qdrant backup"
if ! "$SCRIPT_DIR/backup_qdrant.sh"; then
    log "ERROR" "Qdrant backup failed"
    exit 1
fi

log "SUCCESS" "All backups completed successfully"
exit 0

