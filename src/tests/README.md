# Project Vyasa Test Suite

This directory contains the test suite for Project Vyasa backend services.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── pytest.ini               # Pytest configuration
├── unit/                    # Unit tests (no external dependencies)
│   ├── test_nodes.py        # Cartographer/Critic/Saver node tests (mocked Cortex/Arango)
│   ├── test_pdf_parser.py   # PDF processing tests
│   ├── test_role_registry.py# Dynamic role registry behaviors (Arango mocked)
│   └── test_workflow_contract.py # /workflow/process contract (triples normalization)
└── integration/             # Integration tests (require Docker services)
    └── test_db.py           # Database connection tests
```

## Running Tests

### Unit Tests Only (Recommended for Development)

```bash
# From project root
./scripts/test_local.sh
```

Or directly:
```bash
cd src
export PYTHONPATH=.:$PYTHONPATH
pytest tests/unit/ -v
```

### Unit + Integration Tests

Requires Docker services to be running:

```bash
# Start services
cd deploy
docker compose up -d

# Run all tests
./scripts/test_local.sh --with-integration
```

Or directly:
```bash
cd src
export PYTHONPATH=.:$PYTHONPATH
pytest tests/ -v -m integration
```

## Test Categories

### Unit Tests

- **No external dependencies**: Can run without Docker or GPU
- **Fast execution**: Typically complete in seconds
- **Mocked services**: Uses mocks for Cortex, ArangoDB, Qdrant

### Integration Tests

- **Require running services**: Need Docker Compose services running
- **Real connections**: Test actual database connections
- **Marked with `@pytest.mark.integration`**: Can be skipped if services unavailable

## Test Update Summary (Committee-of-Experts refactor)
- Kept: PDF processor coverage and normalization utilities.
- Changed: Node tests now target Cartographer/Critic/Saver with mocked Cortex and Arango.
- Added: RoleRegistry persistence/lookup tests and /workflow/process contract tests to enforce `extracted_json.triples`.
- Obsolete: Legacy vision/worker-specific node tests removed in favor of the new agentic workflow shape.

## Fixtures

### `mock_pdf_path`
Creates a temporary PDF file using reportlab for testing PDF parsing.

### `mock_cortex`
Mocks Cortex (SGLang) API responses. Simulates structured JSON extraction.

### `real_arango`
Connects to real ArangoDB instance (requires `ARANGODB_PASSWORD` in environment).

### `real_qdrant`
Connects to real Qdrant instance (requires `QDRANT_URL` in environment).

## Writing New Tests

### Unit Test Example

```python
def test_my_function(mock_cortex):
    """Test my function with mocked dependencies."""
    with patch('requests.post', mock_cortex):
        result = my_function("input")
        assert result == expected
```

### Integration Test Example

```python
@pytest.mark.integration
def test_database_operation(real_arango):
    """Test database operation with real connection."""
    db = real_arango
    # Test code
```

## Environment Variables

Integration tests use these environment variables (from `deploy/.env`):

- `MEMORY_URL`: ArangoDB connection URL
- `ARANGODB_DB`: Database name
- `ARANGODB_USER`: Database username
- `ARANGODB_PASSWORD` or `ARANGO_ROOT_PASSWORD`: Database password
- `QDRANT_URL`: Qdrant connection URL
- `QDRANT_API_KEY`: Qdrant API key (optional)

## Continuous Integration

For CI/CD, run:

```bash
# Unit tests only (fast, no dependencies)
pytest tests/unit/ -v

# Integration tests (requires services)
docker compose -f deploy/docker-compose.yml up -d
pytest tests/ -v -m integration
docker compose -f deploy/docker-compose.yml down
```
