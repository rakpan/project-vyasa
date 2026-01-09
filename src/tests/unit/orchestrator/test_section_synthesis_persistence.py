"""
Unit tests for Section Synthesis Persistence.

Tests:
- persist_section_run with RetrievalBundle + SectionDraft + promotions
- Block persistence with provenance fields
- Promotion application (Analytical Notes)
- Error handling (fatal vs non-fatal failures)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.orchestrator.schemas.retrieval import RetrievalBundle
from src.orchestrator.services.section_synthesis_service import SectionSynthesisService
from src.shared.schema import ManuscriptBlock
from src.orchestrator.schemas.analytical_notes import AnalyticalNote, NoteState


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.has_collection = Mock(return_value=False)
    db.create_collection = Mock()
    db.collection = Mock(return_value=Mock())
    return db


@pytest.fixture
def synthesis_service(mock_db):
    """Section Synthesis Service with mocked DB."""
    return SectionSynthesisService(mock_db)


@pytest.fixture
def sample_retrieval_bundle():
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
    
    bundle = RetrievalBundle.create(
        query_text="Test query",
        project_id="test-project-123",
        candidate_chunks=candidate_chunks,
        reranked_chunks=reranked_chunks,
        embedder_model_id="nvidia/nv-embedqa-e5-v5",
        reranker_model_id="nvidia/llama-3.2-nv-rerankqa-1b-v2",
        top_k_embed=64,
        top_k_rerank=16,
        section_id="section-1",
    )
    # Add rerank_skipped field
    bundle.rerank_skipped = False  # type: ignore
    return bundle


@pytest.fixture
def sample_section_draft():
    """Sample SectionDraft block for testing."""
    return ManuscriptBlock(
        block_id="block-1",
        section_title="Introduction",
        content="# Introduction\n\nThis section presents...",
        order_index=0,
        claim_ids=["claim-1", "claim-2"],
        citation_keys=["smith2023"],
    )


@pytest.fixture
def sample_promotions():
    """Sample Analytical Note promotions."""
    return [
        {
            "note_id": "note-1",
            "reason": "Framing supported by evidence chunks [chunk-1, chunk-2]",
            "linked_evidence": ["chunk-1", "chunk-2"],
        },
        {
            "note_id": "note-2",
            "reason": "Analogy appropriate for section context",
            "linked_evidence": ["chunk-1"],
        },
    ]


def test_persist_section_run_success(
    synthesis_service,
    sample_retrieval_bundle,
    sample_section_draft,
    sample_promotions,
    mock_db,
):
    """Test successful section run persistence."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock RetrievalBundleService
    mock_bundle_service = Mock()
    mock_bundle_service.save_bundle = Mock(return_value=sample_retrieval_bundle)
    synthesis_service.retrieval_bundle_service = mock_bundle_service
    
    # Mock ManuscriptService
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock(return_value=sample_section_draft)
    synthesis_service.manuscript_service = mock_manuscript_service
    
    # Mock AnalyticalNotesService
    from src.orchestrator.services.analytical_notes_service import AnalyticalNotesService
    mock_notes_service = Mock(spec=AnalyticalNotesService)
    mock_note = AnalyticalNote.create(
        text="Test note",
        project_id=project_id,
        state=NoteState.DRAFT,
    )
    mock_notes_service.get_note = Mock(return_value=mock_note)
    mock_notes_service.update_note = Mock(return_value=mock_note)
    
    with patch("src.orchestrator.services.section_synthesis_service.AnalyticalNotesService", return_value=mock_notes_service):
        results = synthesis_service.persist_section_run(
            project_id=project_id,
            section_id=section_id,
            retrieval_bundle=sample_retrieval_bundle,
            section_draft=sample_section_draft,
            promotions=sample_promotions,
        )
        
        # Verify results
        assert results["bundle_persisted"] is True
        assert results["block_persisted"] is True
        assert results["promotions_applied"] == 2
        assert results["promotions_failed"] == 0
        assert len(results["errors"]) == 0
        
        # Verify provenance fields set on block
        assert sample_section_draft.retrieval_bundle_id == sample_retrieval_bundle.bundle_id
        assert sample_section_draft.section_id == section_id
        assert len(sample_section_draft.chunk_ids) == 2  # From reranked_chunks
        assert len(sample_section_draft.note_ids) == 2  # From promotions
        assert "embedder" in sample_section_draft.model_ids
        assert "reranker" in sample_section_draft.model_ids
        
        # Verify services called
        mock_bundle_service.save_bundle.assert_called_once_with(sample_retrieval_bundle)
        mock_manuscript_service.save_block.assert_called_once_with(sample_section_draft, project_id, validate_citations=True)
        assert mock_notes_service.update_note.call_count == 2


