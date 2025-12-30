"""
Export utilities for Project Vyasa expert review.

Generates Markdown, JSON-LD, and BibTeX outputs from a completed job result.
Production-ready with verification gating and standards compliance.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import quote

from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "exports"


def _ensure_dir(path: Path) -> None:
    """Ensure export directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def _get_triples(result: Dict[str, Any], include_drafts: bool = False) -> List[Dict[str, Any]]:
    """
    Extract triples from result, optionally filtering by verification status.
    
    Args:
        result: Job result dictionary containing extracted_json
        include_drafts: If False (default), only include verified claims (is_expert_verified=True)
    
    Returns:
        List of triple dictionaries
    """
    extracted = result.get("extracted_json") or {}
    triples = extracted.get("triples") if isinstance(extracted, dict) else []
    if not isinstance(triples, list):
        return []
    
    if include_drafts:
        return [t for t in triples if isinstance(t, dict)]
    
    # Default: Only include verified claims
    verified = [
        t for t in triples
        if isinstance(t, dict) and t.get("is_expert_verified", False) is True
    ]
    
    if verified:
        logger.info(
            f"Export gating: {len(verified)} verified claims included, {len(triples) - len(verified)} drafts excluded",
            extra={"payload": {"job_id": result.get("job_id"), "total": len(triples), "verified": len(verified)}}
        )
    else:
        logger.warning(
            f"Export gating: No verified claims found. Use include_drafts=True to include unverified data.",
            extra={"payload": {"job_id": result.get("job_id"), "total": len(triples)}}
        )
    
    return verified


def _get_manuscript_blocks(result: Dict[str, Any], include_drafts: bool = False) -> List[Dict[str, Any]]:
    """
    Extract manuscript blocks from result, optionally filtering by verification status.
    
    Args:
        result: Job result dictionary
        include_drafts: If False (default), only include verified blocks
    
    Returns:
        List of manuscript block dictionaries
    """
    blocks = result.get("manuscript_blocks") or []
    if not isinstance(blocks, list):
        return []
    
    if include_drafts:
        return [b for b in blocks if isinstance(b, dict)]
    
    # Default: Only include verified blocks
    verified = [
        b for b in blocks
        if isinstance(b, dict) and b.get("is_expert_verified", False) is True
    ]
    
    return verified


def export_markdown(job_id: str, result: Dict[str, Any], include_drafts: bool = False) -> str:
    """
    Export job result as Markdown.
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
        include_drafts: If False (default), only include verified claims
    
    Returns:
        Markdown-formatted string
    """
    triples = _get_triples(result, include_drafts=include_drafts)
    
    lines = [f"# Research Brief for Job {job_id}", ""]
    
    if not triples:
        if include_drafts:
            lines.append("_No triples available._")
        else:
            lines.append("_No verified triples available. Use include_drafts=true to include unverified data._")
    else:
        status_label = "All Claims" if include_drafts else "Verified Claims Only"
        lines.append(f"**{status_label}** ({len(triples)} total)\n")
        
        for idx, t in enumerate(triples, 1):
            subj = t.get("subject", "?")
            pred = t.get("predicate", "?")
            obj = t.get("object", "?")
            conf = t.get("confidence", 0)
            source = t.get("source") or "N/A"
            verified = "Yes" if t.get("is_expert_verified") else "No"
            notes = t.get("expert_notes") or ""
            
            # Include evidence if available
            evidence = t.get("evidence") or ""
            source_pointer = t.get("source_pointer") or {}
            doc_hash = source_pointer.get("doc_hash") or ""
            page = source_pointer.get("page")
            
            lines.append(f"## Claim {idx}")
            lines.append(f"- Triple: **{subj} — {pred} → {obj}**")
            lines.append(f"- Confidence Score: {conf:.2f}")
            if doc_hash:
                lines.append(f"- Document Hash: `{doc_hash[:16]}...`")
            if page:
                lines.append(f"- Source Page: {page}")
            if evidence:
                lines.append(f"- Evidence: _{evidence[:200]}{'...' if len(evidence) > 200 else ''}_")
            lines.append(f"- Source Reference: {source}")
            lines.append(f"- Expert Verified: {verified}")
            if notes:
                lines.append(f"- Expert Notes: {notes}")
            lines.append("")
    
    return "\n".join(lines)


