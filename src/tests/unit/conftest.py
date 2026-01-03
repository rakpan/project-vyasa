"""
Unit Test Firewall - Automatically mocks all external IO for unit tests.

This conftest.py applies to all tests in src/tests/unit/ and subdirectories.
It uses autouse=True fixtures to create a "firewall" that prevents any
real network calls, database connections, or file I/O.

**Patching Strategy: "Patch the Source, Not the Consumer"**

All mocks patch at the source library level, not downstream consumers.
This prevents AttributeError crashes when modules don't expose imported
classes/functions as module-level attributes.

Examples:
- ✅ GOOD: `monkeypatch.setattr('arango.ArangoClient', ...)` - patches the source library
- ✅ GOOD: `monkeypatch.setattr('requests.get', ...)` - patches the source library
- ❌ BAD: `monkeypatch.setattr('src.orchestrator.nodes.ArangoClient', ...)` - patches downstream consumer
"""

import json
from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock, MagicMock

import pytest


def pytest_configure(config):
    """Pytest hook to patch dependencies before any tests run.
    
    This runs before test collection, ensuring patches are applied
    before any imports that might use the patched functions.
    """
    # Patch importlib.metadata.version early (before any imports that might use it)
    # This prevents TypeError when werkzeug/Flask call version() during test_client() initialization
    # The error "initial_value must be str or None, not bytes" occurs when version() returns bytes
    try:
        import importlib.metadata
        def _mock_version(package_name: str) -> str:
            """Mock version() to always return a string, not bytes."""
            return "3.0.0"
        importlib.metadata.version = _mock_version
    except (ImportError, AttributeError):
        pass

    try:
        import importlib_metadata
        def _mock_version_metadata(package_name: str) -> str:
            """Mock version() to always return a string, not bytes."""
            return "3.0.0"
        importlib_metadata.version = _mock_version_metadata
    except ImportError:
        pass
    
    # Patch joblib.Memory early to prevent cache lock file creation
    try:
        from joblib import Memory
        original_init = Memory.__init__
        def noop_init(self, *args, **kwargs):
            """No-op __init__ that skips cache directory creation."""
            object.__init__(self)  # Just initialize the object, skip cache dir creation
        Memory.__init__ = noop_init
    except ImportError:
        pass  # joblib might not be installed
    
    # Patch RoleRegistry._init_arangodb early to prevent DB connections during import
    # RoleRegistry is instantiated at module level in nodes.py and tone_guard.py,
    # so we need to patch it before those modules are imported
    try:
        # Patch _init_arangodb early to prevent connections during module import
        # This is a no-op that just sets db=None
        def early_mock_init_arangodb(self):
            self.db = None
        
        # Try to patch if the module is already loaded
        import sys
        if "src.shared.role_manager" in sys.modules:
            role_manager_module = sys.modules["src.shared.role_manager"]
            if hasattr(role_manager_module, "RoleRegistry"):
                # Patch the method on the class
                role_manager_module.RoleRegistry._init_arangodb = early_mock_init_arangodb
                
                # Also patch any existing instances in modules that might have been imported
                modules_to_check = [
                    "src.orchestrator.nodes.nodes",
                    "src.orchestrator.tone_guard",
                    "src.orchestrator.nodes.tone_guard",
                ]
                for module_name in modules_to_check:
                    if module_name in sys.modules:
                        module = sys.modules[module_name]
                        if hasattr(module, "role_registry"):
                            # Set db to None and patch methods on the instance
                            instance = module.role_registry
                            instance.db = None
                            instance._init_arangodb = lambda: None  # No-op
    except Exception:
        pass  # Will be handled by fixture, but early patch helps if module is already loaded


