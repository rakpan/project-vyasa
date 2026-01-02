# Testing Strategy

## Overview

Project Vyasa uses a **split test architecture** that physically separates unit tests (fully mocked) from integration tests (real connections). This ensures fast, reliable unit tests that never hit the network, while integration tests verify real system behavior.

## 1. The Two Lanes

### Unit Tests (`src/tests/unit/`)

**Purpose:** Test pure logic, algorithms, and business rules without external dependencies.

**Rule:** **NO IO allowed.** Unit tests must never:
- Make network calls
- Connect to databases
- Read/write files
- Call external APIs

**Mechanism:** Protected by the **"Mock Firewall"** - autouse fixtures in `src/tests/unit/conftest.py` that automatically mock all external IO at the source library level.

**Speed:** Must run in <100ms per test. The entire unit test suite should complete in seconds.

**Location:**
- `src/tests/unit/` - Main unit tests
- `src/tests/unit/orchestrator/` - Orchestrator-specific unit tests (moved from `src/orchestrator/tests/`)

**Example:**
```python
# src/tests/unit/test_nodes.py
def test_cartographer_extracts_triples(base_node_state, mock_llm_client):
    """Test cartographer logic - no manual mocking needed!"""
    # mock_llm_client is automatically available via firewall
    mock_llm_client.return_value = (
        {"choices": [{"message": {"content": '{"triples": [...]}'}}]},
        {"duration_ms": 100}
    )
    
    result = cartographer_node(base_node_state)
    assert "triples" in result["extracted_json"]
```

### Integration Tests (`src/tests/integration/`)

**Purpose:** Test real system behavior with actual Docker services.

**Rule:** **Real Docker connections allowed.** Integration tests:
- Connect to real ArangoDB (`localhost:8529`)
- Connect to real Cortex services (`localhost:30000+`)
- May read/write files
- Verify end-to-end workflows

**Mechanism:** Uses `real_stack` fixture that checks Docker services are running and provides real client connections.

**Speed:** Slow allowed. Integration tests may take seconds or minutes.

**Location:** `src/tests/integration/`

**Example:**
```python
# src/tests/integration/test_pipeline_e2e.py
@pytest.mark.integration
def test_real_end_to_end_flow(real_stack, real_arango):
    """Test complete workflow with real services."""
    # real_arango provides actual ArangoDB connection
    result = graph.invoke(initial_state)
    
    # Verify data was actually saved
    db = real_arango
    docs = list(db.aql.execute("FOR doc IN extractions RETURN doc"))
    assert len(docs) > 0
```

## 2. How to Run Tests

### Default Mode (Unit Tests Only)

Fast, no dependencies required:

```bash
./scripts/run_tests.sh
# or explicitly:
./scripts/run_tests.sh --unit
```

**Command:** `pytest -v -m "not integration" src/tests/unit/ src/orchestrator/tests/`

**Output:** Green success indicators, fast execution.

### Integration Mode (Integration Tests Only)

Requires Docker stack to be running:

```bash
./scripts/run_tests.sh --integration
```

**Command:** `pytest -v -s -m "integration" src/tests/integration/`

**Pre-check:** Script prints warning: "⚠ WARNING: Ensure Docker stack is running!"

**Required Services:**
- ArangoDB at `localhost:8529`
- Cortex Brain at `localhost:30000` (optional)

### All Tests Mode

Runs both unit and integration tests sequentially:

```bash
./scripts/run_tests.sh --all
```

**Execution Order:**
1. Unit tests run first (fast)
2. Integration tests run second (slow)
3. Summary shows overall pass/fail status

### Help

```bash
./scripts/run_tests.sh --help
```

## 3. The "Firewall" Fixtures

All unit tests in `src/tests/unit/` automatically inherit these autouse fixtures from `src/tests/unit/conftest.py`. **You do NOT need to manually patch external dependencies.**

### `mock_arango_firewall`

**What it does:** Mocks `arango.ArangoClient` at the source library level.

