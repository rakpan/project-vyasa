#!/usr/bin/env bash
set -euo pipefail

# Backup verification script
# Verifies that latest backups exist and are non-empty

# Configuration with defaults
: "${BACKUP_ROOT_ARANGO:=/raid/backups/arangodb}"
: "${BACKUP_ROOT_QDRANT:=/raid/backups/qdrant}"
: "${LOG_FILE:=/var/log/vyasa-backups.log}"

# Logging function
log() {
    local component="backup-verify"
    local status="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $component $status $message" | tee -a "$LOG_FILE"
}

# Ensure log file directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Track verification failures
FAILURES=0

# Verify ArangoDB backup
verify_arangodb_backup() {
    local backup_root="$1"
    
    if [ ! -d "$backup_root" ]; then
        log "ERROR" "ArangoDB backup root does not exist: $backup_root"
        return 1
    fi
    
    # Find latest dated directory or tar.gz
    LATEST_DIR=$(find "$backup_root" -maxdepth 1 -type d -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]" 2>/dev/null | sort -r | head -1)
    LATEST_TAR=$(find "$backup_root" -maxdepth 1 -type f -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].tar.gz" 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_DIR" ] && [ -z "$LATEST_TAR" ]; then
        log "ERROR" "No ArangoDB backup found in $backup_root"
        return 1
    fi
    
    # Check if we have a directory or tar.gz
    if [ -n "$LATEST_TAR" ]; then
        # Verify tar.gz is non-empty and valid
        if [ ! -s "$LATEST_TAR" ]; then
            log "ERROR" "ArangoDB backup tarball is empty: $LATEST_TAR"
            return 1
        fi
        
        # Verify it's a valid tar.gz
        if ! tar -tzf "$LATEST_TAR" >/dev/null 2>&1; then
            log "ERROR" "ArangoDB backup tarball is corrupted: $LATEST_TAR"
            return 1
        fi
        
        BACKUP_NAME=$(basename "$LATEST_TAR")
        BACKUP_SIZE=$(du -h "$LATEST_TAR" | cut -f1)
        log "INFO" "ArangoDB backup verified: $BACKUP_NAME ($BACKUP_SIZE)"
        return 0
    elif [ -n "$LATEST_DIR" ]; then
        # Verify directory is non-empty
        if [ -z "$(find "$LATEST_DIR" -type f 2>/dev/null | head -1)" ]; then
            log "ERROR" "ArangoDB backup directory is empty: $LATEST_DIR"
            return 1
        fi
        
        BACKUP_NAME=$(basename "$LATEST_DIR")
        BACKUP_SIZE=$(du -sh "$LATEST_DIR" 2>/dev/null | cut -f1 || echo "unknown")
        log "INFO" "ArangoDB backup verified: $BACKUP_NAME ($BACKUP_SIZE)"
        return 0
    fi
    
    return 1
}

# Verify Qdrant backup
verify_qdrant_backup() {
    local backup_root="$1"
    
    if [ ! -d "$backup_root" ]; then
        log "ERROR" "Qdrant backup root does not exist: $backup_root"
        return 1
    fi
    
    # Find latest dated directory
    LATEST_DIR=$(find "$backup_root" -maxdepth 1 -type d -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]" 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_DIR" ]; then
        log "ERROR" "No Qdrant backup found in $backup_root"
        return 1
    fi
    
    # Verify directory contains snapshot files
    SNAPSHOT_COUNT=$(find "$LATEST_DIR" -type f -name "*.snapshot" 2>/dev/null | wc -l)
    
    if [ "$SNAPSHOT_COUNT" -eq 0 ]; then
        log "ERROR" "Qdrant backup directory contains no snapshot files: $LATEST_DIR"
        return 1
    fi
    
    BACKUP_NAME=$(basename "$LATEST_DIR")
    BACKUP_SIZE=$(du -sh "$LATEST_DIR" 2>/dev/null | cut -f1 || echo "unknown")
    log "INFO" "Qdrant backup verified: $BACKUP_NAME ($BACKUP_SIZE, $SNAPSHOT_COUNT snapshot(s))"
    return 0
}

# Main verification
log "INFO" "Starting backup verification"

# Verify ArangoDB backup
if ! verify_arangodb_backup "$BACKUP_ROOT_ARANGO"; then
    FAILURES=$((FAILURES + 1))
fi

# Verify Qdrant backup
if ! verify_qdrant_backup "$BACKUP_ROOT_QDRANT"; then
    FAILURES=$((FAILURES + 1))
fi

# Report results
if [ $FAILURES -eq 0 ]; then
    log "SUCCESS" "All backups verified successfully"
    exit 0
else
    log "ERROR" "Backup verification failed ($FAILURES failure(s))"
    exit 1
fi