@pytest.fixture(autouse=True)
def mock_arango_firewall(monkeypatch):
    """Automatically mock ArangoDB client for all unit tests.
    
    Patches arango.ArangoClient at the source library level.
    Returns a MagicMock that supports method chaining (db().collection().insert()).
    """
    # Create a mock collection with insert method and len() support
    def create_mock_collection(name: str):
        mock_col = MagicMock()
        mock_col.insert.return_value = {
            "_key": "test-key",
            "_id": f"{name}/test-key",
            "_rev": "1"
        }
        mock_col.get.return_value = None
        mock_col.has_index.return_value = True
        mock_col.add_index.return_value = None
        mock_col.update.return_value = {"_key": "test-key", "_rev": "2"}
        mock_col.delete.return_value = None
        # Support len() for collection size checks
        mock_col.__len__ = Mock(return_value=0)
        return mock_col
    
    # Create a mock database
    mock_db = Mock()
    mock_db.version.return_value = "3.11.0"
    mock_db.has_collection.return_value = True
    mock_db.create_collection.side_effect = create_mock_collection
    mock_db.collection.side_effect = create_mock_collection
    mock_db.delete_collection.return_value = None
    
    # Mock AQL execution
    mock_db.aql = Mock()
    mock_db.aql.execute.return_value = iter([])
    
    # Create a mock client factory
    def mock_arango_client(hosts: str):
        mock_client = Mock()
        mock_client.db.return_value = mock_db
        return mock_client
    
    # Patch at the source library
    monkeypatch.setattr("arango.ArangoClient", mock_arango_client)
    
    yield mock_arango_client


@pytest.fixture(autouse=True)
def mock_requests_firewall(monkeypatch):
    """Automatically mock all requests methods for all unit tests.
    
    Patches requests.api.request at the source library level to cover all HTTP methods
    (GET, POST, PUT, DELETE, etc.) and prevent any network calls.
    """
    def create_mock_response(**kwargs):
        """Create a mock response object with all necessary attributes."""
        mock_response = MagicMock()
        mock_response.text = kwargs.get("text", "# Mock Prometheus metrics\nsglang:prompt_tokens_total 0\n")
        mock_response.content = kwargs.get("content", b"")
        mock_response.json.return_value = kwargs.get("json_data", {
            "choices": [{
                "message": {
                    "content": json.dumps({"triples": [], "entities": []})
                }
            }]
        })
        mock_response.raise_for_status = Mock()
        mock_response.status_code = kwargs.get("status_code", 200)
        mock_response.headers = {}
        mock_response.ok = mock_response.status_code < 400
        # Support iteration if response is used as iterable
        mock_response.__iter__ = Mock(return_value=iter([]))
        return mock_response
    
    def mock_requests_request(method, url, timeout=None, **kwargs):
        """Mock requests.api.request to prevent real HTTP calls for all methods."""
        return create_mock_response()
    
    def mock_requests_get(url, timeout=None, **kwargs):
        """Mock requests.get to prevent real HTTP calls."""
        return create_mock_response()
    
    def mock_requests_post(url, timeout=None, **kwargs):
        """Mock requests.post to prevent real HTTP calls."""
        return create_mock_response()
    
    # Patch at the source library - patch api.request to cover all methods
    try:
        import requests.api
        monkeypatch.setattr("requests.api.request", mock_requests_request)
    except (ImportError, AttributeError):
        pass  # Fallback if api.request doesn't exist
    
    # Also patch get and post directly for compatibility
    monkeypatch.setattr("requests.get", mock_requests_get)
    monkeypatch.setattr("requests.post", mock_requests_post)
    
    yield {
        "request": mock_requests_request,
        "get": mock_requests_get,
        "post": mock_requests_post,
    }


@pytest.fixture(autouse=True)
def mock_llm_client_firewall(monkeypatch):
    """Automatically mock LLM client chat function for all unit tests.
    
    Patches src.shared.llm_client.chat at the source.
    Tests can override behavior using side_effect or return_value.
    """
    # Default mock response
    default_response = (
        {
            "choices": [{
                "message": {
                    "content": json.dumps({"triples": [], "entities": []})
                }
            }]
        },
        {
            "duration_ms": 100,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "expert_name": "Worker",
            "model_id": "test-model",
            "url_base": "http://mock-llm:8000",
            "path": "primary",
            "attempt": 1,
        }
    )
    
    # Create a MagicMock that can be configured
    mock_chat = MagicMock(return_value=default_response)
    
    # Patch at the source
    monkeypatch.setattr("src.shared.llm_client.chat", mock_chat)
    
    yield mock_chat


