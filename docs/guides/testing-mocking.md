# Test Mocking Best Practices - The "Golden Rule"

## Overview

This guide explains the **"Golden Rule of Mocking"** and how to write robust, maintainable tests that don't break when code changes.

## The Golden Rule

**Never mock a project file. Always mock the library.**

### Why This Matters

When you mock a project file (like `src.orchestrator.nodes.ArangoClient`), your test becomes **brittle** - it breaks if the import statement changes, even though the functionality is the same.

### Example: Brittle vs. Robust

**❌ BAD (Brittle):**
```python
@patch('src.orchestrator.nodes.ArangoClient')
def test_my_function(mock_client):
    # This breaks if nodes.py changes from:
    #   from arango import ArangoClient
    # to:
    #   import arango
    #   ArangoClient = arango.ArangoClient
```

**Why it fails:** If `nodes.py` changes how it imports `ArangoClient`, the patch target `src.orchestrator.nodes.ArangoClient` may no longer exist, causing `AttributeError`.

**✅ GOOD (Robust):**
```python
def test_my_function(monkeypatch):
    # Mock at the library level
    monkeypatch.setattr('arango.ArangoClient', mock_client_factory)
    # Works regardless of how nodes.py imports it
```

**Why it works:** The patch targets the class in the library's memory. No matter how your code imports it (`from arango import ArangoClient` or `import arango`), it gets the mock.

## Protocol for Fixing Tests

When fixing or writing tests, follow this **"Analyze First, Act Second"** protocol:

### 1. Scan Imports

Before patching, check how the module under test imports the dependency.

**Tools:**
- Use `grep` to find import statements: `grep -r "import.*ArangoClient" src/orchestrator/`
- Use `codebase_search` to understand the import pattern
- Identify the **source library** (e.g., `arango`, `requests`, `pathlib`)

**Example:**
```bash
# Find how ArangoClient is imported
grep -r "ArangoClient" src/orchestrator/nodes/nodes.py
# Result: from arango import ArangoClient
# → Patch target: 'arango.ArangoClient'
```

### 2. Check Fixtures

Do not manually `@patch` a dependency if a global `mock_*_firewall` fixture already exists.

**Check:** `src/tests/unit/conftest.py` for autouse fixtures:
- `mock_arango_firewall` - Already mocks `arango.ArangoClient`
- `mock_requests_firewall` - Already mocks `requests.get` and `requests.post`
- `mock_llm_client_firewall` - Already mocks `src.shared.llm_client.chat`
- `mock_filesystem_firewall` - Already mocks `pathlib.Path` and `builtins.open`

**Use the fixture instead of manual patches:**
```python
# ❌ BAD: Manual patch when fixture exists
@patch('arango.ArangoClient')
def test_my_function(mock_client):
    ...

# ✅ GOOD: Use the firewall fixture
def test_my_function(mock_arango_firewall):
    # Firewall already mocked ArangoClient
    # Configure it if needed:
    def custom_client(hosts):
        # Return custom mock
        ...
    mock_arango_firewall.return_value = custom_client
```

### 3. Verify Scope

Ensure autouse fixtures are actually active in the test's directory scope.

**Rules:**
- Unit tests in `src/tests/unit/` automatically inherit firewall fixtures
- Integration tests in `src/tests/integration/` use real connections
- Tests in `src/orchestrator/tests/` should be moved to `src/tests/unit/orchestrator/` to inherit fixtures

**Check:**
```bash
# Verify your test is in the right location
pytest --collect-only src/tests/unit/your_test.py
# Should show: "collected X items"
```

### 4. Use State Fixtures

Never handwrite state dictionaries.

**❌ BAD:**
```python
def test_my_node():
    state = {
        "jobId": "job-123",
        "threadId": "thread-123",
        "raw_text": "test",
        "url": "http://test.com",
        # ... 20 more fields
    }
    # If schema changes, this breaks
```

**✅ GOOD:**
```python
def test_my_node(base_node_state):
    state = {
        **base_node_state,  # Includes all required fields
        "custom_field": "value",  # Add test-specific fields
    }
    # If schema changes, update base_node_state once, all tests update
```

**Available State Fixtures:**
- `base_node_state` - Complete state dictionary with all required fields
- Located in: `src/tests/conftest.py`

## When Internal Function Patches Are Acceptable

It's acceptable to patch internal functions (`src.orchestrator.*`) if:

1. **They are pure business logic** (not I/O wrappers)
2. **The test is specifically testing that function's behavior**
3. **There's no library equivalent to patch**

### Examples of Acceptable Internal Patches

**Business Logic Functions:**
```python
@patch("src.orchestrator.nodes.route_to_expert")
def test_routing_logic(mock_route):
    """Testing the routing algorithm itself."""
    mock_route.return_value = ("http://worker", "Worker", "model-id")
    # Test routing logic
```

