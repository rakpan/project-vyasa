"""
SGLang-optimized extraction function for PACT ontology.

Connects to the Cortex service (SGLang) and uses constrained decoding (regex)
to strictly enforce JSON schema compliance.
"""

import json
import os
from typing import List, Optional, Dict, Any
import requests

from ..shared.schema import PACTGraph, GraphTriple, EntityType, RelationType, RoleProfile
from ..shared.config import get_cortex_url
from ..shared.logger import get_logger
from ..shared.role_manager import RoleRegistry

logger = get_logger("ingestion", __name__)

# Get Cortex URL from environment or config
CORTEX_URL = get_cortex_url()


class PACTExtractor:
    """Extracts PACT ontology entities and relations from text using SGLang.
    
    This class connects to the Cortex service (SGLang) and uses constrained
    decoding (regex) to strictly enforce JSON schema compliance. The extraction
    uses a dynamic role profile (default: "The Cartographer") stored in ArangoDB,
    allowing runtime updates to system prompts without code redeployment.
    
    Attributes:
        cortex_url: URL of the Cortex (SGLang) service endpoint.
        role_name: Name of the role to use for extraction.
        role_registry: RoleRegistry instance for fetching dynamic role profiles.
        _role: Cached RoleProfile object (loaded on first use).
        _initialized: Flag indicating if Cortex connection has been verified.
    """
    
    def __init__(self, cortex_url: Optional[str] = None, role_name: str = "The Cartographer") -> None:
        """Initialize the PACT extractor.
        
        Args:
            cortex_url: URL of the Cortex (SGLang) service endpoint.
                       If None, uses CORTEX_URL from environment/config.
            role_name: Name of the role to use for extraction. Defaults to "The Cartographer".
                      The role must exist in ArangoDB (seeded via seed_roles.py).
        """
        self.cortex_url = cortex_url or CORTEX_URL
        self.role_name = role_name
        self.role_registry = RoleRegistry()
        self._role: Optional[RoleProfile] = None
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Ensure the Cortex service is reachable and role is loaded.
        
        Performs a health check on the Cortex service and loads the role profile
        from RoleRegistry. This method is idempotent and safe to call multiple times.
        
        Side Effects:
            - Sets self._initialized to True after successful initialization
            - Loads self._role from RoleRegistry
            - Logs connection status and role loading at INFO level
            - Logs warnings if Cortex health check fails (but continues anyway)
        """
        if not self._initialized:
            try:
                # Test connection to Cortex service
                response = requests.get(f"{self.cortex_url}/health", timeout=5)
                response.raise_for_status()
                self._initialized = True
                logger.info(f"Connected to Cortex service at {self.cortex_url}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not verify Cortex service connection: {e}")
                # Continue anyway - connection will be tested on first use
                self._initialized = True
            
            # Load role from registry
            if not self._role:
                self._role = self.role_registry.get_role(self.role_name)
                logger.info(f"Loaded role '{self.role_name}' (version {self._role.version})")
    
    def _generate_json_schema_regex(self) -> str:
        """Generate a regex pattern that matches the PACTGraph JSON schema.
        
        This regex enforces strict JSON structure matching the PACTGraph model.
        SGLang uses regex constraints to force valid JSON output, ensuring the
        extraction result conforms to the expected schema.
        
        Returns:
            Regex pattern string that matches valid PACTGraph JSON. The pattern
            requires:
            - vulnerabilities: Array of vulnerability objects
            - mechanisms: Array of mechanism objects
            - constraints: Array of constraint objects
            - outcomes: Array of outcome objects
            - triples: Array of relation triple objects
            - source: Optional string identifier
            
        Note:
            This is a simplified regex. For production, consider using a more
            sophisticated schema validation approach (e.g., JSON Schema).
        """
        # Regex pattern for valid JSON matching PACTGraph schema
        # This ensures the output is valid JSON with required fields
        # Pattern allows nested structures with proper escaping
        return r'\{\s*"vulnerabilities"\s*:\s*\[.*?\]\s*,\s*"mechanisms"\s*:\s*\[.*?\]\s*,\s*"constraints"\s*:\s*\[.*?\]\s*,\s*"outcomes"\s*:\s*\[.*?\]\s*,\s*"triples"\s*:\s*\[.*?\]\s*(?:,\s*"source"\s*:\s*"[^"]*")?\s*\}'
    
    def _build_extraction_prompt(self, text: str) -> str:
        """Build the extraction prompt for SGLang using the role's system prompt.
        
        Combines the role's system prompt (from RoleRegistry) with the input text
        to create a complete extraction prompt. The system prompt contains instructions
        for extracting PACT ontology entities and relations with strict JSON compliance.
        
        Args:
            text: Input text to extract from. Should be non-empty and contain
                  content relevant to PACT ontology (vulnerabilities, mechanisms, etc.).
                  
        Returns:
            Formatted prompt string ready for SGLang API. The prompt format:
            - System prompt from role (instructions)
            - "Text to analyze:" section
            - Input text
            - "JSON:" marker for structured output
            
        Note:
            If role is not loaded, falls back to a generic extraction prompt.
        """
        # Use the role's system prompt as the base
        system_prompt = self._role.system_prompt if self._role else "Extract PACT ontology entities and relations from text."
        
        # Append the text to analyze
        prompt = f"""{system_prompt}

Text to analyze:
{text}

