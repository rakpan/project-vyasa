# Testing Guide

Single reference for how to run tests and how to mock in Vyasa. Runbooks stay procedural; testing philosophy lives here.

## How to Run Tests
- **Unit (default):** fast, no I/O. `./scripts/run_tests.sh --unit` (or just `./scripts/run_tests.sh`). Equivalent: `pytest -v -m "not integration" src/tests/unit/`.
- **Integration:** real services (Arango, Cortex, etc.) must be up. `./scripts/run_tests.sh --integration` → `pytest -v -s -m "integration" src/tests/integration/`.
- **All:** run unit then integration. `./scripts/run_tests.sh --all`.
- **Markers/skip:** mark integration tests with `@pytest.mark.integration`; unit tests should never hit network/DB/files.
- **Paths:** unit tests live in `src/tests/unit/` (including `orchestrator/` subfolder); integration tests in `src/tests/integration/`.

## How to Mock (Principles + Examples)
- **Golden Rule:** Mock the library/source, not our modules. `monkeypatch.setattr("arango.ArangoClient", ...)`, never `src.orchestrator.nodes.ArangoClient`.
- **Trust the Firewall:** Autouse fixtures in `src/tests/unit/conftest.py` already mock:
  - `arango.ArangoClient` (`mock_arango_firewall`)
  - `requests.get/post` (`mock_requests_firewall`)
  - `src.shared.llm_client.chat` (`mock_llm_client_firewall`)
  - Filesystem (`mock_filesystem_firewall`)
  - Project context (`mock_project_context_firewall`)
  - Localhost config (`mock_network_config_firewall`)
  Customize by injecting the fixture (e.g., `mock_llm_client.return_value = (...)`), not by adding new patches.
- **Use state fixtures:** start from `base_node_state` (in `src/tests/conftest.py`) instead of hand-building dicts.
- **Acceptable patches:** internal pure logic is fine to patch when you’re testing that logic (e.g., routing helpers). I/O wrappers should be covered by firewall mocks.
- **Examples:**
  - ✅ Custom LLM response:
    ```python
    def test_synthesis(mock_llm_client, base_node_state):
        mock_llm_client.return_value = ({"choices":[{"message":{"content":"ok"}}]}, {"duration_ms":50})
        result = synthesizer_node(base_node_state)
        assert "synthesis" in result
    ```
  - ✅ Mock Arango at source:
    ```python
    def test_job_lookup(monkeypatch):
        def fake_client(hosts):
            db = Mock(); coll = Mock()
            coll.get.return_value = {"job_id": "j1"}
            db.collection.return_value = coll
            client = Mock(); client.db.return_value = db
            return client
        monkeypatch.setattr("arango.ArangoClient", fake_client)
        # call code under test...
    ```
  - ❌ Don’t patch `src.orchestrator.*.ArangoClient` or re-mock `requests` in unit tests—the firewall already did it.

References: `scripts/run_tests.sh`, `src/tests/unit/conftest.py`, `src/tests/integration/conftest.py`, `src/tests/conftest.py`.