**Internal Transformations:**
```python
@patch("src.orchestrator.normalize.normalize_extracted_json")
def test_normalization(mock_normalize):
    """Testing normalization behavior."""
    mock_normalize.return_value = {"triples": []}
    # Test normalization logic
```

### Examples of Unacceptable Internal Patches

**I/O Wrappers (Should Use Firewall):**
```python
# ❌ BAD: Patching I/O wrapper
@patch("src.orchestrator.server.get_job_record")
def test_endpoint(mock_get_record):
    # Should configure arango.ArangoClient mock instead
```

**✅ GOOD: Configure Library Mock:**
```python
def test_endpoint(monkeypatch):
    """Configure arango.ArangoClient to return test data."""
    def mock_client_factory(hosts):
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"job_id": "job-123", ...}
        mock_db.collection.return_value = mock_collection
        mock_client.db.return_value = mock_db
        return mock_client
    
    monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
    # Now get_job_record() will use the mock
```

## Common Violations and How to Fix Them

### Violation 1: Patching Internal I/O Functions

**Problem:**
```python
@patch("src.orchestrator.api.knowledge._get_db")
def test_knowledge_api(mock_get_db):
    mock_get_db.return_value = mock_db
```

**Fix:**
```python
def test_knowledge_api(monkeypatch):
    """Configure arango.ArangoClient instead."""
    def mock_client_factory(hosts):
        mock_client = Mock()
        mock_client.db.return_value = mock_db
        return mock_client
    
    monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
    # _get_db() will now use the mocked ArangoClient
```

### Violation 2: Manual State Dictionary Creation

**Problem:**
```python
def test_my_node():
    state = {
        "jobId": "job-123",
        "threadId": "thread-123",
        "raw_text": "test",
        # Missing required fields causes KeyError
    }
```

**Fix:**
```python
def test_my_node(base_node_state):
    state = {
        **base_node_state,  # All required fields included
        "custom_field": "value",  # Add test-specific fields
    }
```

### Violation 3: Redundant Patches

**Problem:**
```python
@patch('requests.post')  # Firewall already mocks this!
def test_my_function(mock_post):
    # Unnecessary - firewall handles it
```

**Fix:**
```python
def test_my_function():
    # Firewall already mocks requests.post
    # If you need custom behavior, configure mock_requests_firewall
    # But usually you don't need to
```

## Refactoring Checklist

When refactoring existing tests to follow the Golden Rule:

1. **Identify patches:** Find all `@patch("src.*")` decorators
2. **Categorize:**
   - I/O operations (DB, network) → Should use firewall
   - Business logic → Acceptable to patch
3. **Replace I/O patches:**
   - Remove `@patch("src.orchestrator.*._get_db")`
   - Configure `arango.ArangoClient` mock instead
4. **Replace state creation:**
   - Find manual state dictionaries
   - Replace with `{**base_node_state, ...}`
5. **Test:** Run tests to ensure they still pass

## Examples

### Example 1: Refactoring a Server Validation Test

**Before (Brittle):**
```python
@patch("src.orchestrator.server.get_job_record")
@patch("src.orchestrator.server.get_job")
def test_job_status(self, mock_get_job, mock_get_job_record):
    mock_get_job.return_value = {"status": "queued"}
    mock_get_job_record.return_value = {"initial_state": {"project_id": "p1"}}
    # Test code
```

**After (Robust):**
```python
def test_job_status(self, monkeypatch):
    """Configure arango.ArangoClient to return job records."""
    def mock_client_factory(hosts):
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "job_id": "job-123",
            "initial_state": {"project_id": "p1"}
        }
        mock_db.collection.return_value = mock_collection
        mock_client.db.return_value = mock_db
        return mock_client
    
    monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
    # get_job_record() now uses the mock
```

### Example 2: Using State Fixtures

**Before (Brittle):**
```python
def test_cartographer():
    state = {
        "jobId": "job-123",
        "threadId": "thread-123",
        "raw_text": "test",
        "url": "http://test.com",
        # Missing fields cause KeyError when schema changes
    }
```

**After (Robust):**
```python
def test_cartographer(base_node_state):
    state = {
        **base_node_state,  # All required fields
        "raw_text": "test",  # Override if needed
        "url": "http://test.com",
    }
```

## Summary

1. **Golden Rule:** Mock libraries (`arango.ArangoClient`), not project files (`src.orchestrator.nodes.ArangoClient`)
2. **Use Firewall:** Don't manually patch what the firewall already handles
3. **Use Fixtures:** Always use `base_node_state` instead of manual state creation
4. **Acceptable Exceptions:** Internal business logic functions can be patched if testing that specific function

Following these rules ensures your tests remain robust and don't break when code is refactored.

