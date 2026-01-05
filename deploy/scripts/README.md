# Deployment Scripts

This directory contains utility scripts for managing Project Vyasa deployments.

## ArangoDB Management

### `reset-arangodb.sh`

Resets ArangoDB to use the password from `deploy/.env`. This script:
- Stops the ArangoDB container
- Creates a backup of the existing database (if possible)
- Removes the ArangoDB data directory
- Restarts ArangoDB (which will reinitialize with the password from `.env`)
- Verifies authentication
- Restarts the orchestrator

**Usage:**
```bash
# May require sudo for removing the data directory
sudo ./deploy/scripts/reset-arangodb.sh

# Or run without sudo if you have permissions
./deploy/scripts/reset-arangodb.sh
```

**Note:** This will delete all ArangoDB data. A backup will be created if possible.

### `rotate-arangodb-password.sh`

Rotates the ArangoDB root password. This script:
- Generates a new password (or accepts a custom one)
- Updates `deploy/.env` with the new password
- Resets ArangoDB to use the new password
- Restarts services

**Usage:**
```bash
# Interactive mode - will prompt for password choice
sudo ./deploy/scripts/rotate-arangodb-password.sh
```

**Options:**
1. Generate a new random password (recommended)
2. Enter a custom password
3. Cancel

## Password Management

All scripts read the password from `deploy/.env` using the `ARANGO_ROOT_PASSWORD` variable.

**Important:** The password in `.env` is stored in plain text. For production deployments:
- Ensure `deploy/.env` has restricted permissions (chmod 600)
- Consider using a secrets management system
- Never commit `.env` to version control

## Troubleshooting

### "Permission denied" when removing ArangoDB data

The ArangoDB data directory is owned by root. You need sudo access:
```bash
sudo rm -rf /raid/vyasa/arangodb
```

### "Database unavailable" after reset

1. Verify ArangoDB is running: `docker ps | grep graph`
2. Check logs: `docker logs deploy-graph-1`
3. Verify password in `.env` matches what ArangoDB was initialized with
4. Test authentication: `curl -u "root:PASSWORD" http://localhost:8529/_api/version`
5. Restart orchestrator: `docker restart deploy-orchestrator-1`

### Password mismatch

If ArangoDB was initialized with a different password than what's in `.env`:
1. Use `reset-arangodb.sh` to reset the database
2. Or manually remove `/raid/vyasa/arangodb` and restart the graph container

