"""
Unit tests for Section Synthesis Orchestrator.

Tests:
- Section query building
- Packet A and Packet B construction
- Synthesizer and Critic LLM calls (mocked)
- Persistence of manuscript blocks and note promotions
- Vocabulary guardrails
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.section_synthesis.section_orchestrator import (
    build_section_query,
    build_packet_a,
    build_packet_b,
    synthesize_section,
    criticize_section,
    run_section_synthesis,
    SectionSynthesisError,
)
from src.orchestrator.schemas.blueprint import BlueprintSection, JournalSlot, DepthIntent
from src.orchestrator.schemas.analytical_notes import AnalyticalNote, NoteState
from src.orchestrator.schemas.retrieval import RetrievalBundle
from src.project.types import ProjectConfig


@pytest.fixture
def sample_project_config():
    """Sample ProjectConfig."""
    return ProjectConfig(
        project_id="test-project-123",
        thesis="Test thesis statement",
        research_questions=["RQ1: What is X?", "RQ2: How does Y work?"],
        rigor_level="exploratory",
    )


@pytest.fixture
def sample_section():
    """Sample BlueprintSection."""
    return BlueprintSection(
        section_id="section-1",
        heading="Introduction",
        journal_slot=JournalSlot.INTRODUCTION,
        linked_rqs=["RQ1"],
        depth_intent=DepthIntent.HOOK,
    )


@pytest.fixture
def sample_chunks():
    """Sample reranked chunks for Packet A."""
    return [
        {
            "chunk_id": "chunk-1",
            "text_content": "First chunk text with important information.",
            "payload": {"file_hash": "abc123", "page_number": 1},
            "score": 0.95,
            "rerank_score": 0.98,
            "rerank_rank": 1,
        },
        {
            "chunk_id": "chunk-2",
            "text_content": "Second chunk text with supporting evidence.",
            "payload": {"file_hash": "abc123", "page_number": 2},
            "score": 0.92,
            "rerank_score": 0.96,
            "rerank_rank": 2,
        },
    ]


@pytest.fixture
def sample_notes():
    """Sample Analytical Notes for Packet B."""
    return [
        AnalyticalNote.create(
            text="This is a perspective note about the topic.",
            project_id="test-project-123",
            tags=["introduction", "background"],
            linked_rq="RQ1",
        ),
        AnalyticalNote.create(
            text="Another perspective note with different framing.",
            project_id="test-project-123",
            tags=["introduction"],
            linked_rq="RQ1",
        ),
    ]


def test_build_section_query(sample_section, sample_project_config):
    """Test section query building."""
    query = build_section_query(sample_section, sample_project_config)
    
    assert "Introduction" in query
    assert "introduction" in query.lower()
    assert "RQ1: What is X?" in query
    assert "hook" in query.lower() or "attention" in query.lower()


def test_build_packet_a(sample_chunks):
    """Test Packet A construction."""
    packet_a = build_packet_a(sample_chunks)
    
    assert len(packet_a) == 2
    assert packet_a[0]["citation"]["chunk_id"] == "chunk-1"
    assert packet_a[0]["citation"]["page"] == 1
    assert "chunk-1" in packet_a[0]["text"] or "important" in packet_a[0]["text"]
    assert "full_chunk" in packet_a[0]


def test_build_packet_a_rerank_rank_sorting():
    """Test Packet A sorting with rerank_rank (ascending: rank 1 is best)."""
    chunks_with_rerank = [
        {
            "chunk_id": "chunk-3",
            "text_content": "Third best chunk",
            "payload": {"file_hash": "abc123", "page_number": 3},
            "score": 0.90,
            "rerank_score": 0.94,
            "rerank_rank": 3,  # Worst rank
        },
        {
            "chunk_id": "chunk-1",
            "text_content": "Best chunk",
            "payload": {"file_hash": "abc123", "page_number": 1},
            "score": 0.95,
            "rerank_score": 0.98,
            "rerank_rank": 1,  # Best rank
        },
        {
            "chunk_id": "chunk-2",
            "text_content": "Second best chunk",
            "payload": {"file_hash": "abc123", "page_number": 2},
            "score": 0.92,
            "rerank_score": 0.96,
            "rerank_rank": 2,  # Middle rank
        },
    ]
    
    packet_a = build_packet_a(chunks_with_rerank)
    
    # Verify order: rank 1 (best) should be first, then 2, then 3
    assert len(packet_a) == 3
    assert packet_a[0]["citation"]["chunk_id"] == "chunk-1"  # Rank 1 (best)
    assert packet_a[1]["citation"]["chunk_id"] == "chunk-2"  # Rank 2
    assert packet_a[2]["citation"]["chunk_id"] == "chunk-3"  # Rank 3 (worst)


def test_build_packet_a_score_sorting():
    """Test Packet A sorting with score (descending: highest score is best)."""
    chunks_with_scores = [
        {
            "chunk_id": "chunk-low",
            "text_content": "Low score chunk",
            "payload": {"file_hash": "abc123", "page_number": 3},
            "score": 0.70,  # Lowest score
        },
        {
            "chunk_id": "chunk-high",
            "text_content": "High score chunk",
            "payload": {"file_hash": "abc123", "page_number": 1},
            "score": 0.95,  # Highest score (best)
        },
        {
            "chunk_id": "chunk-medium",
            "text_content": "Medium score chunk",
            "payload": {"file_hash": "abc123", "page_number": 2},
            "score": 0.85,  # Middle score
        },
    ]
    
    packet_a = build_packet_a(chunks_with_scores)
    
    # Verify order: highest score (best) should be first, then medium, then low
    assert len(packet_a) == 3
    assert packet_a[0]["citation"]["chunk_id"] == "chunk-high"  # Score 0.95 (best)
    assert packet_a[1]["citation"]["chunk_id"] == "chunk-medium"  # Score 0.85
    assert packet_a[2]["citation"]["chunk_id"] == "chunk-low"  # Score 0.70 (worst)


def test_build_packet_b(sample_section, sample_notes):
    """Test Packet B construction."""
    mock_notes_service = Mock()
    mock_notes_service.list_notes = Mock(return_value=sample_notes)
    
    packet_b = build_packet_b(
        project_id="test-project-123",
        section=sample_section,
        notes_service=mock_notes_service,
    )
    
    assert len(packet_b) == 2
    assert packet_b[0]["note_id"] == sample_notes[0].note_id
    assert packet_b[0]["text"] == sample_notes[0].text
    assert packet_b[0]["linked_rq"] == "RQ1"
    mock_notes_service.list_notes.assert_called()


def test_synthesize_section(sample_section, sample_project_config):
    """Test section synthesis with mocked LLM."""
    packet_a = [
        {
            "text": "Evidence chunk 1",
            "citation": {"chunk_id": "chunk-1", "page": 1, "source": "abc123"},
        }
    ]
    packet_b = [
        {"note_id": "note-1", "text": "Perspective note", "tags": [], "linked_rq": "RQ1", "state": "Draft"}
    ]
    
    # Mock LLM response
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "## Introduction\n\nThis is the synthesized section text with [[chunk-1]] citation."
                }
            }
        ]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_call:
        mock_call.return_value = (mock_response, {})
        
        with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=None):
            section_text = synthesize_section(
                section=sample_section,
                packet_a=packet_a,
                packet_b=packet_b,
                project_config=sample_project_config,
            )
    
    assert "Introduction" in section_text
    assert "[[chunk-1]]" in section_text
    mock_call.assert_called_once()


def test_criticize_section(sample_project_config):
    """Test section criticism with mocked LLM."""
    section_text = "This is the section text with [[chunk-1]] citation."
    packet_a = [
        {
            "text": "Evidence chunk 1",
            "citation": {"chunk_id": "chunk-1", "page": 1, "source": "abc123"},
        }
    ]
    packet_b = [
        {
            "note_id": "note-1",
            "text": "Perspective note",
            "tags": [],
            "linked_rq": "RQ1",
            "state": "Draft",
        }
    ]
    
    # Mock LLM response (JSON)
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "overreach_flags": [],
                        "suggested_promotions": [
                            {
                                "note_id": "note-1",
                                "reason": "Framing supported by evidence chunks [chunk-1]",
                                "linked_evidence": ["chunk-1"]
                            }
                        ],
                        "vocabulary_suggestions": [],
                        "required_citations_missing": []
                    }"""
                }
            }
        ]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_call:
        mock_call.return_value = (mock_response, {})
        
        critique = criticize_section(
            section_text=section_text,
            packet_a=packet_a,
            packet_b=packet_b,
            project_config=sample_project_config,
            section_id="section-1",
        )
    
    assert len(critique["suggested_promotions"]) == 1
    assert critique["suggested_promotions"][0]["note_id"] == "note-1"
    assert "chunk-1" in critique["suggested_promotions"][0]["linked_evidence"]
    mock_call.assert_called_once()


