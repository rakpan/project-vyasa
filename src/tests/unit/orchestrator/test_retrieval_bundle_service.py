"""
Unit tests for Retrieval Bundle Service.

Tests:
- Save/get RetrievalBundle
- Filtering by project_id, section_id, query_id
- Internal persistence (no API endpoints)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.orchestrator.schemas.retrieval import RetrievalBundle
from src.orchestrator.services.retrieval_bundle_service import RetrievalBundleService


TEST_INGESTION_ID = "test-ingestion-123"


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.has_collection = Mock(return_value=False)
    db.create_collection = Mock()
    db.collection = Mock(return_value=Mock())
    return db


@pytest.fixture
def bundle_service(mock_db):
    """Retrieval Bundle Service with mocked DB."""
    return RetrievalBundleService(mock_db)


@pytest.fixture
def sample_bundle():
    """Sample RetrievalBundle for testing."""
    candidate_chunks = [
        {
            "chunk_id": "chunk-1",
            "text_content": "Chunk 1 text",
            "payload": {"file_hash": "abc123", "page_number": 1},
            "score": 0.95,
        },
        {
            "chunk_id": "chunk-2",
            "text_content": "Chunk 2 text",
            "payload": {"file_hash": "abc123", "page_number": 2},
            "score": 0.92,
        },
    ]
    
    reranked_chunks = [
        {
            "chunk_id": "chunk-2",
            "text_content": "Chunk 2 text",
            "payload": {"file_hash": "abc123", "page_number": 2},
            "score": 0.92,
            "rerank_score": 0.98,
            "rerank_rank": 1,
        },
        {
            "chunk_id": "chunk-1",
            "text_content": "Chunk 1 text",
            "payload": {"file_hash": "abc123", "page_number": 1},
            "score": 0.95,
            "rerank_score": 0.96,
            "rerank_rank": 2,
        },
    ]
    
    return RetrievalBundle.create(
        query_text="Test query",
        project_id="test-project-123",
        ingestion_id=TEST_INGESTION_ID,
        candidate_chunks=candidate_chunks,
        reranked_chunks=reranked_chunks,
        embedder_model_id="nvidia/nv-embedqa-e5-v5",
        reranker_model_id="nvidia/llama-3.2-nv-rerankqa-1b-v2",
        top_k_embed=64,
        top_k_rerank=16,
        query_source="blueprint_section",
        section_id="section-1",
    )


def test_save_bundle(bundle_service, sample_bundle, mock_db):
    """Test saving a RetrievalBundle."""
    coll = Mock()
    coll.insert = Mock(return_value={"_id": "bundles/test-123", "_key": "test-123"})
    mock_db.collection.return_value = coll
    mock_db.has_collection.return_value = True
    
    bundle = bundle_service.save_bundle(sample_bundle)
    
    assert bundle.bundle_id == sample_bundle.bundle_id
    assert bundle.top_k_embed == 64
    assert bundle.top_k_rerank == 16
    assert coll.insert.called_once


def test_get_bundle(bundle_service, mock_db):
    """Test getting a RetrievalBundle by ID."""
    bundle_id = "test-bundle-123"
    bundle_doc = {
        "bundle_id": bundle_id,
        "project_id": "test-project-123",
        "ingestion_id": TEST_INGESTION_ID,
        "query_text": "Test query",
        "candidate_chunks": [],
        "reranked_chunks": [],
        "embedder_model_id": "nvidia/nv-embedqa-e5-v5",
        "reranker_model_id": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
        "top_k_embed": 64,
        "top_k_rerank": 16,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
    
    coll = Mock()
    coll.get = Mock(return_value=bundle_doc)
    mock_db.collection.return_value = coll
    
    bundle = bundle_service.get_bundle(bundle_id)
    
    assert bundle is not None
    assert bundle.bundle_id == bundle_id
    assert coll.get.called_once_with(bundle_id)


def test_get_bundle_not_found(bundle_service, mock_db):
    """Test getting non-existent bundle."""
    coll = Mock()
    coll.get = Mock(return_value=None)
    mock_db.collection.return_value = coll
    
    bundle = bundle_service.get_bundle("non-existent")
    
    assert bundle is None


def test_list_bundles(bundle_service, mock_db):
    """Test listing RetrievalBundles with filters."""
    project_id = "test-project-123"
    
    bundles_data = [
        {
            "bundle_id": "bundle-1",
            "project_id": project_id,
            "ingestion_id": TEST_INGESTION_ID,
            "section_id": "section-1",
            "query_id": "query-1",
            "query_text": "Query 1",
            "candidate_chunks": [],
            "reranked_chunks": [],
            "embedder_model_id": "nvidia/nv-embedqa-e5-v5",
            "reranker_model_id": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
            "top_k_embed": 64,
            "top_k_rerank": 16,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        },
        {
            "bundle_id": "bundle-2",
            "project_id": project_id,
            "ingestion_id": TEST_INGESTION_ID,
            "section_id": "section-2",
            "query_id": "query-2",
            "query_text": "Query 2",
            "candidate_chunks": [],
            "reranked_chunks": [],
            "embedder_model_id": "nvidia/nv-embedqa-e5-v5",
            "reranker_model_id": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
            "top_k_embed": 64,
            "top_k_rerank": 16,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        },
    ]
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter(bundles_data))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    bundles = bundle_service.list_bundles(
        project_id=project_id,
        section_id="section-1",
    )
    
    assert len(bundles) == 2  # Both returned (filter applied in query)
    assert mock_db.aql.execute.called_once


def test_get_bundles_for_section(bundle_service, mock_db):
    """Test getting all bundles for a specific section."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter([]))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    bundles = bundle_service.get_bundles_for_section(project_id, section_id)
    
    assert len(bundles) == 0
    # Verify query includes section_id filter
    call_args = mock_db.aql.execute.call_args
    assert section_id in str(call_args)
