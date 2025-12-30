"""
Workflow nodes for the agentic Cartographer -> Critic loop.
"""

import json
import os
import sys
import uuid
import shutil
import requests
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..shared.config import (
    get_worker_url,
    get_brain_url,
    get_vision_url,
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD,
    WORKER_MODEL_NAME,
    BRAIN_MODEL_NAME,
    VISION_MODEL_NAME,
)
from ..shared.logger import get_logger
from ..shared.llm_client import call_model
from .state import PaperState
from .normalize import normalize_extracted_json
from arango import ArangoClient

logger = get_logger("orchestrator", __name__)

# Lazy import to avoid circular dependencies
_project_service: Optional[Any] = None
_synthesis_service: Optional[Any] = None


def _get_synthesis_service() -> Optional[Any]:
    """Get or initialize SynthesisService for canonical knowledge queries.
    
    Returns:
        SynthesisService instance or None if DB unavailable
    """
    global _synthesis_service
    if _synthesis_service is None:
        try:
            from .synthesis_service import SynthesisService
            from ..shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
            
            arango_url = os.getenv("MEMORY_URL", get_memory_url())
            arango_db = os.getenv("ARANGODB_DB", ARANGODB_DB)
            arango_user = os.getenv("ARANGODB_USER", ARANGODB_USER)
            arango_password = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", ARANGODB_PASSWORD)
            
            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            _synthesis_service = SynthesisService(db)
            logger.debug("SynthesisService initialized in nodes module")
        except Exception as e:
            logger.warning(f"Failed to initialize SynthesisService in nodes: {e}")
            _synthesis_service = None
    return _synthesis_service


def _query_established_knowledge(raw_text: str) -> List[Dict[str, Any]]:
    """Query canonical knowledge for entities mentioned in the text.
    
    This performs a simple keyword-based lookup to find relevant established knowledge.
    In production, this could be enhanced with semantic search.
    
    Args:
        raw_text: Text to extract entity names from
    
    Returns:
        List of canonical knowledge entries
    """
    service = _get_synthesis_service()
    if not service:
        return []
    
    # Simple extraction: look for capitalized words/phrases (potential entity names)
    # This is a basic heuristic; could be enhanced with NER
    import re
    words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', raw_text)
    entity_names = list(set(words))[:20]  # Limit to 20 unique names
    
    if not entity_names:
        return []
    
    try:
        return service.query_established_knowledge(entity_names)
    except Exception as e:
        logger.warning(f"Failed to query established knowledge: {e}", exc_info=True)
        return []


def _get_project_service() -> Optional[Any]:
    """Get ProjectService instance (lazy import to avoid circular dependencies).
    
    Returns:
        ProjectService instance if available, None if DB unavailable.
    """
    global _project_service
    if _project_service is None:
        try:
            # Lazy imports to avoid circular dependencies
            from ..project.service import ProjectService
            from ..shared.config import MEMORY_URL, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
            arango_url = os.getenv("MEMORY_URL", MEMORY_URL)
            arango_db = os.getenv("ARANGODB_DB", ARANGODB_DB)
            arango_user = os.getenv("ARANGODB_USER", ARANGODB_USER)
            arango_password = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", ARANGODB_PASSWORD)
            
            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            # Do not create DBs/collections here; assume pre-provisioned (matches server.py behavior)
            _project_service = ProjectService(db)
            logger.debug("ProjectService initialized in nodes module (no DB creation)")
        except Exception as e:
            logger.warning(f"Failed to initialize ProjectService in nodes: {e}")
            _project_service = None
    return _project_service


