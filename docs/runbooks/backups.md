# Daily Backup Runbook

## Overview

Project Vyasa includes automated backup scripts for ArangoDB and Qdrant that run daily and maintain a rolling retention window.

**Quick Start:**
```bash
# Run backup manually
./scripts/run_stack.sh backup

# Verify backups
./scripts/run_stack.sh verify
```

## Backup Scripts

### `scripts/backup_arangodb.sh`
Creates ArangoDB backups using `arangodump`:
- Backs up all databases (or specific database if `ARANGO_DATABASE` is set)
- Includes system collections
- Compresses backups by default (tar.gz)
- Rotates backups older than retention period

### `scripts/backup_qdrant.sh`
Creates Qdrant snapshots for each collection:
- Creates snapshots via Qdrant API
- Copies snapshots from container to host
- Supports multiple collections (space or comma separated)
- Rotates old snapshots

### `scripts/backup_all.sh`
Master script that runs both backups sequentially:
- Intended for cron/systemd timer
- Fails if either backup fails
- Logs all operations

## Configuration

### Environment Variables

All scripts support configuration via environment variables with sensible defaults:

**ArangoDB Backup:**
- `ARANGO_CONTAINER` (default: `graph`)
- `ARANGO_ENDPOINT` (default: `tcp://127.0.0.1:8529`)
- `ARANGO_USER` (default: `root`)
- `ARANGO_PASSWORD` (required; read from env or `deploy/.secrets.env`)
- `ARANGO_DATABASE` (optional; if set, dump only that DB)
- `BACKUP_ROOT` (default: `/raid/backups/arangodb`)
- `RETENTION_DAYS` (default: `14`)
- `COMPRESS` (default: `true`)
- `LOG_FILE` (default: `/var/log/vyasa-backups.log`)

**Qdrant Backup:**
- `QDRANT_URL` (default: `http://127.0.0.1:6333`)
- `QDRANT_COLLECTIONS` (default: `vyasa`)
- `QDRANT_CONTAINER` (default: `vector`)
- `SNAPSHOT_ROOT` (default: `/raid/backups/qdrant`)
- `RETENTION_DAYS` (default: `14`)
- `LOG_FILE` (default: `/var/log/vyasa-backups.log`)

### Setting Up Backups

1. **Ensure backup directories exist:**
   ```bash
   sudo mkdir -p /raid/backups/arangodb /raid/backups/qdrant
   sudo chown -R $(id -u):$(id -g) /raid/backups
   ```

2. **Ensure log directory exists:**
   ```bash
   sudo mkdir -p /var/log
   sudo touch /var/log/vyasa-backups.log
   sudo chmod 666 /var/log/vyasa-backups.log
   ```

3. **Set ARANGO_PASSWORD in environment or .secrets.env:**
   ```bash
   # Option 1: Export in shell
   export ARANGO_PASSWORD="your-password"
   
   # Option 2: Add to deploy/.secrets.env
   echo "ARANGO_ROOT_PASSWORD=your-password" >> deploy/.secrets.env
   ```

## Scheduling Backups

### Daily Local Backups

#### Option 1: Cron (User-Level)

For user-level cron (no sudo required), add to your crontab (`crontab -e`):

```bash
# Daily backup at 2 AM (low traffic window)
# Set environment variables in crontab or use .secrets.env
0 2 * * * cd /path/to/project-vyasa && ./scripts/backup_all.sh >> /var/log/vyasa-backups.log 2>&1
```

**Note:** Ensure the log file is writable by your user:
```bash
sudo touch /var/log/vyasa-backups.log
sudo chmod 666 /var/log/vyasa-backups.log
```

Or use a user-writable log location:
```bash
# Daily backup at 2 AM with user log
0 2 * * * cd /path/to/project-vyasa && ./scripts/backup_all.sh >> ~/vyasa-backups.log 2>&1
```

#### Option 2: Cron (Root-Level)

For system-wide cron (requires root), add to root's crontab (`sudo crontab -e`):

```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/project-vyasa && /path/to/project-vyasa/scripts/backup_all.sh >> /var/log/vyasa-backups.log 2>&1
```

#### Option 3: Systemd Timer (User-Level)