@pytest.fixture
def mock_llm_client(mock_llm_client_firewall):
    """Expose the LLM client mock for test configuration.
    
    This fixture provides access to the mocked chat function so tests can
    configure its return value or side_effect.
    """
    return mock_llm_client_firewall


@pytest.fixture(autouse=True)
def mock_filesystem_firewall(monkeypatch):
    """Automatically mock filesystem operations for all unit tests.
    
    Patches pathlib.Path.mkdir, pathlib.Path.open, and builtins.open to prevent actual file I/O.
    Tests that need file operations can override these mocks.
    """
    # Mock Path.mkdir
    original_mkdir = None
    original_path_open = None
    try:
        from pathlib import Path
        original_mkdir = Path.mkdir
        original_path_open = Path.open
    except ImportError:
        pass
    
    def mock_mkdir(self, *args, **kwargs):
        """Mock Path.mkdir to prevent actual directory creation.
        
        Allows directory creation in pytest-managed temp directories (tmp_path fixture).
        """
        # Allow directory creation in pytest temp dirs
        path_str = str(self)
        if "pytest" in path_str or "/tmp/pytest" in path_str or "/tmp/pytest-of" in path_str:
            # Use original mkdir for pytest temp dirs
            if original_mkdir:
                return original_mkdir(self, *args, **kwargs)
        return None
    
    def create_mock_file(**kwargs):
        """Create a mock file object with len() support and context manager protocol.
        
        Supports file-like operations needed for uploads and reads.
        """
        # Determine if binary mode
        mode = kwargs.get("mode", "rb")
        is_binary = "b" in mode
        
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.write = Mock()
        
        # Set read values based on mode
        if is_binary:
            read_value = kwargs.get("read_value", kwargs.get("content", b"%PDF-1.4 fake pdf content"))
            mock_file.read = Mock(return_value=read_value)
            mock_file.read_bytes = Mock(return_value=read_value)
        else:
            read_value = kwargs.get("read_value", kwargs.get("content", ""))
            mock_file.read = Mock(return_value=read_value)
            mock_file.read_bytes = Mock(return_value=read_value.encode() if isinstance(read_value, str) else b"")
        
        mock_file.readlines = Mock(return_value=kwargs.get("readlines_value", []))
        mock_file.write_bytes = Mock()
        
        # Support len() for file size checks
        content = kwargs.get("content", read_value)
        size = len(content) if content else kwargs.get("size", 1024)
        mock_file.__len__ = Mock(return_value=size)
        
        # Support iteration (for file-like objects)
        mock_file.__iter__ = Mock(return_value=iter([content] if content else []))
        
        # Support file-like attributes for Flask uploads
        mock_file.name = kwargs.get("name", "/tmp/test.pdf")
        mock_file.fileno = Mock(return_value=1)
        mock_file.seek = Mock(return_value=0)
        mock_file.tell = Mock(return_value=0)
        
        return mock_file
    
    def mock_path_open(self, *args, **kwargs):
        """Mock Path.open to prevent actual file I/O.
        
        Allows writes to pytest-managed temp directories (tmp_path fixture).
        """
        # Allow writes to pytest temp dirs
        path_str = str(self)
        if "pytest" in path_str or "/tmp/pytest" in path_str or "/tmp/pytest-of" in path_str:
            # Use original open for pytest temp dirs
            if original_path_open:
                return original_path_open(self, *args, **kwargs)
        return create_mock_file()
    
    # Mock builtins.open
    original_builtins_open = None
    try:
        import builtins
        original_builtins_open = builtins.open
    except ImportError:
        pass
    
    def mock_open(*args, **kwargs):
        """Mock builtins.open to prevent actual file I/O.
        
        If a file path is provided, attempts to read mock content.
        For test code that creates files with tempfile, this will return a mock file object.
        Allows writes to pytest-managed temp directories (tmp_path fixture).
        """
        # Allow writes to pytest temp dirs
        if args:
            file_path = args[0]
            path_str = str(file_path)
            if "pytest" in path_str or "/tmp/pytest" in path_str or "/tmp/pytest-of" in path_str:
                # Use original open for pytest temp dirs
                if original_builtins_open:
                    return original_builtins_open(*args, **kwargs)
        
        # Determine if binary mode
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        is_binary = "b" in mode
        
        # Try to get file path if provided
        file_path = args[0] if args else kwargs.get("file", "")
        file_name = str(file_path) if file_path else "/tmp/test.pdf"
        
        # For test files, provide reasonable mock content
        if is_binary:
            # Default PDF-like content for binary files
            content = b"%PDF-1.4 fake pdf content"
            return create_mock_file(mode=mode, content=content, name=file_name, size=len(content))
        else:
            content = "# Test Markdown\nSample content"
            return create_mock_file(mode=mode, content=content, name=file_name, size=len(content))
    
    # Mock Path.read_text to prevent YAML parsing of dummy PDF content
    def mock_path_read_text(self, encoding="utf-8", errors=None):
        """Mock Path.read_text to return safe YAML content instead of dummy PDF."""
        # If this looks like a config file path, return valid YAML
        path_str = str(self)
        if "rigor_policy" in path_str or "neutral_tone" in path_str:
            # Return valid YAML config
            return "rigor_level: exploratory\nmax_decimals_default: 3\npolicies:\n  default:\n    density: 0.5\n    depth: 1\n"
        # Otherwise return empty string (file doesn't exist)
        return ""
    
    original_read_text = None
    try:
        from pathlib import Path
        original_read_text = Path.read_text
    except ImportError:
        pass
    
    # Patch at the source
    if original_mkdir:
        monkeypatch.setattr("pathlib.Path.mkdir", mock_mkdir)
    if original_path_open:
        monkeypatch.setattr("pathlib.Path.open", mock_path_open)
    if original_read_text:
        monkeypatch.setattr("pathlib.Path.read_text", mock_path_read_text)
    monkeypatch.setattr("builtins.open", mock_open)
    
    yield {
        "mkdir": mock_mkdir,
        "path_open": mock_path_open,
        "read_text": mock_path_read_text,
        "open": mock_open,
    }


