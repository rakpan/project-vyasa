"""
Layered context packing helpers (opt-in).

Keeps implementation minimal: when enabled, it composes a single text block
with three layers:
- Corpus/document memory (structured summaries, metadata, provenance)
- Evidence window (top-K retrieved chunks)
- Working state (schema/constraints/conflicts)

Retrieval is stubbed and returns empty by default; callers may supply evidence
explicitly in state to avoid new dependencies.
"""

from typing import List, Dict, Any

from .librarian import LibrarianKernel

_telemetry_kernel = LibrarianKernel()


def build_extraction_layers(
    corpus_memory: List[Dict[str, Any]],
    evidence_chunks: List[Dict[str, Any]],
    working_state: Dict[str, Any],
) -> str:
    """Compose layered context for extraction."""
    lines: List[str] = []

    if corpus_memory:
        lines.append("## CORPUS MEMORY")
        for mem in corpus_memory:
            title = mem.get("title", "memory")
            summary = mem.get("summary", "")
            source = mem.get("source_id") or mem.get("doc_id") or "unknown"
            lines.append(f"- [{source}] {title}: {summary}")
        lines.append("")

    if evidence_chunks:
        lines.append("## EVIDENCE WINDOW (top-K)")
        for idx, chunk in enumerate(evidence_chunks, 1):
            text = chunk.get("text", "")
            src = chunk.get("source_id") or chunk.get("doc_id") or f"chunk-{idx}"
            prov = chunk.get("provenance") or {}
            cite = prov.get("citation") or f"cite:{src}"
            lines.append(f"[{cite}] {text}")
        lines.append("")

    if working_state:
        lines.append("## WORKING STATE")
        schema = working_state.get("schema")
        constraints = working_state.get("constraints") or []
        conflicts = working_state.get("conflicts") or []
        if schema:
            lines.append(f"Schema: {schema}")
        if constraints:
            lines.append("Constraints:")
            for c in constraints:
                lines.append(f"- {c}")
        if conflicts:
            lines.append("Conflicts:")
            for c in conflicts:
                lines.append(f"- {c}")

    return "\n".join(lines)


def stub_retrieve_evidence(_query: str, *, job_id: str | None = None, project_id: str | None = None) -> List[Dict[str, Any]]:
    """Placeholder retrieval hook. Returns empty list to avoid new dependencies while emitting telemetry."""
    try:
        _telemetry_kernel.log_retrieval_metrics(
            job_id=job_id,
            project_id=project_id,
            retrieval_hit=False,
            max_score=None,
            chunk_count=0,
            metadata={"stub": True},
        )
    except Exception:
        # Telemetry should never break caller
        pass
    return []
