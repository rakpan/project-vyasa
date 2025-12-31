#!/bin/bash
#
# Test runner script for Project Vyasa
#
# Purpose: Executes pytest test suite with proper Python path configuration.
# Ensures pytest can correctly find the src module using absolute imports.
#
# Usage:
#   ./scripts/run_tests.sh                    # Run all tests
#   ./scripts/run_tests.sh --unit             # Run only unit tests
#   ./scripts/run_tests.sh --integration      # Run only integration tests
#   ./scripts/run_tests.sh --with-integration # Run unit + integration tests
#

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)

cd "$PROJECT_ROOT"

# Export PYTHONPATH to ensure pytest can find the src module
export PYTHONPATH="${PYTHONPATH:-}:${PROJECT_ROOT}"

# Default: run unit tests only
TEST_ARGS=()

# Parse arguments
if [ $# -eq 0 ]; then
    # Default: unit tests only
    TEST_ARGS=("src/tests/unit" "src/orchestrator/tests")
elif [ "$1" == "--unit" ]; then
    TEST_ARGS=("src/tests/unit" "src/orchestrator/tests")
elif [ "$1" == "--integration" ]; then
    TEST_ARGS=("-m" "integration" "src/tests/integration")
elif [ "$1" == "--with-integration" ]; then
    TEST_ARGS=("src/tests" "src/orchestrator/tests")
elif [ "$1" == "--all" ]; then
    TEST_ARGS=("src/tests" "src/orchestrator/tests")
else
    # Pass through any other arguments to pytest
    TEST_ARGS=("$@")
fi

# Check if pytest is installed
if ! python3 -m pytest --version >/dev/null 2>&1; then
    echo "Error: pytest is not installed."
    echo ""
    echo "Install dependencies from requirements.txt:"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Or install pytest directly:"
    echo "  pip install pytest pytest-asyncio httpx"
    exit 1
fi

echo "Running tests from: $PROJECT_ROOT"
echo "PYTHONPATH: $PYTHONPATH"
echo "Command: python3 -m pytest ${TEST_ARGS[*]}"
echo ""

# Run pytest using python3 -m pytest (automatically adds current directory to path)
python3 -m pytest "${TEST_ARGS[@]}"

