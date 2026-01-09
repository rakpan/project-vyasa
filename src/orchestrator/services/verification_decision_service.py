"""
VerificationDecision Service for Project Vyasa.

Handles persistence of VerificationDecision records (Critic's bounded spot-check verification).
"""

from typing import List, Optional
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.verification_decision import VerificationDecisionRecord
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

VERIFICATION_DECISIONS_COLLECTION = "verification_decisions"


class VerificationDecisionService:
    """Service for managing VerificationDecision records."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the verification decision service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(VERIFICATION_DECISIONS_COLLECTION):
            self.db.create_collection(VERIFICATION_DECISIONS_COLLECTION)
            logger.info(f"Created collection: {VERIFICATION_DECISIONS_COLLECTION}")
        
        coll = self.db.collection(VERIFICATION_DECISIONS_COLLECTION)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["decision_id"], unique=True)
            coll.ensure_persistent_index(["claim_id"])
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["ingestion_id"])
            coll.ensure_persistent_index(["evidence_pack_id"])
            coll.ensure_persistent_index(["retrieval_bundle_id"])
            # Composite indexes for common queries
            coll.ensure_persistent_index(["project_id", "claim_id"])
            coll.ensure_persistent_index(["project_id", "ingestion_id"])
            coll.ensure_persistent_index(["evidence_pack_id", "claim_id"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def save_decision(
        self,
        decision: VerificationDecisionRecord,
    ) -> VerificationDecisionRecord:
        """Save a VerificationDecision record.
        
        Args:
            decision: VerificationDecisionRecord to save.
        
        Returns:
            Saved VerificationDecisionRecord with ArangoDB fields populated.
        
        Raises:
            ArangoError: If database operation fails.
        """
        # Ensure timestamp is set
        if not decision.created_at:
            decision.created_at = datetime.now(timezone.utc).isoformat()
        
        # Generate document key
        doc_key = decision.decision_id
        
        # Convert to dict for ArangoDB
        doc = decision.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(VERIFICATION_DECISIONS_COLLECTION)
        result = coll.insert(doc)
        
        logger.debug(
            f"Saved VerificationDecision",
            extra={
                "payload": {
                    "decision_id": decision.decision_id,
                    "claim_id": decision.claim_id,
                    "decision": decision.decision.value,
                    "evidence_pack_id": decision.evidence_pack_id,
                    "retrieval_bundle_id": decision.retrieval_bundle_id,
                }
            }
        )
        
        return decision
    
    def get_decision(
        self,
        decision_id: str,
    ) -> Optional[VerificationDecisionRecord]:
        """Get VerificationDecision by ID.
        
        Args:
            decision_id: VerificationDecision identifier.
        
        Returns:
            VerificationDecisionRecord if found, None otherwise.
        """
        try:
            coll = self.db.collection(VERIFICATION_DECISIONS_COLLECTION)
            doc = coll.get(decision_id)
            
            if not doc:
                return None
            
            # Remove ArangoDB metadata
            doc.pop("_key", None)
            doc.pop("_id", None)
            doc.pop("_rev", None)
            
            return VerificationDecisionRecord(**doc)
        except ArangoError as e:
            logger.warning(f"Failed to get VerificationDecision {decision_id}: {e}", exc_info=True)
            return None
    
    def get_decisions_by_claim(
        self,
        claim_id: str,
        project_id: Optional[str] = None,
    ) -> List[VerificationDecisionRecord]:
        """Get VerificationDecisions for a specific claim.
        
        Args:
            claim_id: Claim identifier.
            project_id: Optional project identifier for filtering.
        
        Returns:
            List of VerificationDecisionRecords for the claim (most recent first).
        """
        try:
            coll = self.db.collection(VERIFICATION_DECISIONS_COLLECTION)
            # Query by claim_id (and optionally project_id)
            if project_id:
                query = f"""
                FOR decision IN {VERIFICATION_DECISIONS_COLLECTION}
                FILTER decision.claim_id == @claim_id AND decision.project_id == @project_id
                SORT decision.created_at DESC
                RETURN decision
                """
                cursor = self.db.aql.execute(query, bind_vars={"claim_id": claim_id, "project_id": project_id})
            else:
                query = f"""
                FOR decision IN {VERIFICATION_DECISIONS_COLLECTION}
                FILTER decision.claim_id == @claim_id
                SORT decision.created_at DESC
                RETURN decision
                """
                cursor = self.db.aql.execute(query, bind_vars={"claim_id": claim_id})
            
            results = list(cursor)
            
            decisions = []
            for doc in results:
                # Remove ArangoDB metadata
                doc.pop("_key", None)
                doc.pop("_id", None)
                doc.pop("_rev", None)
                
                decisions.append(VerificationDecisionRecord(**doc))
            
            return decisions
        except ArangoError as e:
            logger.warning(f"Failed to get VerificationDecisions for claim {claim_id}: {e}", exc_info=True)
            return []
    
    def get_decisions_by_evidence_pack(
        self,
        evidence_pack_id: str,
    ) -> List[VerificationDecisionRecord]:
        """Get VerificationDecisions for a specific EvidencePack.
        
        Args:
            evidence_pack_id: EvidencePack identifier.
        
        Returns:
            List of VerificationDecisionRecords for the EvidencePack.
        """
        try:
            coll = self.db.collection(VERIFICATION_DECISIONS_COLLECTION)
            query = f"""
            FOR decision IN {VERIFICATION_DECISIONS_COLLECTION}
            FILTER decision.evidence_pack_id == @evidence_pack_id
            SORT decision.created_at DESC
            RETURN decision
            """
            cursor = self.db.aql.execute(query, bind_vars={"evidence_pack_id": evidence_pack_id})
            results = list(cursor)
            
            decisions = []
            for doc in results:
                # Remove ArangoDB metadata
                doc.pop("_key", None)
                doc.pop("_id", None)
                doc.pop("_rev", None)
                
                decisions.append(VerificationDecisionRecord(**doc))
            
            return decisions
        except ArangoError as e:
            logger.warning(f"Failed to get VerificationDecisions for EvidencePack {evidence_pack_id}: {e}", exc_info=True)
            return []