@pytest.fixture(autouse=True)
def mock_role_registry_firewall(monkeypatch):
    """Automatically mock RoleRegistry for all unit tests.
    
    RoleRegistry is instantiated at module level in nodes.py and tone_guard.py,
    which causes it to try to connect to ArangoDB during import. This firewall
    prevents those connections by:
    1. Patching RoleRegistry methods to prevent DB connections
    2. Patching module-level role_registry instances if they already exist
    """
    from src.shared.schema import RoleProfile
    
    # Create a mock RoleProfile with default role configuration
    default_role = RoleProfile(
        name="The Cartographer",
        description="Extracts structured entities and relations from text",
        system_prompt="You are a knowledge graph extractor. Extract triples in JSON format.",
        version=1,
        allowed_tools=[],
        focus_entities=[],
        is_enabled=True
    )
    
    # Also create a Brain role for tone_guard tests
    brain_role = RoleProfile(
        name="The Brain",
        description="High-level reasoning and JSON planning",
        system_prompt="You are a reasoning assistant. Rewrite text for neutral tone while preserving citations.",
        version=1,
        allowed_tools=[],
        focus_entities=[],
        is_enabled=True
    )
    
    # Patch _init_arangodb to be a no-op (prevents DB connection during __init__)
    # This is called by RoleRegistry.__init__, so patching it prevents connections
    def mock_init_arangodb(self):
        """No-op that prevents ArangoDB connection."""
        self.db = None
        # Don't try to connect - just set db to None
    
    # Patch get_role to return default role without DB lookup
    def mock_get_role(self, name: str, version=None):
        """Return default role without DB lookup."""
        # Return appropriate role based on name
        if name == "The Brain":
            return brain_role
        return default_role
    
    # Patch both methods to prevent DB connections
    # IMPORTANT: Patch _init_arangodb first, as it's called during __init__
    monkeypatch.setattr(
        "src.shared.role_manager.RoleRegistry._init_arangodb",
        mock_init_arangodb
    )
    monkeypatch.setattr(
        "src.shared.role_manager.RoleRegistry.get_role",
        mock_get_role
    )
    
    # Also patch module-level role_registry instances if they already exist
    # This handles cases where modules were imported before the fixture ran
    import sys
    modules_to_patch = [
        "src.orchestrator.nodes.nodes",
        "src.orchestrator.tone_guard",
        "src.orchestrator.nodes.tone_guard",
    ]
    for module_name in modules_to_patch:
        if module_name in sys.modules:
            try:
                module = sys.modules[module_name]
                if hasattr(module, "role_registry"):
                    # Patch the instance's methods directly
                    module.role_registry._init_arangodb = lambda self: setattr(self, 'db', None)
                    module.role_registry.get_role = lambda self, name, version=None: (brain_role if name == "The Brain" else default_role)
                    module.role_registry.db = None  # Ensure db is None
            except Exception:
                pass  # If patching fails, the class-level patches should still work
    
    yield default_role


