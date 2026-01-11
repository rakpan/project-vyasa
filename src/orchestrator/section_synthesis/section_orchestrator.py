"""
Section Synthesis Orchestrator for Project Vyasa.

Implements the complete section synthesis loop per orchestration spec:
1. Build section query
2. Retrieve + rerank (via RetrievalService)
3. Build Packet A (Primary Sources)
4. Build Packet B (Analytical Notes)
5. Synthesizer call (Nemotron 49B, section_writer profile)
6. Critic call (Nemotron 49B, cross_examiner profile)
7. Persistence (manuscript blocks + note promotions)
"""

import json
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from ...shared.logger import get_logger
from ...shared.config import (
    RETRIEVAL_TOP_K,
    RERANK_TOP_M,
    RERANKER_ENABLED,
)
from ...project.service import ProjectService
from ...project.types import ProjectConfig
from ..schemas.blueprint import BlueprintSection, DepthIntent, JournalSlot
from ..retrieval.retrieval_service import RetrievalService
from ..services.analytical_notes_service import AnalyticalNotesService
from ..services.blueprint_service import BlueprintService
from ..services.section_synthesis_service import SectionSynthesisService
from ..schemas.retrieval import RetrievalBundle
from ..schemas.evidence_pack import (
    EvidencePack,
    EvidencePointer,
    EvidenceSnippet,
    SourceMetadata,
    ModelVersions,
)
from ..schemas.analytical_notes import AnalyticalNote, NoteState
from ...shared.schema import ManuscriptBlock
from ..nodes.base import wrap_prompt_with_context
from ..nodes.nodes import route_to_expert, call_expert_with_fallback, ExpertType
from ..prompts import get_active_prompt_with_meta
from ..state import ExecutionTier, acquire_tier_b_slot, release_tier_b_slot
from arango.database import StandardDatabase

logger = get_logger("orchestrator", __name__)

# Configuration defaults
ANALYTICAL_NOTES_LIMIT = 10  # Max notes to include in Packet B

# Stage-to-Tier mapping for section synthesis
# Tier A: CPU/Embedder-bound (forkable, parallelizable)
# Tier B: GPU-bound (Nemotron-49B, bounded parallelism)
STAGE_TIER_MAP = {
    "query_building": ExecutionTier.TIER_A,
    "retrieval": ExecutionTier.TIER_A,
    "rerank": ExecutionTier.TIER_A,
    "packet_a": ExecutionTier.TIER_A,  # evidence_pack
    "packet_b": ExecutionTier.TIER_A,  # Building analytical notes packet
    "cartographer_pass2": ExecutionTier.TIER_B,  # Triple extraction (if applicable)
    "critique": ExecutionTier.TIER_B,  # critic_verify
    "synthesis": ExecutionTier.TIER_B,
    "persist": ExecutionTier.TIER_A,
    "complete": None,  # Terminal state, no tier
}


class SectionSynthesisError(Exception):
    """Error during section synthesis."""
    pass


def build_section_query(
    section: BlueprintSection,
    project_config: ProjectConfig,
) -> str:
    """Build section query from blueprint section + linked RQs.
    
    Args:
        section: BlueprintSection with heading, journal_slot, linked_rqs, depth_intent
        project_config: ProjectConfig with research_questions
    
    Returns:
        Query string for retrieval.
    """
    # Resolve RQ texts from linked_rqs
    rq_texts = []
    if section.linked_rqs:
        research_questions = project_config.research_questions or []
        for rq_id in section.linked_rqs:
            # Try to match RQ ID (e.g., "RQ1") to research_questions list
            # If linked_rqs contains RQ IDs, match by index
            try:
                if rq_id.startswith("RQ") and rq_id[2:].isdigit():
                    idx = int(rq_id[2:]) - 1
                    if 0 <= idx < len(research_questions):
                        rq_texts.append(research_questions[idx])
            except (ValueError, IndexError):
                pass
            # If linked_rqs contains RQ texts directly, use them
            if rq_id in research_questions:
                rq_texts.append(rq_id)
    
    # Build query based on depth_intent
    depth_goal_map = {
        DepthIntent.HOOK: "Attention-grabbing opening",
        DepthIntent.PROOF: "Detailed evidence and citations",
        DepthIntent.SO_WHAT: "Interpretation and implications",
    }
    depth_goal = depth_goal_map.get(section.depth_intent, "Detailed content")
    
    # Construct query
    query_parts = [
        f"For {section.journal_slot.value} section \"{section.heading}\":",
    ]
    
    if rq_texts:
        rq_text = "; ".join(rq_texts)
        query_parts.append(f"- Research Questions: {rq_text}")
    
    query_parts.append(f"- Depth Intent: {section.depth_intent.value}")
    query_parts.append(f"- Goal: {depth_goal}")
    
    query_text = "\n".join(query_parts)
    
    logger.debug(
        f"Built section query",
        extra={
            "payload": {
                "section_id": section.section_id,
                "heading": section.heading,
                "depth_intent": section.depth_intent.value,
                "rq_count": len(rq_texts),
            }
        }
    )
    
    return query_text