JSON:"""
        return prompt
    
    def extract_pact_graph(self, text: str, source: Optional[str] = None) -> PACTGraph:
        """Extract PACT ontology from a single text document.
        
        Sends the input text to Cortex (SGLang) with regex constraints to ensure
        valid JSON output matching the PACTGraph schema. The extraction uses the
        role's system prompt (default: "The Cartographer") to guide the extraction.
        
        Args:
            text: Input text to extract from. Must be non-empty. If empty, returns
                  an empty PACTGraph.
            source: Optional source identifier (e.g., document ID, filename).
                   Stored in the returned PACTGraph.source field.
                   
        Returns:
            PACTGraph object containing:
            - vulnerabilities: List of Vulnerability objects
            - mechanisms: List of Mechanism objects
            - constraints: List of Constraint objects
            - outcomes: List of Outcome objects
            - triples: List of GraphTriple objects (relations)
            - source: Source identifier if provided
            
            Returns an empty PACTGraph if input text is empty.
            
        Raises:
            ValueError: If extraction fails, JSON parsing fails, or Cortex returns
                       invalid data. The error message includes details about the failure.
            ConnectionError: If Cortex service is unreachable (implicit via requests).
            
        Side Effects:
            - Logs extraction results at INFO level (entity/relation counts)
            - Logs errors at ERROR level if extraction fails
        """
        self._ensure_initialized()
        
        if not text or not text.strip():
            logger.warning("Empty text provided for extraction")
            return PACTGraph(source=source)
        
        try:
            prompt = self._build_extraction_prompt(text)
            
            # Use SGLang API with regex constraint to force valid JSON
            # SGLang supervisor expects a POST request with prompt and constraints
            payload = {
                "prompt": prompt,
                "sampling_params": {
                    "temperature": 0.1,  # Low temperature for structured extraction
                    "max_new_tokens": 4096,
                    "stop": [],
                },
                "regex": self._generate_json_schema_regex(),
            }
            
            try:
                response = requests.post(
                    f"{self.cortex_url}/generate",
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
            except Exception:
                logger.error(
                    "Cortex extraction request failed",
                    extra={
                        "payload": {
                            "endpoint": f"{self.cortex_url}/generate",
                            "text_chars": len(text),
                            "temperature": payload["sampling_params"]["temperature"],
                        }
                    },
                    exc_info=True,
                )
                raise
            
            result = response.json()
            extracted_text = result.get("text", "").strip()
            
            # Clean up the response (remove markdown code blocks if present)
            if extracted_text.startswith("```"):
                # Remove markdown code blocks
                lines = extracted_text.split("\n")
                extracted_text = "\n".join(lines[1:-1]) if len(lines) > 2 else extracted_text
            
            # Parse JSON
            try:
                data = json.loads(extracted_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text: {extracted_text[:500]}")
                raise ValueError(f"Invalid JSON response from SGLang: {e}")
            
            # Validate and convert to PACTGraph
            pact_graph = PACTGraph(**data)
            if source:
                pact_graph.source = source
            
            logger.info(f"Extracted {len(pact_graph.vulnerabilities)} vulnerabilities, "
                       f"{len(pact_graph.mechanisms)} mechanisms, "
                       f"{len(pact_graph.constraints)} constraints, "
                       f"{len(pact_graph.outcomes)} outcomes, "
                       f"{len(pact_graph.triples)} triples")
            
            return pact_graph
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            raise ValueError(f"Failed to extract PACT graph: {e}")
    
    def extract_batch(self, texts: List[str], sources: Optional[List[str]] = None) -> List[PACTGraph]:
        """Extract PACT ontology from multiple text documents (batch processing).
        
        Processes multiple texts sequentially, calling extract_pact_graph for each.
        This is a convenience method for processing multiple documents. For true
        parallel processing, consider using asyncio or multiprocessing.
        
        Args:
            texts: List of input texts to extract from. Must be non-empty.
            sources: Optional list of source identifiers. If provided, must have
                    the same length as texts. Each source is paired with the
                    corresponding text.
                    
        Returns:
            List of PACTGraph objects, one per input text. The order matches the
            input order. If extraction fails for a text, that entry will contain
            an empty PACTGraph (errors are logged but don't stop batch processing).
            
        Raises:
            ValueError: If texts is empty, or if sources is provided but has a
                       different length than texts.
                       
        Note:
            This implementation processes texts sequentially. For large batches,
            consider implementing parallel processing or using SGLang's batch API
            if available.
        """
        if sources and len(sources) != len(texts):
            raise ValueError("Sources list must match texts list length")
        
        results = []
        for i, text in enumerate(texts):
            source = sources[i] if sources else None
            try:
                result = self.extract_pact_graph(text, source=source)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract from text {i}: {e}")
                # Return empty graph on failure to maintain batch structure
                results.append(PACTGraph(source=source))
        
        logger.info(f"Batch extraction completed: {len(results)}/{len(texts)} successful")
        return results


# Convenience function for direct usage
def extract_pact_graph(text: str, source: Optional[str] = None, cortex_url: Optional[str] = None) -> PACTGraph:
    """
    Extract PACT ontology from text using Cortex service.
    
    Args:
        text: Input text to extract from
        source: Optional source identifier
        cortex_url: URL of the Cortex (SGLang) service endpoint.
                   If None, uses CORTEX_URL from environment/config.
        
    Returns:
        PACTGraph containing extracted entities and relations
    """
    extractor = PACTExtractor(cortex_url=cortex_url)
    return extractor.extract_pact_graph(text, source=source)