def export_jsonld(job_id: str, result: Dict[str, Any], include_drafts: bool = False) -> str:
    """
    Export job result as schema.org-compliant JSON-LD.
    
    Maps:
    - Projects → CreativeWork
    - Claims/Triples → Claim or ClaimReview
    - Includes appearance properties linking to doc_hash and page
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
        include_drafts: If False (default), only include verified claims
    
    Returns:
        JSON-LD formatted string
    """
    triples = _get_triples(result, include_drafts=include_drafts)
    blocks = _get_manuscript_blocks(result, include_drafts=include_drafts)
    project_id = result.get("project_id")
    project_context = result.get("project_context") or {}
    
    # Base context using schema.org
    context = {
        "@context": "https://schema.org",
        "@vocab": "https://schema.org/",
    }
    
    graph: List[Dict[str, Any]] = []
    
    # Project as CreativeWork
    if project_id or project_context:
        project_entry = {
            "@id": f"project:{project_id or job_id}",
            "@type": "CreativeWork",
            "name": project_context.get("title") or f"Research Project {job_id}",
            "description": project_context.get("thesis") or "",
            "about": project_context.get("research_questions") or [],
        }
        if project_context.get("target_journal"):
            project_entry["publisher"] = {
                "@type": "Organization",
                "name": project_context.get("target_journal"),
            }
        graph.append(project_entry)
    
    # Triples/Claims as Claim or ClaimReview
    for idx, t in enumerate(triples):
        if not isinstance(t, dict):
            continue
        
        subj = t.get("subject", "")
        pred = t.get("predicate", "")
        obj = t.get("object", "")
        confidence = t.get("confidence")
        is_verified = t.get("is_expert_verified", False)
        expert_notes = t.get("expert_notes")
        source_pointer = t.get("source_pointer") or {}
        evidence = t.get("evidence") or ""
        
        # Use ClaimReview if verified, Claim if draft
        claim_type = "ClaimReview" if is_verified else "Claim"
        
        claim_entry: Dict[str, Any] = {
            "@id": f"{job_id}#claim-{idx}",
            "@type": claim_type,
            "claimReviewed": {
                "@type": "Statement",
                "about": {
                    "@type": "Thing",
                    "name": subj,
                },
                "name": f"{subj} {pred} {obj}",
            },
        }
        
        # Add confidence if available
        if confidence is not None:
            claim_entry["reviewRating"] = {
                "@type": "Rating",
                "ratingValue": confidence,
                "bestRating": 1.0,
                "worstRating": 0.0,
            }
        
        # Add evidence and appearance properties
        if evidence:
            claim_entry["text"] = evidence
        
        # Appearance properties linking to source
        appearance_props: Dict[str, Any] = {}
        doc_hash = source_pointer.get("doc_hash")
        page = source_pointer.get("page")
        bbox = source_pointer.get("bbox")
        
        if doc_hash:
            appearance_props["identifier"] = doc_hash
            # Create URL-like reference
            appearance_props["url"] = f"doc://{doc_hash}"
        
        if page:
            appearance_props["pageStart"] = page
            appearance_props["pageEnd"] = page
        
        if bbox and isinstance(bbox, list) and len(bbox) == 4:
            # Normalize bbox to 0-1 range for schema.org
            normalized_bbox = [coord / 1000.0 for coord in bbox]
            appearance_props["position"] = {
                "@type": "QuantitativeValue",
                "value": normalized_bbox,
            }
        
        if appearance_props:
            claim_entry["appearance"] = {
                "@type": "CreativeWork",
                **appearance_props,
            }
        
        # Add expert notes if verified
        if is_verified and expert_notes:
            claim_entry["reviewBody"] = expert_notes
        
        # Add source reference
        source_ref = t.get("source")
        if source_ref:
            claim_entry["citation"] = source_ref
        
        graph.append(claim_entry)
    
    # Manuscript blocks as CreativeWork sections
    for idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        
        block_entry = {
            "@id": f"{job_id}#block-{block.get('block_id', idx)}",
            "@type": "CreativeWork",
            "name": block.get("section_title") or f"Section {idx}",
            "text": block.get("content") or "",
            "position": block.get("order_index", idx),
        }
        
        # Link to project
        if project_id:
            block_entry["isPartOf"] = {
                "@id": f"project:{project_id}",
            }
        
        # Add citations
        citation_keys = block.get("citation_keys") or []
        if citation_keys:
            block_entry["citation"] = citation_keys
        
        graph.append(block_entry)
    
    jsonld = {
        "@context": context["@context"],
        "@graph": graph,
    }
    
    return json.dumps(jsonld, indent=2, ensure_ascii=False)


def _bibtex_escape(text: str) -> str:
    """
    Escape special BibTeX characters.
    
    Args:
        text: Text to escape
    
    Returns:
        Escaped text safe for BibTeX
    """
    if not text:
        return ""
    # Replace special characters
    replacements = {
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "^": "\\textasciicircum{}",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "\\": "\\textbackslash{}",
    }
    result = str(text)
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    return result


