"""
Unit tests for ResearchState contract validation and phase transitions.

Tests ensure:
- Required fields are validated
- Phase transitions are enforced through enum
- Serialization round-trip is stable
"""

import pytest
from pydantic import ValidationError

from src.orchestrator.schemas.state import ResearchState, PhaseEnum
from src.orchestrator.schemas.claims import DocumentChunk
from src.project.types import ProjectConfig
from src.shared.schema import Claim, SourcePointer, ConflictItem, ConflictType, ConflictSeverity, ConflictProducer, ManuscriptBlock


@pytest.fixture
def sample_project_config():
    """Sample ProjectConfig for testing."""
    from datetime import datetime
    return ProjectConfig(
        id="test-project-123",
        title="Test Project",
        thesis="This is a test thesis statement.",
        research_questions=["What is the research question?"],
        anti_scope=["Out of scope topic"],
        rigor_level="exploratory",
        created_at=datetime.now().isoformat(),
    )


@pytest.fixture
def sample_source_pointer():
    """Sample SourcePointer for testing."""
    return SourcePointer(
        doc_hash="a" * 64,
        page=1,
        bbox=[100, 200, 300, 400],
        snippet="Sample text snippet",
    )


@pytest.fixture
def sample_claim(sample_source_pointer):
    """Sample Claim for testing."""
    return Claim(
        text="Test claim text",
        confidence=0.9,
        source_pointer=sample_source_pointer,
        project_id="test-project-123",
        doc_hash="a" * 64,
        is_expert_verified=False,
    )


class TestResearchStateInstantiation:
    """Test ResearchState instantiation and validation."""
    
    def test_required_fields_validation(self, sample_project_config):
        """Test that required fields are validated."""
        # Missing job_id should fail
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                project_id="test-project-123",
                thread_id="test-thread-123",
                project_config=sample_project_config,
            )
        assert "job_id" in str(exc_info.value)
        
        # Missing project_id should fail
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                job_id="test-job-123",
                thread_id="test-thread-123",
                project_config=sample_project_config,
            )
        assert "project_id" in str(exc_info.value)
        
        # Missing thread_id should fail
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                job_id="test-job-123",
                project_id="test-project-123",
                project_config=sample_project_config,
            )
        assert "thread_id" in str(exc_info.value)
        
        # Missing project_config should fail
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                job_id="test-job-123",
                project_id="test-project-123",
                thread_id="test-thread-123",
            )
        assert "project_config" in str(exc_info.value)
    
    def test_valid_instantiation(self, sample_project_config):
        """Test that valid ResearchState can be instantiated."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
        )
        
        assert state.job_id == "test-job-123"
        assert state.project_id == "test-project-123"
        assert state.thread_id == "test-thread-123"
        assert state.project_config.id == "test-project-123"
        assert state.phase == PhaseEnum.INGESTING  # Default phase
    
    def test_ingestion_id_optional(self, sample_project_config):
        """Test that ingestion_id is optional."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            ingestion_id=None,
        )
        
        assert state.ingestion_id is None
    
    def test_ingestion_id_present(self, sample_project_config):
        """Test that ingestion_id can be set."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            ingestion_id="ingestion-123",
        )
        
        assert state.ingestion_id == "ingestion-123"
    
    def test_project_config_validation(self, sample_project_config):
        """Test that project_config validation works."""
        # Empty thesis should fail
        invalid_config = ProjectConfig(
            id="test-project-123",
            title="Test",
            thesis="",  # Empty thesis
            research_questions=["RQ1"],
            rigor_level="exploratory",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                job_id="test-job-123",
                project_id="test-project-123",
                thread_id="test-thread-123",
                project_config=invalid_config,
            )
        assert "thesis" in str(exc_info.value).lower()
        
        # No research questions should fail
        invalid_config2 = ProjectConfig(
            id="test-project-123",
            title="Test",
            thesis="Valid thesis",
            research_questions=[],  # Empty RQs
            rigor_level="exploratory",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ResearchState(
                job_id="test-job-123",
                project_id="test-project-123",
                thread_id="test-thread-123",
                project_config=invalid_config2,
            )
        assert "research_questions" in str(exc_info.value).lower()


class TestPhaseTransitions:
    """Test phase enum and transitions."""
    
    def test_phase_enum_values(self):
        """Test that PhaseEnum has correct values."""
        assert PhaseEnum.INGESTING == "INGESTING"
        assert PhaseEnum.MAPPING == "MAPPING"
        assert PhaseEnum.VETTING == "VETTING"
        assert PhaseEnum.SYNTHESIZING == "SYNTHESIZING"
        assert PhaseEnum.PERSISTING == "PERSISTING"
        assert PhaseEnum.DONE == "DONE"
    
    def test_phase_default(self, sample_project_config):
        """Test that phase defaults to INGESTING."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
        )
        
        assert state.phase == PhaseEnum.INGESTING
    
    def test_phase_transition(self, sample_project_config):
        """Test that phase can be transitioned."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            phase=PhaseEnum.INGESTING,
        )
        
        # Transition to MAPPING
        new_state = state.transition_phase(PhaseEnum.MAPPING)
        assert new_state.phase == PhaseEnum.MAPPING
        assert state.phase == PhaseEnum.INGESTING  # Original unchanged (immutability)
        
        # Transition to VETTING
        new_state2 = new_state.transition_phase(PhaseEnum.VETTING)
        assert new_state2.phase == PhaseEnum.VETTING
    
    def test_invalid_phase_string(self, sample_project_config):
        """Test that invalid phase string raises error."""
        with pytest.raises(ValueError):
            ResearchState(
                job_id="test-job-123",
                project_id="test-project-123",
                thread_id="test-thread-123",
                project_config=sample_project_config,
                phase="INVALID_PHASE",  # type: ignore
            )


class TestWorkspaceFields:
    """Test workspace fields (raw_chunks, claims, conflicts, manuscript_blocks)."""
    
    def test_raw_chunks(self, sample_project_config):
        """Test raw_chunks field."""
        chunk = DocumentChunk(
            text="Sample chunk text",
            doc_hash="a" * 64,
            page=1,
            chunk_index=0,
            metadata={"source": "test.pdf"},
        )
        
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            raw_chunks=[chunk],
        )
        
        assert len(state.raw_chunks) == 1
        assert state.raw_chunks[0].text == "Sample chunk text"
        assert state.raw_chunks[0].doc_hash == "a" * 64
    
    def test_claims(self, sample_project_config, sample_claim):
        """Test claims field."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            claims=[sample_claim],
        )
        
        assert len(state.claims) == 1
        assert state.claims[0].text == "Test claim text"
        assert state.claims[0].confidence == 0.9
    
    def test_conflicts(self, sample_project_config):
        """Test conflicts field."""
        conflict = ConflictItem(
            conflict_id="conflict-123",
            conflict_type=ConflictType.STRUCTURAL_CONFLICT,
            severity=ConflictSeverity.HIGH,
            summary="Test conflict summary",
            details="Test conflict details",
            produced_by=ConflictProducer.CRITIC,
            confidence=0.8,
        )
        
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            conflicts=[conflict],
        )
        
        assert len(state.conflicts) == 1
        assert state.conflicts[0].conflict_id == "conflict-123"
        assert state.conflicts[0].severity == ConflictSeverity.HIGH
    
    def test_manuscript_blocks(self, sample_project_config):
        """Test manuscript_blocks field."""
        block = ManuscriptBlock(
            block_id="block-123",
            section_title="Introduction",
            content="# Introduction\n\nTest content",
            order_index=0,
            claim_ids=["claim-1", "claim-2"],
            citation_keys=["smith2023"],
            project_id="test-project-123",
        )
        
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            manuscript_blocks=[block],
        )
        
        assert len(state.manuscript_blocks) == 1
        assert state.manuscript_blocks[0].block_id == "block-123"
        assert len(state.manuscript_blocks[0].claim_ids) == 2