def estimate_tokens(text: str) -> int:
    """Rough token estimate from character length (4 chars per token average)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def build_evidence_pack(
    reranked_chunks: List[Dict[str, Any]],
    retrieval_bundle: RetrievalBundle,
    ingestion_id: str,
    project_id: str,
    section_id: Optional[str] = None,
) -> EvidencePack:
    """Build EvidencePack from RetrievalBundle top-M chunks.
    
    EvidencePack is a first-class persisted artifact with bounded snippet count (5-20)
    and bounded snippet size (~300-800 tokens per snippet).
    
    Args:
        reranked_chunks: List of reranked chunks (top-M from RetrievalBundle).
        retrieval_bundle: RetrievalBundle this EvidencePack is built from.
        ingestion_id: Ingestion identifier (required for evidence scoping).
        project_id: Project identifier.
        section_id: Optional blueprint section ID.
    
    Returns:
        EvidencePack with bounded snippets and pointers.
    
    Raises:
        ValueError: If snippet count is outside bounds (5-20) or snippet tokens exceed 800.
    """
    # Sort by rerank_rank if available, else by score (descending)
    if reranked_chunks:
        # Check if any chunk has rerank_rank
        has_rerank_rank = any(
            chunk.get("rerank_rank") is not None 
            for chunk in reranked_chunks
        )
        
        if has_rerank_rank:
            # Sort ascending by rerank_rank: rank 1 is best
            sorted_chunks = sorted(
                reranked_chunks,
                key=lambda x: x.get("rerank_rank") if x.get("rerank_rank") is not None else 999999,
                reverse=False,  # Ascending: rank 1 (best) comes first
            )
        else:
            # Sort descending by score: highest score is best
            sorted_chunks = sorted(
                reranked_chunks,
                key=lambda x: x.get("score", 0.0),
                reverse=True,  # Descending: highest score (best) comes first
            )
    else:
        sorted_chunks = []
    
    # Apply Tier A budgets: snippet count and token bounds
    from ...shared.runtime_budgets import get_tier_a_limits, cap_snippet_tokens
    tier_a_limits = get_tier_a_limits()
    max_snippets = tier_a_limits.get("max_snippets", 20)
    snippet_min_tokens = tier_a_limits.get("snippet_min_tokens", 50)
    snippet_max_tokens = tier_a_limits.get("snippet_max_tokens", 800)
    
    # Bound snippet count: at least 5, at most max_snippets
    if len(sorted_chunks) < 5:
        raise ValueError(f"EvidencePack requires at least 5 chunks, got {len(sorted_chunks)}")
    bounded_chunks = sorted_chunks[:max_snippets]  # Take at most max_snippets
    
    pointers: List[EvidencePointer] = []
    snippets: List[EvidenceSnippet] = []
    source_meta_map: Dict[str, SourceMetadata] = {}
    
    for chunk in bounded_chunks:
        chunk_id = chunk.get("chunk_id", "")
        text_content = chunk.get("text_content") or chunk.get("text", "")
        payload = chunk.get("payload", {})
        
        file_hash = payload.get("file_hash", "")
        file_id = file_hash or payload.get("doc_id", "") or payload.get("file_id", "")
        page_number = payload.get("page_number")
        section_label = payload.get("section_label") or payload.get("heading")
        
        # Build pointer
        pointer = EvidencePointer(
            chunk_id=chunk_id,
            file_id=file_id,
            doc_id=file_id,  # Alias
            page_number=page_number,
            section_label=section_label,
        )
        pointers.append(pointer)
        
        # Apply Tier A budget: cap snippet tokens
        truncated_text, token_estimate = cap_snippet_tokens(text_content)
        
        # Build source metadata if not already added
        if file_id and file_id not in source_meta_map:
            # Try to get filename from ingestion records or use file_hash
            filename = payload.get("filename") or payload.get("source_filename") or file_hash[:16] if file_hash else "unknown"
            source_meta_map[file_id] = SourceMetadata(
                filename=filename,
                url=payload.get("url"),
                doi=payload.get("doi"),
                ingestion_timestamp=payload.get("ingestion_timestamp"),
            )
        
        # Build snippet
        snippet = EvidenceSnippet(
            chunk_id=chunk_id,
            quote_text=truncated_text,
            page_number=page_number,
            token_estimate=token_estimate,
            source_meta=source_meta_map.get(file_id, {}).model_dump() if file_id in source_meta_map else {},
        )
        snippets.append(snippet)
    
    # Apply Tier B budget: cap Packet A total tokens
    from ...shared.runtime_budgets import cap_packet_a_tokens, cap_evidence_pack_snippets
    snippets = cap_evidence_pack_snippets(snippets)  # Cap snippet count first
    snippets = cap_packet_a_tokens(snippets)  # Then cap total tokens
    
    # Rebuild pointers to match capped snippets
    chunk_ids_in_snippets = {s.chunk_id for s in snippets}
    pointers = [p for p in pointers if p.chunk_id in chunk_ids_in_snippets]
    
    # Convert source_meta_map to dict keyed by file_id
    source_meta_dict = {
        file_id: meta.model_dump()
        for file_id, meta in source_meta_map.items()
    }
    
    # Build ModelVersions
    model_versions = ModelVersions(
        embedder_model_id=retrieval_bundle.embedder_model_id,
        reranker_model_id=retrieval_bundle.reranker_model_id,
    )
    
    # Build EvidencePack
    evidence_pack = EvidencePack(
        project_id=project_id,
        ingestion_id=ingestion_id,
        section_id=section_id,
        query_id=retrieval_bundle.query_id,
        pointers=pointers,
        snippets=snippets,
        source_meta=source_meta_dict,
        glossary_terms=[],  # Optional, can be populated later
        model_versions=model_versions,
        retrieval_bundle_id=retrieval_bundle.bundle_id,
    )
    
    logger.debug(
        f"Built EvidencePack",
        extra={
            "payload": {
                "pack_id": evidence_pack.pack_id,
                "snippet_count": len(snippets),
                "pointer_count": len(pointers),
                "retrieval_bundle_id": retrieval_bundle.bundle_id,
            }
        }
    )
    
    return evidence_pack


def build_packet_a(
    reranked_chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build Packet A (Primary Sources) from reranked chunks.
    
    DEPRECATED: Use build_evidence_pack() instead. This function is kept for backward compatibility.
    
    Args:
        reranked_chunks: List of reranked chunks with chunk_id, text_content, payload, score, etc.
    
    Returns:
        List of packet A entries with text snippets and citation handles.
    """
    packet_a = []
    
    # Sort by rerank_rank if available, else by score (descending)
    if reranked_chunks:
        # Check if any chunk has rerank_rank
        has_rerank_rank = any(
            chunk.get("rerank_rank") is not None 
            for chunk in reranked_chunks
        )
        
        if has_rerank_rank:
            # Sort ascending by rerank_rank: rank 1 is best
            sorted_chunks = sorted(
                reranked_chunks,
                key=lambda x: x.get("rerank_rank") if x.get("rerank_rank") is not None else 999999,
                reverse=False,  # Ascending: rank 1 (best) comes first
            )
        else:
            # Sort descending by score: highest score is best
            sorted_chunks = sorted(
                reranked_chunks,
                key=lambda x: x.get("score", 0.0),
                reverse=True,  # Descending: highest score (best) comes first
            )
    else:
        sorted_chunks = []
    
    for chunk in sorted_chunks:
        chunk_id = chunk.get("chunk_id", "")
        text_content = chunk.get("text_content") or chunk.get("text", "")
        payload = chunk.get("payload", {})
        
        # Build citation handle
        citation_handle = {
            "chunk_id": chunk_id,
            "page": payload.get("page_number"),
            "source": payload.get("file_hash", "")[:16] if payload.get("file_hash") else "",  # Short hash
        }
        
        # Include bbox if available
        if payload.get("bbox"):
            citation_handle["bbox"] = payload["bbox"]
        
        # Build snippet (truncate to 500 chars)
        snippet = {
            "text": text_content[:500],
            "citation": citation_handle,
            "full_chunk": chunk,  # Include full chunk for context
        }
        
        packet_a.append(snippet)
    
    logger.debug(
        f"Built Packet A",
        extra={"payload": {"chunk_count": len(packet_a)}}
    )
    
    return packet_a