**What you get:** A MagicMock that supports method chaining:
```python
db = ArangoClient(hosts="...").db(...)
collection = db.collection("test")
result = collection.insert({"key": "value"})  # Works!
```

**When to override:** If you need specific behavior, you can still use `monkeypatch.setattr` in your test, but it's rarely needed.

### `mock_requests_firewall`

**What it does:** Mocks `requests.get` and `requests.post` at the source library level.

**What you get:** All HTTP calls return mock responses automatically.

**Default behavior:** Returns 200 status with empty JSON.

**When to override:** Use `mock_llm_client_firewall` instead for LLM calls (see below).

### `mock_llm_client_firewall`

**What it does:** Mocks `src.shared.llm_client.chat` at the source.

**What you get:** Default mock responses for all LLM calls.

**Default response:**
```python
(
    {"choices": [{"message": {"content": '{"triples": [], "entities": []}'}}]},
    {"duration_ms": 100, "usage": {...}, ...}
)
```

**How to customize:** Inject the fixture and override:
```python
def test_my_node(mock_llm_client):
    # Override default behavior
    mock_llm_client.return_value = (
        {"choices": [{"message": {"content": "custom response"}}]},
        {"duration_ms": 100}
    )
    # Or use side_effect for multiple calls
    mock_llm_client.side_effect = [response1, response2, ...]
```

### `mock_filesystem_firewall`

**What it does:** Mocks `pathlib.Path.mkdir` and `builtins.open`.

**What you get:** File operations are automatically mocked, preventing PermissionError and FileNotFoundError.

**When to override:** If you need to test file I/O logic, you can still patch these in your test.

### `mock_project_context_firewall`

**What it does:** Mocks `src.orchestrator.nodes.nodes._get_project_service`.

**What you get:** A mock ProjectService with valid project configuration.

**Default config:**
- Project ID: `"p1"`
- Thesis: `"Test thesis statement"`
- Research questions: `["RQ1: What is the research question?"]`
- Rigor level: `"exploratory"`

### `mock_network_config_firewall`

**What it does:** Mocks config functions to return `localhost` instead of container names.

**What you get:** No DNS resolution errors. All config getters return `http://localhost:8529` etc.

## 4. Writing a New Test

### Scenario A: Testing Logic (Parsing, Routing, Algorithms)

**Location:** `src/tests/unit/`

**What to test:**
- Node logic (cartographer, critic, saver)
- Data normalization
- State transformations
- Business rules
- Algorithm correctness

**What NOT to do:**
- ❌ Don't manually patch `requests.post` or `requests.get`
- ❌ Don't manually patch `arango.ArangoClient`
- ❌ Don't manually patch `pathlib.Path.mkdir` or `builtins.open`
- ❌ Don't manually patch `src.shared.llm_client.chat`

**What TO do:**
- ✅ Use `base_node_state` fixture for state dictionaries
- ✅ Use `mock_llm_client` fixture (injected automatically) to customize LLM responses
- ✅ Trust the firewall - external dependencies are already mocked
- ✅ Focus on testing your logic, not mocking infrastructure

**Example:**
```python
# src/tests/unit/test_my_feature.py
def test_my_algorithm(base_node_state, mock_llm_client):
    """Test my algorithm logic."""
    # Customize LLM response if needed
    mock_llm_client.return_value = (
        {"choices": [{"message": {"content": "test"}}]},
        {"duration_ms": 100}
    )
    
    # Use base_node_state
    state = {**base_node_state, "custom_field": "value"}
    
    # Test your logic
    result = my_algorithm(state)
    assert result["expected_field"] == "expected_value"
```

### Scenario B: Testing API Contract (End-to-End, Real Services)

**Location:** `src/tests/integration/`

**What to test:**
- API endpoints with real HTTP requests
- Database persistence with real ArangoDB
- Complete workflows from start to finish
- Service integration (Cortex, ArangoDB, Qdrant)

**What to do:**
- ✅ Mark test with `@pytest.mark.integration`
- ✅ Use `real_stack` fixture to ensure Docker is running
- ✅ Use `real_arango` or `real_qdrant` for real connections
- ✅ Clean up test data in `finally` blocks
- ✅ Skip gracefully if services are unavailable

