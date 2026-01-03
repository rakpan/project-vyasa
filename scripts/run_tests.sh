#!/bin/bash
#
# Test runner script for Project Vyasa
#
# Purpose: Executes test suites with proper configuration.
# Supports split test strategy:
#   - Unit Tests (Python, mocked, fast)
#   - Integration Tests (Python, real Docker stack)
#   - E2E Tests (Playwright, requires Node.js/npm)
#
# Usage:
#   ./scripts/run_tests.sh                    # Run only unit tests (default)
#   ./scripts/run_tests.sh --integration      # Run only integration tests
#   ./scripts/run_tests.sh --e2e             # Run only E2E tests
#   ./scripts/run_tests.sh --all             # Run all tests (unit + integration + e2e)
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
        --e2e)
            MODE="e2e"
            ;;
        --all)
            MODE="all"
            ;;
        --unit)
            MODE="unit"
            ;;
        --help|-h)
            echo "Usage: $0 [--unit|--integration|--e2e|--all]"
            echo ""
            echo "Options:"
            echo "  (no args)     Run only unit tests (mocked, fast)"
            echo "  --unit        Run only unit tests (mocked, fast)"
            echo "  --integration Run only integration tests (requires Docker)"
            echo "  --e2e         Run only E2E tests (requires Node.js/npm)"
            echo "  --all         Run all tests (unit + integration + e2e)"
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

# Function to run E2E tests
run_e2e_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Running E2E Tests (Playwright - Requires Node.js/npm)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check if Node.js is available
    if ! command -v node &> /dev/null; then
        echo -e "${RED}✗ Node.js is not installed or not in PATH${NC}"
        echo -e "${YELLOW}   Please install Node.js to run E2E tests${NC}"
        return 1
    fi
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}✗ npm is not installed or not in PATH${NC}"
        echo -e "${YELLOW}   Please install npm to run E2E tests${NC}"
        return 1
    fi
    
    # Navigate to console directory
    CONSOLE_DIR="$PROJECT_ROOT/src/console"
    if [ ! -d "$CONSOLE_DIR" ]; then
        echo -e "${RED}✗ Console directory not found: $CONSOLE_DIR${NC}"
        return 1
    fi
    
    cd "$CONSOLE_DIR"
    
    # Check if node_modules exists, if not, try to install
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}⚠  node_modules not found, attempting to install dependencies...${NC}"
        npm install
        if [ $? -ne 0 ]; then
            echo -e "${RED}✗ Failed to install npm dependencies${NC}"
            return 1
        fi
    fi
    
    # Check if Playwright is installed
    if [ ! -f "node_modules/.bin/playwright" ]; then
        echo -e "${YELLOW}⚠  Playwright not found, installing...${NC}"
        npx playwright install --with-deps
        if [ $? -ne 0 ]; then
            echo -e "${RED}✗ Failed to install Playwright${NC}"
            return 1
        fi
    fi
    
    # Run E2E tests
    npm run test:e2e
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ E2E tests passed${NC}"
        cd "$PROJECT_ROOT"
        return 0
    else
        echo -e "${RED}✗ E2E tests failed${NC}"
        cd "$PROJECT_ROOT"
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
    e2e)
        run_e2e_tests
        EXIT_CODE=$?
        ;;
    all)
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Running All Tests (Unit + Integration + E2E)${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        
        # Run unit tests first
        run_unit_tests
        UNIT_EXIT=$?
        echo ""
        
        # Run integration tests
        run_integration_tests
        INT_EXIT=$?
        echo ""
        
        # Run E2E tests
        run_e2e_tests
        E2E_EXIT=$?
        
        # Determine overall exit code
        if [ $UNIT_EXIT -eq 0 ] && [ $INT_EXIT -eq 0 ] && [ $E2E_EXIT -eq 0 ]; then
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
