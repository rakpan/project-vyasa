#!/usr/bin/env bash
set -euo pipefail

# Qdrant backup script
# Creates snapshots for each collection and copies them to backup directory

# Configuration with defaults
: "${QDRANT_URL:=http://127.0.0.1:6333}"
: "${QDRANT_COLLECTIONS:=vyasa}"
: "${QDRANT_CONTAINER:=vector}"
: "${SNAPSHOT_ROOT:=/raid/backups/qdrant}"
: "${RETENTION_DAYS:=14}"
: "${LOG_FILE:=/var/log/vyasa-backups.log}"

# Logging function
log() {
    local component="qdrant-backup"
    local status="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $component $status $message" | tee -a "$LOG_FILE"
}

# Ensure log file directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Create dated backup directory
BACKUP_DATE=$(date +"%Y-%m-%d")
BACKUP_DIR="$SNAPSHOT_ROOT/$BACKUP_DATE"
mkdir -p "$BACKUP_DIR"

log "INFO" "Starting backup to $BACKUP_DIR"

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
    log "ERROR" "Container '$QDRANT_CONTAINER' is not running"
    exit 1
fi

# Parse collections (space or comma separated)
IFS=', ' read -ra COLLECTIONS <<< "$QDRANT_COLLECTIONS"

# Track failures
FAILED_COLLECTIONS=()

# Create snapshot for each collection
for collection in "${COLLECTIONS[@]}"; do
    if [ -z "$collection" ]; then
        continue
    fi
    
    log "INFO" "Creating snapshot for collection: $collection"
    
    # Create snapshot via API
    SNAPSHOT_RESPONSE=$(curl -s -X POST "${QDRANT_URL}/collections/${collection}/snapshots" 2>&1)
    
    if [ $? -ne 0 ]; then
        log "ERROR" "Failed to create snapshot for $collection: API request failed"
        FAILED_COLLECTIONS+=("$collection")
        continue
    fi
    
    # Parse snapshot name from response (Qdrant returns JSON with "name" field)
    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [ -z "$SNAPSHOT_NAME" ]; then
        # Try alternative parsing (response might be just the name string)
        SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.snapshot' | head -1 || echo "")
    fi
    
    if [ -z "$SNAPSHOT_NAME" ]; then
        log "ERROR" "Failed to parse snapshot name for $collection from response: $SNAPSHOT_RESPONSE"
        FAILED_COLLECTIONS+=("$collection")
        continue
    fi
    
    log "INFO" "Snapshot created: $SNAPSHOT_NAME"
    
    # Determine snapshot path
    # Qdrant stores snapshots in /qdrant/storage/snapshots/{collection}/{snapshot_name}
    SNAPSHOT_CONTAINER_PATH="/qdrant/storage/snapshots/${collection}/${SNAPSHOT_NAME}"
    
    # Try to copy from container
    # First, check if the snapshot file exists in the container
    if docker exec "$QDRANT_CONTAINER" test -f "$SNAPSHOT_CONTAINER_PATH" >/dev/null 2>&1; then
        # Copy from container
        COLLECTION_BACKUP_DIR="$BACKUP_DIR/$collection"
        mkdir -p "$COLLECTION_BACKUP_DIR"
        
        log "INFO" "Copying snapshot from container: $SNAPSHOT_CONTAINER_PATH"
        if docker cp "${QDRANT_CONTAINER}:${SNAPSHOT_CONTAINER_PATH}" "$COLLECTION_BACKUP_DIR/$SNAPSHOT_NAME" >/dev/null 2>&1; then
            log "INFO" "Snapshot copied successfully: $collection/$SNAPSHOT_NAME"
        else
            log "ERROR" "Failed to copy snapshot for $collection"
            FAILED_COLLECTIONS+=("$collection")
        fi
    else
        # Try host-mounted path (if Qdrant storage is mounted)
        HOST_SNAPSHOT_PATH="/raid/vyasa/qdrant/snapshots/${collection}/${SNAPSHOT_NAME}"
        if [ -f "$HOST_SNAPSHOT_PATH" ]; then
            COLLECTION_BACKUP_DIR="$BACKUP_DIR/$collection"
            mkdir -p "$COLLECTION_BACKUP_DIR"
            
            log "INFO" "Copying snapshot from host path: $HOST_SNAPSHOT_PATH"
            if cp "$HOST_SNAPSHOT_PATH" "$COLLECTION_BACKUP_DIR/$SNAPSHOT_NAME" >/dev/null 2>&1; then
                log "INFO" "Snapshot copied successfully: $collection/$SNAPSHOT_NAME"
            else
                log "ERROR" "Failed to copy snapshot for $collection from host path"
                FAILED_COLLECTIONS+=("$collection")
            fi
        else
            log "ERROR" "Snapshot file not found in container or host: $SNAPSHOT_NAME"
            FAILED_COLLECTIONS+=("$collection")
        fi
    fi
done

# Check if any collections failed
if [ ${#FAILED_COLLECTIONS[@]} -gt 0 ]; then
    log "ERROR" "Failed to backup collections: ${FAILED_COLLECTIONS[*]}"
    exit 1
fi

# Rotate old backups
log "INFO" "Rotating backups older than $RETENTION_DAYS days"
CUTOFF_DATE=$(date -d "$RETENTION_DAYS days ago" +"%Y-%m-%d" 2>/dev/null || date -v-${RETENTION_DAYS}d +"%Y-%m-%d" 2>/dev/null || echo "")

if [ -n "$CUTOFF_DATE" ]; then
    find "$SNAPSHOT_ROOT" -maxdepth 1 -type d -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]" | while read -r dir; do
        dirname=$(basename "$dir")
        if [ "$dirname" \< "$CUTOFF_DATE" ]; then
            log "INFO" "Removing old backup directory: $dirname"
            rm -rf "$dir"
        fi
    done
fi

log "SUCCESS" "Backup completed successfully"
exit 0

