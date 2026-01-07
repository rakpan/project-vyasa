#!/bin/bash
# Setup script for orchestrator container
# Installs Python dependencies from orchestrator-specific requirements file
# Note: The orchestrator uses SGLang via HTTP only, so sglang package is excluded

set -e

# Determine requirements file (default to orchestrator-specific, fallback to main)
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements-orchestrator.txt}"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
  REQUIREMENTS_FILE="requirements.txt"
fi

# Upgrade pip to latest version to avoid upgrade notices
pip install --quiet --upgrade pip

# Install Python dependencies
pip install --no-cache-dir -r "$REQUIREMENTS_FILE"

# Set PYTHONPATH to include /app so src module can be imported
export PYTHONPATH=/app:$PYTHONPATH

# Start uvicorn
exec uvicorn src.orchestrator.main:app --host 0.0.0.0 --port 8000