Create `~/.config/systemd/user/vyasa-backup.service`:
```ini
[Unit]
Description=Project Vyasa Daily Backup
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/project-vyasa
ExecStart=/path/to/project-vyasa/scripts/backup_all.sh
Environment="ARANGO_PASSWORD=your-password"
StandardOutput=append:/var/log/vyasa-backups.log
StandardError=append:/var/log/vyasa-backups.log
```

Create `~/.config/systemd/user/vyasa-backup.timer`:
```ini
[Unit]
Description=Run Vyasa backups daily
Requires=vyasa-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start (user-level):
```bash
systemctl --user enable vyasa-backup.timer
systemctl --user start vyasa-backup.timer
systemctl --user status vyasa-backup.timer
```

#### Option 4: Systemd Timer (System-Level)

Create `/etc/systemd/system/vyasa-backup.service`:
```ini
[Unit]
Description=Project Vyasa Daily Backup
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/project-vyasa
ExecStart=/path/to/project-vyasa/scripts/backup_all.sh
User=your-username
Environment="ARANGO_PASSWORD=your-password"
StandardOutput=append:/var/log/vyasa-backups.log
StandardError=append:/var/log/vyasa-backups.log
```

Create `/etc/systemd/system/vyasa-backup.timer`:
```ini
[Unit]
Description=Run Vyasa backups daily
Requires=vyasa-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start (system-level):
```bash
sudo systemctl enable vyasa-backup.timer
sudo systemctl start vyasa-backup.timer
sudo systemctl status vyasa-backup.timer
```

### Weekly Off-Host Sync

Sync backups to a remote Mac (or other host) weekly using `scripts/sync_backups_to_mac.sh`.

#### Prerequisites

1. **SSH Key Setup (No Password Prompts)**

   Generate SSH key if you don't have one:
   ```bash
   ssh-keygen -t ed25519 -C "vyasa-backup@dgx"
   ```

   Copy public key to Mac:
   ```bash
   ssh-copy-id user@mac-hostname.local
   # Or manually:
   cat ~/.ssh/id_ed25519.pub | ssh user@mac-hostname.local "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ```

   Test passwordless SSH:
   ```bash
   ssh user@mac-hostname.local "echo 'SSH connection successful'"
   ```

2. **Configure Environment Variables**

   Create a config file or export variables:
   ```bash
   export REMOTE_HOST="mac-hostname.local"
   export REMOTE_USER="your-username"
   export REMOTE_BASE_DIR="/Users/your-username/vyasa-backups"
   ```

#### Scheduling Weekly Sync

Add to crontab (`crontab -e`):
```bash
# Weekly sync to Mac every Sunday at 3 AM
0 3 * * 0 cd /path/to/project-vyasa && ./scripts/sync_backups_to_mac.sh >> /var/log/vyasa-backups.log 2>&1
```

Or with systemd timer, create `~/.config/systemd/user/vyasa-sync.service`:
```ini
[Unit]
Description=Project Vyasa Weekly Backup Sync
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/project-vyasa
ExecStart=/path/to/project-vyasa/scripts/sync_backups_to_mac.sh
Environment="REMOTE_HOST=mac-hostname.local"
Environment="REMOTE_USER=your-username"
Environment="REMOTE_BASE_DIR=/Users/your-username/vyasa-backups"
StandardOutput=append:/var/log/vyasa-backups.log
StandardError=append:/var/log/vyasa-backups.log
```

Create `~/.config/systemd/user/vyasa-sync.timer`:
```ini
[Unit]
Description=Sync Vyasa backups weekly
Requires=vyasa-sync.service

[Timer]
OnCalendar=weekly
OnCalendar=Sun 03:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
systemctl --user enable vyasa-sync.timer
systemctl --user start vyasa-sync.timer
```

## Backup Locations

- **ArangoDB:** `/raid/backups/arangodb/YYYY-MM-DD/` or `/raid/backups/arangodb/YYYY-MM-DD.tar.gz`
- **Qdrant:** `/raid/backups/qdrant/YYYY-MM-DD/{collection}/`

## Restoring from Backups

> **⚠️ Important:** Always test restores in a staging container first before restoring to production. See "Test Restore Pattern" below.

### Restore Scripts

#### `scripts/restore_arangodb.sh`

Restores ArangoDB from arangodump output (directory or tar.gz):

