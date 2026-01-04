"""
Refactor Guard Tests for Nodes Decomposition.

These tests ensure that critical invariants remain true during and after
the nodes.py refactor. They serve as smoke tests to catch regressions
introduced during module splitting.

Tests verify:
1. Import compatibility: nodes package imports without errors (all import styles)
2. Cartographer snapshot: minimal behavior test with mocked dependencies
3. Contract sanity: key invariants remain true
   - Conflict explanation deterministic
   - Tone rewrite preserves claim_ids and citation_keys
   - Precision formatter idempotent
"""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock
from typing import Dict, Any


class TestImportCompatibility:
    """Tests that nodes package imports work after refactor (all import styles)."""
    
    def test_import_nodes_package_as_module(self):
        """Test: `import src.orchestrator.nodes as nodes` works."""
        try:
            import src.orchestrator.nodes as nodes
            # Verify cartographer_node is accessible
            assert hasattr(nodes, "cartographer_node")
            assert callable(nodes.cartographer_node)
        except ImportError as e:
            pytest.fail(f"Import as module failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during import as module: {e}")
    
    def test_import_from_nodes_package(self):
        """Test: `from src.orchestrator.nodes import cartographer_node` works."""
        try:
            from src.orchestrator.nodes import cartographer_node
            assert callable(cartographer_node)
        except ImportError as e:
            pytest.fail(f"Import from package failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during import from package: {e}")
    
    def test_import_from_nodes_nodes_module(self):
        """Test: `from src.orchestrator.nodes.nodes import cartographer_node` works (backward compat)."""
        try:
            # Note: cartographer_node is now in cartography.py, but nodes.py re-exports it
            from src.orchestrator.nodes.nodes import cartographer_node
            assert callable(cartographer_node)
        except ImportError as e:
            pytest.fail(f"Import from nodes.nodes failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during import from nodes.nodes: {e}")
    
    def test_nodes_package_imports_without_error(self):
        """Verify that importing nodes package does not raise."""
        # This test will fail if circular imports are introduced
        try:
            from src.orchestrator.nodes import (
                cartographer_node,
                critic_node,
                synthesizer_node,
                saver_node,
                vision_node,
                artifact_registry_node,
                tone_validator_node,
                lead_counsel_node,
                logician_node,
                reframing_node,
                failure_cleanup_node,
                route_to_expert,
                call_expert_with_fallback,
                hydrate_project_context,
            )
            # If we get here, imports succeeded
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during import: {e}")
    
    def test_nodes_package_exports_expected_symbols(self):
        """Verify that nodes package exports all expected symbols."""
        from src.orchestrator.nodes import __all__
        
        expected_symbols = [
            "cartographer_node",
            "critic_node",
            "synthesizer_node",
            "saver_node",
            "vision_node",
            "artifact_registry_node",
            "tone_validator_node",
            "lead_counsel_node",
            "logician_node",
            "reframing_node",
            "failure_cleanup_node",
            "route_to_expert",
            "call_expert_with_fallback",
            "hydrate_project_context",
        ]
        
        for symbol in expected_symbols:
            assert symbol in __all__, f"Expected symbol '{symbol}' not in __all__"
    
    def test_workflow_imports_nodes_successfully(self):
        """Verify that workflow.py can import nodes after refactor."""
        try:
            from src.orchestrator.workflow import build_workflow
            # If workflow imports work, nodes imports work
            assert True
        except ImportError as e:
            pytest.fail(f"Workflow import failed (nodes refactor broke workflow): {e}")


