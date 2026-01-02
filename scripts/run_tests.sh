#!/bin/bash
#
# Test runner script for Project Vyasa
#
# Purpose: Executes pytest test suite with proper Python path configuration.
# Supports split test strategy: Unit Tests (mocked) vs Integration Tests (real).
#
# Usage:
#   ./scripts/run_tests.sh                    # Run only unit tests (default)
#   ./scripts/run_tests.sh --integration      # Run only integration tests
#   ./scripts/run_tests.sh --all              # Run both unit and integration tests
#

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
. "$SCRIPT_DIR/lib/env.sh"
load_env_defaults

cd "$PROJECT_ROOT"

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine Python and pytest executables
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
VENV_PYTEST="$PROJECT_ROOT/.venv/bin/pytest"

if [ -f "$VENV_PYTHON" ] && [ -f "$VENV_PYTEST" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    PYTEST_CMD="$VENV_PYTEST"
    echo -e "${BLUE}Using virtual environment: .venv${NC}"
elif [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    PYTEST_CMD="$PYTHON_CMD -m pytest"
    echo -e "${BLUE}Using virtual environment: .venv (pytest via module)${NC}"
else
    PYTHON_CMD="python3"
    PYTEST_CMD="$PYTHON_CMD -m pytest"
    echo -e "${BLUE}Using system Python (no .venv found)${NC}"
fi

# Export PYTHONPATH to ensure pytest can find the src module
export PYTHONPATH="${PYTHONPATH:-}:${PROJECT_ROOT}"

# Parse arguments using case/esac
MODE="unit"
if [ $# -gt 0 ]; then
    case "$1" in
        --integration)
            MODE="integration"
            ;;
        --all)
            MODE="all"
            ;;
        --unit)
            MODE="unit"
            ;;
        --help|-h)
            echo "Usage: $0 [--unit|--integration|--all]"
            echo ""
            echo "Options:"
            echo "  (no args)     Run only unit tests (mocked, fast)"
            echo "  --unit        Run only unit tests (mocked, fast)"
            echo "  --integration Run only integration tests (requires Docker)"
            echo "  --all         Run both unit and integration tests"
            echo "  --help, -h    Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
fi

# Function to run unit tests
run_unit_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Running Unit Tests (Mocked - No External Dependencies)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    $PYTEST_CMD -v -m "not integration" src/tests/unit/
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Unit tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Unit tests failed${NC}"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Running Integration Tests (Real - Requires Docker Stack)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    echo -e "${YELLOW}⚠  WARNING: Ensure Docker stack is running!${NC}"
    echo -e "${YELLOW}   Required services: ArangoDB (localhost:8529), Cortex (localhost:30000)${NC}"
    echo ""
    
    $PYTEST_CMD -v -s -m "integration" src/tests/integration/
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Integration tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Integration tests failed${NC}"
        return 1
    fi
}

# Execute based on mode
EXIT_CODE=0

case "$MODE" in
    unit)
        run_unit_tests
        EXIT_CODE=$?
        ;;
    integration)
        run_integration_tests
        EXIT_CODE=$?
        ;;
    all)
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Running All Tests (Unit + Integration)${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        
        # Run unit tests first
        run_unit_tests
        UNIT_EXIT=$?
        echo ""
        
        # Run integration tests
        run_integration_tests
        INT_EXIT=$?
        
        # Determine overall exit code
        if [ $UNIT_EXIT -eq 0 ] && [ $INT_EXIT -eq 0 ]; then
            echo ""
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}✓ All tests passed${NC}"
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            EXIT_CODE=0
        else
            echo ""
            echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${RED}✗ Some tests failed${NC}"
            echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            EXIT_CODE=1
        fi
        ;;
esac

exit $EXIT_CODE