```bash
# Restore from compressed backup
./scripts/restore_arangodb.sh \
  --input /raid/backups/arangodb/2024-01-15.tar.gz \
  --password "$ARANGO_PASSWORD"

# Restore from directory
./scripts/restore_arangodb.sh \
  --input /raid/backups/arangodb/2024-01-15 \
  --password "$ARANGO_PASSWORD"

# Restore specific database only
./scripts/restore_arangodb.sh \
  --input /raid/backups/arangodb/2024-01-15.tar.gz \
  --password "$ARANGO_PASSWORD" \
  --database project_vyasa

# Restore to different container (staging)
./scripts/restore_arangodb.sh \
  --input /raid/backups/arangodb/2024-01-15.tar.gz \
  --container graph-staging \
  --password "$ARANGO_PASSWORD"
```

**Options:**
- `--input <path>` - Backup directory or tar.gz file (required)
- `--container <name>` - Container name (default: `graph`)
- `--endpoint <url>` - ArangoDB endpoint (default: `tcp://127.0.0.1:8529`)
- `--user <user>` - ArangoDB user (default: `root`)
- `--password <pass>` - ArangoDB password (required)
- `--database <db>` - Target database (optional, restores all if not set)
- `--overwrite <true|false>` - Overwrite existing data (default: `true`)

#### `scripts/restore_qdrant.sh`

Restores Qdrant collection from snapshot:

```bash
# Restore collection from snapshot
./scripts/restore_qdrant.sh \
  --snapshot /raid/backups/qdrant/2024-01-15/vyasa/abc123.snapshot \
  --collection vyasa

# Restore to a different collection name
./scripts/restore_qdrant.sh \
  --snapshot /raid/backups/qdrant/2024-01-15/vyasa/abc123.snapshot \
  --collection vyasa \
  --target_collection vyasa-restored

# Restore to different Qdrant instance
./scripts/restore_qdrant.sh \
  --snapshot /raid/backups/qdrant/2024-01-15/vyasa/abc123.snapshot \
  --collection vyasa \
  --qdrant_url http://127.0.0.1:6334 \
  --container vector-staging
```

**Options:**
- `--snapshot <path>` - Snapshot file path (required)
- `--collection <name>` - Source collection name (required)
- `--target_collection <name>` - Target collection name (optional, defaults to source)
- `--qdrant_url <url>` - Qdrant API URL (default: `http://127.0.0.1:6333`)
- `--container <name>` - Container name (default: `vector`)

### Test Restore Pattern

Before restoring to production, test in a staging environment:

1. **Create staging containers:**
   ```bash
   # Start ArangoDB staging container
   docker run -d --name graph-staging \
     -p 8528:8529 \
     -e ARANGO_ROOT_PASSWORD=test-password \
     -v /tmp/arangodb-staging:/var/lib/arangodb3 \
     arangodb:latest
   
   # Start Qdrant staging container
   docker run -d --name vector-staging \
     -p 6334:6333 \
     -v /tmp/qdrant-staging:/qdrant/storage \
     qdrant/qdrant:latest
   ```

2. **Test restore:**
   ```bash
   # Test ArangoDB restore
   ./scripts/restore_arangodb.sh \
     --input /raid/backups/arangodb/2024-01-15.tar.gz \
     --container graph-staging \
     --endpoint tcp://127.0.0.1:8528 \
     --password test-password
   
   # Test Qdrant restore
   ./scripts/restore_qdrant.sh \
     --snapshot /raid/backups/qdrant/2024-01-15/vyasa/abc123.snapshot \
     --collection vyasa \
     --target_collection vyasa-test \
     --qdrant_url http://127.0.0.1:6334 \
     --container vector-staging
   ```

3. **Validate restore** (see Validation Checklist below)

4. **If validation passes, proceed with production restore**

## Validation Checklist

After restoring, validate that the restore was successful before using the restored data in production.

### ArangoDB Validation

#### 1. Collections Present
```bash
# List all collections
docker exec graph arangosh --server.endpoint tcp://127.0.0.1:8529 \
  --server.username root --server.password "$ARANGO_PASSWORD" \
  --javascript.execute "db._collections().forEach(c => print(c.name()))"

# Expected collections (at minimum):
# - _graphs
# - _jobs
# - _queues
# - extractions
# - manuscript_blocks
# - projects
# - roles
```

