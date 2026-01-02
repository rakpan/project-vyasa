#!/usr/bin/env bash
#
# Project Vyasa - Virtual Environment Setup
# Purpose: Creates and configures .venv with all required dependencies
# Usage: ./scripts/setup_venv.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Project Vyasa - Virtual Environment Setup"
echo "=========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "Python version: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment: .venv"
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "Virtual environment already exists: .venv"
fi

echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip >/dev/null 2>&1 || true

# Install dependencies
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "Warning: requirements.txt not found"
fi

echo ""
echo "=========================================="
echo "Virtual environment setup complete!"
echo "=========================================="
echo ""
echo "To activate the virtual environment manually:"
echo "  source .venv/bin/activate"
echo ""
echo "To run tests:"
echo "  ./scripts/run_tests.sh"
echo ""