def hydrate_project_context(state: PaperState) -> PaperState:
    """Hydrate project context from project_id if missing.
    
    Ensures project_context is available in state as a JSON-serializable dict.
    If project_id exists but project_context is missing, fetches from ProjectService
    and stores model_dump() into state.
    
    Args:
        state: PaperState that may contain project_id.
    
    Returns:
        Updated PaperState with project_context populated if project_id was present.
    
    Raises:
        ValueError: If project_id is provided but project not found.
        RuntimeError: If project_id is provided but DB is unavailable.
    """
    project_id = state.get("project_id")
    
    # If no project_id, return state unchanged
    if not project_id:
        return state
    
    # If project_context already exists, return state unchanged
    if state.get("project_context"):
        return state
    
    # Fetch project config
    project_service = _get_project_service()
    if project_service is None:
        raise RuntimeError("ProjectService unavailable: cannot fetch project context")
    
    try:
        from ..project.types import ProjectConfig
        project = project_service.get_project(project_id)
        
        # Store as dict (JSON-serializable)
        state["project_context"] = project.model_dump()
        logger.info(f"Hydrated project context for project_id={project_id}")
        
        return state
    except ValueError as e:
        # Project not found
        raise ValueError(f"Project not found: {project_id}") from e
    except Exception as e:
        # Other errors (DB unavailable, etc.)
        logger.error(f"Failed to hydrate project context for {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch project context: {e}") from e


