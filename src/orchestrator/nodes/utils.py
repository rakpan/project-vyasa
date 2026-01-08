"""
Cross-cutting utility functions for workflow nodes.

This module contains utility functions that are used across multiple nodes
but don't belong to a specific domain (cartography, quality, synthesis, export).
"""

import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

import requests

from ...shared.config import get_vision_url, _env
from ...shared.model_registry import get_model_config
from ...shared.logger import get_logger
from ...shared.utils import get_utc_now
from ..state import ResearchState
from ..telemetry import get_telemetry_emitter, trace_node

logger = get_logger("orchestrator", __name__)
telemetry_emitter = get_telemetry_emitter()


def select_images_for_vision(image_paths: List[str]) -> List[str]:
    """Select a subset of images to send to Vision."""
    if not image_paths:
        return []
    max_images = int(_env("VISION_MAX_IMAGES", "5"))
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


@trace_node
def vision_node(state: ResearchState) -> ResearchState:
    """Run Vision on selected images and inject results into raw_text context."""
    # Import validate_state_schema from nodes.py to avoid circular imports
    from .nodes import validate_state_schema
    
    state = validate_state_schema(state)
    job_id = state.get("jobId") or state.get("job_id")
    
    # Debug logging for raw_text preservation at node entry
    raw_text = state.get("raw_text", "")
    logger.debug(
        "Vision node entry",
        extra={
            "payload": {
                "job_id": job_id,
                "raw_text_length": len(raw_text) if raw_text else 0,
                "has_raw_text": "raw_text" in state,
                "has_pdf_path": "pdf_path" in state,
                "state_keys": list(state.keys())[:20],  # Limit to first 20 keys for logging
            }
        }
    )
    image_paths = state.get("image_paths") or []
    if not image_paths:
        logger.warning("Vision: No images to process")
        # Update state with empty vision_output and return immediately
        # Preserve existing state (LangGraph will merge, but explicit is safer)
        return {**state, "vision_output": []}

    selected = select_images_for_vision(image_paths)
    if not selected:
        return {**state, "vision_output": []}

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
                vision_model = get_model_config("vision").model_id
                start = time.time()
                resp = requests.post(
                    f"{vision_url}/v1/vision",
                    data={"payload": json.dumps({"model": vision_model, "image_path": path})},
                    files=files,
                    timeout=60,
                )
                resp.raise_for_status()
                latency_ms = (time.time() - start) * 1000
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
                        "telemetry": {
                            "model_id": vision_model,
                            "task_type": "vision",
                            "latency_ms": latency_ms,
                            "kv_policy": get_model_config("vision").kv_policy,
                        },
                    }
                )
                telemetry_emitter.emit_event(
                    "llm_call",
                    {
                        "job_id": job_id,
                        "project_id": project_id,
                        "node_name": "vision",
                        "timestamp": get_utc_now().isoformat(),
                        "duration_ms": latency_ms,
                        "metadata": {
                            "model_id": vision_model,
                            "image_path": path,
                            "artifact_id": artifact_id,
                            "url": f"{vision_url}/v1/vision",
                        },
                    },
                )
        except Exception as exc:
            logger.warning(
                "Vision processing failed for image",
                extra={"payload": {"image_path": path, "error": str(exc)}},
            )
            continue

    if not vision_results:
        # Preserve state when no vision results (don't return empty dict which loses state)
        return {**state, "vision_results": []}

    vision_context = build_vision_context(vision_results)
    raw_text = state.get("raw_text", "")
    combined_text = raw_text + "\n\n## Vision Extracts\n" + vision_context

    logger.info(
        "Vision context injected",
        extra={"payload": {"images_processed": len(vision_results), "context_chars": len(vision_context)}},
    )

    # Preserve ALL state fields when returning (defensive preservation)
    return {**state, "raw_text": combined_text, "vision_results": vision_results}

