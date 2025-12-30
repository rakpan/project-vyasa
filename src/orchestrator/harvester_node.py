"""
Knowledge Harvester for Project Vyasa.

Automatically generates JSONL instruction datasets from expert-verified research
for fine-tuning models on the DGX Spark.

Harvests two types of training pairs:
1. Manuscript Synthesis: Graph Triples -> Markdown Text
2. Evidence Extraction: Text Snippet -> Structured Triple
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..shared.logger import get_logger
from ..shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password

logger = get_logger("orchestrator", __name__)

# Dataset output directory (configurable via env var)
DEFAULT_DATASET_DIR = Path("/raid/datasets")
DATASET_FILENAME = "fine_tuning_v1.jsonl"


class KnowledgeHarvester:
    """Service for harvesting expert-verified knowledge into training datasets."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the knowledge harvester.
        
        Args:
            db: ArangoDB database instance
        """
        self.db = db
        self.dataset_dir = self._get_dataset_dir()
        self.dataset_file = self.dataset_dir / DATASET_FILENAME
        self._ensure_dataset_dir()
    
    def _get_dataset_dir(self) -> Path:
        """Get dataset directory from env var or use default."""
        dataset_path = os.getenv("VYASA_DATASET_DIR", str(DEFAULT_DATASET_DIR))
        return Path(dataset_path)
    
    def _ensure_dataset_dir(self) -> None:
        """Ensure the dataset directory exists."""
        try:
            self.dataset_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Dataset directory ready: {self.dataset_dir}")
        except Exception as e:
            logger.warning(f"Failed to create dataset directory {self.dataset_dir}: {e}. Using /tmp as fallback.")
            self.dataset_dir = Path("/tmp/vyasa_datasets")
            self.dataset_file = self.dataset_dir / DATASET_FILENAME
            self.dataset_dir.mkdir(parents=True, exist_ok=True)
    
    def harvest_project(
        self,
        project_id: str,
        job_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Harvest expert-verified knowledge from a project.
        
        Args:
            project_id: Project ID to harvest from
            job_ids: Optional list of job IDs to filter by
        
        Returns:
            Dictionary with harvest statistics:
            {
                "manuscript_pairs": int,
                "triple_pairs": int,
                "total_pairs": int,
                "dataset_path": str
            }
        """
        logger.info(
            f"Harvesting knowledge from project {project_id}",
            extra={"payload": {"project_id": project_id, "job_ids": job_ids}}
        )
        
        manuscript_pairs = self._harvest_manuscript_blocks(project_id, job_ids)
        triple_pairs = self._harvest_verified_triples(project_id, job_ids)
        
        total_pairs = manuscript_pairs + triple_pairs
        
        summary = {
            "manuscript_pairs": manuscript_pairs,
            "triple_pairs": triple_pairs,
            "total_pairs": total_pairs,
            "dataset_path": str(self.dataset_file),
        }
        
        logger.info(
            f"Harvesting completed for project {project_id}",
            extra={"payload": {"project_id": project_id, **summary}}
        )
        
        return summary
    
    def _harvest_manuscript_blocks(
        self,
        project_id: str,
        job_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Harvest expert-verified manuscript blocks as instruction pairs.
        
        Format:
        {
            "instruction": "Synthesize this OT security graph into a manuscript section...",
            "input": "[Graph Triples JSON]",
            "output": "[Finalized Markdown Text]",
            "metadata": {
                "project_id": "...",
                "block_id": "...",
                "timestamp": "...",
                "claim_ids": [...],
                "citation_keys": [...]
            }
        }
        
        Args:
            project_id: Project ID
            job_ids: Optional job IDs filter
        
        Returns:
            Number of pairs harvested
        """
        if not self.db.has_collection("manuscript_blocks"):
            logger.warning("manuscript_blocks collection not found")
            return 0
        
        blocks_col = self.db.collection("manuscript_blocks")
        
        # Query expert-verified blocks
        query = """
        FOR b IN manuscript_blocks
        FILTER b.project_id == @project_id
        FILTER b.is_expert_verified == true
        RETURN b
        """
        
        bind_vars = {"project_id": project_id}
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            blocks = list(cursor)
        except ArangoError as e:
            logger.error(f"Failed to query manuscript blocks: {e}", exc_info=True)
            return 0
        
        pairs_written = 0
        
        for block in blocks:
            try:
                # Get the graph triples (input context)
                claim_ids = block.get("claim_ids", [])
                triples = self._get_triples_by_ids(claim_ids, project_id)
                
                if not triples:
                    logger.debug(f"Skipping block {block.get('block_id')}: no triples found")
                    continue
                
                # Format instruction pair
                instruction = self._format_manuscript_instruction(block.get("section_title", "Section"))
                input_text = json.dumps(triples, indent=2)
                output_text = block.get("content", "")
                
                pair = {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "metadata": {
                        "project_id": project_id,
                        "block_id": block.get("block_id"),
                        "section_title": block.get("section_title"),
                        "timestamp": block.get("updated_at") or datetime.now(timezone.utc).isoformat(),
                        "claim_ids": claim_ids,
                        "citation_keys": block.get("citation_keys", []),
                        "version": block.get("version", 1),
                        "type": "manuscript_synthesis",
                    }
                }
                
                # Append to JSONL file
                self._append_to_jsonl(pair)
                pairs_written += 1
                
            except Exception as e:
                logger.error(
                    f"Failed to harvest manuscript block: {e}",
                    extra={"payload": {"block_id": block.get("block_id")}},
                    exc_info=True,
                )
        
        logger.info(
            f"Harvested {pairs_written} manuscript synthesis pairs",
            extra={"payload": {"project_id": project_id}}
        )
        
        return pairs_written
    
    def _harvest_verified_triples(
        self,
        project_id: str,
        job_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Harvest expert-verified triples as evidence-extraction pairs.
        
        Format:
        {
            "instruction": "Extract structured knowledge from this text snippet...",
            "input": "[Text Snippet]",
            "output": "[Triple JSON]",
            "metadata": {
                "project_id": "...",
                "triple_id": "...",
                "timestamp": "...",
                "doc_hash": "...",
                "page": 1
            }
        }
        
        Args:
            project_id: Project ID
            job_ids: Optional job IDs filter
        
        Returns:
            Number of pairs harvested
        """
        if not self.db.has_collection("extractions"):
            logger.warning("extractions collection not found")
            return 0
        
        extractions_col = self.db.collection("extractions")
        
        # Query verified triples
        query = """
        FOR e IN extractions
        FILTER e.project_id == @project_id
        FOR triple IN e.graph.triples
        FILTER triple.is_expert_verified == true
        FILTER triple.source_pointer != null
        RETURN {
            triple: triple,
            job_id: e._key,
            project_id: e.project_id
        }
        """
        
        bind_vars = {"project_id": project_id}
        
        if job_ids:
            query = query.replace(
                "FILTER e.project_id == @project_id",
                "FILTER e.project_id == @project_id AND e._key IN @job_ids"
            )
            bind_vars["job_ids"] = job_ids
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
        except ArangoError as e:
            logger.error(f"Failed to query verified triples: {e}", exc_info=True)
            return 0
        
        pairs_written = 0
        
        for result in results:
            try:
                triple = result.get("triple", {})
                source_pointer = triple.get("source_pointer", {})
                snippet = source_pointer.get("snippet", "")
                doc_hash = source_pointer.get("doc_hash")
                page = source_pointer.get("page")
                bbox = source_pointer.get("bbox")
                
                # Require evidence binding details to avoid training on unverifiable data
                if not snippet or not doc_hash or page is None or not bbox or len(bbox) != 4:
                    logger.debug(
                        "Skipping triple: missing evidence binding",
                        extra={"payload": {"has_snippet": bool(snippet), "has_doc_hash": bool(doc_hash), "page": page}}
                    )
                    continue
                
                # Format instruction pair
                instruction = "Extract structured knowledge from this text snippet. Return a JSON triple with subject, predicate, object, and metadata."
                input_text = snippet
                
                # Format triple as output (exclude source_pointer from output to avoid duplication)
                output_triple = {
                    "subject": triple.get("subject"),
                    "predicate": triple.get("predicate"),
                    "object": triple.get("object"),
                    "subject_type": triple.get("subject_type"),
                    "object_type": triple.get("object_type"),
                    "confidence": triple.get("confidence"),
                    "doc_hash": triple.get("doc_hash"),
                }
                output_text = json.dumps(output_triple, indent=2)
                
                pair = {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "metadata": {
                        "project_id": project_id,
                        "job_id": result.get("job_id"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "doc_hash": doc_hash,
                        "page": page,
                        "bbox": bbox,
                        "type": "evidence_extraction",
                    }
                }
                
                # Append to JSONL file
                self._append_to_jsonl(pair)
                pairs_written += 1
                
            except Exception as e:
                logger.error(
                    f"Failed to harvest triple: {e}",
                    extra={"payload": {"triple": triple.get("subject", "unknown")}},
                    exc_info=True,
                )
        
        logger.info(
            f"Harvested {pairs_written} evidence-extraction pairs",
            extra={"payload": {"project_id": project_id}}
        )
        
        return pairs_written
    
    def _get_triples_by_ids(self, claim_ids: List[str], project_id: str) -> List[Dict[str, Any]]:
        """Get triples by their claim IDs.
        
        Args:
            claim_ids: List of claim/triple IDs
            project_id: Project ID
        
        Returns:
            List of triple dictionaries
        """
        if not claim_ids:
            return []
        
        if not self.db.has_collection("extractions"):
            return []
        
        # Query extractions for triples matching claim_ids
        # Note: claim_ids might be stored as subject/object names or as explicit IDs
        query = """
        FOR e IN extractions
        FILTER e.project_id == @project_id
        FOR triple IN e.graph.triples
        FILTER triple.is_expert_verified == true
        FILTER triple.subject IN @claim_ids OR triple.object IN @claim_ids
        RETURN triple
        """
        
        try:
            cursor = self.db.aql.execute(query, bind_vars={"project_id": project_id, "claim_ids": claim_ids})
            return list(cursor)
        except ArangoError as e:
            logger.warning(f"Failed to query triples by IDs: {e}", exc_info=True)
            return []
    
    def _format_manuscript_instruction(self, section_title: str) -> str:
        """Format instruction text for manuscript synthesis.
        
        Args:
            section_title: Section title (e.g., "Introduction", "Methodology")
        
        Returns:
            Instruction text
        """
        return f"Synthesize the provided knowledge graph triples into a well-structured {section_title} section for a research manuscript. The output should be in Markdown format, properly cite sources, and maintain academic rigor."
    
    def _append_to_jsonl(self, pair: Dict[str, Any]) -> None:
        """Append a training pair to the JSONL dataset file.
        
        Args:
            pair: Training pair dictionary
        """
        try:
            with open(self.dataset_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to dataset file {self.dataset_file}: {e}", exc_info=True)
            raise