def test_run_section_synthesis_full_loop(sample_section, sample_project_config, sample_chunks, sample_notes):
    """Test complete section synthesis loop with mocked dependencies."""
    from arango.database import StandardDatabase
    
    # Mock database and services
    mock_db = Mock(spec=StandardDatabase)
    
    # Mock BlueprintService
    mock_blueprint_service = Mock()
    mock_blueprint = Mock()
    mock_blueprint.sections = [sample_section]
    mock_blueprint_service.get_blueprint = Mock(return_value=mock_blueprint)
    
    # Mock NotesService
    mock_notes_service = Mock()
    mock_notes_service.list_notes = Mock(return_value=sample_notes)
    mock_notes_service.get_note = Mock(return_value=sample_notes[0])
    mock_notes_service.update_note = Mock(return_value=sample_notes[0])
    
    # Mock RetrievalService
    mock_retrieval_service = Mock()
    mock_retrieval_service.retrieve_for_section = Mock(return_value=(sample_chunks, "bundle-123"))
    
    # Mock RetrievalBundleService
    mock_bundle_service = Mock()
    mock_bundle = RetrievalBundle.create(
        query_text="test query",
        project_id="test-project-123",
        candidate_chunks=sample_chunks,
        reranked_chunks=sample_chunks,
        embedder_model_id="test-embedder",
        reranker_model_id="test-reranker",
        top_k_embed=64,
        top_k_rerank=24,
    )
    mock_bundle_service.get_bundle = Mock(return_value=mock_bundle)
    
    # Mock ManuscriptService
    mock_manuscript_service = Mock()
    mock_manuscript_service.save_block = Mock()
    
    # Mock SectionSynthesisService
    mock_synthesis_service = Mock()
    mock_synthesis_service.persist_section_run = Mock(
        return_value={
            "bundle_persisted": True,
            "block_persisted": True,
            "promotions_applied": 1,
            "promotions_failed": 0,
            "errors": [],
        }
    )
    
    # Mock ProjectService
    mock_project_service = Mock()
    mock_project_service.get_project = Mock(return_value=sample_project_config)
    
    # Mock LLM calls
    mock_synthesizer_response = {
        "choices": [
            {
                "message": {
                    "content": "## Introduction\n\nThis is the synthesized section with [[chunk-1]] citation."
                }
            }
        ]
    }
    
    mock_critic_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "overreach_flags": [],
                        "suggested_promotions": [
                            {
                                "note_id": "note-1",
                                "reason": "Framing supported by evidence",
                                "linked_evidence": ["chunk-1"]
                            }
                        ],
                        "vocabulary_suggestions": [],
                        "required_citations_missing": []
                    }"""
                }
            }
        ]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.BlueprintService", return_value=mock_blueprint_service):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.AnalyticalNotesService", return_value=mock_notes_service):
            with patch("src.orchestrator.section_synthesis.section_orchestrator.RetrievalService", return_value=mock_retrieval_service):
                with patch("src.orchestrator.section_synthesis.section_orchestrator.SectionSynthesisService", return_value=mock_synthesis_service):
                    with patch("src.orchestrator.section_synthesis.section_orchestrator.ProjectService", return_value=mock_project_service):
                        with patch("src.orchestrator.section_synthesis.section_orchestrator.RetrievalBundleService", return_value=mock_bundle_service):
                            with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_llm:
                                mock_llm.side_effect = [
                                    (mock_synthesizer_response, {}),  # Synthesizer call
                                    (mock_critic_response, {}),  # Critic call
                                ]
                                
                                with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=None):
                                    results = run_section_synthesis(
                                        project_id="test-project-123",
                                        section_id="section-1",
                                        ingestion_id="ingestion-456",
                                        db=mock_db,
                                    )
    
    assert results["bundle_id"] == "bundle-123"
    assert results["block_id"] is not None
    assert results["promotions_applied"] == 1
    assert "Introduction" in results["section_text"]
    assert len(results["critique"]["suggested_promotions"]) == 1
    
    # Verify services were called
    mock_retrieval_service.retrieve_for_section.assert_called_once()
    mock_synthesis_service.persist_section_run.assert_called_once()
    assert mock_llm.call_count == 2  # Synthesizer + Critic


def test_synthesize_section_vocabulary_guardrails(sample_section, sample_project_config):
    """Test vocabulary guardrails in section synthesis."""
    packet_a = [
        {
            "text": "Evidence chunk",
            "citation": {"chunk_id": "chunk-1", "page": 1, "source": "abc123"},
        }
    ]
    packet_b = []
    
    # Mock vocab guard
    mock_vocab_guard = Mock()
    mock_vocab_guard.apply_constraints = Mock(return_value="Modified prompt with constraints")
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Section text with [[chunk-1]] citation."
                }
            }
        ]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=mock_vocab_guard):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (mock_response, {})
            
            synthesize_section(
                section=sample_section,
                packet_a=packet_a,
                packet_b=packet_b,
                project_config=sample_project_config,
            )
    
    # Verify vocab guard was applied
    mock_vocab_guard.apply_constraints.assert_called_once()


def test_criticize_section_vocabulary_check(sample_project_config):
    """Test vocabulary checking in critic."""
    section_text = "Section text with potentially forbidden words."
    packet_a = []
    packet_b = []
    
    # Mock vocab guard
    mock_vocab_guard = Mock()
    mock_vocab_guard.check_forbidden = Mock(return_value="forbidden_word")
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "overreach_flags": [],
                        "suggested_promotions": [],
                        "vocabulary_suggestions": ["Replace 'forbidden_word'"],
                        "required_citations_missing": []
                    }"""
                }
            }
        ]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=mock_vocab_guard):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (mock_response, {})
            
            critique = criticize_section(
                section_text=section_text,
                packet_a=packet_a,
                packet_b=packet_b,
                project_config=sample_project_config,
                section_id="section-1",
            )
    
    # Verify vocab guard was checked
    mock_vocab_guard.check_forbidden.assert_called_once_with(section_text)
    assert len(critique["vocabulary_suggestions"]) > 0


