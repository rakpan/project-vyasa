"""
Knowledge Synthesis Service for Project Vyasa.

Implements the "Global Repository" pattern: merges expert-verified claims
from finalized projects into a canonical knowledge base.

Key responsibilities:
- Entity Resolution: Match new claims against existing canonical knowledge
- Conflict Detection: Flag contradictions for systemic review
- Provenance Tracking: Maintain audit trail of all contributing projects/jobs
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..shared.schema import (
    CanonicalKnowledge,
    ProvenanceEntry,
    SourcePointer,
    EntityType,
    RelationType,
)
from ..shared.logger import get_logger
from ..shared.config import (
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    get_arango_password,
    get_brain_url,
)
from ..shared.model_registry import get_model_config
import requests

logger = get_logger("orchestrator", __name__)

COLLECTION_NAME = "canonical_knowledge"


class SynthesisService:
    """Service for synthesizing verified claims into canonical knowledge."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the synthesis service.
        
        Args:
            db: ArangoDB database instance
        """
        self.db = db
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """Ensure the canonical_knowledge collection exists with proper indexes."""
        if not self.db.has_collection(COLLECTION_NAME):
            self.db.create_collection(COLLECTION_NAME)
            logger.info(f"Created collection: {COLLECTION_NAME}")
        
        coll = self.db.collection(COLLECTION_NAME)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["entity_id"], unique=True)
            coll.ensure_persistent_index(["entity_name"])
            coll.ensure_persistent_index(["entity_type"])
            coll.ensure_persistent_index(["created_at"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def finalize_project(
        self,
        project_id: str,
        job_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Finalize a project by merging its verified claims into canonical knowledge.
        
        Args:
            project_id: Project ID being finalized
            job_ids: List of job IDs from this project to process
        
        Returns:
            Dictionary with synthesis results:
            {
                "merged_count": int,
                "new_count": int,
                "conflict_count": int,
                "merged_entities": [...],
                "new_entities": [...],
                "conflicts": [...]
            }
        """
        logger.info(
            f"Finalizing project {project_id}",
            extra={"payload": {"project_id": project_id, "job_count": len(job_ids)}}
        )
        
        # Query all verified claims from these jobs
        verified_claims = self._get_verified_claims(project_id, job_ids)
        
        if not verified_claims:
            logger.warning(
                f"No verified claims found for project {project_id}",
                extra={"payload": {"project_id": project_id}}
            )
            return {
                "merged_count": 0,
                "new_count": 0,
                "conflict_count": 0,
                "merged_entities": [],
                "new_entities": [],
                "conflicts": [],
            }
        
        merged_count = 0
        new_count = 0
        conflict_count = 0
        merged_entities = []
        new_entities = []
        conflicts = []
        
        for claim in verified_claims:
            try:
                result = self._synthesize_claim(claim, project_id, claim.get("job_id", ""))
                
                if result["action"] == "merged":
                    merged_count += 1
                    merged_entities.append(result["entity_id"])
                elif result["action"] == "created":
                    new_count += 1
                    new_entities.append(result["entity_id"])
                elif result["action"] == "conflict":
                    conflict_count += 1
                    conflicts.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to synthesize claim: {e}",
                    extra={"payload": {"project_id": project_id, "claim": claim.get("subject", "unknown")}},
                    exc_info=True,
                )
        
        summary = {
            "merged_count": merged_count,
            "new_count": new_count,
            "conflict_count": conflict_count,
            "merged_entities": merged_entities,
            "new_entities": new_entities,
            "conflicts": conflicts,
        }
        
        logger.info(
            f"Project {project_id} finalized",
            extra={"payload": {"project_id": project_id, **summary}}
        )
        
        return summary
    
    def _get_verified_claims(self, project_id: str, job_ids: List[str]) -> List[Dict[str, Any]]:
        """Query all verified claims from the specified jobs.
        
        Args:
            project_id: Project ID
            job_ids: List of job IDs
        
        Returns:
            List of verified claim dictionaries
        """
        claims = []
        
        # Query extractions collection for verified triples
        if not self.db.has_collection("extractions"):
            return claims
        
        extractions_col = self.db.collection("extractions")
        
        # Build AQL query to find verified triples
        query = """
        FOR e IN extractions
        FILTER e.project_id == @project_id
        FOR triple IN e.graph.triples
        FILTER triple.is_expert_verified == true
        RETURN {
            subject: triple.subject,
            predicate: triple.predicate,
            object: triple.object,
            subject_type: triple.subject_type,
            object_type: triple.object_type,
            confidence: triple.confidence,
            source_pointer: triple.source_pointer,
            doc_hash: triple.doc_hash,
            project_id: e.project_id,
            job_id: e._key
        }
        """
        
        try:
            cursor = self.db.aql.execute(query, bind_vars={"project_id": project_id})
            claims = list(cursor)
        except ArangoError as e:
            logger.error(f"Failed to query verified claims: {e}", exc_info=True)
        
        return claims
    
    def _synthesize_claim(
        self,
        claim: Dict[str, Any],
        project_id: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """
        Synthesize a single verified claim into canonical knowledge.
        
        Uses Brain (120B) for entity resolution and conflict detection.
        
        Args:
            claim: Verified claim dictionary
            project_id: Project ID
            job_id: Job ID
        
        Returns:
            Dictionary with action and entity_id:
            {
                "action": "merged" | "created" | "conflict",
                "entity_id": str,
                "canonical_id": Optional[str],
                "conflict_reason": Optional[str]
            }
        """
        pointer = self._validate_claim(claim, project_id, job_id)
        # Build entity identifier from claim
        entity_name = claim.get("subject") or claim.get("object", "")
        entity_type = claim.get("subject_type") or claim.get("object_type", "")
        
        if not entity_name:
            raise ValueError("Claim missing entity name")
        
        # Query existing canonical knowledge
        existing = self._query_canonical_knowledge(entity_name, entity_type)
        
        if existing:
            # Entity resolution: Use Brain to determine if this is a match
            match_result = self._resolve_entity_match(claim, existing)
            
            if match_result["is_match"]:
                # Merge: Update existing entry
                self._merge_into_existing(existing, claim, pointer, project_id, job_id)
                return {
                    "action": "merged",
                    "entity_id": entity_name,
                    "canonical_id": existing["entity_id"],
                }
            elif match_result.get("is_conflict"):
                # Conflict: Flag for review
                self._flag_conflict(existing, claim, pointer, project_id, job_id, match_result.get("reason", ""))
                return {
                    "action": "conflict",
                    "entity_id": entity_name,
                    "canonical_id": existing["entity_id"],
                    "conflict_reason": match_result.get("reason", ""),
                }
        
        # No match: Create new canonical entry
        self._create_canonical_entry(claim, pointer, project_id, job_id)
        return {
            "action": "created",
            "entity_id": entity_name,
            "canonical_id": None,
        }

    def _validate_claim(self, claim: Dict[str, Any], project_id: str, job_id: str) -> Dict[str, Any]:
        """Validate minimal evidence before touching canonical_knowledge."""
        pointer = claim.get("source_pointer") or {}
        if not pointer:
            raise ValueError("Claim missing source_pointer (required)")
        try:
            sp = SourcePointer(**pointer)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid source_pointer: {exc}") from exc
        if not claim.get("doc_hash") and not sp.doc_hash:
            raise ValueError("Claim missing doc_hash")
        if sp.page is None:
            raise ValueError("Claim missing page number in source_pointer")
        if not project_id or not job_id:
            raise ValueError("Claim missing project_id/job_id for provenance")
        return sp.model_dump()
    
    def _query_canonical_knowledge(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Query canonical knowledge for matching entities.
        
        Args:
            entity_name: Entity name to search for
            entity_type: Optional entity type filter
        
        Returns:
            Matching canonical knowledge document or None
        """
        coll = self.db.collection(COLLECTION_NAME)
        
        # Try exact match first
        query = "FOR k IN @@coll FILTER k.entity_name == @name"
        bind_vars = {"@coll": COLLECTION_NAME, "name": entity_name}
        
        if entity_type:
            query += " AND k.entity_type == @type"
            bind_vars["type"] = entity_type
        
        query += " LIMIT 1 RETURN k"
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            if results:
                return results[0]
        except ArangoError as e:
            logger.warning(f"Failed to query canonical knowledge: {e}", exc_info=True)
        
        return None
    
    def _resolve_entity_match(
        self,
        new_claim: Dict[str, Any],
        existing: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use Brain (120B) to determine if new claim matches existing canonical knowledge.
        
        Args:
            new_claim: New verified claim
            existing: Existing canonical knowledge entry
        
        Returns:
            {
                "is_match": bool,
                "is_conflict": bool,
                "reason": Optional[str]
            }
        """
        # Deterministic short-circuit: identical normalized name and matching type
        new_name_norm = (new_claim.get("subject") or new_claim.get("object") or "").strip().lower()
        existing_name_norm = (existing.get("entity_name") or "").strip().lower()
        new_type = new_claim.get("subject_type") or new_claim.get("object_type")
        existing_type = existing.get("entity_type")
        if new_name_norm and new_name_norm == existing_name_norm and (not new_type or not existing_type or new_type == existing_type):
            # Even on deterministic name/type match, ensure no contradictions
            if self._has_contradiction(new_claim, existing):
                return {"is_match": False, "is_conflict": True, "reason": "deterministic match blocked by contradiction"}
            return {"is_match": True, "is_conflict": False, "reason": "deterministic name/type match"}

        brain_url = get_brain_url()
        brain_model = get_model_config("brain").model_id
        
        prompt = [
            {
                "role": "system",
                "content": """You are an Entity Resolution expert. Compare a new verified claim against existing canonical knowledge.

Determine if:
1. They refer to the same entity/concept (MATCH) - merge attributes
2. They contradict each other (CONFLICT) - flag for review
3. They are different entities (NO MATCH) - create new entry

Return JSON only:
{
  "is_match": true/false,
  "is_conflict": true/false,
  "reason": "brief explanation"
}""",
            },
            {
                "role": "user",
                "content": f"""Existing Canonical Knowledge:
Entity: {existing.get("entity_name")}
Type: {existing.get("entity_type")}
Description: {existing.get("description", "N/A")}

New Verified Claim:
Subject: {new_claim.get("subject")}
Object: {new_claim.get("object")}
Type: {new_claim.get("subject_type") or new_claim.get("object_type")}
Source: {new_claim.get("source_pointer", {}).get("snippet", "N/A")[:200]}

Are these the same entity? Do they contradict?""",
            },
        ]
        
        try:
            response = requests.post(
                f"{brain_url}/v1/chat/completions",
                json={
                "model": brain_model,
                "messages": prompt,
                "temperature": 0.3,
                "max_tokens": 200,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            result = json.loads(content) if isinstance(content, str) else content
            return {
                "is_match": result.get("is_match", False),
                "is_conflict": result.get("is_conflict", False),
                "reason": result.get("reason", ""),
            }
        except Exception as e:
            logger.warning(f"Entity resolution failed, defaulting to no match: {e}", exc_info=True)
            return {"is_match": False, "is_conflict": False, "reason": f"Resolution failed: {e}"}
    
    def _merge_into_existing(
        self,
        existing: Dict[str, Any],
        new_claim: Dict[str, Any],
        pointer: Dict[str, Any],
        project_id: str,
        job_id: str,
    ) -> None:
        """Merge new claim into existing canonical knowledge entry.
        
        Args:
            existing: Existing canonical knowledge document
            new_claim: New verified claim to merge
            pointer: Validated source pointer
            project_id: Project ID
            job_id: Job ID
        """
        coll = self.db.collection(COLLECTION_NAME)
        
        source_pointer = pointer or {}

        # Deduplicate source pointers by doc_hash+page+bbox+snippet hash
        def _fingerprint(sp: Dict[str, Any]) -> str:
            key = f"{sp.get('doc_hash','')}-{sp.get('page','')}-{sp.get('bbox', [])}-{sp.get('snippet','')}"
            return hashlib.sha256(key.encode()).hexdigest()

        existing_pointers = existing.get("source_pointers") or []
        fp_existing = {_fingerprint(sp) for sp in existing_pointers if isinstance(sp, dict)}
        fp_new = _fingerprint(source_pointer) if source_pointer else None
        if source_pointer and fp_new not in fp_existing:
            existing_pointers.append(source_pointer)
            existing["source_pointers"] = existing_pointers
        
        # Add provenance entry
        provenance_entry = {
            "project_id": project_id,
            "job_id": job_id,
            "contributed_at": datetime.now(timezone.utc).isoformat(),
            "source_pointer": source_pointer,
        }
        provenance_log = existing.get("provenance_log") or []
        exists = any(
            isinstance(p, dict)
            and p.get("project_id") == project_id
            and p.get("job_id") == job_id
            and (p.get("source_pointer") or {}).get("doc_hash") == source_pointer.get("doc_hash")
            for p in provenance_log
        )
        if not exists:
            provenance_log.append(provenance_entry)
            existing["provenance_log"] = provenance_log
        
        # Update timestamp
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update in database
        coll.update(existing)
        
        logger.debug(
            f"Merged claim into canonical knowledge",
            extra={"payload": {"entity_id": existing.get("entity_id"), "project_id": project_id}}
        )
    
    def _flag_conflict(
        self,
        existing: Dict[str, Any],
        new_claim: Dict[str, Any],
        pointer: Dict[str, Any],
        project_id: str,
        job_id: str,
        reason: str,
    ) -> None:
        """Flag a conflict for systemic review.
        
        Args:
            existing: Existing canonical knowledge document
            new_claim: Conflicting claim
            project_id: Project ID
            job_id: Job ID
            reason: Reason for conflict
        """
        coll = self.db.collection(COLLECTION_NAME)
        
        conflict_flag = f"CONFLICT: {project_id}/{job_id} - {reason}"
        existing.setdefault("conflict_flags", []).append(conflict_flag)
        if pointer:
            existing.setdefault("source_pointers", []).append(pointer)
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        coll.update(existing)
        
        logger.warning(
            f"Flagged conflict in canonical knowledge",
            extra={"payload": {"entity_id": existing.get("entity_id"), "conflict": conflict_flag}}
        )
    
    def _create_canonical_entry(
        self,
        claim: Dict[str, Any],
        pointer: Dict[str, Any],
        project_id: str,
        job_id: str,
    ) -> None:
        """Create a new canonical knowledge entry.
        
        Args:
            claim: Verified claim
            project_id: Project ID
            job_id: Job ID
        """
        coll = self.db.collection(COLLECTION_NAME)
        
        entity_name = claim.get("subject") or claim.get("object", "")
        entity_type = claim.get("subject_type") or claim.get("object_type", "")
        
        # Generate entity_id (normalized)
        entity_id = entity_name.lower().replace(" ", "_").replace("-", "_")
        
        source_pointer = pointer or {}
        
        entry = {
            "_key": entity_id,  # Use normalized name as key
            "entity_id": entity_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "subject": claim.get("subject"),
            "predicate": claim.get("predicate"),
            "object": claim.get("object"),
            "description": source_pointer.get("snippet", "")[:500],  # Truncate for description
            "source_pointers": [source_pointer] if source_pointer else [],
            "provenance_log": [
                {
                    "project_id": project_id,
                    "job_id": job_id,
                    "contributed_at": datetime.now(timezone.utc).isoformat(),
                    "source_pointer": source_pointer,
                }
            ],
            "conflict_flags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        coll.insert(entry)
        
        logger.info(
            f"Created new canonical knowledge entry",
            extra={"payload": {"entity_id": entity_id, "project_id": project_id}}
        )
    
    def query_established_knowledge(
        self,
        entity_names: List[str],
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query established knowledge for pre-extraction lookup.
        
        Args:
            entity_names: List of entity names to search for
            entity_types: Optional list of entity types to filter
        
        Returns:
            List of matching canonical knowledge entries
        """
        if not entity_names:
            return []
        
        coll = self.db.collection(COLLECTION_NAME)
        
        # Build AQL query
        query = "FOR k IN @@coll FILTER k.entity_name IN @names"
        bind_vars = {"@coll": COLLECTION_NAME, "names": entity_names}
        
        if entity_types:
            query += " AND k.entity_type IN @types"
            bind_vars["types"] = entity_types
        
        query += " RETURN k"
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            return list(cursor)
        except ArangoError as e:
            logger.warning(f"Failed to query established knowledge: {e}", exc_info=True)
            return []
