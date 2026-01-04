"""
Export nodes for persistence and artifact manifest generation.

This module contains nodes responsible for:
- Persisting extracted graphs to ArangoDB (saver_node)
- Compiling and persisting artifact manifests (artifact_registry_node)
"""

from typing import Dict, Any, List

from arango import ArangoClient

from ...shared.logger import get_logger
from ...shared.utils import get_utc_now
from ..state import PhaseEnum, ResearchState
from ..telemetry import TelemetryEmitter, trace_node
from ..artifacts.manifest_builder import build_manifest, persist_manifest
from ...shared.config import (
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from .nodes import validate_state_schema

logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()


@trace_node
def saver_node(state: ResearchState) -> ResearchState:
    """Persist extracted graph to ArangoDB with a status flag and receipt.
    
    Raises exceptions on failure (does not swallow errors) to ensure job failure
    is properly tracked.
    """
    extracted = state.get("extracted_json") or {}
    critiques = state.get("critiques", []) or []
    status = state.get("critic_status", "pass")
    vision_results = state.get("vision_results", [])
    project_id = state.get("project_id")
    manuscript_blocks = state.get("manuscript_blocks", [])

    # Ensure expert verification fields exist on triples
    if isinstance(extracted, dict) and isinstance(extracted.get("triples"), list):
        normalized_triples = []
        for triple in extracted.get("triples", []):
            if isinstance(triple, dict):
                triple.setdefault("is_expert_verified", False)
                triple.setdefault("expert_notes", None)
            normalized_triples.append(triple)
        extracted["triples"] = normalized_triples

    def _next_block_version(db, block_id: str, project: str) -> int:
        cursor = db.aql.execute(
            "FOR b IN manuscript_blocks FILTER b.block_id==@bid AND b.project_id==@pid SORT b.version DESC LIMIT 1 RETURN b.version",
            bind_vars={"bid": block_id, "pid": project},
        )
        versions = list(cursor)
        return (versions[0] + 1) if versions else 1

    def _validate_citations(db, project: str, keys: list[str]) -> None:
        """Librarian Key-Guard: Validate citation keys against project bibliography.
        
        This guard ensures that AI cannot save ManuscriptBlocks with invalid citations.
        All citation_keys must exist in the project_bibliography collection.
        
        Args:
            db: ArangoDB database instance.
            project: Project identifier.
            keys: List of citation keys to validate.
        
        Raises:
            ValueError: If bibliography collection is missing or citation keys are invalid.
        """
        if not keys:
            return
        if not db.has_collection("project_bibliography"):
            raise ValueError(
                "Bibliography collection 'project_bibliography' missing. "
                "Cannot validate citation keys. Add bibliography entries first."
            )
        cursor = db.aql.execute(
            "FOR b IN project_bibliography FILTER b.project_id==@pid RETURN b.citation_key",
            bind_vars={"pid": project},
        )
        existing = set(cursor)
        missing = [k for k in keys if k not in existing]
        if missing:
            raise ValueError(
                f"Citation keys not found in project bibliography: {missing}. "
                "Add these keys to 'project_bibliography' collection first."
            )

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        if not db.has_collection("extractions"):
            db.create_collection("extractions")
        if not db.has_collection("manuscript_blocks"):
            db.create_collection("manuscript_blocks")
        collection = db.collection("extractions")
        doc: Dict[str, Any] = {
            "graph": extracted,
            "critiques": critiques,
            "status": status if status == "pass" else "needs_manual_review",
            "vision_results": vision_results,
            "project_id": project_id,
        }
        receipt = collection.insert(doc)
        # Build explicit receipt
        save_receipt = {
            "collection": "extractions",
            "document_key": receipt.get("_key"),
            "document_id": receipt.get("_id"),
            "revision": receipt.get("_rev"),
            "saved_at": get_utc_now().isoformat(),
            "status": "SAVED",
        }
        logger.info("Saved extraction to ArangoDB", extra={"payload": {"status": doc["status"], "key": receipt.get("_key")}})

        # Persist manuscript blocks with versioning and citation guard (Librarian Key-Guard)
        if manuscript_blocks and project_id:
            from ...manuscript.service import ManuscriptService
            from ...shared.schema import ManuscriptBlock
            
            manuscript_service = ManuscriptService(db)
            
            for block_data in manuscript_blocks:
                if not isinstance(block_data, dict):
                    continue
                
                # Convert dict to ManuscriptBlock model
                try:
                    block = ManuscriptBlock(
                        block_id=block_data.get("block_id", ""),
                        section_title=block_data.get("section_title", ""),
                        content=block_data.get("content", ""),
                        order_index=block_data.get("order_index", 0),
                        claim_ids=block_data.get("claim_ids", []),
                        citation_keys=block_data.get("citation_keys", []),
                        project_id=project_id,
                        is_expert_verified=block_data.get("is_expert_verified", False),
                        expert_notes=block_data.get("expert_notes"),
                    )
                    
                    # Save with citation validation (Librarian Key-Guard)
                    manuscript_service.save_block(block, project_id, validate_citations=True)
                    
                except ValueError as e:
                    # Citation validation failed - log and re-raise
                    logger.error(
                        f"Librarian Key-Guard: Citation validation failed for block {block_data.get('block_id')}",
                        extra={"payload": {"error": str(e), "project_id": project_id}},
                        exc_info=True,
                    )
                    raise  # Re-raise to ensure job failure is tracked
                except Exception as e:
                    logger.error(
                        f"Failed to save manuscript block {block_data.get('block_id')}",
                        extra={"payload": {"error": str(e), "project_id": project_id}},
                        exc_info=True,
                    )
                    raise

        # Build and persist artifact manifest (best-effort; do not fail job on manifest issues)
        try:
            manifest = build_manifest(state, rigor_level=state.get("rigor_level"))
            persist_manifest(manifest, db=db, telemetry_emitter=telemetry_emitter)
            state_with_manifest = {**state, "artifact_manifest": manifest.model_dump(mode="json")}
        except Exception as manifest_exc:  # pragma: no cover - defensive
            logger.warning(
                "Artifact manifest persistence failed",
                extra={"payload": {"error": str(manifest_exc), "job_id": state.get("job_id")}},
                exc_info=True,
            )
            try:
                telemetry_emitter.emit_event(
                    "artifact_manifest_failed",
                    {
                        "job_id": state.get("job_id"),
                        "project_id": project_id,
                        "error_type": manifest_exc.__class__.__name__,
                        "error_message": str(manifest_exc)[:200],
                    },
                )
            except Exception:
                logger.debug("Failed to emit artifact_manifest_failed telemetry", exc_info=True)
            state_with_manifest = state

        # Set phase to DONE after successful persistence
        return {
            **state_with_manifest,
            "save_receipt": save_receipt,
            "phase": PhaseEnum.DONE.value,
        }
    except Exception as e:
        logger.error(f"DB Save Failed: {e}", exc_info=True)
        raise  # Re-raise to ensure job failure is tracked


@trace_node
def artifact_registry_node(state: ResearchState) -> ResearchState:
    """Compile a manifest with word/table counts and citation verification."""
    state = validate_state_schema(state)
    try:
        rigor = state.get("rigor_level") or (state.get("project_context") or {}).get("rigor_level")
        job_id = state.get("job_id") or state.get("jobId")
        state_with_ids = {**state, "job_id": job_id, "project_id": state.get("project_id")}
        manifest = build_manifest(state_with_ids, rigor_level=rigor)
        manifest_json = manifest.model_dump(mode="json")
    except Exception as exc:
        logger.warning("Manifest build failed", extra={"payload": {"error": str(exc)}}, exc_info=True)
        return {"artifacts": []}

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        persist_manifest(manifest, db=db, telemetry_emitter=telemetry_emitter)
    except Exception as exc:
        logger.warning("Manifest persistence failed", extra={"payload": {"error": str(exc)}}, exc_info=True)

    artifact_entry = {"type": "manifest", "data": manifest_json}
    result_state: ResearchState = {"artifacts": [artifact_entry], "artifact_manifest": manifest_json}
    if manifest.flags:
        result_state["manifest_flags"] = manifest.flags  # type: ignore[index]
    return result_state

