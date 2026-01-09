"""
Unit tests for Retrieval Service (retrieval + rerank integration).

Tests:
- Retrieval with reranker enabled (success path)
- Retrieval with reranker required but unavailable (failure path)
- Retrieval with reranker optional but unavailable (fallback path)
- RetrievalBundle persistence
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.retrieval.retrieval_service import RetrievalService
from src.orchestrator.schemas.retrieval import RetrievalBundle
from src.shared.config import RERANKER_ENABLED, RERANKER_REQUIRED, EMBEDDER_MODEL_ID, RERANKER_MODEL_ID


@pytest.fixture
def mock_qdrant_storage():
    """Mock QdrantStorage."""
    storage = Mock()
    return storage


@pytest.fixture
def mock_bundle_service():
    """Mock RetrievalBundleService."""
    service = Mock()
    return service


@pytest.fixture
def retrieval_service(mock_bundle_service):
    """RetrievalService with mocked dependencies."""
    service = RetrievalService(db=Mock())
    service.bundle_service = mock_bundle_service
    service.qdrant_storage = Mock()
    return service


@pytest.fixture
def sample_chunks():
    """Sample candidate chunks from Qdrant."""
    return [
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
        {
            "chunk_id": "chunk-3",
            "text_content": "Chunk 3 text",
            "payload": {"file_hash": "abc123", "page_number": 3},
            "score": 0.90,
        },
    ]


def test_retrieve_with_reranker_success(retrieval_service, mock_bundle_service, sample_chunks):
    """Test retrieval with reranker enabled (success path)."""
    query = "Test query"
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock Qdrant retrieval
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=sample_chunks)
    
    # Mock reranker response (OpenAI-style)
    reranked_results = [
        {"id": "chunk-2", "text": "Chunk 2 text", "score": 0.98, "rank": 1},
        {"id": "chunk-1", "text": "Chunk 1 text", "score": 0.96, "rank": 2},
    ]
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": reranked_results}
    mock_response.raise_for_status = Mock()
    
    # Mock bundle service
    # Expected reranked chunks (based on reranker response: chunk-2 first, chunk-1 second)
    expected_reranked = [
        {**sample_chunks[1], "rerank_score": 0.98, "rerank_rank": 1, "score": 0.98},  # chunk-2 reranked first
        {**sample_chunks[0], "rerank_score": 0.96, "rerank_rank": 2, "score": 0.96},  # chunk-1 reranked second
    ]
    
    mock_bundle = RetrievalBundle.create(
        query_text=query,
        project_id=project_id,
        candidate_chunks=sample_chunks,
        reranked_chunks=expected_reranked,
        embedder_model_id=EMBEDDER_MODEL_ID or "test-embedder",
        reranker_model_id=RERANKER_MODEL_ID or "test-reranker",
        top_k_embed=64,
        top_k_rerank=24,
        rerank_skipped=False,
    )
    mock_bundle_service.save_bundle.return_value = mock_bundle
    
    with patch("src.orchestrator.retrieval.retrieval_service.requests.post", return_value=mock_response):
        chunks, bundle_id = retrieval_service.retrieve_for_section(
            query_text=query,
            project_id=project_id,
            section_id=section_id,
            use_reranker=True,
        )
    
    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == "chunk-2"  # Reranked first
    assert chunks[0]["rerank_score"] == 0.98
    assert chunks[0]["rerank_rank"] == 1
    assert bundle_id == mock_bundle.bundle_id
    mock_bundle_service.save_bundle.assert_called_once()


def test_retrieve_reranker_required_failure(retrieval_service, sample_chunks):
    """Test retrieval with reranker required but unavailable (failure path)."""
    query = "Test query"
    project_id = "test-project-123"
    
    # Mock Qdrant retrieval
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=sample_chunks)
    
    # Mock reranker failure
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("Reranker unavailable")
    
    with patch("src.orchestrator.retrieval.retrieval_service.requests.post", return_value=mock_response):
        with patch("src.orchestrator.retrieval.retrieval_service.RERANKER_REQUIRED", True):
            with pytest.raises(ValueError, match="Reranker is required but unavailable"):
                retrieval_service.retrieve_for_section(
                    query_text=query,
                    project_id=project_id,
                    use_reranker=True,
                )


def test_retrieve_reranker_optional_fallback(retrieval_service, mock_bundle_service, sample_chunks):
    """Test retrieval with reranker optional but unavailable (fallback path)."""
    query = "Test query"
    project_id = "test-project-123"
    top_m = 2
    
    # Mock Qdrant retrieval
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=sample_chunks)
    
    # Mock reranker failure
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("Reranker unavailable")
    
    # Mock bundle service
    # Expected reranked chunks (fallback to embed-only, sorted by score descending)
    sorted_chunks = sorted(sample_chunks, key=lambda x: x.get("score", 0.0), reverse=True)
    expected_reranked = sorted_chunks[:top_m]
    
    mock_bundle = RetrievalBundle.create(
        query_text=query,
        project_id=project_id,
        candidate_chunks=sample_chunks,
        reranked_chunks=expected_reranked,
        embedder_model_id=EMBEDDER_MODEL_ID or "test-embedder",
        reranker_model_id="none",
        top_k_embed=64,
        top_k_rerank=top_m,
        rerank_skipped=True,
        rerank_error="Reranker unavailable",
    )
    mock_bundle_service.save_bundle.return_value = mock_bundle
    
    with patch("src.orchestrator.retrieval.retrieval_service.requests.post", return_value=mock_response):
        with patch("src.orchestrator.retrieval.retrieval_service.RERANKER_REQUIRED", False):
            chunks, bundle_id = retrieval_service.retrieve_for_section(
                query_text=query,
                project_id=project_id,
                top_m=top_m,
                use_reranker=True,
            )
    
    # Should fallback to embed-only (top-M by embedding score)
    assert len(chunks) == top_m
    assert chunks[0]["chunk_id"] == "chunk-1"  # Top by embedding score
    assert chunks[0].get("rerank_score") is None  # No rerank score
    assert bundle_id == mock_bundle.bundle_id
    
    # Verify bundle was marked as rerank_skipped
    saved_bundle = mock_bundle_service.save_bundle.call_args[0][0]
    assert saved_bundle.rerank_skipped is True
    assert saved_bundle.rerank_error is not None


def test_retrieve_without_reranker(retrieval_service, mock_bundle_service, sample_chunks):
    """Test retrieval with reranker disabled."""
    query = "Test query"
    project_id = "test-project-123"
    top_m = 2
    
    # Mock Qdrant retrieval
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=sample_chunks)
    
    # Mock bundle service
    mock_bundle = RetrievalBundle.create(
        query_text=query,
        project_id=project_id,
        candidate_chunks=sample_chunks,
        reranked_chunks=sample_chunks[:top_m],
        embedder_model_id=EMBEDDER_MODEL_ID or "test-embedder",
        reranker_model_id="none",
        top_k_embed=64,
        top_k_rerank=top_m,
        rerank_skipped=True,
    )
    mock_bundle_service.save_bundle.return_value = mock_bundle
    
    chunks, bundle_id = retrieval_service.retrieve_for_section(
        query_text=query,
        project_id=project_id,
        top_m=top_m,
        use_reranker=False,
    )
    
    # Should use embed-only (top-M by embedding score)
    assert len(chunks) == top_m
    assert chunks[0]["chunk_id"] == "chunk-1"  # Top by embedding score
    assert bundle_id == mock_bundle.bundle_id


def test_retrieve_no_chunks(retrieval_service):
    """Test retrieval with no chunks found."""
    query = "Test query"
    project_id = "test-project-123"
    
    # Mock Qdrant retrieval returning empty list
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=[])
    
    chunks, bundle_id = retrieval_service.retrieve_for_section(
        query_text=query,
        project_id=project_id,
    )
    
    assert chunks == []
    assert bundle_id is None


def test_retrieve_bundle_persistence_failure(retrieval_service, sample_chunks):
    """Test retrieval with bundle persistence failure (non-fatal)."""
    query = "Test query"
    project_id = "test-project-123"
    
    # Mock Qdrant retrieval
    retrieval_service.qdrant_storage.retrieve_chunks_by_query = Mock(return_value=sample_chunks)
    
    # Mock bundle service to fail
    retrieval_service.bundle_service.save_bundle = Mock(side_effect=Exception("DB unavailable"))
    
    # Mock reranker response
    reranked_results = [
        {"id": "chunk-1", "text": "Chunk 1 text", "score": 0.96, "rank": 1},
    ]
    mock_response = Mock()
    mock_response.json.return_value = {"data": reranked_results}
    mock_response.raise_for_status = Mock()
    
    with patch("src.orchestrator.retrieval.retrieval_service.requests.post", return_value=mock_response):
        chunks, bundle_id = retrieval_service.retrieve_for_section(
            query_text=query,
            project_id=project_id,
            use_reranker=True,
        )
    
    # Should still return chunks even if bundle persistence fails
    assert len(chunks) == 1
    assert bundle_id is None  # Bundle persistence failed


def test_rerank_chunks_fallback_to_rerank_endpoint(retrieval_service, sample_chunks):
    """Test reranker client fallback to /rerank endpoint."""
    query = "Test query"
    
    # Mock /v1/ranking to fail
    mock_v1_response = Mock()
    mock_v1_response.raise_for_status.side_effect = Exception("Not found")
    
    # Mock /rerank to succeed
    reranked_results = [
        {"chunk_id": "chunk-1", "text": "Chunk 1 text", "score": 0.96, "rank": 1},
        {"chunk_id": "chunk-2", "text": "Chunk 2 text", "score": 0.94, "rank": 2},
    ]
    mock_rerank_response = Mock()
    mock_rerank_response.json.return_value = {"results": reranked_results}
    mock_rerank_response.raise_for_status = Mock()
    
    with patch("requests.post") as mock_post:
        # First call to /v1/ranking fails, second call to /rerank succeeds
        mock_post.side_effect = [mock_v1_response, mock_rerank_response]
        
        reranked = retrieval_service._rerank_chunks(query, sample_chunks, top_m=2)
    
    assert len(reranked) == 2
    assert reranked[0]["chunk_id"] == "chunk-1"
    assert reranked[0]["rerank_score"] == 0.96
    assert mock_post.call_count == 2  # Tried /v1/ranking, then /rerank
