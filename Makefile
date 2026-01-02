# Makefile for Project Vyasa
#
# Usage:
#   make test              # Run all unit tests
#   make test-unit         # Run only unit tests
#   make test-integration  # Run only integration tests
#   make test-all          # Run all tests (unit + integration)
#   make lint              # Run linters (if configured)

.PHONY: test test-unit test-integration test-all lint help

# Default target
help:
	@echo "Project Vyasa - Available targets:"
	@echo "  make test              - Run all unit tests"
	@echo "  make test-unit         - Run only unit tests"
	@echo "  make test-integration  - Run only integration tests"
	@echo "  make test-all          - Run all tests (unit + integration)"
	@echo "  make lint              - Run linters (placeholder)"

# Run all unit tests (default)
test: test-unit

# Run unit tests only
test-unit:
	@echo "Running unit tests..."
	python -m pytest src/tests/unit -v

# Run integration tests only
test-integration:
	@echo "Running integration tests..."
	python -m pytest -m integration src/tests/integration -v

# Run all tests (unit + integration)
test-all:
	@echo "Running all tests..."
	python -m pytest src/tests -v

# Lint (placeholder - add your linter commands here)
lint:
	@echo "Linting not yet configured. Add your linter commands here."