class TestControlFlags:
    """Test control flags (needs_human_review, conflict_detected)."""
    
    def test_control_flags_default_false(self, sample_project_config):
        """Test that control flags default to False."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
        )
        
        assert state.needs_human_review is False
        assert state.conflict_detected is False
    
    def test_control_flags_can_be_set(self, sample_project_config):
        """Test that control flags can be set."""
        state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            needs_human_review=True,
            conflict_detected=True,
        )
        
        assert state.needs_human_review is True
        assert state.conflict_detected is True


class TestSerializationRoundTrip:
    """Test serialization round-trip stability."""
    
    def test_serialization_round_trip(self, sample_project_config):
        """Test that serialization and deserialization are stable."""
        original_state = ResearchState(
            job_id="test-job-123",
            project_id="test-project-123",
            thread_id="test-thread-123",
            project_config=sample_project_config,
            ingestion_id="ingestion-123",
            phase=PhaseEnum.MAPPING,
            needs_human_review=True,
            conflict_detected=False,
        )
        
        # Serialize to dict
        state_dict = original_state.to_dict()
        
        # Deserialize from dict
        restored_state = ResearchState.from_dict(state_dict)
        
        # Verify fields match
        assert restored_state.job_id == original_state.job_id
        assert restored_state.project_id == original_state.project_id
        assert restored_state.thread_id == original_state.thread_id
        assert restored_state.ingestion_id == original_state.ingestion_id
        assert restored_state.phase == original_state.phase
        assert restored_state.needs_human_review == original_state.needs_human_review
        assert restored_state.conflict_detected == original_state.conflict_detected
        assert restored_state.project_config.id == original_state.project_config.id
        assert restored_state.project_config.thesis == original_state.project_config.thesis
    
    def test_legacy_key_compatibility(self, sample_project_config):
        """Test that legacy camelCase keys are handled."""
        # Create state with legacy keys
        legacy_dict = {
            "jobId": "test-job-123",
            "threadId": "test-thread-123",
            "project_id": "test-project-123",
            "project_config": sample_project_config.model_dump(),
            "phase": "MAPPING",
        }
        
        state = ResearchState.from_dict(legacy_dict)
        
        # Verify both snake_case and camelCase are set
        assert state.job_id == "test-job-123"
        assert state.thread_id == "test-thread-123"
        assert state.jobId == "test-job-123"  # Legacy field synced
        assert state.threadId == "test-thread-123"  # Legacy field synced
    
    def test_phase_string_to_enum(self, sample_project_config):
        """Test that phase string is converted to enum."""
        state_dict = {
            "job_id": "test-job-123",
            "project_id": "test-project-123",
            "thread_id": "test-thread-123",
            "project_config": sample_project_config.model_dump(),
            "phase": "VETTING",  # String value
        }
        
        state = ResearchState.from_dict(state_dict)
        
        assert isinstance(state.phase, PhaseEnum)
        assert state.phase == PhaseEnum.VETTING

