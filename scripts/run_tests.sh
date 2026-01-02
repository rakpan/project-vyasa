#!/bin/bash
#
# Test runner script for Project Vyasa
#
# Purpose: Executes pytest test suite with proper Python path configuration.
# Ensures pytest can correctly find the src module using absolute imports.
# Uses .venv if available, otherwise falls back to system python3.
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
. "$SCRIPT_DIR/lib/env.sh"
load_env_defaults

cd "$PROJECT_ROOT"

# Determine Python and pytest executables
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
VENV_PYTEST="$PROJECT_ROOT/.venv/bin/pytest"

if [ -f "$VENV_PYTHON" ] && [ -f "$VENV_PYTEST" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    PYTEST_CMD="$VENV_PYTEST"
    echo "Using virtual environment: .venv"
elif [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    PYTEST_CMD="$PYTHON_CMD -m pytest"
    echo "Using virtual environment: .venv (pytest via module)"
else
    PYTHON_CMD="python3"
    PYTEST_CMD="$PYTHON_CMD -m pytest"
    echo "Using system Python (no .venv found)"
fi

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

# Check if pytest is available
if ! $PYTEST_CMD --version >/dev/null 2>&1; then
    echo "Error: pytest is not installed."
    echo ""
    if [ -f "$VENV_PYTHON" ]; then
        echo "Virtual environment exists but pytest is missing."
        echo "Install dependencies:"
        echo "  $VENV_PYTHON -m pip install -r requirements.txt"
    else
        echo "Install dependencies from requirements.txt:"
        echo "  python3 -m pip install -r requirements.txt"
        echo ""
        echo "Or create a virtual environment first:"
        echo "  python3 -m venv .venv"
        echo "  .venv/bin/pip install -r requirements.txt"
    fi
    exit 1
fi

echo "Running tests from: $PROJECT_ROOT"
echo "PYTHONPATH: $PYTHONPATH"
echo "Command: $PYTEST_CMD ${TEST_ARGS[*]}"
echo ""

# Run pytest
$PYTEST_CMD "${TEST_ARGS[@]}"
