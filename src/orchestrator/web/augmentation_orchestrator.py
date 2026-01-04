"""
Web Augmentation Orchestrator for Project Vyasa.

Orchestrates the end-to-end web augmentation loop:
DisputeContext -> URLs -> Firecrawl markdown -> NormalizedEvidenceUnits -> Worker.extract -> ReviewTask(PENDING)

This is a controller that wires sidecar services together behind a feature flag.
No knowledge graph writes occur; only ReviewTask persistence to governance queue.
"""

import json
from typing import List, Dict, Any, Optional
from arango import ArangoClient
from arango.database import StandardDatabase

from ...shared.config import (
    _env,
    get_memory_url,
    get_arango_password,
    get_worker_url,
    get_brain_url,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ...shared.model_registry import get_model_config
from ...shared.logger import get_logger
from ..config import ExpertType, WEB_AUGMENTATION_ENABLED
from ..schemas.disputes import DisputeContext
from ..schemas.review import ReviewTask, ReviewStatus
from ..schemas.claims import Claim
from ..normalize import normalize_extracted_json
from ..nodes.nodes import route_to_expert, call_expert_with_fallback
from .discovery import WebDiscoveryService
from .firecrawl import FirecrawlBridge
from .normalizer import EvidenceNormalizer

logger = get_logger("orchestrator", __name__)

# Configuration
WEB_MAX_URLS = int(_env("WEB_MAX_URLS", "10"))
WEB_MAX_PAGES = int(_env("WEB_MAX_PAGES", "25"))

# Review tasks collection name
REVIEW_TASKS_COLLECTION = "review_tasks"


def _compute_domain_quality_score(domain: str) -> float:
    """Compute simple domain tier scoring for source quality.
    
    Simple heuristic:
    - .edu, .gov, .org: 0.9
    - .com, .net: 0.7
    - Others: 0.5
    
    Args:
        domain: Domain string (normalized, no www.)
    
    Returns:
        Quality score between 0.0 and 1.0
    """
    domain_lower = domain.lower()
    
    if domain_lower.endswith(".edu") or domain_lower.endswith(".gov"):
        return 0.9
    elif domain_lower.endswith(".org"):
        return 0.85
    elif domain_lower.endswith(".com") or domain_lower.endswith(".net"):
        return 0.7
    else:
        return 0.5


def _extract_claims_from_content(
    content: str,
    project_id: str,
    job_id: str,
) -> tuple[List[Dict[str, Any]], bool, Optional[str]]:
    """Extract claims (triples) from content using Worker expert with Brain fallback.
    
    Reuses existing extraction pipeline from knowledge.py.
    
    Args:
        content: Content text to extract from
        project_id: Project ID for context
        job_id: Job ID for telemetry
    
    Returns:
        Tuple of (triples_list, fallback_used, error_message)
    """
    # Build extraction prompt (same as knowledge.py)
    system_prompt = """You are the Cartographer. Extract a structured knowledge graph from text as JSON. Output ONLY JSON.

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
  ]
}

The "triples" array is REQUIRED. Return empty array [] if no relations found."""

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]
    
    try:
        # Route to Worker expert with Brain fallback
        expert_url, expert_name, expert_model = route_to_expert(
            "web_augmentation_extraction", ExpertType.EXTRACTION_SCHEMA
        )
        fallback_url = get_brain_url() if expert_name == "Worker" else None
        fallback_model = get_model_config("brain").model_id if fallback_url else None
        
        state = {"project_id": project_id, "job_id": job_id}
        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=prompt,
            request_params={
                "temperature": 0.6,
                "top_p": 0.95,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
            fallback_url=fallback_url,
            fallback_model_id=fallback_model,
            node_name="web_augmentation_extraction",
            state=state,
        )
        
        content_response = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Parse JSON (handle markdown code blocks if present)
        if isinstance(content_response, str):
            if content_response.strip().startswith("```"):
                lines = content_response.strip().split("\n")
                content_response = "\n".join(lines[1:-1]) if len(lines) > 2 else content_response
            extracted = json.loads(content_response)
        else:
            extracted = content_response
        
        # Normalize to guarantee triples structure
        normalized = normalize_extracted_json(extracted)
        triples = normalized.get("triples", [])
        
        fallback_used = meta.get("path") == "fallback"
        
        return triples, fallback_used, None
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Failed to extract claims from content: {e}",
            extra={
                "payload": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "error": error_msg,
                }
            },
            exc_info=True,
        )
        return [], False, error_msg