#### 2. Document Counts in Expected Range
```bash
# Check document counts
docker exec graph arangosh --server.endpoint tcp://127.0.0.1:8529 \
  --server.username root --server.password "$ARANGO_PASSWORD" \
  --javascript.execute "
    db._useDatabase('project_vyasa');
    print('extractions:', db.extractions.count());
    print('projects:', db.projects.count());
    print('manuscript_blocks:', db.manuscript_blocks.count());
  "

# Verify counts match expected values from before restore
# (Document baseline counts in your runbook or monitoring system)
```

#### 3. Vyasa Stack Can Start and Query Key Endpoints
```bash
# Start Vyasa stack
./scripts/run_stack.sh start

# Wait for services to be healthy
sleep 30

# Test key endpoints
curl http://localhost:8000/api/projects
curl http://localhost:8000/api/jobs

# Check orchestrator logs for errors
docker logs orchestrator | grep -i error

# Verify no authentication errors or missing data errors
```

#### 4. Sample Query Validation
```bash
# Query a known project
docker exec graph arangosh --server.endpoint tcp://127.0.0.1:8529 \
  --server.username root --server.password "$ARANGO_PASSWORD" \
  --javascript.execute "
    db._useDatabase('project_vyasa');
    var project = db.projects.firstExample();
    if (project) {
      print('Project found:', project.title);
      var extractions = db.extractions.toArray({project_id: project.id});
      print('Extractions:', extractions.length);
    }
  "
```

### Qdrant Validation

#### 1. Collection Exists
```bash
# List collections
curl http://127.0.0.1:6333/collections

# Check specific collection
curl http://127.0.0.1:6333/collections/vyasa

# Expected response includes:
# - "status": "green" or "yellow"
# - "points_count": > 0
# - "vectors_count": > 0
```

#### 2. Vector Count Matches Expected Range
```bash
# Get collection info
COLLECTION_INFO=$(curl -s http://127.0.0.1:6333/collections/vyasa)

# Extract counts
POINTS_COUNT=$(echo "$COLLECTION_INFO" | grep -o '"points_count":[0-9]*' | cut -d: -f2)
VECTORS_COUNT=$(echo "$COLLECTION_INFO" | grep -o '"vectors_count":[0-9]*' | cut -d: -f2)

echo "Points: $POINTS_COUNT"
echo "Vectors: $VECTORS_COUNT"

# Verify counts match expected values
# (Document baseline counts in your runbook or monitoring system)
```

#### 3. Sample Similarity Query Returns Results
```bash
# Create a test query vector (384 dimensions for bge-large-en-v1.5)
# This is a dummy vector - in production, use actual query vectors
TEST_VECTOR=$(python3 -c "import json; print(json.dumps([0.1]*384))")

# Perform similarity search
curl -X POST http://127.0.0.1:6333/collections/vyasa/points/search \
  -H "Content-Type: application/json" \
  -d "{
    \"vector\": $TEST_VECTOR,
    \"limit\": 5,
    \"with_payload\": true
  }"

# Expected: Returns JSON with "result" array containing matches
# Verify:
# - Status code 200
# - "result" array is not empty
# - Results include payload data
```

#### 4. Integration Test with Vyasa Stack
```bash
# Start Vyasa stack
./scripts/run_stack.sh start

# Wait for services
sleep 30

# Test knowledge retrieval endpoint (if available)
curl http://localhost:8000/api/knowledge/search?query=test

# Verify no Qdrant connection errors in logs
docker logs orchestrator | grep -i qdrant
docker logs orchestrator | grep -i "vector\|embedding"
```

### Validation Sign-off

Before marking restore as complete, verify:

- [ ] All expected collections exist (ArangoDB)
- [ ] Document counts match baseline (within 5% tolerance)
- [ ] Vyasa stack starts without errors
- [ ] Key API endpoints respond successfully
- [ ] Sample queries return expected results
- [ ] No authentication or connection errors in logs
- [ ] Qdrant collection status is "green" or "yellow"
- [ ] Vector counts match baseline
- [ ] Similarity search returns results

**If any validation step fails, do not use the restored data in production. Investigate and re-restore if necessary.**

## Backup Verification

### `scripts/verify_backups.sh`

Validates that backups exist and are non-empty. Run this script regularly to catch backup failures early.

