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
from ..schemas.analytical_notes import AnalyticalNote, NoteState
from ...shared.schema import ManuscriptBlock
from ..nodes.base import wrap_prompt_with_context
from ..nodes.nodes import route_to_expert, call_expert_with_fallback, ExpertType
from ..prompts import get_active_prompt_with_meta
from arango.database import StandardDatabase

logger = get_logger("orchestrator", __name__)

# Configuration defaults
ANALYTICAL_NOTES_LIMIT = 10  # Max notes to include in Packet B


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


def build_packet_a(
    reranked_chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build Packet A (Primary Sources) from reranked chunks.
    
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
    packet_a: List[Dict[str, Any]],
    packet_b: List[Dict[str, Any]],
    project_config: ProjectConfig,
    state: Optional[Dict[str, Any]] = None,
) -> str:
    """Synthesize section using Nemotron 49B with section_writer prompt profile.
    
    Args:
        section: BlueprintSection with heading, journal_slot, depth_intent
        packet_a: Primary Sources with citations
        packet_b: Analytical Notes (style influence only)
        project_config: ProjectConfig for context wrapping
        state: Optional ResearchState for context injection
    
    Returns:
        Section text in Markdown format with inline citations.
    
    Raises:
        SectionSynthesisError: If synthesis fails.
    """
    from ..prompts.defaults import DEFAULT_SECTION_WRITER_PROMPT
    from ...shared.vocab_guard import get_vocab_guard
    
    # Fetch prompt from Prompt Registry
    system_template, prompt_meta = get_active_prompt_with_meta(
        "vyasa-section-writer",
        DEFAULT_SECTION_WRITER_PROMPT,
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
    
    user_message = f"""Section: {section.heading}
Journal Slot: {section.journal_slot.value}
Depth Intent: {section.depth_intent.value}

{packet_a_text}

{packet_b_text if packet_b else "No analytical notes available."}

CRITICAL RULES:
1. All factual claims and citations MUST come from Packet A (Primary Sources).
2. Packet B (Analytical Notes) may influence style, analogies, and pedagogy ONLY.
3. Use sandwich pattern: {depth_instruction}
4. Include inline citations: [[chunk:<chunk_id>]] for each claim from Packet A (e.g., [[chunk:chunk-123]]).
5. Do NOT cite Packet B directly. Use it to guide framing and style.
6. Generate section text in Markdown format.

Generate the section text now:"""
    
    # Build prompt messages
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    
    # Route to Synthesizer (Brain/Nemotron 49B)
    expert_url, expert_name, expert_model = route_to_expert("section_synthesizer", ExpertType.PROSE_WRITING)
    
    # Call LLM
    try:
        request_params = {
            "temperature": 0.7,
            "max_tokens": 4096,  # Reasonable limit for section text
        }
        
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
        
        # Validate: Check for at least one citation marker
        if "[[chunk_id" not in section_text and "[[" not in section_text:
            logger.warning(
                "Section text contains no citation markers",
                extra={"payload": {"section_id": section.section_id, "text_length": len(section_text)}}
            )
            # Non-fatal in exploratory mode, fatal in conservative mode
            # Get rigor_level from project_config (may be dict or Pydantic model)
            if isinstance(project_config, dict):
                rigor_level = project_config.get("rigor_level", "exploratory")
            else:
                rigor_level = getattr(project_config, "rigor_level", "exploratory") or "exploratory"
            
            if rigor_level == "conservative":
                raise SectionSynthesisError("Section text must include citation markers [[chunk:<chunk_id>]] in conservative mode")
        
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


def criticize_section(
    section_text: str,
    packet_a: List[Dict[str, Any]],
    packet_b: List[Dict[str, Any]],
    project_config: ProjectConfig,
    section_id: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Criticize section using Nemotron 49B with cross_examiner prompt profile.
    
    Args:
        section_text: Synthesized section text
        packet_a: Primary Sources with citations
        packet_b: Analytical Notes
        project_config: ProjectConfig for context
        state: Optional ResearchState for context injection
    
    Returns:
        Dict with flags, promotions, vocabulary_suggestions, required_citations_missing.
    """
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
    
    user_message = f"""Section Draft:
{section_text}

{packet_a_text}

{packet_b_text}

CRITICAL VALIDATION RULES:
1. Check that ALL citations [[chunk:<chunk_id>]] in section_text reference chunks in Packet A.
2. Flag any factual claims that cannot be traced to Packet A.
3. Flag any analogies/framing in section_text that go beyond what's supported by Packet A.
4. For each Analytical Note in Packet B:
   - Check if note's framing/style is used appropriately (influences style, not facts).
   - If note's framing is used AND supported by Packet A evidence:
     → Propose promotion: Draft Note → Manuscript Note (with reason + linked evidence).
   - If note's framing goes beyond Packet A:
     → Flag as "overreach" (do not promote).
5. Check for vocabulary violations: {vocab_clause}

Return JSON:
{{
    "overreach_flags": ["flag1", "flag2", ...],
    "suggested_promotions": [
        {{
            "note_id": "uuid",
            "reason": "Framing supported by evidence chunks [chunk_id1, chunk_id2]",
            "linked_evidence": ["chunk_id1", "chunk_id2"]
        }},
        ...
    ],
    "vocabulary_suggestions": ["suggestion1", ...],
    "required_citations_missing": ["chunk_id1", "chunk_id2", ...]
}}"""
    
    # Build prompt messages
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    
    # Route to Critic (Brain/Nemotron 49B)
    expert_url, expert_name, expert_model = route_to_expert("section_critic", ExpertType.LOGIC_REASONING)
    
    # Call LLM
    try:
        request_params = {
            "temperature": 0.3,  # Lower temperature for critical analysis
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},  # Require JSON response
        }
        
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


def run_section_synthesis(
    project_id: str,
    section_id: str,
    ingestion_id: Optional[str] = None,
    blueprint_version: Optional[int] = None,
    db: Optional[StandardDatabase] = None,
    job_id: Optional[str] = None,
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
        """Update job progress if job_id is provided."""
        if job_id:
            try:
                from ..job_store import update_job_record
                from ..state import JobStatus
                update_job_record(job_id, {
                    "current_step": stage,
                    "progress": progress,
                    "message": message or f"Section synthesis: {stage}",
                    "status": JobStatus.PROCESSING.value if progress < 1.0 else JobStatus.SUCCEEDED.value,
                })
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
    
    # Step 3: Build Packet A
    update_progress("packet_a", 0.4, "Building evidence packet")
    packet_a = build_packet_a(reranked_chunks)
    
    # Step 4: Build Packet B
    update_progress("packet_b", 0.5, "Building analytical notes packet")
    packet_b = build_packet_b(project_id, section, notes_service)
    
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
        packet_a=packet_a,
        packet_b=packet_b,
        project_config=project_config,
        state=state,
    )
    
    # Step 6: Critic call
    update_progress("critique", 0.8, "Validating section content")
    critique = criticize_section(
        section_text=section_text,
        packet_a=packet_a,
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
        # Create a minimal RetrievalBundle if not persisted
        retrieval_bundle = RetrievalBundle.create(
            query_text=query_text,
            project_id=project_id,
            candidate_chunks=reranked_chunks,
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
    
    # Extract chunk citations from section_text (look for [[chunk:<id>]] or [[<id>]] patterns)
    # Support both formats: [[chunk:<id>]] (preferred) and [[<id>]] (backward compatible)
    import re
    # Pattern 1: [[chunk:<id>]] (explicit chunk citation)
    chunk_citation_pattern = r'\[\[chunk:([^\]]+)\]\]'
    # Pattern 2: [[<id>]] (backward compatible - assume chunk if not claim: or chunk: prefix)
    # This matches simple IDs like [[chunk-123]] but excludes [[chunk:...]] and [[claim:...]]
    simple_citation_pattern = r'\[\[(?!chunk:|claim:)([^\]]+)\]\]'
    
    chunk_citations_explicit = re.findall(chunk_citation_pattern, section_text)
    chunk_citations_simple = re.findall(simple_citation_pattern, section_text)
    
    # Combine and deduplicate chunk citations
    chunk_citation_ids = list(set(chunk_citations_explicit + chunk_citations_simple))
    
    # Extract actual claim IDs if present (format: [[claim:<id>]])
    claim_citation_pattern = r'\[\[claim:([^\]]+)\]\]'
    claim_ids = list(set(re.findall(claim_citation_pattern, section_text)))
    
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
                "promotions_applied": persistence_results["promotions_applied"],
            }
        }
    )
    
    # Mark as complete
    if job_id:
        try:
            from ..job_store import update_job_record
            from ..state import JobStatus
            update_job_record(job_id, {
                "current_step": "complete",
                "progress": 1.0,
                "message": "Section synthesis completed",
                "status": JobStatus.SUCCEEDED.value,
            })
        except Exception as e:
            logger.warning(f"Failed to update job completion: {e}", exc_info=True)
    
    return {
        "bundle_id": bundle_id,
        "block_id": section_block.block_id,
        "block_ids": [section_block.block_id],  # For now, single block
        "promotions_applied": persistence_results["promotions_applied"],
        "section_text": section_text,
        "critique": critique,
        "persistence_results": persistence_results,
    }