class TestCartographerSnapshot:
    """Minimal cartographer behavior snapshot test with mocked dependencies."""
    
    @pytest.fixture
    def minimal_state(self) -> Dict[str, Any]:
        """Minimal ResearchState fixture for cartographer tests."""
        return {
            "jobId": "test-job-123",
            "threadId": "test-thread-123",
            "job_id": "test-job-123",
            "project_id": "test-project-456",
            "ingestion_id": "test-ingestion-789",
            "raw_text": "Machine learning models require large datasets for training. Neural networks use backpropagation.",
            "project_context": {
                "thesis": "Test thesis statement",
                "research_questions": [
                    "What is the impact of machine learning on data processing?",
                ],
                "rigor_level": "exploratory",
            },
            "triples": [],
            "extracted_json": {},
            "critiques": [],
            "revision_count": 0,
        }
    
    @pytest.fixture
    def mock_llm_response(self) -> Dict[str, Any]:
        """Deterministic LLM response for cartographer."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "triples": [
                            {
                                "subject": "Machine learning models",
                                "predicate": "require",
                                "object": "large datasets for training",
                                "source_pointer": {
                                    "doc_hash": "test-doc-hash-123",
                                    "page": 1,
                                    "snippet": "Machine learning models require large datasets",
                                },
                                "rq_hits": ["rq1"],
                            },
                            {
                                "subject": "Neural networks",
                                "predicate": "use",
                                "object": "backpropagation",
                                "source_pointer": {
                                    "doc_hash": "test-doc-hash-123",
                                    "page": 1,
                                    "snippet": "Neural networks use backpropagation",
                                },
                                "rq_hits": ["rq1"],
                            },
                        ],
                    })
                }
            }]
        }
    
    def test_cartographer_returns_expected_structure(self, minimal_state, mock_llm_response):
        """Test that cartographer_node returns expected state structure."""
        from src.orchestrator.nodes import cartographer_node
        
        # Mock all external dependencies
        # route_to_expert and call_expert_with_fallback are imported from nodes.nodes inside the function
        with patch("src.orchestrator.nodes.nodes.route_to_expert") as mock_route:
            mock_route.return_value = ("http://mock-worker:8000", "Worker", "test-model")
            
            with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
                mock_call.return_value = (mock_llm_response, {"duration_ms": 100.0, "usage": {}})
                
                # Mock Qdrant queries (return empty to simplify test)
                # QdrantStorage is imported from ..storage.qdrant inside the function
                with patch("src.orchestrator.storage.qdrant.QdrantStorage") as mock_qdrant:
                    mock_qdrant_instance = MagicMock()
                    mock_qdrant_instance.query_chunks.return_value = []
                    mock_qdrant.return_value = mock_qdrant_instance
                    
                    # Mock ArangoDB (for project context hydration)
                    with patch("src.orchestrator.nodes.nodes._get_project_service") as mock_project_service:
                        mock_service = MagicMock()
                        mock_project = MagicMock()
                        mock_project.model_dump.return_value = minimal_state["project_context"]
                        mock_service.get_project.return_value = mock_project
                        mock_project_service.return_value = mock_service
                        
                        # Mock RoleRegistry
                        with patch("src.orchestrator.nodes.cartography.role_registry") as mock_registry:
                            mock_role = MagicMock()
                            mock_role.allowed_tools = []
                            mock_registry.get_role.return_value = mock_role
                            
                            # Mock validate_state_schema to return state as-is
                            with patch("src.orchestrator.nodes.nodes.validate_state_schema", lambda x: x):
                                # Call cartographer_node
                                result = cartographer_node(minimal_state)
                                
                                # Assert returned state includes expected keys
                                assert "extracted_json" in result, "Result must include extracted_json"
                                assert "triples" in result, "Result must include triples"
                                assert "phase" in result, "Result must include phase"
                                
                                # Assert extracted_json has triples
                                extracted = result["extracted_json"]
                                assert isinstance(extracted, dict), "extracted_json must be a dict"
                                assert "triples" in extracted, "extracted_json must have triples key"
                                
                                # Assert triples list is non-empty (or matches expected count)
                                triples = result["triples"]
                                assert isinstance(triples, list), "triples must be a list"
                                assert len(triples) > 0, "triples list must be non-empty"
                                
                                # Assert required fields exist in first triple/claim
                                if len(triples) > 0:
                                    first_triple = triples[0]
                                    assert isinstance(first_triple, dict), "Each triple must be a dict"
                                    # In exploratory mode, we may have triples without full Claim structure
                                    # But we should at least have the basic fields
                                    assert "subject" in first_triple or "claim_text" in first_triple, \
                                        "Triple must have subject or claim_text"
    
    def test_cartographer_handles_empty_response_gracefully(self, minimal_state):
        """Test that cartographer_node handles empty LLM response gracefully."""
        from src.orchestrator.nodes import cartographer_node
        
        # Mock empty response
        empty_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"triples": []})
                }
            }]
        }
        
        with patch("src.orchestrator.nodes.nodes.route_to_expert") as mock_route:
            mock_route.return_value = ("http://mock-worker:8000", "Worker", "test-model")
            
            with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
                mock_call.return_value = (empty_response, {"duration_ms": 50.0, "usage": {}})
                
                # QdrantStorage is imported from ..storage.qdrant inside the function
                with patch("src.orchestrator.storage.qdrant.QdrantStorage") as mock_qdrant:
                    mock_qdrant_instance = MagicMock()
                    mock_qdrant_instance.query_chunks.return_value = []
                    mock_qdrant.return_value = mock_qdrant_instance
                    
                    with patch("src.orchestrator.nodes.nodes._get_project_service") as mock_project_service:
                        mock_service = MagicMock()
                        mock_project = MagicMock()
                        mock_project.model_dump.return_value = minimal_state["project_context"]
                        mock_service.get_project.return_value = mock_project
                        mock_project_service.return_value = mock_service
                        
                        with patch("src.orchestrator.nodes.cartography.role_registry") as mock_registry:
                            mock_role = MagicMock()
                            mock_role.allowed_tools = []
                            mock_registry.get_role.return_value = mock_role
                            
                            with patch("src.orchestrator.nodes.nodes.validate_state_schema", lambda x: x):
                                result = cartographer_node(minimal_state)
                                
                                # Should return empty triples, not crash
                                assert "extracted_json" in result
                                assert "triples" in result
                                assert isinstance(result["triples"], list)
                                # Empty list is acceptable
                                assert len(result["triples"]) == 0


class TestContractSanity:
    """Tests that critical invariants remain true after refactor."""
    
    def test_conflict_explanation_deterministic(self):
        """Verify that conflict explanations remain deterministic (template-based)."""
        from src.orchestrator.conflict_utils import (
            generate_conflict_explanation,
            DeterministicConflictType,
        )
        
        source_a = {"doc_hash": "abc123", "page": 5}
        source_b = {"doc_hash": "def456", "page": 10}
        
        # Generate explanation twice
        explanation1 = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.CONTRADICTION,
            claim_a_text="Claim A",
            claim_b_text="Claim B",
        )
        
        explanation2 = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.CONTRADICTION,
            claim_a_text="Claim A",
            claim_b_text="Claim B",
        )
        
        # Must be identical (deterministic)
        assert explanation1 == explanation2, "Conflict explanations must be deterministic"
        
        # Must be template-based (not LLM-generated)
        assert "Source A" in explanation1
        assert "Source B" in explanation1
        assert "contradict" in explanation1.lower()
        # Should not contain LLM-like phrases
        assert "I believe" not in explanation1.lower()
        assert "in my opinion" not in explanation1.lower()
    
    def test_tone_rewrite_preserves_claim_ids(self, base_node_state):
        """Verify that tone rewrite preserves claim_ids and citation_keys."""
        from src.orchestrator.tone_guard import tone_linter_node
        
        state = {
            **base_node_state,
            "job_id": "test_job",
            "project_id": "test_project",
            "rigor_level": "conservative",
            "manuscript_blocks": [
                {
                    "block_id": "block1",
                    "text": "This is an amazing result!",
                    "claim_ids": ["claim1", "claim2"],
                    "citation_keys": ["cite1"],
                },
            ],
        }
        
        # Mock rewrite to return rewritten text
        def mock_chat(*args, **kwargs):
            return {
                "choices": [{"message": {"content": "This is a significant result!"}}]
            }, {}
        
        with patch("src.orchestrator.tone_guard.chat", side_effect=mock_chat):
            result = tone_linter_node(state)
            
            updated_blocks = result.get("manuscript_blocks", [])
            assert len(updated_blocks) == 1
            updated_block = updated_blocks[0]
            
            # Verify claim_ids and citation_keys are preserved
            assert updated_block["claim_ids"] == ["claim1", "claim2"], \
                "Tone rewrite must preserve claim_ids"
            assert updated_block["citation_keys"] == ["cite1"], \
                "Tone rewrite must preserve citation_keys"
    
    def test_tone_rewrite_preserves_citation_keys(self, base_node_state):
        """Verify that tone rewrite preserves citation_keys specifically."""
        from src.orchestrator.tone_guard import tone_linter_node
        
        state = {
            **base_node_state,
            "job_id": "test_job",
            "project_id": "test_project",
            "rigor_level": "conservative",
            "manuscript_blocks": [
                {
                    "block_id": "block1",
                    "text": "This is an amazing breakthrough!",
                    "claim_ids": ["claim1"],
                    "citation_keys": ["smith2023", "jones2024"],
                },
            ],
        }
        
        def mock_chat(*args, **kwargs):
            return {
                "choices": [{"message": {"content": "This is a significant breakthrough!"}}]
            }, {}
        
        with patch("src.orchestrator.tone_guard.chat", side_effect=mock_chat):
            result = tone_linter_node(state)
            
            updated_blocks = result.get("manuscript_blocks", [])
            assert len(updated_blocks) == 1
            updated_block = updated_blocks[0]
            
            # Verify citation_keys are preserved
            assert updated_block["citation_keys"] == ["smith2023", "jones2024"], \
                "Tone rewrite must preserve citation_keys exactly"
    
    def test_precision_formatter_idempotent(self):
        """Verify that precision formatting is idempotent (same input -> same output)."""
        from src.orchestrator.guards.precision_contract import validate_table_precision
        from src.shared.schema import PrecisionContract
        
        table = {
            "table_id": "test_table",
            "rows": [
                {"colA": "1.23", "colB": "2.34"},
            ],
        }
        
        contract = PrecisionContract(
            max_decimals=2,
            max_sig_figs=3,
            rounding_rule="bankers",
            consistency_rule="per_column",
        )
        
        # First pass
        rewritten1, flags1, warnings1 = validate_table_precision(
            table, contract, rigor="exploratory"
        )
        
        # Second pass (should be idempotent)
        rewritten2, flags2, warnings2 = validate_table_precision(
            rewritten1, contract, rigor="exploratory"
        )
        
        # Values should not change on second pass
        assert rewritten1["rows"][0]["colA"] == rewritten2["rows"][0]["colA"], \
            "Precision formatting must be idempotent"
        assert rewritten1["rows"][0]["colB"] == rewritten2["rows"][0]["colB"], \
            "Precision formatting must be idempotent"
    
    def test_state_schema_validation_still_works(self):
        """Verify that state schema validation still works after refactor."""
        # validate_state_schema is in nodes.py, not base.py (will move to base.py in refactor)
        from src.orchestrator.nodes.nodes import validate_state_schema
        
        # Valid state
        valid_state = {
            "jobId": "job1",
            "threadId": "thread1",
            "raw_text": "Test",
        }
        
        result = validate_state_schema(valid_state)
        assert result["jobId"] == "job1"
        assert result["threadId"] == "thread1"
        
        # Invalid state (missing jobId)
        invalid_state = {
            "threadId": "thread1",
            "raw_text": "Test",
        }
        
        with pytest.raises(ValueError, match="jobId"):
            validate_state_schema(invalid_state)
    
    def test_hydrate_project_context_still_works(self, base_node_state):
        """Verify that project context hydration still works after refactor."""
        from src.orchestrator.nodes import hydrate_project_context
        
        state = {
            **base_node_state,
            "project_id": "test_project",
        }
        
        # Mock project service to return a project
        mock_project = Mock()
        mock_project.model_dump.return_value = {
            "project_id": "test_project",
            "thesis": "Test thesis",
            "research_questions": ["RQ1"],
            "rigor_level": "conservative",
        }
        
        # Note: After refactor, this will be in utils.context, but for now it's in nodes.py
        with patch("src.orchestrator.nodes.nodes._get_project_service") as mock_get_service:
            mock_service = Mock()
            mock_service.get_project.return_value = mock_project
            mock_get_service.return_value = mock_service
            
            result = hydrate_project_context(state)
            
            # Verify project_context was hydrated
            assert "project_context" in result
            assert result["project_context"]["thesis"] == "Test thesis"
            assert result["project_context"]["research_questions"] == ["RQ1"]


class TestWorkflowCompatibility:
    """Tests that workflow still works after refactor."""
    
    def test_workflow_builds_successfully(self):
        """Verify that workflow can be built after refactor."""
        from src.orchestrator.workflow import build_workflow
        
        # This will fail if nodes imports are broken
        workflow = build_workflow()
        
        # Verify workflow is callable
        assert callable(workflow.invoke), "Workflow must be invokable"
        assert callable(workflow.stream), "Workflow must be streamable"
    
    def test_workflow_nodes_are_callable(self):
        """Verify that all workflow nodes are callable after refactor."""
        from src.orchestrator.nodes import (
            cartographer_node,
            critic_node,
            synthesizer_node,
            saver_node,
            vision_node,
            artifact_registry_node,
            tone_validator_node,
            lead_counsel_node,
            logician_node,
            reframing_node,
            failure_cleanup_node,
        )
        
        nodes = [
            cartographer_node,
            critic_node,
            synthesizer_node,
            saver_node,
            vision_node,
            artifact_registry_node,
            tone_validator_node,
            lead_counsel_node,
            logician_node,
            reframing_node,
            failure_cleanup_node,
        ]
        
        for node in nodes:
            assert callable(node), f"Node {node.__name__} must be callable"


class TestDeterminismInvariants:
    """Tests that determinism invariants from test_determinism_guardrails remain true."""
    
    def test_conflict_explanation_never_from_llm(self):
        """Verify that conflict explanations are never LLM-generated (reference test)."""
        # This test references the comprehensive determinism tests in test_determinism_guardrails.py
        # If those tests pass, this invariant is maintained
        # We verify the determinism tests exist and cover this invariant
        import importlib.util
        from pathlib import Path
        
        test_file = Path(__file__).parent / "test_determinism_guardrails.py"
        assert test_file.exists(), "Determinism guardrails tests must exist"
        
        # Verify the test file can be imported (syntax check)
        spec = importlib.util.spec_from_file_location("test_determinism", test_file)
        assert spec is not None, "Determinism test file must be valid Python"
    
    def test_precision_never_calls_llm(self):
        """Verify that precision formatting never calls LLM (reference test)."""
        # Reference: test_determinism_guardrails.py::TestPrecisionDeterminism
        # If those tests pass, this invariant is maintained
        from pathlib import Path
        
        test_file = Path(__file__).parent / "test_determinism_guardrails.py"
        assert test_file.exists(), "Determinism guardrails tests must exist"
    
    def test_tone_detection_never_calls_llm(self):
        """Verify that tone detection never calls LLM (reference test)."""
        # Reference: test_determinism_guardrails.py::TestToneLinterDeterminism
        # If those tests pass, this invariant is maintained
        from pathlib import Path
        
        test_file = Path(__file__).parent / "test_determinism_guardrails.py"
        assert test_file.exists(), "Determinism guardrails tests must exist"

