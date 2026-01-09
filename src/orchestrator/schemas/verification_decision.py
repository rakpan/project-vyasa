"""
VerificationDecision schema for Project Vyasa.

VerificationDecision represents the Critic's bounded spot-check verification
of claims/triples against EvidencePack snippets.

Decisions are persisted with full provenance for reproducibility and audit.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class VerificationDecision(str, Enum):
    """Verification decision types."""
    VERIFIED = "Verified"
    UNSUPPORTED = "Unsupported"
    CONTRADICTED = "Contradicted"
    AMBIGUOUS = "Ambiguous"


class VerificationDecisionRecord(BaseModel):
    """Verification decision record for a single claim/triple.
    
    Persisted with full provenance to retrieval_bundle_id and evidence_pack_id
    for reproducibility and audit.
    """
    # Identifiers
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique decision identifier")
    claim_id: str = Field(..., description="Claim/triple identifier being verified")
    
    # Decision
    decision: VerificationDecision = Field(..., description="Verification decision")
    rationale: str = Field(..., max_length=500, description="Short rationale for the decision")
    
    # Supporting evidence (1-3 chunk IDs from EvidencePack)
    supporting_chunk_ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=3,
        description="Chunk IDs from EvidencePack that support this decision (1-3)"
    )
    
    # Bounded retry flag
    bounded_retry_used: bool = Field(
        default=False,
        description="True if a bounded retry (one extra snippet) was used for Ambiguous decisions"
    )
    
    # Provenance (required for reproducibility)
    project_id: str = Field(..., description="Project identifier")
    ingestion_id: str = Field(..., description="Ingestion identifier")
    evidence_pack_id: str = Field(..., description="EvidencePack ID used for verification")
    retrieval_bundle_id: str = Field(..., description="RetrievalBundle ID used for verification")
    
    # Timestamp
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp of decision")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }
