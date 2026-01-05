#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Reset ArangoDB with password from .env file
# This script stops ArangoDB, removes the data directory, and restarts it
# so it reinitializes with the correct password from deploy/.env

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$DEPLOY_DIR/.env"

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

# Check if .env file exists
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}[ERROR] $ENV_FILE not found${NC}" >&2
  exit 1
fi

# Source .env file to get ARANGO_ROOT_PASSWORD
source "$ENV_FILE"

if [[ -z "${ARANGO_ROOT_PASSWORD:-}" ]]; then
  echo -e "${RED}[ERROR] ARANGO_ROOT_PASSWORD not set in $ENV_FILE${NC}" >&2
  exit 1
fi

echo -e "${YELLOW}⚠️  WARNING: This will delete all ArangoDB data!${NC}"
echo -e "${YELLOW}Press Ctrl+C to cancel, or wait 5 seconds to continue...${NC}"
sleep 5

echo -e "${GREEN}Stopping ArangoDB container...${NC}"
cd "$DEPLOY_DIR"
docker compose stop graph || true

echo -e "${GREEN}Removing ArangoDB data directory...${NC}"
if [[ -d "/raid/vyasa/arangodb" ]]; then
  # Create backup with timestamp
  BACKUP_DIR="/raid/vyasa/arangodb.backup.$(date +%Y%m%d_%H%M%S)"
  echo -e "${YELLOW}Creating backup at $BACKUP_DIR${NC}"
  if command -v sudo >/dev/null 2>&1; then
    sudo cp -r /raid/vyasa/arangodb "$BACKUP_DIR" 2>/dev/null || {
      echo -e "${YELLOW}Note: Could not create backup. Proceeding anyway...${NC}"
    }
  else
    cp -r /raid/vyasa/arangodb "$BACKUP_DIR" 2>/dev/null || {
      echo -e "${YELLOW}Note: Could not create backup. Proceeding anyway...${NC}"
    }
  fi
  
  # Remove the directory
  if command -v sudo >/dev/null 2>&1; then
    if sudo rm -rf /raid/vyasa/arangodb 2>/dev/null; then
      echo -e "${GREEN}✅ Removed with sudo${NC}"
    else
      echo -e "${YELLOW}Trying without sudo...${NC}"
      rm -rf /raid/vyasa/arangodb || {
        echo -e "${RED}[ERROR] Failed to remove /raid/vyasa/arangodb.${NC}" >&2
        echo -e "${YELLOW}Please run manually: sudo rm -rf /raid/vyasa/arangodb${NC}" >&2
        exit 1
      }
    fi
  else
    rm -rf /raid/vyasa/arangodb || {
      echo -e "${RED}[ERROR] Failed to remove /raid/vyasa/arangodb.${NC}" >&2
      exit 1
    }
  fi
  echo -e "${GREEN}✅ ArangoDB data directory removed${NC}"
else
  echo -e "${YELLOW}ArangoDB data directory doesn't exist, skipping removal${NC}"
fi

echo -e "${GREEN}Starting ArangoDB container (will initialize with password from .env)...${NC}"
docker compose up -d graph

echo -e "${GREEN}Waiting for ArangoDB to initialize (15 seconds)...${NC}"
sleep 15

# Verify initialization
echo -e "${GREEN}Verifying ArangoDB initialization...${NC}"
if docker logs deploy-graph-1 2>&1 | grep -q "ready for business"; then
  echo -e "${GREEN}✅ ArangoDB is ready${NC}"
else
  echo -e "${YELLOW}⚠️  ArangoDB may still be initializing. Check logs with: docker logs deploy-graph-1${NC}"
fi

# Test authentication
echo -e "${GREEN}Testing authentication with password from .env...${NC}"
if curl -s -u "root:${ARANGO_ROOT_PASSWORD}" "http://localhost:8529/_api/version" > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Authentication successful!${NC}"
  echo -e "${GREEN}You can now log into ArangoDB web UI at http://localhost:8529${NC}"
  echo -e "${GREEN}  Username: root${NC}"
  echo -e "${GREEN}  Password: ${ARANGO_ROOT_PASSWORD}${NC}"
else
  echo -e "${YELLOW}⚠️  Authentication test failed. ArangoDB may still be initializing.${NC}"
  echo -e "${YELLOW}Wait a few more seconds and try: curl -u 'root:${ARANGO_ROOT_PASSWORD}' http://localhost:8529/_api/version${NC}"
fi

echo -e "${GREEN}Restarting orchestrator to pick up new database...${NC}"
docker restart deploy-orchestrator-1 || true

echo -e "${GREEN}✅ ArangoDB reset complete!${NC}"