**What It Checks:**
- Latest ArangoDB backup exists (directory or tar.gz)
- ArangoDB backup is non-empty and valid
- Latest Qdrant backup exists (dated directory)
- Qdrant backup contains snapshot files

**Usage:**
```bash
# Verify backups with default paths
./scripts/verify_backups.sh

# Verify with custom paths
BACKUP_ROOT_ARANGO=/custom/path/arangodb \
BACKUP_ROOT_QDRANT=/custom/path/qdrant \
./scripts/verify_backups.sh
```

**Exit Codes:**
- `0` - All backups verified successfully
- `1` - One or more backups missing or invalid

**Output:**
The script logs verification results to `/var/log/vyasa-backups.log` and prints a summary:
```
[2024-01-15T02:05:00Z] backup-verify INFO ArangoDB backup verified: 2024-01-15.tar.gz (2.3G)
[2024-01-15T02:05:00Z] backup-verify INFO Qdrant backup verified: 2024-01-15 (1.1G, 3 snapshot(s))
[2024-01-15T02:05:00Z] backup-verify SUCCESS All backups verified successfully
```

### Scheduling Verification

**Daily Verification (Recommended):**

Add to crontab (`crontab -e`):
```bash
# Verify backups daily at 3 AM (after backup at 2 AM)
0 3 * * * cd /path/to/project-vyasa && ./scripts/verify_backups.sh >> /var/log/vyasa-backups.log 2>&1
```

**Weekly Verification:**

Add to crontab:
```bash
# Verify backups weekly on Sunday at 3 AM
0 3 * * 0 cd /path/to/project-vyasa && ./scripts/verify_backups.sh >> /var/log/vyasa-backups.log 2>&1
```

### Spotting Failures in Logs

**Check verification results:**
```bash
# View recent verification logs
grep "backup-verify" /var/log/vyasa-backups.log | tail -20

# Check for failures
grep "backup-verify.*ERROR" /var/log/vyasa-backups.log

# View last verification result
grep "backup-verify" /var/log/vyasa-backups.log | tail -5
```

**Common Failure Patterns:**

1. **Missing Backup:**
   ```
   [timestamp] backup-verify ERROR No ArangoDB backup found in /raid/backups/arangodb
   ```
   - **Cause:** Backup script failed or didn't run
   - **Action:** Check backup script logs, verify containers are running

2. **Empty Backup:**
   ```
   [timestamp] backup-verify ERROR ArangoDB backup directory is empty: 2024-01-15
   ```
   - **Cause:** Backup process started but didn't complete
   - **Action:** Check backup script logs for errors, verify container has sufficient space

3. **Corrupted Tarball:**
   ```
   [timestamp] backup-verify ERROR ArangoDB backup tarball is corrupted: 2024-01-15.tar.gz
   ```
   - **Cause:** Disk I/O error or incomplete compression
   - **Action:** Check disk health, re-run backup

4. **No Snapshots:**
   ```
   [timestamp] backup-verify ERROR Qdrant backup directory contains no snapshot files
   ```
   - **Cause:** Snapshot creation failed or collection doesn't exist
   - **Action:** Check Qdrant API logs, verify collection names

## Monitoring

Check backup logs:
```bash
tail -f /var/log/vyasa-backups.log
```

Verify backups exist:
```bash
ls -lh /raid/backups/arangodb/
ls -lh /raid/backups/qdrant/
```

Run verification manually:
```bash
./scripts/verify_backups.sh
```

## Troubleshooting

### Backup fails with "Container not running"
- Ensure Docker containers are running: `docker ps`
- Check container names match configuration (default: `graph`, `vector`)

### Backup fails with "Permission denied"
- Ensure backup directories are writable
- Check log file permissions

### ArangoDB backup fails with authentication error
- Verify `ARANGO_PASSWORD` is set correctly
- Check password in `deploy/.secrets.env` or environment

### Qdrant snapshot creation fails
- Verify Qdrant API is accessible: `curl http://127.0.0.1:6333/collections`
- Check collection names match `QDRANT_COLLECTIONS` setting

## Retention Policy

By default, backups older than 14 days are automatically deleted. Adjust `RETENTION_DAYS` to change this:
```bash
export RETENTION_DAYS=30
./scripts/backup_all.sh
```

