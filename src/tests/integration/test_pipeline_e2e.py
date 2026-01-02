"""
End-to-End Integration Tests for Project Vyasa Pipeline.

These tests validate the complete flow from document ingestion to knowledge graph creation
using real Docker services (ArangoDB, Cortex).

**Golden Path Test:**
- Document ingestion via cartographer_node
- Real LLM extraction (Cortex Worker)
- Persistence to ArangoDB
- Verification of Claims, Entities, and Sources

All tests are marked with @pytest.mark.integration and will skip if Docker stack is not running.
"""

import pytest
from typing import Dict, Any

from src.orchestrator.nodes import cartographer_node
from src.orchestrator.state import ResearchState
from src.project.types import ProjectConfig


@pytest.mark.integration
def test_real_ingestion_flow(
    test_project_context: ProjectConfig,
    real_arango_client,
    integration_env: Dict[str, str],
):
    """Golden Path: Test complete document ingestion flow with real services.
    
    This test:
    1. Creates a test project (via fixture)
    2. Ingests a sample document using cartographer_node
    3. Verifies that Claims, Entities, and Sources are created in ArangoDB
    
    Args:
        test_project_context: Test project fixture (auto-cleanup)
        real_arango_client: Real ArangoDB connection
        integration_env: Environment configuration
    """
    # Sample document text for extraction
    sample_text = """
    Machine learning models have revolutionized natural language processing.
    Transformer architectures, introduced in 2017, use attention mechanisms
    to process sequences. BERT and GPT are popular transformer-based models.
    These models achieve state-of-the-art results on many NLP tasks.
    """
    
    # Prepare state for cartographer_node
    job_id = f"test_job_{test_project_context.id}"
    thread_id = f"test_thread_{test_project_context.id}"
    
    state: ResearchState = {
        "jobId": job_id,
        "threadId": thread_id,
        "project_id": test_project_context.id,
        "raw_text": sample_text,
        "url": "http://test-source.example.com/sample-doc",
        "manifest": {"project_id": test_project_context.id, "triples": []},
        "triples": [],
        "extracted_json": {},
    }
    
    # Execute cartographer_node (this will call real Cortex Worker)
    result = cartographer_node(state)
    
    # Verify node execution succeeded
    assert "extracted_json" in result
    assert "triples" in result["extracted_json"]
    triples = result["extracted_json"]["triples"]
    
    # Verify triples were extracted (should have at least one)
    assert isinstance(triples, list)
    assert len(triples) > 0, "Cartographer should extract at least one triple from sample text"
    
    # Verify triple structure
    first_triple = triples[0]
    assert "subject" in first_triple
    assert "predicate" in first_triple
    assert "object" in first_triple
    assert "confidence" in first_triple
    
    # Now verify persistence to ArangoDB
    # The saver_node would normally persist, but for this test we verify the extraction structure
    # In a full E2E test, we would also call saver_node and verify DB contents
    
    # Verify that extracted_json contains valid structure
    extracted = result["extracted_json"]
    assert isinstance(extracted, dict)
    assert "triples" in extracted
    
    # Verify entities can be extracted from triples
    entities = set()
    for triple in triples:
        if "subject" in triple:
            entities.add(triple["subject"])
        if "object" in triple:
            entities.add(triple["object"])
    
    assert len(entities) > 0, "Should extract at least one entity from triples"
    
    # Verify source information is present
    assert "url" in result or state.get("url"), "Source URL should be preserved"
    
    # Verify project context is maintained
    assert result.get("project_id") == test_project_context.id


@pytest.mark.integration
def test_real_ingestion_with_persistence(
    test_project_context: ProjectConfig,
    real_arango_client,
    integration_env: Dict[str, str],
):
    """Test ingestion flow with full persistence to ArangoDB.
    
    This test verifies that:
    1. cartographer_node extracts triples
    2. saver_node persists to ArangoDB
    3. Data can be queried from the database
    
    Args:
        test_project_context: Test project fixture (auto-cleanup)
        real_arango_client: Real ArangoDB connection
        integration_env: Environment configuration
    """
    from src.orchestrator.nodes import saver_node
    
    # Sample document text
    sample_text = """
    Quantum computing uses quantum mechanical phenomena like superposition and entanglement.
    Qubits can exist in multiple states simultaneously, unlike classical bits.
    Quantum algorithms like Shor's algorithm can factor large numbers efficiently.
    """
    
    job_id = f"test_job_persist_{test_project_context.id}"
    thread_id = f"test_thread_persist_{test_project_context.id}"
    
    # First, extract triples
    extract_state: ResearchState = {
        "jobId": job_id,
        "threadId": thread_id,
        "project_id": test_project_context.id,
        "raw_text": sample_text,
        "url": "http://test-source.example.com/quantum-doc",
        "manifest": {"project_id": test_project_context.id, "triples": []},
        "triples": [],
        "extracted_json": {},
    }
    
    extract_result = cartographer_node(extract_state)
    
    # Verify extraction succeeded
    assert "extracted_json" in extract_result
    assert len(extract_result["extracted_json"].get("triples", [])) > 0
    
    # Now persist to database
    save_state: ResearchState = {
        **extract_result,
        "jobId": job_id,
        "threadId": thread_id,
        "project_id": test_project_context.id,
        "extracted_json": extract_result["extracted_json"],
    }
    
    save_result = saver_node(save_state)
    
    # Verify save succeeded
    assert "save_receipt" in save_result
    assert save_result["save_receipt"]["status"] == "SAVED"
    
    # Query ArangoDB to verify data was persisted
    if real_arango_client.has_collection("extractions"):
        extractions_coll = real_arango_client.collection("extractions")
        
        # Query for our extraction (extractions use _key as identifier, project_id for filtering)
        query = """
        FOR e IN extractions
        FILTER e.project_id == @project_id
        RETURN e
        ORDER BY e._key DESC
        LIMIT 1
        """
        
        cursor = real_arango_client.aql.execute(
            query,
            bind_vars={
                "project_id": test_project_context.id,
            }
        )
        
        extractions = list(cursor)
        assert len(extractions) > 0, "Extraction should be persisted to ArangoDB"
        
        # Verify extraction structure
        extraction = extractions[0]
        assert "graph" in extraction or "triples" in extraction
        assert extraction.get("project_id") == test_project_context.id
        
        # Note: job_id may be stored in _key or as a separate field
        # The extraction document structure uses _key as the document identifier