def cartographer_node(state: PaperState) -> PaperState:
    """Extract graph JSON from raw text using Cortex Worker, incorporating prior critiques.
    
    Uses Worker (SGLang) to extract structured knowledge graph with STRICT JSON
    requirements. The output is normalized to guarantee a `triples` array structure
    that the console expects.
    
    Args:
        state: PaperState containing raw_text, optional critiques, and optional project context.
        
    Returns:
        Updated PaperState with extracted_json containing guaranteed `triples` array.
        
    Raises:
        ValueError: If raw_text is missing or project_id provided but project not found.
        RuntimeError: If project_id provided but DB unavailable.
        requests.RequestException: If Worker API call fails.
    """
    # Hydrate project context if project_id is present
    state = hydrate_project_context(state)
    
    # Safe access to project context (already hydrated if project_id exists)
    project_id = state.get("project_id")
    project_context = state.get("project_context")
    
    raw_text = state.get("raw_text", "")
    critiques = state.get("critiques", []) or []

    if not raw_text:
        raise ValueError("raw_text is required for cartographer node")

    # Build strict extraction prompt leveraging Nemotron reasoning (<think/>)
    system_prompt = """You are the Cartographer. Extract a structured knowledge graph from text as JSON. Use <think> ... </think> to plan internally, but output ONLY JSON.

CRITICAL REQUIREMENTS:
- Output MUST be valid JSON only (no prose, no markdown code blocks)
- MUST include a "triples" array, even if empty
- Each triple must have: subject, predicate, object, confidence (0.0-1.0), and optional evidence
- Each claim MUST include: project_id, doc_hash from context, and a source_pointer with normalized coordinates (0-1000 scale):
  { "doc_hash": "sha256:...", "page": number, "bbox": [x1,y1,x2,y2], "snippet": "exact text" }
- Keep reasoning inside <think>...</think> and DO NOT include it in the final JSON.

Required JSON structure:
{
  "triples": [
    {
      "subject": "entity or concept name",
      "predicate": "relationship type (e.g., 'causes', 'enables', 'mitigates', 'requires')",
      "object": "target entity or concept",
      "confidence": 0.0-1.0,
      "evidence": "text excerpt supporting this relation (optional)"
    }
  ],
  "entities": [...],  # Optional: list of extracted entities
  "claims": [...],    # Optional: list of claims or assertions
  "metadata": {...}   # Optional: additional metadata
}

The "triples" array is REQUIRED. Return empty array [] if no relations found."""

    # Project-aware prompting: Inject thesis and research questions if available
    if project_context:
        thesis = project_context.get("thesis", "")
        research_questions = project_context.get("research_questions", [])
        
        if thesis or research_questions:
            project_section = "\n\n### PROJECT CONTEXT\n"
            if thesis:
                project_section += f'The user is researching the following Thesis: "{thesis}"\n'
            if research_questions:
                project_section += "Prioritize extracting claims relevant to these Research Questions:\n"
                for i, rq in enumerate(research_questions, 1):
                    project_section += f"{i}. {rq}\n"
                project_section += "Tag relevant claims as priority=HIGH.\n"
            
            system_prompt += project_section
            logger.debug(
                "Cartographer: Injected project context into prompt",
                extra={"payload": {"has_thesis": bool(thesis), "rq_count": len(research_questions)}}
            )
    
    # Evidence-Aware RAG: Pre-extraction lookup in canonical_knowledge
    established_knowledge = _query_established_knowledge(raw_text)
    if established_knowledge:
        knowledge_section = "\n\n### ESTABLISHED KNOWLEDGE\n"
        knowledge_section += "The following entities/concepts are already known in the global knowledge base:\n"
        for entry in established_knowledge[:10]:  # Limit to top 10 to avoid prompt bloat
            knowledge_section += f"- {entry.get('entity_name')} ({entry.get('entity_type')}): {entry.get('description', 'N/A')[:100]}\n"
        knowledge_section += "\nUse this context to guide extraction of nuanced details. Focus on new relationships or updated information.\n"
        system_prompt += knowledge_section
        logger.debug(
            "Cartographer: Injected established knowledge into prompt",
            extra={"payload": {"knowledge_count": len(established_knowledge)}}
        )

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Extract knowledge graph from this text:\n\n{raw_text}"},
    ]

    if critiques:
        prompt.append(
            {
                "role": "system",
                "content": f"Previous attempt critiques: {' | '.join(critiques)}. Address them in the next output.",
            }
        )

    try:
        # Cartographer uses Worker (extraction) service
        worker_url = get_worker_url()
        response = requests.post(
            f"{worker_url}/v1/chat/completions",
            json={
                "model": WORKER_MODEL_NAME,
                "messages": prompt,
                "temperature": 0.6,
                "top_p": 0.95,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Parse JSON (handle markdown code blocks if present)
        if isinstance(content, str):
            # Remove markdown code blocks if present
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            extracted = json.loads(content)
        else:
            extracted = content
        
        # Normalize to guarantee triples structure
        normalized = normalize_extracted_json(extracted)
        
        triples_count = len(normalized.get("triples", []))
        logger.info(
            "Cartographer extracted graph",
            extra={"payload": {"triples_count": triples_count, "has_entities": "entities" in normalized}}
        )
        
        return {**state, "extracted_json": normalized}
    except json.JSONDecodeError as e:
        logger.error(
            "Cartographer failed to parse JSON response",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on JSON parse failure
        return {**state, "extracted_json": {"triples": []}}
    except Exception as e:
        logger.error(
            "Cartographer failed to extract graph",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on failure (don't raise to allow workflow to continue)
        return {**state, "extracted_json": {"triples": []}}


def _detect_quantization_failure(text: str) -> bool:
    """Detect FP4 quantization failures: garbled text or repetitive tokens.
    
    Args:
        text: Text to analyze for quantization artifacts.
    
    Returns:
        True if quantization failure is detected, False otherwise.
    """
    if not text or len(text) < 10:
        return False

    # Treat structured JSON as likely valid; avoid false positives on compact payloads
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return False
    
    # Check for repetitive token patterns (common FP4 failure)
    # Look for sequences of 3+ identical tokens
    words = text.split()
    if len(words) >= 3:
        for i in range(len(words) - 2):
            if words[i] == words[i + 1] == words[i + 2]:
                return True
    
    # Check for garbled text patterns
    # High ratio of non-alphanumeric characters or unusual character sequences
    alphanumeric_ratio = sum(1 for c in text if c.isalnum()) / len(text) if text else 0
    if alphanumeric_ratio < 0.3:  # Less than 30% alphanumeric suggests garbled text
        return True
    
    # Check for excessive special characters or control characters
    special_char_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if len(text) > 0 and special_char_count / len(text) > 0.5:  # More than 50% special chars
        return True
    
    return False


def critic_node(state: PaperState) -> PaperState:
    """Validate extracted graph and return pass/fail with critiques.
    
    Uses Brain (high-level reasoning) service for validation.
    Includes FP4 quantization failure detection to catch garbled text or repetitive tokens.
    """
    extracted = state.get("extracted_json") or {}
    raw_text = state.get("raw_text", "")
    
    # Pre-validation: Check for FP4 quantization failures in extracted text
    # This catches failures before sending to Brain, saving compute
    extracted_str = json.dumps(extracted, ensure_ascii=False)
    if _detect_quantization_failure(extracted_str):
        logger.warning(
            "FP4 quantization failure detected in extraction",
            extra={"payload": {"extracted_preview": extracted_str[:200]}},
        )
        revision_count = state.get("revision_count", 0) + 1
        return {
            **state,
            "critiques": ["Extraction appears garbled or contains repetitive tokens (possible FP4 quantization failure)"],
            "revision_count": revision_count,
            "critic_status": "fail",
        }

    def _load_page_text(doc_hash: str, page: int) -> str:
        """Load page text from cache or extract from PDF.
        
        Args:
            doc_hash: SHA256 hash of the PDF document
            page: 1-based page number
        
        Returns:
            Text content of the page, or empty string if not available
        """
        try:
            from .pdf_text_cache import load_page_text
            pdf_path = state.get("pdf_path")
            return load_page_text(doc_hash, page, pdf_path=pdf_path)
        except Exception as e:
            logger.warning(
                f"Failed to load page text for doc_hash={doc_hash[:16]}... page={page}: {e}",
                extra={"payload": {"doc_hash": doc_hash[:16], "page": page}},
                exc_info=True,
            )
            # Fallback to raw_text if cache fails (graceful degradation)
            return raw_text or ""

    def _snippet_exists(snippet: str, text: str) -> bool:
        if not snippet or not text:
            return False
        if snippet in text:
            return True
        # Fuzzy containment
        import difflib
        return difflib.SequenceMatcher(None, snippet, text).quick_ratio() > 0.6

    def _validate_claims() -> tuple[list[str], bool]:
        """Validate claims and triples with hardened evidence binding checks.
        
        The Critic's Gate: Rejects any claim/triple that:
        - Lacks doc_hash (hard requirement)
        - Has invalid bbox range [0, 1000]
        - Has snippet that doesn't match page text (fuzzy match)
        
        Returns:
            Tuple of (critiques list, validation_ok bool)
        """
        critiques_local: list[str] = []
        ok = True
        claims = extracted.get("claims") or []
        triples = extracted.get("triples") or []
        
        # Validate claims
        for claim in claims:
            if not isinstance(claim, dict):
                critiques_local.append("Claim is not an object")
                ok = False
                continue
            
            pointer = claim.get("source_pointer") or {}
            bbox = pointer.get("bbox")
            doc_hash = claim.get("doc_hash") or pointer.get("doc_hash")
            page = pointer.get("page")
            snippet = pointer.get("snippet", "")
            project_id = claim.get("project_id")
            
            # Hard requirement: doc_hash must exist
            if not doc_hash:
                critiques_local.append("Claim missing doc_hash (required for evidence binding)")
                ok = False
                continue
            
            # Hard requirement: source_pointer must have all fields
            if not page or not bbox or len(bbox) != 4:
                critiques_local.append("Claim missing source_pointer fields (page/bbox required)")
                ok = False
                continue
            
            # Validate bbox range [0, 1000]
            if any((c < 0 or c > 1000) for c in bbox):
                critiques_local.append(f"Claim bbox out of range (must be 0-1000): {bbox}")
                ok = False
            
            # Validate project_id
            if not project_id:
                critiques_local.append("Claim missing project_id")
                ok = False
            
            # Real text verification: fuzzy match snippet against page text
            if doc_hash and page and snippet:
                try:
                    page_text = _load_page_text(doc_hash, page)
                    if not _snippet_exists(snippet, page_text):
                        critiques_local.append(
                            f"Claim snippet not found in page text (doc_hash={doc_hash[:16]}... page={page})"
                        )
                        ok = False
                except Exception as e:
                    logger.warning(f"Failed to verify snippet for claim: {e}", exc_info=True)
                    critiques_local.append(f"Failed to verify claim snippet: {e}")
                    ok = False
        
        # Validate triples (same checks)
        for triple in triples:
            if not isinstance(triple, dict) or not triple:
                continue
            
            pointer = triple.get("source_pointer") or {}
            bbox = pointer.get("bbox")
            doc_hash = triple.get("doc_hash") or pointer.get("doc_hash")
            page = pointer.get("page")
            snippet = triple.get("snippet") or triple.get("evidence", "")
            
            # Hard requirement: doc_hash must exist
            if not doc_hash:
                critiques_local.append("Triple missing doc_hash (required for evidence binding)")
                ok = False
                continue
            
            # If source_pointer exists, validate it
            if pointer:
                if not page or not bbox or len(bbox) != 4:
                    critiques_local.append("Triple source_pointer missing required fields (page/bbox)")
                    ok = False
                    continue
                
                # Validate bbox range
                if any((c < 0 or c > 1000) for c in bbox):
                    critiques_local.append(f"Triple bbox out of range (must be 0-1000): {bbox}")
                    ok = False
                
                # Real text verification
                if snippet:
                    try:
                        page_text = _load_page_text(doc_hash, page)
                        if not _snippet_exists(snippet, page_text):
                            critiques_local.append(
                                f"Triple snippet not found in page text (doc_hash={doc_hash[:16]}... page={page})"
                            )
                            ok = False
                    except Exception as e:
                        logger.warning(f"Failed to verify triple snippet: {e}", exc_info=True)
                        critiques_local.append(f"Failed to verify triple snippet: {e}")
                        ok = False
        
        return critiques_local, ok

    claim_critiques, claims_ok = _validate_claims()

    critique_prompt = [
        {
            "role": "system",
            "content": "You are the Critic. You run on a 120B model with large context. Validate the extracted graph JSON for completeness, missing source IDs, hallucinations, quantization artifacts, and evidence binding. For every claim, ensure project_id, doc_hash, and source_pointer exist with bbox normalized (0-1000). For each claim.snippet, confirm it is present in the document text. Return JSON only.",
        },
        {"role": "user", "content": extracted_str},
    ]

    try:
        # Critic uses Brain (high-level reasoning) service
        brain_url = get_brain_url()
        resp = requests.post(
            f"{brain_url}/v1/chat/completions",
            json={
                "model": BRAIN_MODEL_NAME,
                "messages": critique_prompt,
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": 8192,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        parsed = json.loads(content) if isinstance(content, str) else content
        status = parsed.get("status", "fail").lower()
        critiques = parsed.get("critiques", [])
        if not isinstance(critiques, list):
            critiques = [str(critiques)]
        
        # Additional check: If Brain response itself looks garbled, mark as fail
        if _detect_quantization_failure(content):
            logger.warning(
                "FP4 quantization failure detected in Brain response",
                extra={"payload": {"response_preview": content[:200]}},
            )
            status = "fail"
            critiques.append("Brain response appears garbled (possible quantization failure)")

        # Snippet existence check (best-effort)
        critiques.extend(claim_critiques)
        if not claims_ok:
            status = "fail"
        
        # Increment revision count on failure
        revision_count = state.get("revision_count", 0)
        if status != "pass":
            revision_count += 1
        return {**state, "critiques": critiques, "revision_count": revision_count, "critic_status": status}
    except Exception:
        logger.error(
            "Critic validation failed",
            extra={"payload": {"has_extracted": bool(extracted)}},
            exc_info=True,
        )
        # On failure to critique, force manual review path
        revision_count = state.get("revision_count", 0) + 1
        return {**state, "critiques": ["Critic execution failed"], "revision_count": revision_count, "critic_status": "fail"}


def select_images_for_vision(image_paths: List[str]) -> List[str]:
    """Select a subset of images to send to Vision."""
    if not image_paths:
        return []
    max_images = int(os.getenv("VISION_MAX_IMAGES", "5"))
    preferred = []
    others = []
    for path in image_paths:
        name = os.path.basename(path).lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if any(tag in name for tag in ["fig", "table", "chart", "diagram"]) or size > 500_000:
            preferred.append(path)
        else:
            others.append(path)
    ordered = preferred + others
    return ordered[:max_images]


def build_vision_context(vision_results: List[Dict[str, Any]]) -> str:
    """Create a deterministic context block from vision results."""
    lines: List[str] = []
    for res in vision_results:
        path = os.path.basename(res.get("image_path", "image"))
        lines.append(f"[FIGURE {path}]")
        caption = res.get("caption", "").strip()
        if caption:
            lines.append(f"caption: {caption}")
        facts = res.get("extracted_facts") or []
        if facts:
            lines.append("extracted_facts:")
            for fact in facts:
                key = fact.get("key", "")
                value = fact.get("value", "")
                unit = fact.get("unit", "")
                conf = fact.get("confidence", 0.0)
                lines.append(f"- key: {key} value: {value} unit: {unit} (confidence={conf})")
        tables = res.get("tables") or []
        for tbl in tables:
            lines.append(f"table: {tbl.get('title','')}".strip())
            rows = tbl.get("rows") or []
            for row in rows:
                lines.append(f"  row: {row}")
    return "\n".join(lines)


def vision_node(state: PaperState) -> PaperState:
    """Run Vision on selected images and inject results into raw_text context."""
    image_paths = state.get("image_paths") or []
    if not image_paths:
        logger.warning("Vision: No images to process")
        # Update state with empty vision_output and return immediately
        return {**state, "vision_output": []}

    selected = select_images_for_vision(image_paths)
    if not selected:
        return state

    vision_url = get_vision_url()
    vision_results: List[Dict[str, Any]] = []
    project_id = state.get("project_id") or "default_project"
    artifacts_root = Path("/raid/artifacts") / project_id
    try:
        artifacts_root.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback for environments without /raid (tests/local)
        tmp_root = Path(tempfile.mkdtemp(prefix="vyasa_artifacts_"))
        artifacts_root = tmp_root / project_id
        artifacts_root.mkdir(parents=True, exist_ok=True)

    for path in selected:
        try:
            artifact_id = f"artifact-{uuid.uuid4()}"
            artifact_path = artifacts_root / f"{artifact_id}.png"
            try:
                shutil.copy(path, artifact_path)
            except Exception:
                logger.warning("Failed to copy artifact", extra={"payload": {"source": path, "target": str(artifact_path)}})
            with open(path, "rb") as fh:
                files = {"file": (os.path.basename(path), fh, "application/octet-stream")}
                resp = requests.post(
                    f"{vision_url}/v1/vision",
                    data={"payload": json.dumps({"model": VISION_MODEL_NAME, "image_path": path})},
                    files=files,
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                if "choices" in data:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    data = json.loads(content) if isinstance(content, str) else content
                vision_results.append(
                    {
                        "image_path": path,
                        "caption": data.get("caption", ""),
                        "extracted_facts": data.get("extracted_facts", []),
                        "tables": data.get("tables", []),
                        "confidence": data.get("confidence", 0.0),
                        "notes": data.get("notes", ""),
                        "artifact_id": artifact_id,
                    }
                )
        except Exception as exc:
            logger.warning(
                "Vision processing failed for image",
                extra={"payload": {"image_path": path, "error": str(exc)}},
            )
            continue

    if not vision_results:
        return state

    vision_context = build_vision_context(vision_results)
    raw_text = state.get("raw_text", "")
    combined_text = raw_text + "\n\n## Vision Extracts\n" + vision_context

    logger.info(
        "Vision context injected",
        extra={"payload": {"images_processed": len(vision_results), "context_chars": len(vision_context)}},
    )

    return {**state, "raw_text": combined_text, "vision_results": vision_results}


def saver_node(state: PaperState) -> PaperState:
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
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=ARANGODB_PASSWORD)
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
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "status": "SAVED",
        }
        logger.info("Saved extraction to ArangoDB", extra={"payload": {"status": doc["status"], "key": receipt.get("_key")}})

        # Persist manuscript blocks with versioning and citation guard (Librarian Key-Guard)
        if manuscript_blocks and project_id:
            from ..manuscript.service import ManuscriptService
            from ..shared.schema import ManuscriptBlock
            
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

        return {**state, "save_receipt": save_receipt}
    except Exception as e:
        logger.error(f"DB Save Failed: {e}", exc_info=True)
        raise  # Re-raise to ensure job failure is tracked