def build_packet_b(
    project_id: str,
    section: BlueprintSection,
    notes_service: AnalyticalNotesService,
    state_filter: Optional[NoteState] = None,
) -> List[Dict[str, Any]]:
    """Build Packet B (Analytical Notes) relevant to section.
    
    Args:
        project_id: Project identifier.
        section: BlueprintSection with linked_rqs, tags (optional)
        notes_service: AnalyticalNotesService instance.
        state_filter: Optional state filter (default: include Draft and Manuscript).
    
    Returns:
        List of Analytical Notes formatted for Packet B.
    """
    # Query notes by linked_rqs and tags
    # Include both Draft and Manuscript notes (prefer Manuscript)
    notes = []
    
    # First, try Manuscript state notes (higher priority)
    manuscript_notes = notes_service.list_notes(
        project_id=project_id,
        state=NoteState.MANUSCRIPT,
        linked_rq=section.linked_rqs[0] if section.linked_rqs else None,
        tags=section.heading.split() if section.heading else None,  # Simple tag matching from heading words
        limit=ANALYTICAL_NOTES_LIMIT,
    )
    notes.extend(manuscript_notes)
    
    # Then, try Draft state notes (if we don't have enough)
    if len(notes) < ANALYTICAL_NOTES_LIMIT:
        draft_notes = notes_service.list_notes(
            project_id=project_id,
            state=NoteState.DRAFT,
            linked_rq=section.linked_rqs[0] if section.linked_rqs else None,
            tags=section.heading.split() if section.heading else None,
            limit=ANALYTICAL_NOTES_LIMIT - len(notes),
        )
        notes.extend(draft_notes)
    
    # Format notes for Packet B
    packet_b = []
    for note in notes[:ANALYTICAL_NOTES_LIMIT]:
        packet_b.append({
            "note_id": note.note_id,
            "text": note.text,
            "tags": note.tags,
            "linked_rq": note.linked_rq,
            "state": note.state.value,
            "source_ref": note.source_ref,
        })
    
    logger.debug(
        f"Built Packet B",
        extra={
            "payload": {
                "note_count": len(packet_b),
                "manuscript_notes": len([n for n in packet_b if n["state"] == "Manuscript"]),
            }
        }
    )
    
    return packet_b


