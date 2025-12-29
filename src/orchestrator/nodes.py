"""
Workflow nodes for the agentic Cartographer -> Critic loop.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

import requests

from ..shared.config import get_worker_url, get_vision_url, get_memory_url, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
from ..shared.logger import get_logger
from .state import PaperState
from .normalize import normalize_extracted_json
from arango import ArangoClient

logger = get_logger("orchestrator", __name__)


def cartographer_node(state: PaperState) -> PaperState:
    """Extract graph JSON from raw text using Cortex Worker, incorporating prior critiques.
    
    Uses Worker (SGLang) to extract structured knowledge graph with STRICT JSON
    requirements. The output is normalized to guarantee a `triples` array structure
    that the console expects.
    
    Args:
        state: PaperState containing raw_text and optional critiques.
        
    Returns:
        Updated PaperState with extracted_json containing guaranteed `triples` array.
        
    Raises:
        ValueError: If raw_text is missing.
        requests.RequestException: If Worker API call fails.
    """
    raw_text = state.get("raw_text", "")
    critiques = state.get("critiques", []) or []

    if not raw_text:
        raise ValueError("raw_text is required for cartographer node")

    # Build strict extraction prompt requiring triples array
    system_prompt = """You are the Cartographer. Extract a structured knowledge graph from text as JSON.

CRITICAL REQUIREMENTS:
- Output MUST be valid JSON only (no prose, no markdown code blocks)
- MUST include a "triples" array, even if empty
- Each triple must have: subject, predicate, object, confidence (0.0-1.0), and optional evidence

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
                "model": "nvidia/nemotron-3-nano-30b",  # Use configured model
                "messages": prompt,
                "temperature": 0.1,  # Lower temperature for more deterministic extraction
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


def critic_node(state: PaperState) -> PaperState:
    """Validate extracted graph and return pass/fail with critiques.
    
    Uses Worker (cheap model) service for validation.
    """
    extracted = state.get("extracted_json") or {}

    critique_prompt = [
        {
            "role": "system",
            "content": "You are the Critic. Validate the extracted graph JSON for completeness, missing source IDs, and hallucinations.",
        },
        {"role": "user", "content": json.dumps(extracted, ensure_ascii=False)},
    ]

    try:
        # Critic uses Worker (cheap model) service
        worker_url = get_worker_url()
        response = requests.post(
            f"{worker_url}/v1/chat/completions",
            json={
                "model": "meta-llama/Llama-3.1-8B-Instruct",  # Cheap model for validation
                "messages": critique_prompt,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        parsed = json.loads(content) if isinstance(content, str) else content
        status = parsed.get("status", "fail").lower()
        critiques = parsed.get("critiques", [])
        if not isinstance(critiques, list):
            critiques = [str(critiques)]
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
        return state

    selected = select_images_for_vision(image_paths)
    if not selected:
        return state

    vision_url = get_vision_url()
    vision_results: List[Dict[str, Any]] = []

    for path in selected:
        try:
            with open(path, "rb") as fh:
                payload = {
                    "model": "vision-model",
                    "image_path": path,
                }
                files = {"file": (os.path.basename(path), fh, "application/octet-stream")}
                response = requests.post(
                    f"{vision_url}/v1/vision",
                    data={"payload": json.dumps(payload)},
                    files=files,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
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
    """Persist extracted graph to ArangoDB with a status flag and receipt."""
    extracted = state.get("extracted_json") or {}
    critiques = state.get("critiques", []) or []
    status = state.get("critic_status", "pass")
    vision_results = state.get("vision_results", [])

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=ARANGODB_PASSWORD)
        if not db.has_collection("extractions"):
            db.create_collection("extractions")
        collection = db.collection("extractions")
        doc: Dict[str, Any] = {
            "graph": extracted,
            "critiques": critiques,
            "status": status if status == "pass" else "needs_manual_review",
            "vision_results": vision_results,
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
        return {**state, "save_receipt": save_receipt}
    except Exception:
        logger.error("Failed to save extraction to ArangoDB", exc_info=True)
        raise
