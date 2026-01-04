#!/usr/bin/env bash
set -euo pipefail

# Qdrant restore script
# Restores a collection from a snapshot file

# Default configuration
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-vector}"

# Parse command line arguments
SNAPSHOT_PATH=""
COLLECTION=""
TARGET_COLLECTION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --snapshot)
            SNAPSHOT_PATH="$2"
            shift 2
            ;;
        --collection)
            COLLECTION="$2"
            shift 2
            ;;
        --target_collection)
            TARGET_COLLECTION="$2"
            shift 2
            ;;
        --qdrant_url)
            QDRANT_URL="$2"
            shift 2
            ;;
        --container)
            QDRANT_CONTAINER="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --snapshot <snapshot_path> --collection <collection_name> [options]"
            echo ""
            echo "Options:"
            echo "  --snapshot <path>          Snapshot file path (required)"
            echo "  --collection <name>        Source collection name (required)"
            echo "  --target_collection <name>  Target collection name (optional, defaults to source)"
            echo "  --qdrant_url <url>         Qdrant API URL (default: http://127.0.0.1:6333)"
            echo "  --container <name>         Container name (default: vector)"
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
if [ -z "$SNAPSHOT_PATH" ]; then
    echo "ERROR: --snapshot is required" >&2
    echo "Use --help for usage information" >&2
    exit 1
fi

if [ -z "$COLLECTION" ]; then
    echo "ERROR: --collection is required" >&2
    echo "Use --help for usage information" >&2
    exit 1
fi

# Use target collection name if provided, otherwise use source collection
if [ -z "$TARGET_COLLECTION" ]; then
    TARGET_COLLECTION="$COLLECTION"
fi

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
    echo "ERROR: Container '$QDRANT_CONTAINER' is not running" >&2
    exit 1
fi

# Check if snapshot file exists
if [ ! -f "$SNAPSHOT_PATH" ]; then
    echo "ERROR: Snapshot file does not exist: $SNAPSHOT_PATH" >&2
    exit 1
fi

# Extract snapshot filename
SNAPSHOT_NAME=$(basename "$SNAPSHOT_PATH")

# Determine snapshot destination in container
# Qdrant stores snapshots in /qdrant/storage/snapshots/{collection}/
CONTAINER_SNAPSHOT_DIR="/qdrant/storage/snapshots/${TARGET_COLLECTION}"
CONTAINER_SNAPSHOT_PATH="${CONTAINER_SNAPSHOT_DIR}/${SNAPSHOT_NAME}"

echo "Restoring snapshot: $SNAPSHOT_NAME"
echo "Source collection: $COLLECTION"
echo "Target collection: $TARGET_COLLECTION"

# Create snapshot directory in container if it doesn't exist
echo "Preparing snapshot directory in container..."
docker exec "$QDRANT_CONTAINER" mkdir -p "$CONTAINER_SNAPSHOT_DIR" >/dev/null 2>&1 || true

# Copy snapshot into container
echo "Copying snapshot to container..."
if ! docker cp "$SNAPSHOT_PATH" "${QDRANT_CONTAINER}:${CONTAINER_SNAPSHOT_PATH}" >/dev/null 2>&1; then
    echo "ERROR: Failed to copy snapshot to container" >&2
    exit 1
fi

# Verify snapshot file exists in container
if ! docker exec "$QDRANT_CONTAINER" test -f "$CONTAINER_SNAPSHOT_PATH" >/dev/null 2>&1; then
    echo "ERROR: Snapshot file not found in container after copy" >&2
    exit 1
fi

# If target collection is different from source, we need to create it first
# For now, we'll assume the collection already exists or will be created by the restore
# Qdrant's recover endpoint will handle collection creation if needed

# Call Qdrant recover endpoint
echo "Recovering collection from snapshot..."
RECOVER_URL="${QDRANT_URL}/collections/${TARGET_COLLECTION}/snapshots/${SNAPSHOT_NAME}/recover"

RECOVER_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "$RECOVER_URL" 2>&1)
HTTP_CODE=$(echo "$RECOVER_RESPONSE" | tail -1)
BODY=$(echo "$RECOVER_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "202" ]; then
    echo "ERROR: Qdrant recover failed (HTTP $HTTP_CODE)" >&2
    echo "Response: $BODY" >&2
    exit 1
fi

echo "Recovery initiated successfully"
echo "Waiting for recovery to complete..."

# Poll for recovery status (Qdrant recovery is async)
MAX_WAIT=60
WAIT_INTERVAL=2
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check collection status
    STATUS_URL="${QDRANT_URL}/collections/${TARGET_COLLECTION}"
    STATUS_RESPONSE=$(curl -s "$STATUS_URL" 2>&1)
    
    if echo "$STATUS_RESPONSE" | grep -q '"status":"green"' || echo "$STATUS_RESPONSE" | grep -q '"status":"yellow"'; then
        echo "Recovery completed successfully"
        exit 0
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    echo -n "."
done

echo ""
echo "WARNING: Recovery may still be in progress (timeout after ${MAX_WAIT}s)"
echo "Check collection status manually: curl ${QDRANT_URL}/collections/${TARGET_COLLECTION}"

exit 0

