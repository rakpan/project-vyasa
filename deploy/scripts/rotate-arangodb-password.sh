#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Rotate ArangoDB root password
# This script updates the password in .env and resets ArangoDB to use the new password
# Note: This will delete all ArangoDB data unless you export/import it first

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$DEPLOY_DIR/.env"

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
NC="\033[0m"

# Check if .env file exists
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}[ERROR] $ENV_FILE not found${NC}" >&2
  exit 1
fi

# Generate a secure random password (24 characters, alphanumeric)
generate_password() {
  openssl rand -base64 18 | tr -d "=+/" | cut -c1-24
}

echo -e "${BLUE}ArangoDB Password Rotation Script${NC}"
echo -e "${BLUE}===================================${NC}"
echo ""

# Read current password
if [[ -f "$ENV_FILE" ]]; then
  CURRENT_PASSWORD=$(grep "^ARANGO_ROOT_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2 || echo "")
  if [[ -n "$CURRENT_PASSWORD" ]]; then
    echo -e "${YELLOW}Current password in .env: ${CURRENT_PASSWORD:0:8}...${NC}"
  fi
fi

echo ""
echo -e "${YELLOW}Options:${NC}"
echo "1. Generate a new random password"
echo "2. Enter a custom password"
echo "3. Cancel"
echo ""
read -p "Choose an option (1-3): " choice

case $choice in
  1)
    NEW_PASSWORD=$(generate_password)
    echo -e "${GREEN}Generated new password: ${NEW_PASSWORD}${NC}"
    ;;
  2)
    read -sp "Enter new password: " NEW_PASSWORD
    echo ""
    if [[ -z "$NEW_PASSWORD" ]]; then
      echo -e "${RED}[ERROR] Password cannot be empty${NC}" >&2
      exit 1
    fi
    ;;
  3)
    echo "Cancelled."
    exit 0
    ;;
  *)
    echo -e "${RED}[ERROR] Invalid option${NC}" >&2
    exit 1
    ;;
esac

echo ""
echo -e "${YELLOW}⚠️  WARNING: This will reset ArangoDB and delete all data!${NC}"
echo -e "${YELLOW}Press Ctrl+C to cancel, or wait 5 seconds to continue...${NC}"
sleep 5

# Update .env file
echo -e "${GREEN}Updating $ENV_FILE...${NC}"
if grep -q "^ARANGO_ROOT_PASSWORD=" "$ENV_FILE"; then
  # Update existing password
  if [[ "$(uname)" == "Darwin" ]]; then
    # macOS
    sed -i '' "s|^ARANGO_ROOT_PASSWORD=.*|ARANGO_ROOT_PASSWORD=${NEW_PASSWORD}|" "$ENV_FILE"
  else
    # Linux
    sed -i "s|^ARANGO_ROOT_PASSWORD=.*|ARANGO_ROOT_PASSWORD=${NEW_PASSWORD}|" "$ENV_FILE"
  fi
else
  # Add new password line
  echo "ARANGO_ROOT_PASSWORD=${NEW_PASSWORD}" >> "$ENV_FILE"
fi

echo -e "${GREEN}✅ Password updated in .env file${NC}"

# Stop ArangoDB
echo -e "${GREEN}Stopping ArangoDB container...${NC}"
cd "$DEPLOY_DIR"
docker compose stop graph || true

# Remove data directory
echo -e "${GREEN}Removing ArangoDB data directory...${NC}"
if [[ -d "/raid/vyasa/arangodb" ]]; then
  BACKUP_DIR="/raid/vyasa/arangodb.backup.$(date +%Y%m%d_%H%M%S)"
  echo -e "${YELLOW}Creating backup at $BACKUP_DIR${NC}"
  sudo cp -r /raid/vyasa/arangodb "$BACKUP_DIR" 2>/dev/null || {
    echo -e "${YELLOW}Note: Could not create backup (may require sudo). Proceeding anyway...${NC}"
  }
  
  sudo rm -rf /raid/vyasa/arangodb || {
    echo -e "${RED}[ERROR] Failed to remove /raid/vyasa/arangodb. You may need to run with sudo.${NC}" >&2
    exit 1
  }
  echo -e "${GREEN}✅ ArangoDB data directory removed${NC}"
fi

# Restart ArangoDB with new password
echo -e "${GREEN}Starting ArangoDB container (will initialize with new password)...${NC}"
docker compose up -d graph

echo -e "${GREEN}Waiting for ArangoDB to initialize (15 seconds)...${NC}"
sleep 15

# Verify
echo -e "${GREEN}Verifying ArangoDB with new password...${NC}"
if curl -s -u "root:${NEW_PASSWORD}" "http://localhost:8529/_api/version" > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Authentication successful with new password!${NC}"
else
  echo -e "${YELLOW}⚠️  Authentication test failed. ArangoDB may still be initializing.${NC}"
fi

# Restart orchestrator
echo -e "${GREEN}Restarting orchestrator...${NC}"
docker restart deploy-orchestrator-1 || true

echo ""
echo -e "${GREEN}✅ Password rotation complete!${NC}"
echo ""
echo -e "${BLUE}New credentials:${NC}"
echo -e "  Username: ${GREEN}root${NC}"
echo -e "  Password: ${GREEN}${NEW_PASSWORD}${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Update any other services or scripts that use the old password!${NC}"