def synthesize_section(
    section: BlueprintSection,
    evidence_pack: EvidencePack,
    packet_b: List[Dict[str, Any]],
    project_config: ProjectConfig,
    state: Optional[Dict[str, Any]] = None,
    db: Optional[Any] = None,
) -> str:
    r"""Synthesize section using Nemotron 49B with section_writer prompt profile.
    
    Tier-B call: Requires EvidencePack (not raw PDF).
    
    Protocol:
    - Uses canonical citation tokens: \cite{chunk:<chunk_id>} (no numeric superscripts in stored text)
    - Checks for locked sections (blocks synthesis if locked)
    - Outputs structured Markdown blocks with fixed headings
    
    Args:
        section: BlueprintSection with heading, journal_slot, depth_intent
        evidence_pack: EvidencePack (Packet A) - REQUIRED for Tier-B calls
        packet_b: Analytical Notes (style influence only)
        project_config: ProjectConfig for context wrapping
        state: Optional ResearchState for context injection
        db: Optional ArangoDB database for checking locked status
    
    Returns:
        Section text in Markdown format with canonical citation tokens \cite{chunk:<chunk_id>}.
    
    Raises:
        SectionSynthesisError: If EvidencePack is missing, section is locked, or synthesis fails.
    """
    # Validate EvidencePack is provided (Tier-B contract enforcement)
    if not evidence_pack:
        raise SectionSynthesisError("EvidencePack is required for Synthesizer (Tier-B call)")
    
    if not evidence_pack.snippets or len(evidence_pack.snippets) == 0:
        raise SectionSynthesisError("EvidencePack must contain at least one snippet (Tier-B contract violation)")
    
    # Locked text safety: Check if section is locked (blocks synthesis)
    if db:
        try:
            # Query blocks directly from ArangoDB collection
            # Check if any existing blocks for this section are locked
            query = """
            FOR block IN manuscript_blocks
                FILTER block.project_id == @project_id AND block.section_id == @section_id
                FILTER block.locked == true OR block.is_locked == true
                LIMIT 1
                RETURN block
            """
            cursor = db.aql.execute(
                query,
                bind_vars={
                    "project_id": project_config.project_id if hasattr(project_config, "project_id") else project_config.get("project_id"),
                    "section_id": section.section_id,
                }
            )
            locked_blocks = list(cursor)
            
            if locked_blocks:
                raise SectionSynthesisError(
                    f"Section {section.section_id} is locked. Synthesis blocked to prevent modifications."
                )
        except Exception as e:
            # Non-fatal: log and continue (locked check is best-effort)
            # If collection doesn't exist or query fails, allow synthesis to proceed
            logger.warning(f"Failed to check locked status: {e}", exc_info=True)
    
    # Convert EvidencePack to packet_a format for prompt formatting
    packet_a = [
        {
            "text": snippet.quote_text,
            "citation": {
                "chunk_id": snippet.chunk_id,
                "page": snippet.page_number,
                "source": pointer.file_id[:16] if pointer.file_id else "",
            },
        }
        for snippet, pointer in zip(evidence_pack.snippets, evidence_pack.pointers)
    ]
    from ..prompts.defaults import DEFAULT_SECTION_WRITER_PROMPT
    from ...shared.vocab_guard import get_vocab_guard
    from ...shared.prompt_registry import get_prompt as get_db_prompt
    
    # Fetch prompt from DB-backed registry (with fallback to Opik/defaults)
    prompt_profile = get_db_prompt("synthesizer_section_writer", DEFAULT_SECTION_WRITER_PROMPT)
    system_template = prompt_profile["template"]
    
    # Fallback to Opik/defaults if DB not available
    if prompt_profile.get("source") == "default":
        system_template, prompt_meta = get_active_prompt_with_meta(
            "vyasa-section-writer",
            DEFAULT_SECTION_WRITER_PROMPT,
        )
    else:
        # Use DB-backed template
        from ..prompts.models import PromptUse
        prompt_meta = PromptUse.from_template(
            prompt_name="synthesizer_section_writer",
            template=system_template,
            resolved_source="db",
            tag=f"v{prompt_profile.get('version', 0)}",
            cache_hit=False,
        )
    
    # Wrap with ProjectConfig context
    if state is None:
        state = {"project_context": project_config.model_dump()}
    else:
        state = {**state, "project_context": project_config.model_dump()}
    
    system_prompt = wrap_prompt_with_context(state, system_template)
    
    # Apply vocabulary guardrails (forbidden words check)
    try:
        vocab_guard = get_vocab_guard()
        if vocab_guard:
            system_prompt = vocab_guard.apply_constraints(system_prompt)
            logger.debug("Applied vocabulary guardrails to synthesizer prompt")
    except Exception as e:
        logger.warning(f"Failed to apply vocabulary guardrails: {e}", exc_info=True)
        # Non-fatal: continue without guardrails
    
    # Build user message (Sandwich Pattern)
    depth_instructions = {
        DepthIntent.HOOK: "Create an attention-grabbing opening that hooks the reader.",
        DepthIntent.PROOF: "Provide detailed evidence with citations from Packet A. Every factual claim must be cited.",
        DepthIntent.SO_WHAT: "Interpret the evidence and discuss implications. Connect findings to broader context.",
    }
    depth_instruction = depth_instructions.get(section.depth_intent, "Provide detailed content with citations.")
    
    # Format Packet A with citations
    packet_a_text = "EVIDENCE PACKET A (Primary Sources - MUST be cited):\n"
    for idx, entry in enumerate(packet_a, 1):
        citation = entry["citation"]
        text = entry["text"]
        chunk_id = citation.get("chunk_id", "")
        page = citation.get("page", "?")
        source = citation.get("source", "")
        
        packet_a_text += f"[{idx}] {text}\n"
        packet_a_text += f"    (chunk_id: {chunk_id}, page {page}, source: {source})\n\n"
    
    # Format Packet B
    packet_b_text = "ANALYTICAL NOTES PACKET B (Perspectives - Influence style only, NOT citeable):\n"
    if packet_b:
        for idx, note in enumerate(packet_b, 1):
            packet_b_text += f"Note {idx}: {note['text']}\n"
            note_tags = note.get("tags", [])
            note_linked_rq = note.get("linked_rq")  # Singular, not plural
            if note_tags or note_linked_rq:
                packet_b_text += "    ("
                if note_tags:
                    packet_b_text += f"tags: {', '.join(note_tags)}"
                if note_tags and note_linked_rq:
                    packet_b_text += ", "
                if note_linked_rq:
                    packet_b_text += f"linked RQ: {note_linked_rq}"
                packet_b_text += ")\n\n"
            else:
                packet_b_text += "\n"
    else:
        packet_b_text += "No analytical notes available.\n\n"
    
    # Store citation pattern to avoid backslash issues in f-string (Python 3.12 restriction)
    cite_pattern = "\\cite{chunk:<chunk_id>}"
    cite_example = "\\cite{chunk:chunk-123}"
    
    # Build user message using string concatenation to avoid f-string parsing issues
    user_message = (
        f"Section: {section.heading}\n"
        f"Journal Slot: {section.journal_slot.value}\n"
        f"Depth Intent: {section.depth_intent.value}\n\n"
        f"{packet_a_text}\n\n"
        f"{packet_b_text if packet_b else 'No analytical notes available.'}\n\n"
        "CRITICAL RULES:\n"
        "1. All factual claims and citations MUST come from Packet A (Primary Sources).\n"
        "2. Packet B (Analytical Notes) may influence style, analogies, and pedagogy ONLY.\n"
        f"3. Use sandwich pattern: {depth_instruction}\n"
        f"4. Include inline citations using CANONICAL format: {cite_pattern} for each claim from Packet A (e.g., {cite_example}).\n"
        f"5. Do NOT use numeric superscripts (e.g., [1], [2]) in the stored text. Only use {cite_pattern} format.\n"
        "6. Do NOT cite Packet B directly. Use it to guide framing and style.\n"
        "7. Generate section text in Markdown format with fixed headings (use ## for section heading, ### for subsections).\n"
        f"8. The compiler will later resolve {cite_pattern} tokens into numeric superscripts at render time.\n\n"
        "Generate the section text now:"
    )
    
    # Build prompt messages
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    
    # Route to Synthesizer (Brain/Nemotron 49B)
    expert_url, expert_name, expert_model = route_to_expert("section_synthesizer", ExpertType.PROSE_WRITING)
    
    # Acquire Tier B slot (serialize Nemotron calls: max-running-requests=1)
    if not acquire_tier_b_slot(blocking=True, timeout=300.0):  # 5 minute timeout
        raise SectionSynthesisError("Tier B slot unavailable (timeout waiting for Nemotron call slot)")
    
    # Apply Tier B budget: max output tokens
    from ...shared.runtime_budgets import get_output_max_tokens
    max_output_tokens = get_output_max_tokens("synthesizer")
    
    # Call LLM
    try:
        request_params = {
            "temperature": 0.7,
            "max_tokens": max_output_tokens,  # From runtime budgets
        }
        
        logger.debug(
            f"Using output max_tokens={max_output_tokens} for synthesizer (from budgets)",
            extra={"payload": {"agent": "synthesizer", "max_tokens": max_output_tokens}}
        )
        
        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=prompt_messages,
            request_params=request_params,
            node_name="section_synthesizer",
            state=state,
        )
        
        # Extract response text
        section_text = ""
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                section_text = message.get("content", "")
        elif isinstance(data, str):
            section_text = data
        else:
            # Try to parse as JSON
            try:
                parsed = json.loads(str(data)) if isinstance(data, str) else data
                section_text = parsed.get("synthesis") or parsed.get("text") or str(parsed)
            except (json.JSONDecodeError, AttributeError):
                section_text = str(data)
        
        if not section_text or not section_text.strip():
            raise SectionSynthesisError("Synthesizer returned empty response")
        
        # Normalize citation format: Convert any [[chunk:<id>]] or [[<id>]] to \cite{chunk:<id>}
        import re
        # Pattern 1: [[chunk:<id>]] -> \cite{chunk:<id>}
        section_text = re.sub(r'\[\[chunk:([^\]]+)\]\]', r'\\cite{chunk:\1}', section_text)
        # Pattern 2: [[<id>]] (backward compatible) -> \cite{chunk:<id>}
        # Only if it doesn't match claim: or chunk: prefix
        section_text = re.sub(r'\[\[(?!chunk:|claim:)([^\]]+)\]\]', r'\\cite{chunk:\1}', section_text)
        
        # Remove any numeric superscripts that may have been generated (safety check)
        # Pattern: [1], [2], etc. or ^1, ^2, etc.
        section_text = re.sub(r'\[\d+\]', '', section_text)  # Remove [1], [2], etc.
        section_text = re.sub(r'\^\d+', '', section_text)  # Remove ^1, ^2, etc.
        
        # Validate: Check for at least one canonical citation marker
        if r'\cite{chunk:' not in section_text:
            logger.warning(
                "Section text contains no canonical citation markers",
                extra={"payload": {"section_id": section.section_id, "text_length": len(section_text)}}
            )
            # Non-fatal in exploratory mode, fatal in conservative mode
            # Get rigor_level from project_config (may be dict or Pydantic model)
            if isinstance(project_config, dict):
                rigor_level = project_config.get("rigor_level", "exploratory")
            else:
                rigor_level = getattr(project_config, "rigor_level", "exploratory") or "exploratory"
            
            if rigor_level == "conservative":
                raise SectionSynthesisError("Section text must include canonical citation markers \\cite{chunk:<chunk_id>} in conservative mode")
        
        logger.info(
            f"Synthesized section",
            extra={
                "payload": {
                    "section_id": section.section_id,
                    "text_length": len(section_text),
                    "expert": expert_name,
                }
            }
        )
        
        return section_text
        
    except Exception as e:
        logger.error(
            f"Synthesis failed: {e}",
            extra={"payload": {"section_id": section.section_id}},
            exc_info=True
        )
        raise SectionSynthesisError(f"Synthesis failed: {str(e)}") from e
    finally:
        # Always release Tier B slot after synthesis completes (success or failure)
        release_tier_b_slot()