def _bibtex_entry(key: str, meta: Dict[str, Any], entry_type: str = "article") -> str:
    """
    Generate IEEE/ACM-compliant BibTeX entry.
    
    Args:
        key: Citation key
        meta: Metadata dictionary with standard fields
        entry_type: BibTeX entry type (article, inproceedings, book, etc.)
    
    Returns:
        Formatted BibTeX entry string
    """
    # Extract and escape fields
    author = _bibtex_escape(meta.get("author") or meta.get("authors") or "Unknown")
    title = _bibtex_escape(meta.get("title") or f"Source {key}")
    year = str(meta.get("year") or meta.get("date") or "2024")
    
    # Conference vs Journal
    booktitle = meta.get("booktitle") or meta.get("conference") or ""
    journal = meta.get("journal") or meta.get("venue") or ""
    
    volume = meta.get("volume")
    number = meta.get("number") or meta.get("issue")
    pages = meta.get("pages") or meta.get("page_range")
    doi = meta.get("doi") or meta.get("DOI")
    
    # Build entry
    lines = [f"@{entry_type}{{{key},"]
    
    # Required fields
    lines.append(f"  author = {{{author}}},")
    lines.append(f"  title = {{{title}}},")
    lines.append(f"  year = {{{year}}},")
    
    # Conference or Journal
    if booktitle:
        lines.append(f"  booktitle = {{{_bibtex_escape(booktitle)}}},")
    elif journal:
        lines.append(f"  journal = {{{_bibtex_escape(journal)}}},")
    
    # Optional fields
    if volume:
        lines.append(f"  volume = {{{volume}}},")
    if number:
        lines.append(f"  number = {{{number}}},")
    if pages:
        lines.append(f"  pages = {{{_bibtex_escape(pages)}}},")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    
    # Additional metadata
    publisher = meta.get("publisher")
    if publisher:
        lines.append(f"  publisher = {{{_bibtex_escape(publisher)}}},")
    
    url = meta.get("url") or meta.get("pdf_path")
    if url:
        lines.append(f"  url = {{{_bibtex_escape(url)}}},")
    
    # Remove trailing comma from last line
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    
    lines.append("}")
    
    return "\n".join(lines)


def export_bibtex(job_id: str, result: Dict[str, Any], include_drafts: bool = False) -> str:
    """
    Export bibliography as IEEE/ACM-compliant BibTeX.
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
        include_drafts: If False (default), only include verified citations
    
    Returns:
        BibTeX-formatted string
    """
    sources = result.get("sources") or []
    project_id = result.get("project_id")
    project_context = result.get("project_context") or {}
    
    entries: List[str] = []
    
    # Extract citation keys from manuscript blocks
    blocks = _get_manuscript_blocks(result, include_drafts=include_drafts)
    citation_keys = set()
    for block in blocks:
        keys = block.get("citation_keys") or []
        citation_keys.update(keys)
    
    # Generate entries from sources
    if isinstance(sources, list) and sources:
        for idx, meta in enumerate(sources, 1):
            if not isinstance(meta, dict):
                continue
            
            # Determine entry type
            entry_type = "article"
            if meta.get("booktitle") or meta.get("conference"):
                entry_type = "inproceedings"
            elif meta.get("journal"):
                entry_type = "article"
            elif meta.get("publisher") and not meta.get("journal"):
                entry_type = "book"
            
            # Use citation key if available, otherwise generate
            key = meta.get("citation_key") or meta.get("key") or f"{job_id}-src-{idx}"
            entries.append(_bibtex_entry(key, meta, entry_type=entry_type))
    else:
        # Fallback: Generate entry from project metadata
        if project_context:
            meta = {
                "title": project_context.get("title") or f"Research Project {job_id}",
                "author": "Research Team",
                "year": project_context.get("created_at", "").split("-")[0] if project_context.get("created_at") else "2024",
                "journal": project_context.get("target_journal"),
            }
            entries.append(_bibtex_entry(job_id, meta))
        else:
            # Minimal fallback
            entries.append(_bibtex_entry(job_id, result.get("metadata", {})))
    
    if not entries:
        return "% No bibliography entries available\n"
    
    return "\n\n".join(entries)


def write_exports(
    job_id: str,
    result: Dict[str, Any],
    include_drafts: bool = False,
) -> Dict[str, Path]:
    """
    Generate and write all formats to exports/{job_id}/.
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
        include_drafts: If False (default), only include verified claims/blocks
    
    Returns:
        Dictionary mapping format names to file paths
    """
    target_dir = EXPORT_DIR / job_id
    _ensure_dir(target_dir)
    
    outputs = {
        "markdown": export_markdown(job_id, result, include_drafts=include_drafts),
        "json-ld": export_jsonld(job_id, result, include_drafts=include_drafts),
        "bibtex": export_bibtex(job_id, result, include_drafts=include_drafts),
    }
    
    files: Dict[str, Path] = {}
    for fmt, content in outputs.items():
        path = target_dir / f"{fmt.replace('-', '_')}.txt" if fmt != "json-ld" else target_dir / "graph.jsonld"
        with path.open("w", encoding="utf-8") as f:
            f.write(content)
        files[fmt] = path
        logger.info(
            "Export written",
            extra={
                "payload": {
                    "job_id": job_id,
                    "format": fmt,
                    "path": str(path),
                    "include_drafts": include_drafts,
                }
            }
        )
    
    return files