def test_run_section_synthesis_no_ingestion_id(sample_section):
    """Test section synthesis fails without ingestion_id."""
    mock_db = Mock()
    
    with pytest.raises(SectionSynthesisError, match="ingestion_id is required"):
        run_section_synthesis(
            project_id="test-project-123",
            section_id="section-1",
            ingestion_id=None,  # Missing ingestion_id
            db=mock_db,
        )


def test_run_section_synthesis_order_index(sample_project_config):
    """Test that order_index is set correctly based on section position in blueprint."""
    from src.orchestrator.section_synthesis.section_orchestrator import run_section_synthesis
    from arango.database import StandardDatabase
    from unittest.mock import Mock, patch
    
    # Create blueprint with 3 sections: A, B, C
    section_a = BlueprintSection(
        section_id="section-a",
        heading="Section A",
        journal_slot=JournalSlot.INTRODUCTION,
        linked_rqs=["RQ1"],
        depth_intent=DepthIntent.DETAILED,
    )
    section_b = BlueprintSection(
        section_id="section-b",
        heading="Section B",
        journal_slot=JournalSlot.METHODS,
        linked_rqs=["RQ2"],
        depth_intent=DepthIntent.DETAILED,
    )
    section_c = BlueprintSection(
        section_id="section-c",
        heading="Section C",
        journal_slot=JournalSlot.RESULTS,
        linked_rqs=["RQ3"],
        depth_intent=DepthIntent.DETAILED,
    )
    
    mock_db = Mock(spec=StandardDatabase)
    
    # Mock services
    mock_blueprint_service = Mock()
    mock_blueprint = Mock()
    mock_blueprint.sections = [section_a, section_b, section_c]  # B is at index 1
    mock_blueprint_service.get_blueprint = Mock(return_value=mock_blueprint)
    
    mock_project_service = Mock()
    mock_project_service.get_project = Mock(return_value=sample_project_config)
    
    mock_retrieval_service = Mock()
    sample_chunks = [
        {"chunk_id": "chunk-1", "text_content": "Chunk 1", "payload": {}, "score": 0.95},
    ]
    mock_retrieval_service.retrieve_for_section = Mock(return_value=(sample_chunks, "bundle-123"))
    
    mock_notes_service = Mock()
    mock_notes_service.list_notes = Mock(return_value=[])
    
    mock_synthesis_service = Mock()
    mock_synthesis_service.persist_section_run = Mock(
        return_value={
            "bundle_persisted": True,
            "block_persisted": True,
            "promotions_applied": 0,
            "promotions_failed": 0,
            "errors": [],
        }
    )
    
    # Mock LLM responses
    mock_synthesizer_response = {
        "choices": [{"message": {"content": "## Section B\n\nContent with [[chunk:chunk-1]] citation."}}]
    }
    mock_critic_response = {
        "choices": [{"message": {"content": '{"overreach_flags": [], "suggested_promotions": [], "vocabulary_suggestions": [], "required_citations_missing": []}'}}]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.BlueprintService", return_value=mock_blueprint_service):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.ProjectService", return_value=mock_project_service):
            with patch("src.orchestrator.section_synthesis.section_orchestrator.RetrievalService", return_value=mock_retrieval_service):
                with patch("src.orchestrator.section_synthesis.section_orchestrator.AnalyticalNotesService", return_value=mock_notes_service):
                    with patch("src.orchestrator.section_synthesis.section_orchestrator.SectionSynthesisService", return_value=mock_synthesis_service):
                        with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_llm:
                            mock_llm.side_effect = [
                                (mock_synthesizer_response, {}),  # Synthesizer
                                (mock_critic_response, {}),  # Critic
                            ]
                            
                            with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=None):
                                results = run_section_synthesis(
                                    project_id="test-project-123",
                                    section_id="section-b",  # Section B (index 1)
                                    ingestion_id="ingestion-456",
                                    db=mock_db,
                                )
    
    # Verify persist_section_run was called with correct block structure
    call_args = mock_synthesis_service.persist_section_run.call_args
    section_block = call_args[1]["section_draft"]  # Get section_draft from kwargs
    
    # Assert: order_index should be 1 (section B is at index 1 in blueprint)
    assert section_block.order_index == 1, f"Expected order_index=1 for section B, got {section_block.order_index}"


