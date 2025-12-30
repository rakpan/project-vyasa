#!/bin/bash
#
# Test runner script for Project Vyasa
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

echo "Running tests from: $PROJECT_ROOT"
echo "Python path: ${PYTHONPATH:-<not set>}"
echo "Command: python -m pytest ${TEST_ARGS[*]}"
echo ""

# Run pytest using python -m pytest (automatically adds current directory to path)
python -m pytest "${TEST_ARGS[@]}"

