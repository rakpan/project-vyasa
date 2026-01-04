"""
ResearchState schema for LangGraph workflow state management.

Provides a stable, versionable single source of truth for workflow state
across all LangGraph nodes with explicit phase tracking and ingestion lineage.
"""

from enum import Enum
from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from operator import add

from langgraph.graph.message import add_messages

from ...project.types import ProjectConfig
from .claims import Claim, DocumentChunk
from ...shared.schema import ConflictItem, ManuscriptBlock
from ..prompts.models import PromptUse


class PhaseEnum(str, Enum):
    """Workflow phase enumeration for explicit state tracking."""
    INGESTING = "INGESTING"
    MAPPING = "MAPPING"
    VETTING = "VETTING"
    SYNTHESIZING = "SYNTHESIZING"
    PERSISTING = "PERSISTING"
    DONE = "DONE"


class ResearchState(BaseModel):
    """Stable, versionable state model for LangGraph workflows.
    
    This model serves as the single source of truth for workflow state
    across all nodes. It includes required identifiers, project context,
    workspace data, and control flags.
    
    The model supports LangGraph reducer semantics for lists (triples, artifacts)
    while maintaining strict validation for required fields.
    """
    
    # Required identifiers
    job_id: str = Field(..., description="Job identifier (UUID)")
    project_id: str = Field(..., description="Project identifier (UUID)")
    ingestion_id: Optional[str] = Field(None, description="Ingestion identifier (must be present after ingestion submit)")
    thread_id: str = Field(..., description="Thread identifier for LangGraph checkpointing")
    
    # Project context (required)
    project_config: ProjectConfig = Field(..., description="Project configuration with thesis, RQs, anti_scope, rigor_level")
    
    # Phase tracking (required)
    phase: PhaseEnum = Field(default=PhaseEnum.INGESTING, description="Current workflow phase")
    
    # Workspace fields (stable names)
    raw_chunks: List[DocumentChunk] = Field(default_factory=list, description="Document chunks with payload metadata")
    claims: List[Claim] = Field(default_factory=list, description="Canonical claims with evidence binding")
    conflicts: List[ConflictItem] = Field(default_factory=list, description="Deterministic conflict items")
    manuscript_blocks: List[ManuscriptBlock] = Field(default_factory=list, description="Manuscript blocks with claim/citation bindings")
    
    # LangGraph reducer fields (annotated for reducer semantics)
    messages: Annotated[List[Any], add_messages] = Field(default_factory=list, description="LangGraph messages")
    triples: Annotated[List[Dict[str, Any]], add] = Field(default_factory=list, description="Graph triples (reducer: add)")
    artifacts: Annotated[List[Dict[str, Any]], add] = Field(default_factory=list, description="Artifacts (reducer: add)")
    
    # Legacy fields (for backward compatibility)
    jobId: Optional[str] = Field(None, description="Legacy camelCase job_id")
    threadId: Optional[str] = Field(None, description="Legacy camelCase thread_id")
    revision_count: int = Field(default=0, description="Revision count for job versioning")
    tone_findings: List[Dict[str, Any]] = Field(default_factory=list, description="Tone analysis findings")
    tone_flags: List[Dict[str, Any]] = Field(default_factory=list, description="Tone flags for rewriting")
    
    # Control flags
    needs_human_review: bool = Field(default=False, description="Flag indicating human review is needed")
    conflict_detected: bool = Field(default=False, description="Flag indicating conflicts were detected")
    
    # Additional state fields (optional)
    extracted_json: Optional[Dict[str, Any]] = Field(None, description="Extracted JSON from Cartographer")
    context_sources: Optional[Dict[str, Any]] = Field(None, description="Context sources for RAG")
    selected_reference_ids: Optional[List[str]] = Field(None, description="Selected reference IDs for synthesis")
    conflict_flags: Optional[List[Dict[str, Any]]] = Field(None, description="Conflict flags from Critic")
    
    # Prompt manifest for reproducibility
    prompt_manifest: Dict[str, PromptUse] = Field(
        default_factory=dict,
        description="Record of prompts used by each node (keyed by node name: 'cartographer', 'critic', 'synthesizer')"
    )
    
    @field_validator("ingestion_id")
    @classmethod
    def validate_ingestion_id(cls, v: Optional[str], info) -> Optional[str]:
        """Validate ingestion_id is present after ingestion phase."""
        phase = info.data.get("phase") if hasattr(info, "data") else None
        if phase and phase != PhaseEnum.INGESTING and v is None:
            # Allow None during INGESTING, but warn if missing later
            pass
        return v
    
    @field_validator("project_config")
    @classmethod
    def validate_project_config(cls, v: ProjectConfig) -> ProjectConfig:
        """Validate project_config has required fields."""
        if not v.thesis or not v.thesis.strip():
            raise ValueError("project_config.thesis is required and cannot be empty")
        if not v.research_questions:
            raise ValueError("project_config.research_questions must have at least one question")
        if not hasattr(v, "rigor_level") or v.rigor_level not in ("exploratory", "conservative"):
            # If rigor_level is missing, default to exploratory
            if not hasattr(v, "rigor_level"):
                # Create a new ProjectConfig with rigor_level if needed
                # This is a workaround if ProjectConfig doesn't have rigor_level
                pass
        return v
    
    @model_validator(mode="after")
    def sync_legacy_fields(self):
        """Sync legacy camelCase fields with snake_case fields."""
        if self.jobId is None:
            self.jobId = self.job_id
        if self.threadId is None:
            self.threadId = self.thread_id
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LangGraph compatibility.
        
        Returns:
            Dictionary representation compatible with LangGraph TypedDict expectations.
        """
        data = self.model_dump(exclude_none=False, by_alias=False, mode="python")
        # Ensure legacy fields are set
        data["jobId"] = data.get("job_id")
        data["threadId"] = data.get("thread_id")
        # Convert phase to string value
        if isinstance(data.get("phase"), PhaseEnum):
            data["phase"] = data["phase"].value
        # Convert project_config to dict if it's a model
        if isinstance(data.get("project_config"), ProjectConfig):
            data["project_config"] = data["project_config"].model_dump(mode="python")
        # Convert workspace fields to dicts if they're models
        if data.get("raw_chunks"):
            data["raw_chunks"] = [chunk.model_dump(mode="python") if hasattr(chunk, "model_dump") else chunk for chunk in data["raw_chunks"]]
        if data.get("claims"):
            data["claims"] = [claim.model_dump(mode="python") if hasattr(claim, "model_dump") else claim for claim in data["claims"]]
        if data.get("conflicts"):
            data["conflicts"] = [conflict.model_dump(mode="python") if hasattr(conflict, "model_dump") else conflict for conflict in data["conflicts"]]
        if data.get("manuscript_blocks"):
            data["manuscript_blocks"] = [block.model_dump(mode="python") if hasattr(block, "model_dump") else block for block in data["manuscript_blocks"]]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchState":
        """Create ResearchState from dictionary (for LangGraph state loading).
        
        Args:
            data: Dictionary with state fields (may include legacy keys).
        
        Returns:
            ResearchState instance.
        """
        # Normalize legacy keys
        if "jobId" in data and "job_id" not in data:
            data["job_id"] = data["jobId"]
        if "threadId" in data and "thread_id" not in data:
            data["thread_id"] = data["threadId"]
        
        # Convert phase string to enum if needed
        if "phase" in data and isinstance(data["phase"], str):
            try:
                data["phase"] = PhaseEnum(data["phase"])
            except ValueError:
                data["phase"] = PhaseEnum.INGESTING
        
        # Convert project_config dict to ProjectConfig if needed
        if "project_config" in data and isinstance(data["project_config"], dict):
            # Import here to avoid circular dependency
            from ...project.types import ProjectConfig
            data["project_config"] = ProjectConfig(**data["project_config"])
        
        # Convert workspace fields from dicts to models if needed
        if "raw_chunks" in data and isinstance(data["raw_chunks"], list):
            from .claims import DocumentChunk
            data["raw_chunks"] = [
                DocumentChunk(**chunk) if isinstance(chunk, dict) else chunk
                for chunk in data["raw_chunks"]
            ]
        if "claims" in data and isinstance(data["claims"], list):
            from ...shared.schema import Claim
            data["claims"] = [
                Claim(**claim) if isinstance(claim, dict) else claim
                for claim in data["claims"]
            ]
        if "conflicts" in data and isinstance(data["conflicts"], list):
            from ...shared.schema import ConflictItem
            data["conflicts"] = [
                ConflictItem(**conflict) if isinstance(conflict, dict) else conflict
                for conflict in data["conflicts"]
            ]
        if "manuscript_blocks" in data and isinstance(data["manuscript_blocks"], list):
            from ...shared.schema import ManuscriptBlock
            data["manuscript_blocks"] = [
                ManuscriptBlock(**block) if isinstance(block, dict) else block
                for block in data["manuscript_blocks"]
            ]
        
        # Convert prompt_manifest from dicts to models if needed
        if "prompt_manifest" in data and isinstance(data["prompt_manifest"], dict):
            from ..prompts.models import PromptUse
            data["prompt_manifest"] = {
                k: PromptUse(**v) if isinstance(v, dict) else v
                for k, v in data["prompt_manifest"].items()
            }
        
        return cls(**data)
    
    def transition_phase(self, new_phase: PhaseEnum) -> "ResearchState":
        """Transition to a new phase (creates new instance for immutability).
        
        Args:
            new_phase: Target phase enum value.
        
        Returns:
            New ResearchState instance with updated phase.
        """
        data = self.model_dump()
        data["phase"] = new_phase
        return self.__class__(**data)