def test_run_section_synthesis_no_chunks(sample_section, sample_project_config):
    """Test section synthesis fails when no chunks retrieved."""
    mock_db = Mock()
    
    # Mock services
    mock_blueprint_service = Mock()
    mock_blueprint = Mock()
    mock_blueprint.sections = [sample_section]
    mock_blueprint_service.get_blueprint = Mock(return_value=mock_blueprint)
    
    mock_retrieval_service = Mock()
    mock_retrieval_service.retrieve_for_section = Mock(return_value=([], None))  # No chunks
    
    mock_project_service = Mock()
    mock_project_service.get_project = Mock(return_value=sample_project_config)
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.BlueprintService", return_value=mock_blueprint_service):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.RetrievalService", return_value=mock_retrieval_service):
            with patch("src.orchestrator.section_synthesis.section_orchestrator.ProjectService", return_value=mock_project_service):
                with pytest.raises(SectionSynthesisError, match="No chunks retrieved"):
                    run_section_synthesis(
                        project_id="test-project-123",
                        section_id="section-1",
                        ingestion_id="ingestion-456",
                        db=mock_db,
                    )


def test_section_synthesis_chunk_citation_extraction():
    """Test that chunk citations are extracted correctly and stored in chunk_ids, not claim_ids."""
    from src.orchestrator.section_synthesis.section_orchestrator import run_section_synthesis
    from arango.database import StandardDatabase
    from unittest.mock import Mock, patch
    
    # Sample section text with chunk citations
    section_text_with_chunks = """
    This is a section with citations: [[chunk:chunk-123]] and [[chunk:chunk-456]].
    Also supports backward compatible format: [[chunk-789]].
    """
    
    # Mock services
    mock_db = Mock(spec=StandardDatabase)
    
    mock_blueprint_service = Mock()
    mock_blueprint = Mock()
    mock_section = Mock()
    mock_section.section_id = "section-1"
    mock_section.heading = "Test Section"
    mock_section.journal_slot = Mock()
    mock_section.journal_slot.value = "introduction"
    mock_section.linked_rqs = ["RQ1"]
    mock_section.depth_intent = Mock()
    mock_section.depth_intent.value = "detailed"
    mock_blueprint.sections = [mock_section]
    mock_blueprint_service.get_blueprint = Mock(return_value=mock_blueprint)
    
    mock_project_service = Mock()
    mock_project_config = Mock()
    mock_project_config.rigor_level = "exploratory"
    mock_project_service.get_project = Mock(return_value=mock_project_config)
    
    mock_retrieval_service = Mock()
    sample_chunks = [
        {"chunk_id": "chunk-123", "text_content": "Chunk 1", "payload": {}, "score": 0.95},
        {"chunk_id": "chunk-456", "text_content": "Chunk 2", "payload": {}, "score": 0.92},
    ]
    mock_retrieval_service.retrieve_for_section = Mock(return_value=(sample_chunks, "bundle-123"))
    
    mock_notes_service = Mock()
    mock_notes_service.list_notes = Mock(return_value=[])
    
    mock_synthesis_service = Mock()
    mock_synthesis_service.persist_section_run = Mock(
        return_value={
            "bundle_persisted": True,
            "block_persisted": True,
            "promotions_applied": 0,
            "promotions_failed": 0,
            "errors": [],
        }
    )
    
    # Mock LLM responses
    mock_synthesizer_response = {
        "choices": [{"message": {"content": section_text_with_chunks}}]
    }
    mock_critic_response = {
        "choices": [{"message": {"content": '{"overreach_flags": [], "suggested_promotions": [], "vocabulary_suggestions": [], "required_citations_missing": []}'}}]
    }
    
    with patch("src.orchestrator.section_synthesis.section_orchestrator.BlueprintService", return_value=mock_blueprint_service):
        with patch("src.orchestrator.section_synthesis.section_orchestrator.ProjectService", return_value=mock_project_service):
            with patch("src.orchestrator.section_synthesis.section_orchestrator.RetrievalService", return_value=mock_retrieval_service):
                with patch("src.orchestrator.section_synthesis.section_orchestrator.AnalyticalNotesService", return_value=mock_notes_service):
                    with patch("src.orchestrator.section_synthesis.section_orchestrator.SectionSynthesisService", return_value=mock_synthesis_service):
                        with patch("src.orchestrator.section_synthesis.section_orchestrator.call_expert_with_fallback") as mock_llm:
                            mock_llm.side_effect = [
                                (mock_synthesizer_response, {}),  # Synthesizer
                                (mock_critic_response, {}),  # Critic
                            ]
                            
                            with patch("src.orchestrator.section_synthesis.section_orchestrator.get_vocab_guard", return_value=None):
                                results = run_section_synthesis(
                                    project_id="test-project-123",
                                    section_id="section-1",
                                    ingestion_id="ingestion-456",
                                    db=mock_db,
                                )
    
    # Verify persist_section_run was called with correct block structure
    call_args = mock_synthesis_service.persist_section_run.call_args
    section_block = call_args[1]["section_draft"]  # Get section_draft from kwargs
    
    # Assert: chunk_ids contains chunk citations, claim_ids is empty
    assert len(section_block.chunk_ids) > 0, "chunk_ids should contain chunk citations"
    assert "chunk-123" in section_block.chunk_ids or "chunk-456" in section_block.chunk_ids, "chunk_ids should contain extracted chunk IDs"
    assert len(section_block.claim_ids) == 0, "claim_ids should be empty (no actual KG claim IDs)"
    assert len(section_block.citation_keys) == 0, "citation_keys should be empty (reserved for BibTeX)"