def criticize_section(
    section_text: str,
    evidence_pack: EvidencePack,
    packet_b: List[Dict[str, Any]],
    project_config: ProjectConfig,
    section_id: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Criticize section using Nemotron 49B with cross_examiner prompt profile.
    
    Tier-B call: Requires EvidencePack (not raw PDF).
    
    Args:
        section_text: Synthesized section text
        evidence_pack: EvidencePack (Packet A) - REQUIRED for Tier-B calls
        packet_b: Analytical Notes
        project_config: ProjectConfig for context
        section_id: Optional section ID for logging
        state: Optional ResearchState for context injection
    
    Returns:
        Dict with flags, promotions, vocabulary_suggestions, required_citations_missing.
    
    Raises:
        SectionSynthesisError: If EvidencePack is missing (Tier-B contract violation).
    """
    # Validate EvidencePack is provided (Tier-B contract enforcement)
    if not evidence_pack:
        raise SectionSynthesisError("EvidencePack is required for Critic (Tier-B call)")
    
    if not evidence_pack.snippets or len(evidence_pack.snippets) == 0:
        raise SectionSynthesisError("EvidencePack must contain at least one snippet (Tier-B contract violation)")
    
    # Convert EvidencePack to packet_a format for prompt formatting
    packet_a = [
        {
            "text": snippet.quote_text,
            "citation": {
                "chunk_id": snippet.chunk_id,
                "page": snippet.page_number,
                "source": pointer.file_id[:16] if pointer.file_id else "",
            },
        }
        for snippet, pointer in zip(evidence_pack.snippets, evidence_pack.pointers)
    ]
    
    from ..prompts.defaults import DEFAULT_CROSS_EXAMINER_PROMPT
    
    # Fetch prompt from Prompt Registry
    system_template, prompt_meta = get_active_prompt_with_meta(
        "vyasa-cross-examiner",
        DEFAULT_CROSS_EXAMINER_PROMPT,
    )
    
    # Wrap with ProjectConfig context
    if state is None:
        state = {"project_context": project_config.model_dump()}
    else:
        state = {**state, "project_context": project_config.model_dump()}
    
    system_prompt = wrap_prompt_with_context(state, system_template)
    
    # Format Packet A for validation
    packet_a_text = "Evidence Packet A (Primary Sources - Ground Truth):\n"
    for idx, entry in enumerate(packet_a, 1):
        citation = entry["citation"]
        text = entry["text"]
        chunk_id = citation.get("chunk_id", "")
        packet_a_text += f"[{idx}] {text} (chunk_id: {chunk_id})\n\n"
    
    # Format Packet B
    packet_b_text = "Analytical Notes Packet B (Perspectives - NOT citeable):\n"
    if packet_b:
        for idx, note in enumerate(packet_b, 1):
            packet_b_text += f"Note {idx} (ID: {note['note_id']}): {note['text']}\n"
            note_tags = note.get('tags', [])
            note_linked_rq = note.get('linked_rq')  # Singular, not plural
            if note_tags or note_linked_rq:
                packet_b_text += "    ("
                if note_tags:
                    packet_b_text += f"tags: {', '.join(note_tags)}"
                if note_tags and note_linked_rq:
                    packet_b_text += ", "
                if note_linked_rq:
                    packet_b_text += f"linked RQ: {note_linked_rq}"
                packet_b_text += ")\n\n"
            else:
                packet_b_text += "\n"
    else:
        packet_b_text += "No analytical notes available.\n\n"
    
    # Apply vocabulary guardrails check to section_text
    vocabulary_violations = []
    try:
        from ...shared.vocab_guard import get_vocab_guard
        vocab_guard = get_vocab_guard()
        if vocab_guard:
            forbidden_word = vocab_guard.check_forbidden(section_text)
            if forbidden_word:
                vocabulary_violations.append(f"Forbidden word '{forbidden_word}' found in section text")
                logger.warning(
                    f"Forbidden vocabulary detected in section text",
                    extra={"payload": {"section_id": section_id, "forbidden_word": forbidden_word}}
                )
    except Exception as e:
        logger.warning(f"Failed to check vocabulary guardrails: {e}", exc_info=True)
        # Non-fatal: continue without guardrail check
    
    vocab_clause = f"Vocabulary violations detected: {', '.join(vocabulary_violations)}" if vocabulary_violations else "No vocabulary violations detected."
    
    # Store citation pattern to avoid backslash issues in f-string (Python 3.12 restriction)
    cite_pattern = "\\cite{chunk:<chunk_id>}"
    
    # Build user message using string formatting to avoid f-string parsing issues in Python 3.12
    user_message = (
        "Section Draft:\n"
        f"{section_text}\n\n"
        f"{packet_a_text}\n\n"
        f"{packet_b_text}\n\n"
        "CRITICAL VALIDATION RULES:\n"
        f"1. Check that ALL citations {cite_pattern} in section_text reference chunks in Packet A.\n"
        "2. Flag any factual claims that cannot be traced to Packet A.\n"
        "3. Flag any analogies/framing in section_text that go beyond what's supported by Packet A.\n"
        "4. For each Analytical Note in Packet B:\n"
        "   - Check if note's framing/style is used appropriately (influences style, not facts).\n"
        "   - If note's framing is used AND supported by Packet A evidence:\n"
        "     → Propose promotion: Draft Note → Manuscript Note (with reason + linked evidence).\n"
        "   - If note's framing goes beyond Packet A:\n"
        '     → Flag as "overreach" (do not promote).\n'
        f"5. Check for vocabulary violations: {vocab_clause}\n"
        f"6. Ensure citations use canonical format: {cite_pattern} (not numeric superscripts like [1], [2]).\n\n"
        "Return JSON:\n"
        "{\n"
        '    "overreach_flags": ["flag1", "flag2", ...],\n'
        '    "suggested_promotions": [\n'
        "        {\n"
        '            "note_id": "uuid",\n'
        '            "reason": "Framing supported by evidence chunks [chunk_id1, chunk_id2]",\n'
        '            "linked_evidence": ["chunk_id1", "chunk_id2"]\n'
        "        },\n"
        "        ...\n"
        "    ],\n"
        '    "vocabulary_suggestions": ["suggestion1", ...],\n'
        '    "required_citations_missing": ["chunk_id1", "chunk_id2", ...]\n'
        "}"
    )
    
    # Build prompt messages
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    
    # Load prompt from DB-backed registry (with fallback to defaults)
    from ...shared.prompt_registry import get_prompt as get_db_prompt
    from ..prompts.defaults import DEFAULT_CROSS_EXAMINER_PROMPT
    
    prompt_profile = get_db_prompt("critic_verify", DEFAULT_CROSS_EXAMINER_PROMPT)
    system_template = prompt_profile["template"]
    
    # Route to Critic (Brain/Nemotron 49B)
    expert_url, expert_name, expert_model = route_to_expert("section_critic", ExpertType.LOGIC_REASONING)
    
    # Acquire Tier B slot (serialize Nemotron calls: max-running-requests=1)
    if not acquire_tier_b_slot(blocking=True, timeout=300.0):  # 5 minute timeout
        raise SectionSynthesisError("Tier B slot unavailable (timeout waiting for Nemotron call slot)")
    
    # Apply Tier B budget: max output tokens
    from ...shared.runtime_budgets import get_output_max_tokens
    max_output_tokens = get_output_max_tokens("critic")
    
    # Call LLM
    try:
        request_params = {
            "temperature": 0.3,  # Lower temperature for critical analysis
            "max_tokens": max_output_tokens,  # From runtime budgets
            "response_format": {"type": "json_object"},  # Require JSON response
        }
        
        logger.debug(
            f"Using prompt profile v{prompt_profile.get('version', 0)} and output max_tokens={max_output_tokens} for critic",
            extra={"payload": {"agent": "critic", "max_tokens": max_output_tokens, "prompt_version": prompt_profile.get("version", 0), "prompt_source": prompt_profile.get("source", "default")}}
        )
        
        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=prompt_messages,
            request_params=request_params,
            node_name="section_critic",
            state=state,
        )
        
        # Parse JSON response
        response_text = ""
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                response_text = message.get("content", "")
        elif isinstance(data, str):
            response_text = data
        
        if not response_text:
            # Fallback: empty critique
            logger.warning("Critic returned empty response", extra={"payload": {"section_id": section_id}})
            return {
                "overreach_flags": [],
                "suggested_promotions": [],
                "vocabulary_suggestions": [],
                "required_citations_missing": [],
            }
        
        # Parse JSON
        try:
            critique = json.loads(response_text) if isinstance(response_text, str) else response_text
        except json.JSONDecodeError:
            logger.warning(
                "Critic response is not valid JSON, using empty critique",
                extra={"payload": {"section_id": section_id, "response_preview": response_text[:200]}}
            )
            return {
                "overreach_flags": [],
                "suggested_promotions": [],
                "vocabulary_suggestions": [],
                "required_citations_missing": [],
            }
        
        # Validate structure
        result = {
            "overreach_flags": critique.get("overreach_flags", []),
            "suggested_promotions": critique.get("suggested_promotions", []),
            "vocabulary_suggestions": critique.get("vocabulary_suggestions", []),
            "required_citations_missing": critique.get("required_citations_missing", []),
        }
        
        logger.info(
            f"Critiqued section",
            extra={
                "payload": {
                    "section_id": section_id,
                    "overreach_flags": len(result["overreach_flags"]),
                    "promotions_suggested": len(result["suggested_promotions"]),
                }
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Critic call failed: {e}",
            extra={"payload": {"section_id": section_id}},
            exc_info=True
        )
        # Non-fatal: return empty critique
        return {
            "overreach_flags": [],
            "suggested_promotions": [],
            "vocabulary_suggestions": [],
            "required_citations_missing": [],
        }
    finally:
        # Always release Tier B slot after critique completes (success or failure)
        release_tier_b_slot()


def run_section_synthesis(
    project_id: str,
    section_id: str,
    ingestion_id: Optional[str] = None,
    blueprint_version: Optional[int] = None,
    db: Optional[StandardDatabase] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run complete section synthesis loop.
    
    Orchestrates the 8-step section synthesis loop:
    1. Build section query
    2. Retrieve + rerank
    3. Build Packet A
    4. Build Packet B
    5. Synthesizer call
    6. Critic call
    7. Persistence
    8. Return results
    
    Args:
        project_id: Project identifier
        section_id: Blueprint section identifier
        ingestion_id: Optional ingestion identifier (required for retrieval)
        blueprint_version: Optional blueprint version (default: latest)
        db: Optional ArangoDB database instance (for persistence)
    
    Returns:
        Dict with:
        - bundle_id: RetrievalBundle ID
        - block_ids: List of manuscript block IDs
        - promotions_applied: Number of note promotions
        - section_text: Synthesized section text
        - critique: Critic output
    
    Raises:
        SectionSynthesisError: If any critical step fails.
    """
    from arango import ArangoClient
    from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
    
    # Initialize services
    if db is None:
        try:
            client = ArangoClient(hosts=get_memory_url())
            db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        except Exception as e:
            raise SectionSynthesisError(f"Failed to connect to database: {e}") from e
    
    blueprint_service = BlueprintService(db)
    notes_service = AnalyticalNotesService(db)
    retrieval_service = RetrievalService(db)
    synthesis_service = SectionSynthesisService(db)
    
    # Get project config
    from ...project.service import ProjectService
    project_service = ProjectService(db)
    try:
        project_config = project_service.get_project(project_id)
    except ValueError as e:
        raise SectionSynthesisError(f"Project {project_id} not found") from e
    
    # Get blueprint and section
    blueprint = blueprint_service.get_blueprint(project_id, version=blueprint_version)
    if not blueprint:
        raise SectionSynthesisError(f"Blueprint not found for project {project_id}")
    
    # Find section in blueprint and determine its position
    section = None
    section_index = None
    for idx, s in enumerate(blueprint.sections):
        if s.section_id == section_id:
            section = s
            section_index = idx  # 0-based index
            break
    
    if not section:
        raise SectionSynthesisError(f"Section {section_id} not found in blueprint")
    
    if not ingestion_id:
        raise SectionSynthesisError("ingestion_id is required for retrieval")
    
    # Helper to update job progress
    def update_progress(stage: str, progress: float, message: Optional[str] = None):
        """Update job progress if job_id is provided.
        
        Includes tier information based on STAGE_TIER_MAP.
        """
        if job_id:
            try:
                from ..job_store import update_job_record
                from ..state import JobStatus
                
                # Get tier for this stage
                tier = STAGE_TIER_MAP.get(stage)
                tier_value = tier.value if tier else None
                
                update_data = {
                    "current_step": stage,
                    "progress": progress,
                    "message": message or f"Section synthesis: {stage}",
                    "status": JobStatus.PROCESSING.value if progress < 1.0 else JobStatus.SUCCEEDED.value,
                }
                
                # Include tier if available
                if tier_value:
                    update_data["tier"] = tier_value
                
                update_job_record(job_id, update_data)
            except Exception as e:
                logger.warning(f"Failed to update job progress: {e}", exc_info=True)
    
    # Step 1: Build section query
    update_progress("query_building", 0.1, "Building section query")
    query_text = build_section_query(section, project_config)
    
    # Step 2: Retrieve + rerank (via RetrievalService)
    update_progress("retrieval", 0.2, "Retrieving evidence chunks")
    # Section synthesis uses reranking for quality (explicitly opt-in)
    reranked_chunks, bundle_id = retrieval_service.retrieve_for_section(
        query_text=query_text,
        project_id=project_id,
        ingestion_id=ingestion_id,
        section_id=section_id,
        top_k=RETRIEVAL_TOP_K,
        top_m=RERANK_TOP_M,
        use_reranker=True,  # Section synthesis opts into reranking for quality
    )
    
    if not reranked_chunks:
        raise SectionSynthesisError("No chunks retrieved for section synthesis")
    
    update_progress("rerank", 0.3, "Reranking evidence chunks")
    
    # Step 3: Build EvidencePack (Packet A) from RetrievalBundle
    update_progress("packet_a", 0.4, "Building evidence packet")
    
    # Get RetrievalBundle
    from ..services.retrieval_bundle_service import RetrievalBundleService
    bundle_service = RetrievalBundleService(db)
    retrieval_bundle = bundle_service.get_bundle(bundle_id) if bundle_id else None
    
    if not retrieval_bundle:
        raise SectionSynthesisError(f"RetrievalBundle {bundle_id} not found")
    
    # Build EvidencePack from RetrievalBundle top-M chunks
    evidence_pack = build_evidence_pack(
        reranked_chunks=reranked_chunks,
        retrieval_bundle=retrieval_bundle,
        ingestion_id=ingestion_id,
        project_id=project_id,
        section_id=section_id,
    )
    
    # Persist EvidencePack
    from ..services.evidence_pack_service import EvidencePackService
    pack_service = EvidencePackService(db)
    
    # Opik tracing: EvidencePack creation (critical path span 1)
    from ..telemetry.opik_emitter import get_opik_emitter
    opik_emitter = get_opik_emitter()
    error_msg = None
    
    try:
        evidence_pack = pack_service.save_pack(evidence_pack)
        
        logger.info(
            f"Built and persisted EvidencePack",
            extra={
                "payload": {
                    "pack_id": evidence_pack.pack_id,
                    "retrieval_bundle_id": bundle_id,
                    "snippet_count": len(evidence_pack.snippets),
                }
            }
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to persist EvidencePack: {e}", exc_info=True)
        raise
    finally:
        # Emit span even on failure (with error field)
        opik_emitter.emit_span(
            span_name="evidence_pack_creation",
            job_id=job_id or f"section_{section_id}",
            project_id=project_id,
            ingestion_id=ingestion_id,
            meta={
                "retrieval_bundle_id": bundle_id,
                "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
                "section_id": section_id,
                "snippet_count": len(evidence_pack.snippets) if evidence_pack else 0,
            },
            error=error_msg,
        )
    
    # Build legacy packet_a format for backward compatibility with synthesize_section/criticize_section
    packet_a = [
        {
            "text": snippet.quote_text,
            "citation": {
                "chunk_id": snippet.chunk_id,
                "page": snippet.page_number,
                "source": pointer.file_id[:16] if pointer.file_id else "",
            },
        }
        for snippet, pointer in zip(evidence_pack.snippets, evidence_pack.pointers)
    ]
    
    # Step 4: Build Packet B
    update_progress("packet_b", 0.5, "Building analytical notes packet")
    packet_b = build_packet_b(project_id, section, notes_service)
    
    # Apply Tier B budget: cap Packet B total tokens
    from ...shared.runtime_budgets import cap_packet_b_tokens
    packet_b = cap_packet_b_tokens(packet_b)
    
    # Step 5: Synthesizer call
    update_progress("synthesis", 0.6, "Synthesizing section content")
    state = {
        "project_id": project_id,
        "job_id": f"section_{section_id}",
        "jobId": f"section_{section_id}",
        "threadId": f"section_{section_id}",
        "project_context": project_config.model_dump(),
    }
    
    section_text = synthesize_section(
        section=section,
        evidence_pack=evidence_pack,
        packet_b=packet_b,
        project_config=project_config,
        state=state,
        db=db,  # Pass db for locked section check
    )
    
    # Step 6: Critic call
    update_progress("critique", 0.8, "Validating section content")
    critique = criticize_section(
        section_text=section_text,
        evidence_pack=evidence_pack,
        packet_b=packet_b,
        project_config=project_config,
        section_id=section_id,  # Pass section_id for logging
        state=state,
    )
    
    # Step 6.5: Inject visual anchor markers if section has visual_anchors
    if section.visual_anchors:
        visual_markers = []
        for anchor in section.visual_anchors:
            # Determine marker type from anchor_type
            anchor_type_upper = anchor.anchor_type.upper()
            if anchor_type_upper in ("TABLE", "TAB"):
                marker_type = "TABLE"
            elif anchor_type_upper in ("FIGURE", "FIG", "IMAGE", "CHART"):
                marker_type = "FIGURE"
            else:
                # Default to FIGURE for unknown types
                marker_type = "FIGURE"
            
            # Create marker: [[FIGURE:<anchor_id>]] or [[TABLE:<anchor_id>]]
            marker = f"[[{marker_type}:{anchor.anchor_id}]]"
            visual_markers.append(marker)
        
        # Append markers at end of section (or use placement_hint if available in future)
        if visual_markers:
            section_text += "\n\n" + "\n".join(visual_markers)
    
    # Step 7: Persistence
    update_progress("persist", 0.9, "Persisting section blocks")
    # Get RetrievalBundle
    from ..services.retrieval_bundle_service import RetrievalBundleService
    bundle_service = RetrievalBundleService(db)
    retrieval_bundle = bundle_service.get_bundle(bundle_id) if bundle_id else None
    
    if not retrieval_bundle:
        # Create a minimal RetrievalBundle if not persisted (fallback)
        # This should not happen in normal flow - RetrievalService should persist it
        if not ingestion_id:
            raise SectionSynthesisError("ingestion_id is required for RetrievalBundle persistence")
        
        retrieval_bundle = RetrievalBundle.create(
            query_text=query_text,
            project_id=project_id,
            ingestion_id=ingestion_id,  # Required for evidence scoping
            candidate_chunks=reranked_chunks,  # Fallback: use reranked as candidates
            reranked_chunks=reranked_chunks,
            embedder_model_id="nvidia/nv-embedqa-e5-v5",
            reranker_model_id="nvidia/llama-3.2-nv-rerankqa-1b-v2" if RERANKER_ENABLED else "none",
            top_k_embed=RETRIEVAL_TOP_K,
            top_k_rerank=RERANK_TOP_M,
            section_id=section_id,
        )
        bundle_service.save_bundle(retrieval_bundle)
        bundle_id = retrieval_bundle.bundle_id
    
    # Extract chunk IDs from Packet A for provenance
    chunk_ids = [entry["citation"]["chunk_id"] for entry in packet_a if entry["citation"].get("chunk_id")]
    
    # Extract note IDs from promotions
    promotion_note_ids = [
        prom.get("note_id")
        for prom in critique.get("suggested_promotions", [])
        if prom.get("note_id")
    ]
    
    # Extract chunk citations from section_text (canonical format: \cite{chunk:<id>})
    import re
    # Pattern 1: \cite{chunk:<id>} (canonical format)
    chunk_citation_pattern = r'\\cite\{chunk:([^\}]+)\}'
    chunk_citations_canonical = re.findall(chunk_citation_pattern, section_text)
    
    # Pattern 2: Backward compatibility - [[chunk:<id>]] or [[<id>]] (convert to canonical if found)
    # This handles any legacy format that may have slipped through
    legacy_chunk_pattern = r'\[\[chunk:([^\]]+)\]\]'
    legacy_simple_pattern = r'\[\[(?!chunk:|claim:)([^\]]+)\]\]'
    chunk_citations_legacy = re.findall(legacy_chunk_pattern, section_text) + re.findall(legacy_simple_pattern, section_text)
    
    # Combine and deduplicate chunk citations (prefer canonical format)
    chunk_citation_ids = list(set(chunk_citations_canonical + chunk_citations_legacy))
    
    # Extract actual claim IDs if present (format: \cite{claim:<id>} or [[claim:<id>]])
    claim_citation_pattern_canonical = r'\\cite\{claim:([^\}]+)\}'
    claim_citation_pattern_legacy = r'\[\[claim:([^\]]+)\]\]'
    claim_ids = list(set(re.findall(claim_citation_pattern_canonical, section_text) + re.findall(claim_citation_pattern_legacy, section_text)))
    
    # citation_keys should remain empty for section blocks (reserved for BibTeX keys)
    citation_keys = []
    
    # Determine block type based on depth_intent (for future: split into hook/proof/so_what sub-blocks)
    # For now, create a single block per section
    section_block = ManuscriptBlock(
        block_id=f"section_{section_id}_{int(datetime.now(timezone.utc).timestamp())}",  # Unique block ID
        section_title=section.heading,
        content=section_text,
        order_index=section_index,  # Set to section's position in blueprint (0-based)
        claim_ids=claim_ids,  # Only actual KG claim IDs (from [[claim:<id>]] if present)
        citation_keys=citation_keys,  # BibTeX citation keys (empty for section blocks)
        chunk_ids=chunk_citation_ids if chunk_citation_ids else chunk_ids,  # Chunk citations from text ([[chunk:<id>]]), fallback to Packet A chunks
        retrieval_bundle_id=bundle_id,
        section_id=section_id,
        note_ids=promotion_note_ids,  # Provenance: notes that influenced (and were promoted)
        model_ids={
            "embedder": "nvidia/nv-embedqa-e5-v5",
            "reranker": "nvidia/llama-3.2-nv-rerankqa-1b-v2" if RERANKER_ENABLED else "none",
            "synthesizer": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5",
            "critic": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5",
        },
    )
    
    # Persist section run
    promotions = [
        {
            "note_id": prom.get("note_id"),
            "reason": prom.get("reason", ""),
            "linked_evidence": prom.get("linked_evidence", []),
        }
        for prom in critique.get("suggested_promotions", [])
    ]
    
    # Opik tracing: Final compile/section persist (critical path span 4)
    from ..telemetry.opik_emitter import get_opik_emitter
    opik_emitter = get_opik_emitter()
    persist_error = None
    persistence_results = {}
    
    try:
        persistence_results = synthesis_service.persist_section_run(
            project_id=project_id,
            section_id=section_id,
            retrieval_bundle=retrieval_bundle,
            section_draft=section_block,
            promotions=promotions,
        )
        
        logger.info(
            f"Section synthesis completed",
            extra={
                "payload": {
                    "project_id": project_id,
                    "section_id": section_id,
                    "bundle_id": bundle_id,
                    "block_id": section_block.block_id,
                    "promotions_applied": persistence_results.get("promotions_applied", 0),
                }
            }
        )
    except Exception as e:
        persist_error = str(e)
        logger.error(f"Failed to persist section run: {e}", exc_info=True)
        raise
    finally:
        # Emit span even on failure (with error field)
        opik_emitter.emit_span(
            span_name="section_persist",
            job_id=job_id or f"section_{section_id}",
            project_id=project_id,
            ingestion_id=ingestion_id,
            meta={
                "block_id": section_block.block_id,
                "section_id": section_id,
                "retrieval_bundle_id": bundle_id,
                "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
                "promotions_applied": persistence_results.get("promotions_applied", 0) if not persist_error else 0,
            },
            error=persist_error,
        )
    
    # Mark as complete (use update_progress for consistency, tier will be None for complete)
    update_progress("complete", 1.0, "Section synthesis completed")
    
    return {
        "bundle_id": bundle_id,
        "block_id": section_block.block_id,
        "block_ids": [section_block.block_id],  # For now, single block
        "promotions_applied": persistence_results["promotions_applied"],
        "section_text": section_text,
        "critique": critique,
        "persistence_results": persistence_results,
    }
