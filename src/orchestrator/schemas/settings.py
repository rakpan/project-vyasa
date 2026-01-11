"""
Settings and Prompt Profile schemas for Project Vyasa.

Defines data models for:
- system_settings: Runtime budgets, manuscript defaults, feature flags
- prompt_profiles: Versioned prompt templates with constraints
- active_prompt_set: Active version mapping for prompt profiles
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class TierABudgets(BaseModel):
    """Tier A (CPU/Embedder-bound) runtime budgets."""
    retrieval_top_k: int = Field(default=64, ge=1, le=256, description="Top-K chunks to retrieve from Qdrant")
    rerank_top_m: int = Field(default=24, ge=1, le=64, description="Top-M chunks after reranking")
    candidate_trunc_tokens: int = Field(default=600, ge=100, le=2000, description="Max tokens per candidate chunk")
    snippet_min_tokens: int = Field(default=50, ge=10, le=500, description="Min tokens per snippet")
    snippet_max_tokens: int = Field(default=800, ge=100, le=2000, description="Max tokens per snippet")
    max_snippets: int = Field(default=20, ge=5, le=50, description="Max snippets in EvidencePack")


class TierBBudgets(BaseModel):
    """Tier B (GPU/Nemotron-49B-bound) runtime budgets."""
    shared_prefix_max_tokens: int = Field(default=4096, ge=0, le=16384, description="Max tokens for shared prefix (KV cache reuse)")
    packet_a_max_tokens: int = Field(default=8192, ge=1000, le=32768, description="Max tokens for Packet A (EvidencePack)")
    packet_b_max_tokens: int = Field(default=2048, ge=500, le=8192, description="Max tokens for Packet B (Analytical Notes)")
    output_max_tokens_by_agent: Dict[str, int] = Field(
        default_factory=lambda: {
            "synthesizer": 4096,
            "critic": 2048,
            "cartographer_pass2": 4096,
        },
        description="Max output tokens per agent type"
    )
    critic_bounded_retry_max: int = Field(default=1, ge=0, le=3, description="Max bounded retries for Critic verification")


class RuntimeBudgets(BaseModel):
    """Runtime budget configuration for Tier A and Tier B."""
    tier_a: TierABudgets = Field(default_factory=TierABudgets)
    tier_b: TierBBudgets = Field(default_factory=TierBBudgets)


class CitationStyle(BaseModel):
    """Citation style configuration."""
    numeric_superscript: bool = Field(default=True, description="Use numeric superscripts (e.g., [1], [2])")
    order_of_appearance: bool = Field(default=True, description="Number citations by order of appearance")


class LockingDefaults(BaseModel):
    """Manuscript locking defaults."""
    locked_sections_immutable: bool = Field(default=True, description="Locked sections cannot be modified by synthesis")
    allow_citation_reindexing_without_text_change: bool = Field(
        default=False,
        description="Allow citation renumbering without text modification"
    )


class ManuscriptDefaults(BaseModel):
    """Manuscript generation defaults."""
    word_limit_total: int = Field(default=8000, ge=1000, le=50000, description="Total word limit for manuscript")
    abstract_word_limit: int = Field(default=250, ge=100, le=500, description="Word limit for abstract")
    abstract_char_limit: int = Field(default=1500, ge=500, le=3000, description="Character limit for abstract")
    max_tables: int = Field(default=10, ge=0, le=50, description="Max number of tables")
    max_figures: int = Field(default=10, ge=0, le=50, description="Max number of figures")
    citation_style: CitationStyle = Field(default_factory=CitationStyle)
    locking_defaults: LockingDefaults = Field(default_factory=LockingDefaults)


class FeatureFlags(BaseModel):
    """Feature flag configuration."""
    reranker_enabled_default: bool = Field(default=True, description="Default reranker enabled state")
    vision_enabled_default: bool = Field(default=False, description="Default vision enabled state")
    reranker_required_for_sections: bool = Field(default=False, description="Reranker required for section synthesis")
    vision_triage_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "confidence_min": 0.5,
            "relevance_min": 0.6,
        },
        description="Vision triage thresholds"
    )


class SystemSettings(BaseModel):
    """System-wide settings (single document in ArangoDB)."""
    key: str = Field(default="system_settings", alias="_key", description="ArangoDB document key (singleton)")
    runtime_budgets: RuntimeBudgets = Field(default_factory=RuntimeBudgets)
    manuscript_defaults: ManuscriptDefaults = Field(default_factory=ManuscriptDefaults)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = Field(default=None, description="User/system that last updated settings")
    
    model_config = {"populate_by_name": True}  # Allow access by both 'key' and '_key'


class PromptConstraints(BaseModel):
    """Constraints for prompt profiles."""
    citation_token_format: Optional[str] = Field(
        default=r"\cite{chunk:<id>}",
        description="Required citation token format (regex pattern)"
    )
    bounded_retry: bool = Field(default=False, description="Allow bounded retry on ambiguous results")
    packet_a_facts_only: bool = Field(default=True, description="Only cite facts from Packet A (EvidencePack)")
    require_claim_ids: bool = Field(default=False, description="Require claim_ids in output")
    max_output_length: Optional[int] = Field(default=None, ge=1, description="Max output length in tokens")


class PromptProfile(BaseModel):
    """A versioned prompt profile."""
    key: str = Field(..., alias="_key", description="ArangoDB document key: {prompt_id}_v{version}")
    prompt_id: str = Field(..., description="Prompt identifier (e.g., 'critic_verify', 'synthesizer_section_writer')")
    version: int = Field(..., ge=1, description="Version number (auto-incremented per prompt_id)")
    template: str = Field(..., min_length=1, description="Prompt template text")
    output_type: str = Field(..., pattern="^(json|markdown)$", description="Output type: 'json' or 'markdown'")
    required_fields: List[str] = Field(default_factory=list, description="Required fields for JSON output")
    constraints: PromptConstraints = Field(default_factory=PromptConstraints)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = Field(default=None, description="User/system that created this version")
    
    model_config = {"populate_by_name": True}  # Allow access by both 'key' and '_key'
    
    # Validation status (for activation gating)
    validation_status: Optional[str] = Field(
        default=None,
        description="Validation status: 'valid', 'invalid', or None (not validated)"
    )
    validation_timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last validation (UTC)"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors (empty if valid)"
    )
    
    @field_validator("required_fields")
    @classmethod
    def validate_required_fields_for_json(cls, v: List[str], info) -> List[str]:
        """Validate that required_fields is non-empty for JSON output type."""
        if info.data.get("output_type") == "json" and not v:
            raise ValueError("required_fields must be non-empty for output_type='json'")
        return v


class ActivePromptSet(BaseModel):
    """Active prompt version mapping (single document in ArangoDB)."""
    key: str = Field(default="active_prompt_set", alias="_key", description="ArangoDB document key (singleton)")
    active_versions: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of prompt_id -> active version number"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = Field(default=None, description="User/system that last updated active versions")
    
    model_config = {"populate_by_name": True}  # Allow access by both 'key' and '_key'