"""
Section Synthesis Service for Project Vyasa.

Handles internal persistence of section synthesis artifacts:
- RetrievalBundle (retrieval pipeline results)
- SectionDraft blocks (synthesized manuscript blocks with provenance)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase

from ..schemas.retrieval import RetrievalBundle
from ..schemas.analytical_notes import NoteState
from .retrieval_bundle_service import RetrievalBundleService
from ...manuscript.service import ManuscriptService
from ...shared.schema import ManuscriptBlock
from ...shared.logger import get_logger
from ..retrieval.retrieval_service import RetrievalService

logger = get_logger("orchestrator", __name__)


class SectionSynthesisService:
    """Service for persisting section synthesis artifacts."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the section synthesis service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self.retrieval_bundle_service = RetrievalBundleService(db)
        self.manuscript_service = ManuscriptService(db)
        self.retrieval_service = RetrievalService(db)
    
    def persist_section_run(
        self,
        project_id: str,
        section_id: str,
        retrieval_bundle: RetrievalBundle,
        section_draft: ManuscriptBlock,
        promotions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Persist section synthesis run artifacts.
        
        Persists:
        1. RetrievalBundle (internal artifact, may fail non-fatally)
        2. SectionDraft block (mandatory, fails section run if fails)
        3. Analytical Note promotions (best-effort, non-fatal)
        
        Args:
            project_id: Project identifier.
            section_id: Blueprint section identifier.
            retrieval_bundle: RetrievalBundle to persist.
            section_draft: ManuscriptBlock to persist.
            promotions: Optional list of Analytical Note promotions to apply.
        
        Returns:
            Dictionary with persistence results:
            {
                "bundle_persisted": bool,
                "block_persisted": bool,
                "promotions_applied": int,
                "promotions_failed": int,
                "errors": List[str]
            }
        
        Raises:
            ValueError: If block persistence fails (fatal).
        """
        from .analytical_notes_service import AnalyticalNotesService
        
        results = {
            "bundle_persisted": False,
            "block_persisted": False,
            "promotions_applied": 0,
            "promotions_failed": 0,
            "errors": [],
        }
        
        # 1. Persist RetrievalBundle (non-fatal)
        try:
            self.retrieval_bundle_service.save_bundle(retrieval_bundle)
            results["bundle_persisted"] = True
            logger.debug(
                f"Persisted RetrievalBundle",
                extra={
                    "payload": {
                        "bundle_id": retrieval_bundle.bundle_id,
                        "section_id": section_id,
                    }
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to persist RetrievalBundle: {e}",
                exc_info=True
            )
            results["errors"].append(f"RetrievalBundle persistence failed: {str(e)}")
        
        # 2. Persist SectionDraft block (mandatory)
        try:
            # Ensure provenance fields are set
            section_draft.retrieval_bundle_id = retrieval_bundle.bundle_id
            section_draft.section_id = section_id
            
            # Extract chunk_ids from retrieval_bundle.reranked_chunks
            chunk_ids = [
                chunk.get("chunk_id")
                for chunk in retrieval_bundle.reranked_chunks
                if chunk.get("chunk_id")
            ]
            section_draft.chunk_ids = chunk_ids
            
            # Extract note_ids from promotions (if any)
            note_ids = []
            if promotions:
                note_ids = [
                    prom.get("note_id")
                    for prom in promotions
                    if prom.get("note_id")
                ]
            section_draft.note_ids = note_ids
            
            # Set model_ids
            section_draft.model_ids = {
                "embedder": retrieval_bundle.embedder_model_id,
                "reranker": retrieval_bundle.reranker_model_id,
                "synthesizer": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5",  # TODO: Get from config
                "critic": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5",  # TODO: Get from config
            }
            
            # Persist block
            self.manuscript_service.save_block(section_draft, project_id, validate_citations=True)
            results["block_persisted"] = True
            logger.info(
                f"Persisted SectionDraft block",
                extra={
                    "payload": {
                        "block_id": section_draft.block_id,
                        "section_id": section_id,
                        "retrieval_bundle_id": retrieval_bundle.bundle_id,
                        "chunk_count": len(chunk_ids),
                        "note_count": len(note_ids),
                    }
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to persist SectionDraft block: {e}",
                exc_info=True
            )
            results["errors"].append(f"Block persistence failed: {str(e)}")
            # Block persistence is mandatory - raise error
            raise ValueError(f"Block persistence failed: {str(e)}") from e
        
        # 3. Apply Analytical Note promotions (best-effort, non-fatal)
        if promotions:
            notes_service = AnalyticalNotesService(self.db)
            for promotion in promotions:
                note_id = promotion.get("note_id")
                if not note_id:
                    continue
                
                try:
                    note = notes_service.get_note(note_id)
                    if not note:
                        logger.warning(
                            f"Note {note_id} not found for promotion",
                            extra={"payload": {"note_id": note_id}}
                        )
                        results["promotions_failed"] += 1
                        continue
                    
                    # Update note state to Manuscript with audit fields
                    updates = {
                        "state": NoteState.MANUSCRIPT.value,
                        "promotion_reason": promotion.get("reason", ""),
                        "promoted_by_section_id": section_id,  # Audit: section that triggered promotion
                        "supporting_chunk_ids": promotion.get("linked_evidence", []),  # Audit: supporting chunks
                        "critic_flags": [],  # Flags should be included in promotion if needed
                    }
                    
                    notes_service.update_note(note_id, updates)
                    results["promotions_applied"] += 1
                    logger.info(
                        f"Promoted Analytical Note to Manuscript",
                        extra={
                            "payload": {
                                "note_id": note_id,
                                "project_id": project_id,
                                "reason": promotion.get("reason"),
                            }
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to promote Analytical Note {note_id}: {e}",
                        exc_info=True
                    )
                    results["promotions_failed"] += 1
                    results["errors"].append(f"Promotion failed for note {note_id}: {str(e)}")
        
        return results