@pytest.fixture(autouse=True)
def mock_project_context_firewall(monkeypatch):
    """Automatically mock ProjectService for all unit tests.
    
    Patches _get_project_service (for nodes) and get_project_service (for server)
    to return a mock ProjectService with valid project configuration.
    """
    # Create a mock ProjectConfig with all required fields
    mock_project_config = Mock()
    mock_project_config.model_dump.return_value = {
        "id": "p1",
        "name": "Test Project",
        "title": "Test Project",
        "thesis": "Test thesis statement",
        "research_questions": ["RQ1: What is the research question?"],
        "anti_scope": [],
        "target_journal": "Test Journal",
        "seed_files": [],
        "created_at": datetime.utcnow().isoformat(),
        "extract_config": {
            "enabled": True,
            "confidence_threshold": 0.7,
        },
        "rigor_level": "exploratory",
    }
    
    # Create a mock ProjectService
    mock_service = Mock()
    mock_service.get_project.return_value = mock_project_config
    mock_service.add_seed_file = Mock()
    
    # Patch at the source - both for nodes and server
    # IMPORTANT: We patch the function itself, which should prevent any real connections.
    # However, we also need to ensure that if the module is already loaded, the global
    # _project_service variable is set to prevent lazy initialization attempts.
    monkeypatch.setattr(
        "src.orchestrator.nodes.nodes._get_project_service",
        lambda: mock_service
    )
    # Also patch server.get_project_service to prevent DB connections in API endpoints
    monkeypatch.setattr(
        "src.orchestrator.server.get_project_service",
        lambda: mock_service
    )
    # Pre-emptively set the global _project_service if the module is already loaded
    # This prevents _get_project_service() from trying to create a real ArangoClient
    # if it's called before our patch is fully applied
    import sys
    if "src.orchestrator.nodes.nodes" in sys.modules:
        try:
            nodes_module = sys.modules["src.orchestrator.nodes.nodes"]
            # Set the global variable directly to prevent lazy initialization
            setattr(nodes_module, "_project_service", mock_service)
        except Exception:
            # If setting fails, the function patch should still work
            pass
    
    yield mock_service


@pytest.fixture(autouse=True)
def mock_network_config_firewall(monkeypatch):
    """Automatically mock network configuration for all unit tests.
    
    Patches config functions to return localhost instead of container names.
    This prevents DNS resolution errors.
    """
    # Patch config getters to return localhost
    monkeypatch.setattr("src.shared.config.get_arango_url", lambda: "http://localhost:8529")
    monkeypatch.setattr("src.shared.config.get_memory_url", lambda: "http://localhost:8529")
    
    # Patch constants directly
    monkeypatch.setattr("src.shared.config.MEMORY_URL", "http://localhost:8529")
    monkeypatch.setattr("src.shared.config.ARANGODB_URL", "http://localhost:8529")
    
    # Suppress urllib3 retry warnings
    try:
        import urllib3
        original_HTTPConnectionPool = urllib3.connectionpool.HTTPConnectionPool
        def mock_HTTPConnectionPool(*args, **kwargs):
            """Mock HTTPConnectionPool to prevent real connections."""
            pool = Mock(spec=original_HTTPConnectionPool)
            pool.urlopen = Mock(side_effect=Exception("Mocked connection - no real network calls"))
            return pool
        monkeypatch.setattr("urllib3.connectionpool.HTTPConnectionPool", mock_HTTPConnectionPool)
    except ImportError:
        pass  # urllib3 might not be available
    
    yield