def _triples_to_claims(triples: List[Dict[str, Any]], source_metadata: Dict[str, Any]) -> List[Claim]:
    """Convert triples to Claim objects.
    
    Args:
        triples: List of triple dictionaries
        source_metadata: Metadata about the source (for provenance)
    
    Returns:
        List of Claim objects
    """
    import hashlib
    
    claims: List[Claim] = []
    
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        
        # Extract triple fields
        subject = triple.get("subject", "")
        predicate = triple.get("predicate", "")
        obj = triple.get("object", "")
        confidence = triple.get("confidence", 0.5)
        evidence = triple.get("evidence", "")
        
        if not subject or not predicate or not obj:
            continue
        
        # Build claim_text (include evidence if present)
        claim_text = f"{subject} {predicate} {obj}"
        if evidence:
            claim_text += f" (Evidence: {evidence})"
        
        # Get URL for file_hash (use URL hash for web sources)
        url = source_metadata.get("url", "")
        file_hash = hashlib.sha256(url.encode("utf-8")).hexdigest() if url else hashlib.sha256("web-source-unknown".encode("utf-8")).hexdigest()
        
        # Generate stable claim_id from triple + source (use page 1 for web sources)
        # Use Claim.generate_claim_id for consistency
        claim_id = Claim.generate_claim_id(
            subject=subject,
            predicate=predicate,
            obj=obj,
            file_hash=file_hash,
            page_number=1,  # Web sources don't have pages, use 1 as placeholder
        )
        
        # Create Claim (minimal structure for review)
        # Note: source_anchor is optional for web sources (None is OK)
        claim = Claim(
            claim_id=claim_id,
            claim_text=claim_text,
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=float(confidence),
            ingestion_id="web-augmentation",  # Placeholder for web sources
            file_hash=file_hash,
            source_anchor=None,  # Web sources don't have page/bbox anchors
        )
        
        claims.append(claim)
    
    return claims


def _persist_review_task(db: StandardDatabase, review_task: ReviewTask) -> bool:
    """Persist ReviewTask to ArangoDB review_tasks collection.
    
    This is governance queue storage, not knowledge graph persistence.
    
    Args:
        db: ArangoDB database instance
        review_task: ReviewTask to persist
    
    Returns:
        True if persisted successfully, False otherwise
    """
    try:
        # Ensure collection exists
        if not db.has_collection(REVIEW_TASKS_COLLECTION):
            db.create_collection(REVIEW_TASKS_COLLECTION)
        
        collection = db.collection(REVIEW_TASKS_COLLECTION)
        
        # Convert to dict for storage
        doc = review_task.model_dump(mode="json")
        doc["_key"] = review_task.review_id
        
        # Store
        collection.insert(doc)
        
        logger.info(
            f"Persisted ReviewTask {review_task.review_id} to {REVIEW_TASKS_COLLECTION}",
            extra={
                "payload": {
                    "review_id": review_task.review_id,
                    "dispute_id": review_task.dispute_id,
                    "project_id": review_task.project_id,
                    "status": review_task.status.value,
                    "claim_count": len(review_task.candidate_claims),
                }
            },
        )
        
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to persist ReviewTask {review_task.review_id}: {e}",
            exc_info=True,
        )
        return False