**Example:**
```python
# src/tests/integration/test_my_api.py
@pytest.mark.integration
def test_api_endpoint(real_stack, real_arango):
    """Test API endpoint with real database."""
    # real_stack ensures Docker is running
    # real_arango provides real ArangoDB connection
    
    # Make real API call
    response = client.post("/api/endpoint", json={"data": "test"})
    assert response.status_code == 200
    
    # Verify data in real database
    db = real_arango
    docs = list(db.aql.execute("FOR doc IN collection RETURN doc"))
    assert len(docs) > 0
    
    # Cleanup
    try:
        db.aql.execute("FOR doc IN collection REMOVE doc IN collection")
    except:
        pass
```

## 5. Best Practices

### Unit Tests

1. **Fast First:** If a test takes >100ms, it's probably doing too much. Split it or move to integration.
2. **No Network Calls:** If you see a network call in a unit test, the firewall isn't working. Check that your test is in `src/tests/unit/`.
3. **Trust the Firewall:** Don't manually patch external dependencies. The firewall handles it.
4. **Test Logic, Not Mocks:** Focus on testing your code's behavior, not the mock setup.

### Integration Tests

1. **Mark Correctly:** Always use `@pytest.mark.integration`.
2. **Check Services:** Use `real_stack` fixture to ensure Docker is running.
3. **Clean Up:** Always clean up test data to avoid polluting the database.
4. **Skip Gracefully:** Use `pytest.skip()` if services are unavailable.

### General

1. **Use Fixtures:** Leverage `base_node_state`, `mock_pdf_path`, etc. from `src/tests/conftest.py`.
2. **Clear Names:** Test names should clearly describe what they're testing.
3. **One Assertion Per Concept:** Group related assertions, but test one concept per test.
4. **Document Edge Cases:** Add comments for non-obvious test scenarios.

## 6. Troubleshooting

### "My unit test is making real network calls!"

**Problem:** The firewall isn't active.

**Solution:**
1. Ensure your test is in `src/tests/unit/` or a subdirectory
2. Check that `src/tests/unit/conftest.py` exists and has autouse fixtures
3. Verify pytest is discovering the conftest: `pytest --collect-only src/tests/unit/`

### "My integration test is being mocked!"

**Problem:** Integration test is in the wrong location or firewall is too aggressive.

**Solution:**
1. Ensure your test is in `src/tests/integration/`
2. Verify test is marked with `@pytest.mark.integration`
3. Check that you're using `real_arango` or `real_qdrant` fixtures (not mocks)

### "AttributeError: module has no attribute 'ArangoClient'"

**Problem:** Trying to patch downstream consumer instead of source.

**Solution:**
- ❌ Bad: `monkeypatch.setattr('src.orchestrator.nodes.ArangoClient', ...)`
- ✅ Good: `monkeypatch.setattr('arango.ArangoClient', ...)` (but you shouldn't need this - firewall handles it)

### "Test is slow (>100ms)"

**Problem:** Unit test is doing too much or hitting real services.

**Solution:**
1. Check if test is in `src/tests/unit/` (should be fast)
2. If logic is complex, consider splitting into smaller tests
3. If it needs real services, move to `src/tests/integration/`

## 7. Migration Notes

If you have existing tests that need to be migrated:

1. **Move orchestrator tests:** Tests in `src/orchestrator/tests/` should be moved to `src/tests/unit/orchestrator/`
2. **Remove manual patches:** Delete `@patch` decorators for `requests`, `ArangoClient`, `pathlib.Path`, etc.
3. **Use fixtures:** Replace manual state setup with `base_node_state` fixture
4. **Mark integration tests:** Add `@pytest.mark.integration` to tests that need real services

## 8. References

- **Firewall Implementation:** `src/tests/unit/conftest.py`
- **Integration Setup:** `src/tests/integration/conftest.py`
- **Shared Fixtures:** `src/tests/conftest.py`
- **Test Runner:** `scripts/run_tests.sh`