@pytest.fixture(autouse=True)
def mock_rigor_config_firewall(monkeypatch):
    """Automatically mock rigor policy YAML loading for all unit tests.
    
    Prevents YAML parsing errors when dummy PDF content accidentally
    gets passed to the YAML parser. Returns a safe default config dictionary.
    """
    def mock_load_rigor_policy_yaml(path=None):
        """Return safe default rigor policy config."""
        return {
            "rigor_level": "exploratory",
            "max_decimals_default": 3,
            "policies": {
                "default": {
                    "density": 0.5,
                    "depth": 1
                }
            }
        }
    
    def mock_load_neutral_tone_yaml(path=None):
        """Return safe default neutral tone config."""
        return {
            "hard_ban": [],
            "soft_ban": [],
            "suggestions": {}
        }
    
    # Patch at the source - both functions that load YAML
    monkeypatch.setattr("src.shared.rigor_config.load_rigor_policy_yaml", mock_load_rigor_policy_yaml)
    monkeypatch.setattr("src.shared.rigor_config.load_neutral_tone_yaml", mock_load_neutral_tone_yaml)
    
    yield {
        "rigor_policy": mock_load_rigor_policy_yaml,
        "neutral_tone": mock_load_neutral_tone_yaml,
    }


@pytest.fixture(autouse=True)
def mock_joblib_cache_firewall(monkeypatch):
    """Automatically mock joblib.Memory to prevent cache lock file conflicts.
    
    Disables joblib caching during tests to prevent multiple tests from
    fighting over the same cache directory and lock files.
    """
    def create_noop_memory(*args, **kwargs):
        """Create a mock Memory object that does nothing (no caching).
        
        Returns a mock that supports the .cache() decorator pattern
        but doesn't actually cache anything or create lock files.
        """
        mock_memory = MagicMock()
        
        # Make .cache() return a decorator that returns the function unchanged
        def noop_cache(func=None, *cache_args, **cache_kwargs):
            """No-op cache decorator that returns the function unchanged."""
            if func is None:
                # Called as @memory.cache()
                return lambda f: f
            # Called as @memory.cache(func)
            return func
        
        mock_memory.cache = noop_cache
        # Support other common Memory attributes
        mock_memory.clear = Mock()
        mock_memory.clear_warn = Mock()
        mock_memory.reduce_size = Mock()
        
        return mock_memory
    
    # Patch at the source
    try:
        import joblib
        monkeypatch.setattr("joblib.Memory", create_noop_memory)
    except ImportError:
        pass  # joblib might not be installed
    
    yield create_noop_memory


@pytest.fixture(autouse=True)
def mock_importlib_metadata_version(monkeypatch):
    """Automatically mock importlib.metadata.version for all unit tests.
    
    Prevents TypeError when werkzeug or other packages call version()
    during test_client() initialization. Ensures version() always returns
    a string, not bytes.
    """
    def mock_version(package_name: str) -> str:
        """Return a valid version string for any package.
        
        This mock handles all package names and always returns a string,
        preventing TypeError when werkzeug or Flask call version() during
        test_client() initialization.
        """
        # Return a standard version string format
        return "3.0.0"
    
    # Patch at the source - both importlib.metadata and importlib_metadata (backport)
    # We patch the version function directly to ensure it's always a string
    try:
        import importlib.metadata
        # Patch the version function
        monkeypatch.setattr(importlib.metadata, "version", mock_version)
        # Also patch via string path for modules that import it differently
        monkeypatch.setattr("importlib.metadata.version", mock_version)
    except (ImportError, AttributeError):
        pass
    
    try:
        import importlib_metadata
        monkeypatch.setattr(importlib_metadata, "version", mock_version)
        monkeypatch.setattr("importlib_metadata.version", mock_version)
    except ImportError:
        pass  # importlib_metadata might not be installed
    
    yield mock_version