def test_librarian_guard_passes_with_chunk_ids():
    """Test that Librarian guard passes when block has chunk_ids but no citation_keys."""
    from src.manuscript.service import ManuscriptService
    from src.shared.schema import ManuscriptBlock
    from arango.database import StandardDatabase
    from unittest.mock import Mock, patch
    
    # Create a section block with chunk_ids but no citation_keys
    block = ManuscriptBlock(
        block_id="test-block-123",
        section_title="Test Section",
        content="Section text with [[chunk:chunk-123]] citation.",
        claim_ids=[],  # Empty - no actual KG claim IDs
        citation_keys=[],  # Empty - no BibTeX keys
        chunk_ids=["chunk-123", "chunk-456"],  # Chunk citations
        project_id="test-project-123",
    )
    
    # Mock database
    mock_db = Mock(spec=StandardDatabase)
    mock_db.has_collection = Mock(return_value=True)
    mock_collection = Mock()
    mock_db.collection = Mock(return_value=mock_collection)
    mock_collection.get = Mock(return_value=None)  # No existing block
    mock_collection.insert = Mock(return_value={"_id": "test-id", "_key": "test-key"})
    
    # Mock AQL query for version lookup
    mock_cursor = Mock()
    mock_cursor.__iter__ = Mock(return_value=iter([]))  # No existing versions
    mock_db.aql.execute = Mock(return_value=mock_cursor)
    
    service = ManuscriptService(mock_db)
    
    # Should not raise ValueError (guard should skip validation for section blocks)
    try:
        saved_block = service.save_block(block, "test-project-123", validate_citations=True)
        assert saved_block is not None
        assert len(saved_block.chunk_ids) == 2
        assert len(saved_block.claim_ids) == 0
        assert len(saved_block.citation_keys) == 0
    except ValueError as e:
        if "Citation keys not found" in str(e):
            pytest.fail(f"Librarian guard should skip validation for section blocks with chunk_ids: {e}")
        else:
            raise
