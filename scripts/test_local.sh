#!/bin/bash
#
# Local test runner for Project Vyasa.
#
# Usage:
#   ./scripts/test_local.sh              # Run unit tests only
#   ./scripts/test_local.sh --with-integration  # Run unit + integration tests
#

set -e

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"

# Set PYTHONPATH to include src/
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest is not installed."
    echo "Install it with: pip install pytest pytest-asyncio httpx reportlab"
    exit 1
fi

# Default to unit tests only
INTEGRATION_FLAG=""

# Parse arguments
if [[ "$1" == "--with-integration" ]]; then
    INTEGRATION_FLAG="-m integration"
    echo "Running unit tests + integration tests..."
else
    echo "Running unit tests only (use --with-integration for integration tests)..."
fi

# Run pytest
cd "$PROJECT_ROOT"
pytest "$SRC_DIR/tests/" \
    -v \
    --tb=short \
    --strict-markers \
    $INTEGRATION_FLAG \
    "$@"

echo ""
echo "✅ Tests completed!"