def test_persist_section_run_bundle_failure(
    synthesis_service,
    sample_retrieval_bundle,
    sample_section_draft,
    mock_db,
):
    """Test section run persistence when bundle persistence fails (non-fatal)."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock RetrievalBundleService to fail
    mock_bundle_service = Mock()
    mock_bundle_service.save_bundle = Mock(side_effect=Exception("DB unavailable"))
    synthesis_service.retrieval_bundle_service = mock_bundle_service
    
    # Mock ManuscriptService to succeed
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock(return_value=sample_section_draft)
    synthesis_service.manuscript_service = mock_manuscript_service
    
    # Should not raise - bundle failure is non-fatal
    results = synthesis_service.persist_section_run(
        project_id=project_id,
        section_id=section_id,
        retrieval_bundle=sample_retrieval_bundle,
        section_draft=sample_section_draft,
        promotions=None,
    )
    
    # Verify results
    assert results["bundle_persisted"] is False
    assert results["block_persisted"] is True  # Block persistence succeeded
    assert len(results["errors"]) > 0


def test_persist_section_run_block_failure(
    synthesis_service,
    sample_retrieval_bundle,
    sample_section_draft,
    mock_db,
):
    """Test section run persistence when block persistence fails (fatal)."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock RetrievalBundleService to succeed
    mock_bundle_service = Mock()
    mock_bundle_service.save_bundle = Mock(return_value=sample_retrieval_bundle)
    synthesis_service.retrieval_bundle_service = mock_bundle_service
    
    # Mock ManuscriptService to fail
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock(side_effect=Exception("DB unavailable"))
    synthesis_service.manuscript_service = mock_manuscript_service
    
    # Should raise - block failure is fatal
    with pytest.raises(ValueError, match="Block persistence failed"):
        synthesis_service.persist_section_run(
            project_id=project_id,
            section_id=section_id,
            retrieval_bundle=sample_retrieval_bundle,
            section_draft=sample_section_draft,
            promotions=None,
        )


def test_persist_section_run_promotion_failure(
    synthesis_service,
    sample_retrieval_bundle,
    sample_section_draft,
    sample_promotions,
    mock_db,
):
    """Test section run persistence when promotion fails (non-fatal)."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock RetrievalBundleService to succeed
    mock_bundle_service = Mock()
    mock_bundle_service.save_bundle = Mock(return_value=sample_retrieval_bundle)
    synthesis_service.retrieval_bundle_service = mock_bundle_service
    
    # Mock ManuscriptService to succeed
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock(return_value=sample_section_draft)
    synthesis_service.manuscript_service = mock_manuscript_service
    
    # Mock AnalyticalNotesService to fail for one note
    from src.orchestrator.services.analytical_notes_service import AnalyticalNotesService
    mock_notes_service = Mock(spec=AnalyticalNotesService)
    mock_note = AnalyticalNote.create(
        text="Test note",
        project_id=project_id,
        state=NoteState.DRAFT,
    )
    
    def get_note_side_effect(note_id):
        if note_id == "note-1":
            return mock_note
        return None  # note-2 not found
    
    mock_notes_service.get_note = Mock(side_effect=get_note_side_effect)
    mock_notes_service.update_note = Mock(return_value=mock_note)
    
    with patch("src.orchestrator.services.section_synthesis_service.AnalyticalNotesService", return_value=mock_notes_service):
        results = synthesis_service.persist_section_run(
            project_id=project_id,
            section_id=section_id,
            retrieval_bundle=sample_retrieval_bundle,
            section_draft=sample_section_draft,
            promotions=sample_promotions,
        )
        
        # Verify results
        assert results["bundle_persisted"] is True
        assert results["block_persisted"] is True
        assert results["promotions_applied"] == 1  # note-1 succeeded
        assert results["promotions_failed"] == 1  # note-2 failed (not found)
        assert len(results["errors"]) > 0


def test_persist_section_run_provenance_fields(
    synthesis_service,
    sample_retrieval_bundle,
    sample_section_draft,
    mock_db,
):
    """Test that provenance fields are correctly set on SectionDraft block."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    # Mock services
    mock_bundle_service = Mock()
    mock_bundle_service.save_bundle = Mock(return_value=sample_retrieval_bundle)
    synthesis_service.retrieval_bundle_service = mock_bundle_service
    
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock(return_value=sample_section_draft)
    synthesis_service.manuscript_service = mock_manuscript_service
    
    # Persist
    synthesis_service.persist_section_run(
        project_id=project_id,
        section_id=section_id,
        retrieval_bundle=sample_retrieval_bundle,
        section_draft=sample_section_draft,
        promotions=None,
    )
    
    # Verify provenance fields
    assert sample_section_draft.retrieval_bundle_id == sample_retrieval_bundle.bundle_id
    assert sample_section_draft.section_id == section_id
    assert len(sample_section_draft.chunk_ids) == 2  # From reranked_chunks
    assert sample_section_draft.chunk_ids == ["chunk-2", "chunk-1"]  # From reranked_chunks
    assert sample_section_draft.note_ids == []  # No promotions
    assert "embedder" in sample_section_draft.model_ids
    assert "reranker" in sample_section_draft.model_ids
    assert sample_section_draft.model_ids["embedder"] == "nvidia/nv-embedqa-e5-v5"
    assert sample_section_draft.model_ids["reranker"] == "nvidia/llama-3.2-nv-rerankqa-1b-v2"