class AugmentationOrchestrator:
    """Orchestrates web augmentation workflow.
    
    Wires discovery, scraping, normalization, and extraction together
    to produce ReviewTasks for human approval.
    """
    
    def __init__(
        self,
        discovery_service: Optional[WebDiscoveryService] = None,
        firecrawl_bridge: Optional[FirecrawlBridge] = None,
        db: Optional[StandardDatabase] = None,
    ):
        """Initialize AugmentationOrchestrator.
        
        Args:
            discovery_service: WebDiscoveryService instance (defaults to new instance)
            firecrawl_bridge: FirecrawlBridge instance (defaults to new instance)
            db: ArangoDB database instance (defaults to new connection)
        """
        self.discovery_service = discovery_service or WebDiscoveryService()
        self.firecrawl_bridge = firecrawl_bridge or FirecrawlBridge()
        
        # Initialize DB connection if not provided
        if db is None:
            try:
                arango_url = get_memory_url()
                arango_db = ARANGODB_DB
                arango_user = ARANGODB_USER
                arango_password = get_arango_password()
                
                client = ArangoClient(hosts=arango_url)
                self.db = client.db(arango_db, username=arango_user, password=arango_password)
            except Exception as e:
                logger.warning(f"Failed to initialize ArangoDB connection: {e}")
                self.db = None
        else:
            self.db = db
    
    def run(self, dispute: DisputeContext) -> ReviewTask:
        """Run web augmentation workflow for a dispute.
        
        Pipeline:
        1. Check feature flag (WEB_AUGMENTATION_ENABLED)
        2. Discover URLs (bounded by WEB_MAX_URLS)
        3. Scrape URLs via Firecrawl (bounded by WEB_MAX_PAGES)
        4. Normalize to NormalizedEvidenceUnits
        5. Extract claims via Worker
        6. Create ReviewTask with status PENDING
        7. Persist ReviewTask to governance queue
        
        Args:
            dispute: DisputeContext triggering web augmentation
        
        Returns:
            ReviewTask with status PENDING (or FAILED if disabled/error)
        
        Raises:
            RuntimeError: If feature is disabled or critical error occurs
        """
        # Check feature flag
        if not WEB_AUGMENTATION_ENABLED:
            logger.info(
                f"Web augmentation disabled for dispute {dispute.dispute_id}. "
                "Set WEB_AUGMENTATION_ENABLED=true to enable."
            )
            # Return FAILED ReviewTask with reason
            return ReviewTask.create(
                project_id=dispute.project_id,
                job_id=dispute.job_id,
                dispute_id=dispute.dispute_id,
                candidate_claims=[],
                source_quality_score=0.0,
                status=ReviewStatus.FAILED,
            )
        
        if self.db is None:
            logger.error("ArangoDB connection unavailable for ReviewTask persistence")
            return ReviewTask.create(
                project_id=dispute.project_id,
                job_id=dispute.job_id,
                dispute_id=dispute.dispute_id,
                candidate_claims=[],
                source_quality_score=0.0,
                status=ReviewStatus.FAILED,
            )
        
        try:
            # Step 1: Discover URLs
            logger.info(
                f"Discovering URLs for dispute {dispute.dispute_id}",
                extra={"payload": {"dispute_id": dispute.dispute_id, "project_id": dispute.project_id}},
            )
            urls = self.discovery_service.discover(dispute)
            
            # Bound by WEB_MAX_URLS
            urls = urls[:WEB_MAX_URLS]
            
            if not urls:
                logger.warning(f"No URLs discovered for dispute {dispute.dispute_id}")
                return ReviewTask.create(
                    project_id=dispute.project_id,
                    job_id=dispute.job_id,
                    dispute_id=dispute.dispute_id,
                    candidate_claims=[],
                    source_quality_score=0.0,
                    status=ReviewStatus.FAILED,
                )
            
            logger.info(f"Discovered {len(urls)} URLs for dispute {dispute.dispute_id}")
            
            # Step 2: Scrape URLs via Firecrawl
            logger.info(f"Scraping {len(urls)} URLs via Firecrawl")
            firecrawl_results = self.firecrawl_bridge.scrape(urls)
            
            # Filter successful results and bound by WEB_MAX_PAGES
            successful_results = [r for r in firecrawl_results if r.get("error") is None]
            successful_results = successful_results[:WEB_MAX_PAGES]
            
            if not successful_results:
                logger.warning(f"No successful scrapes for dispute {dispute.dispute_id}")
                return ReviewTask.create(
                    project_id=dispute.project_id,
                    job_id=dispute.job_id,
                    dispute_id=dispute.dispute_id,
                    candidate_claims=[],
                    source_quality_score=0.0,
                    status=ReviewStatus.FAILED,
                )
            
            logger.info(f"Successfully scraped {len(successful_results)} pages")
            
            # Step 3: Normalize to NormalizedEvidenceUnits
            evidence_units = []
            for firecrawl_item in successful_results:
                try:
                    unit = EvidenceNormalizer.normalize_web(firecrawl_item)
                    evidence_units.append(unit)
                except Exception as e:
                    logger.warning(f"Failed to normalize Firecrawl item: {e}", exc_info=True)
                    continue
            
            if not evidence_units:
                logger.warning(f"No evidence units created for dispute {dispute.dispute_id}")
                return ReviewTask.create(
                    project_id=dispute.project_id,
                    job_id=dispute.job_id,
                    dispute_id=dispute.dispute_id,
                    candidate_claims=[],
                    source_quality_score=0.0,
                    status=ReviewStatus.FAILED,
                )
            
            logger.info(f"Normalized {len(evidence_units)} evidence units")
            
            # Step 4: Extract claims from each evidence unit
            all_claims: List[Claim] = []
            domain_scores: List[float] = []
            
            for unit in evidence_units:
                # Extract claims
                triples, fallback_used, error = _extract_claims_from_content(
                    content=unit.content,
                    project_id=dispute.project_id,
                    job_id=dispute.job_id,
                )
                
                if error:
                    logger.warning(f"Extraction error for unit {unit.id}: {error}")
                    continue
                
                # Convert triples to Claims
                source_metadata = unit.provenance_metadata
                claims = _triples_to_claims(triples, source_metadata)
                all_claims.extend(claims)
                
                # Collect domain for quality scoring
                domain = source_metadata.get("domain", "unknown")
                domain_scores.append(_compute_domain_quality_score(domain))
            
            if not all_claims:
                logger.warning(f"No claims extracted for dispute {dispute.dispute_id}")
                return ReviewTask.create(
                    project_id=dispute.project_id,
                    job_id=dispute.job_id,
                    dispute_id=dispute.dispute_id,
                    candidate_claims=[],
                    source_quality_score=0.0,
                    status=ReviewStatus.FAILED,
                )
            
            logger.info(f"Extracted {len(all_claims)} candidate claims")
            
            # Step 5: Compute source quality score (average of domain scores)
            source_quality_score = sum(domain_scores) / len(domain_scores) if domain_scores else 0.5
            
            # Step 6: Create ReviewTask
            review_task = ReviewTask.create(
                project_id=dispute.project_id,
                job_id=dispute.job_id,
                dispute_id=dispute.dispute_id,
                candidate_claims=all_claims,
                source_quality_score=source_quality_score,
                status=ReviewStatus.PENDING,
            )
            
            # Step 7: Persist ReviewTask to governance queue
            if not _persist_review_task(self.db, review_task):
                logger.error(f"Failed to persist ReviewTask {review_task.review_id}")
                # Still return the task, but mark as FAILED
                review_task = review_task.update_status(ReviewStatus.FAILED)
            
            logger.info(
                f"Created ReviewTask {review_task.review_id} with {len(all_claims)} claims",
                extra={
                    "payload": {
                        "review_id": review_task.review_id,
                        "dispute_id": dispute.dispute_id,
                        "claim_count": len(all_claims),
                        "quality_score": source_quality_score,
                    }
                },
            )
            
            return review_task
            
        except Exception as e:
            logger.error(
                f"Web augmentation workflow failed for dispute {dispute.dispute_id}: {e}",
                exc_info=True,
            )
            # Return FAILED ReviewTask
            return ReviewTask.create(
                project_id=dispute.project_id,
                job_id=dispute.job_id,
                dispute_id=dispute.dispute_id,
                candidate_claims=[],
                source_quality_score=0.0,
                status=ReviewStatus.FAILED,
            )

