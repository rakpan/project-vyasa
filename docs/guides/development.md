# Development Guide: Project Vyasa

> **The Rules** - Coding standards, conventions, and best practices for contributing to Project Vyasa.

## Core Principles

1. **Functional Naming**: Use functional names (Cortex, Drafter, Graph), not mythological metaphors
2. **Type Safety**: All Python code must use type hints
3. **Structured Logging**: JSON-structured logs for backend services
4. **Error Handling**: All AI calls wrapped in try/except with fallbacks
5. **Local-First**: No external APIs (OpenAI, Pinecone, etc.)

## Naming Conventions

### Service Names

| Service | Name | Port | Purpose |
|---------|------|------|---------|
| Inference Engine | **Cortex** | 30000 | SGLang structured extraction |
| Prose Generator | **Drafter** | 11434 | Ollama content generation |
| Knowledge Graph | **Graph** | 8529 | ArangoDB storage |
| Vector Database | **Vector** | 6333 | Qdrant embeddings |
| Embedding Service | **Embedder** | 8000 | Sentence-Transformers |
| Web UI | **Console** | 3000 | Next.js frontend |
| Coordinator | **Orchestrator** | N/A | LangGraph state machine |

**❌ Wrong**: "Zeus", "Apollo", "Athena"  
**✅ Correct**: "Cortex", "Drafter", "Graph"

### Code Naming

- **Classes**: PascalCase (`PACTExtractor`, `RoleRegistry`)
- **Functions**: snake_case (`extract_pact_graph`, `get_role`)
- **Constants**: UPPER_SNAKE_CASE (`CORTEX_URL`, `ARANGODB_DB`)
- **Variables**: snake_case (`cortex_url`, `role_name`)

## Python Code Style

### Type Hints (Required)

**All functions must have type hints:**

```python
def process_document(doc: Document) -> Graph:
    """
    Process a document and return a knowledge graph.
    
    Args:
        doc: Input document with text content.
        
    Returns:
        Graph object containing extracted entities and relations.
    """
    # Implementation
    pass
```

**❌ Wrong**:
```python
def process_document(doc):
    # No type hints
    pass
```

**✅ Correct**:
```python
def process_document(doc: Document) -> Graph:
    # Type hints provided
    pass
```

### Google-Style Docstrings

**All classes and functions must have docstrings:**

```python
class PACTExtractor:
    """Extracts PACT ontology entities and relations from text using SGLang.
    
    This class connects to the Cortex service (SGLang) and uses constrained
    decoding (regex) to strictly enforce JSON schema compliance.
    
    Attributes:
        cortex_url: URL of the Cortex service endpoint.
        role_name: Name of the role to use for extraction.
        role_registry: Registry for fetching dynamic role profiles.
    """
    
    def extract_pact_graph(self, text: str) -> PACTGraph:
        """Extract PACT ontology entities and relations from text.
        
        Args:
            text: Input text to extract from.
            
        Returns:
            PACTGraph object containing entities, relations, and triples.
            Returns an empty graph if extraction fails.
            
        Raises:
            ConnectionError: If Cortex service is unreachable.
            ValueError: If extracted JSON is invalid.
        """
        pass
```

### Error Handling

**All AI/API calls must be wrapped in try/except:**

```python
def call_cortex(prompt: str) -> Dict[str, Any]:
    """Call Cortex API with error handling and fallback."""
    try:
        response = requests.post(
            f"{self.cortex_url}/v1/chat/completions",
            json={"prompt": prompt},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error("Cortex request timed out", exc_info=True)
        return {"error": "Timeout", "fallback": True}
    except requests.exceptions.RequestException as e:
        logger.error(f"Cortex request failed: {e}", exc_info=True)
        return {"error": str(e), "fallback": True}
    except Exception as e:
        logger.error(f"Unexpected error calling Cortex: {e}", exc_info=True)
        return {"error": "Unknown error", "fallback": True}
```

### Structured Logging

**Use JSON-structured logs for backend services:**

```python
from ..shared.logger import get_logger

logger = get_logger("ingestion", __name__)

# Good: Structured logging
logger.info(
    "Extraction completed",
    extra={
        "payload": {
            "document_id": doc_id,
            "entities_count": len(entities),
            "relations_count": len(relations),
            "duration_ms": duration
        }
    }
)

# Bad: String formatting
logger.info(f"Extracted {len(entities)} entities from document {doc_id}")
```

## TypeScript/Next.js Code Style

### Type Safety

**Use TypeScript interfaces matching Python Pydantic models:**

```typescript
// types/pact.ts
export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  description?: string;
  confidence?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  predicate: RelationType;
  confidence?: number;
  evidence_span?: string;
}
```

### API Calls

**Use environment variables for service URLs:**

```typescript
// Server-side (API routes)
const CORTEX_URL = process.env.CORTEX_SERVICE_URL || "http://vyasa-cortex:30000";

// Client-side (use proxy)
const response = await fetch("/api/proxy/cortex", {
  method: "POST",
  body: JSON.stringify({ prompt }),
});
```

**❌ Wrong**: Hardcoded URLs
```typescript
const response = await fetch("http://localhost:30000/v1/chat/completions");
```

**✅ Correct**: Environment variables
```typescript
const response = await fetch(`${process.env.CORTEX_SERVICE_URL}/v1/chat/completions`);
```

## Database Interactions

### ArangoDB

**Use python-arango client with proper error handling:**

```python
from arango import ArangoClient
from arango.exceptions import DocumentNotFoundError

def get_entity(entity_id: str) -> Optional[Dict[str, Any]]:
    """Get entity from ArangoDB with error handling."""
    try:
        collection = self.db.collection("entities")
        return collection.get(entity_id)
    except DocumentNotFoundError:
        logger.warning(f"Entity {entity_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error fetching entity {entity_id}: {e}", exc_info=True)
        return None
```

### Qdrant

**Use qdrant-client with API key authentication:**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://vyasa-qdrant:6333"),
    api_key=os.getenv("QDRANT_API_KEY")
)
```

## Testing

### Unit Tests

**Test individual functions with mocked dependencies:**

```python
import pytest
from unittest.mock import Mock, patch
from src.ingestion.extractor import PACTExtractor

def test_extract_pact_graph_success():
    """Test successful extraction."""
    extractor = PACTExtractor(cortex_url="http://mock-cortex:30000")
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": '{"entities": []}'}}]
        }
        
        result = extractor.extract_pact_graph("Test text")
        assert isinstance(result, PACTGraph)
```

### Integration Tests

**Test service interactions with Docker Compose:**

```python
@pytest.fixture(scope="session")
def docker_compose():
    """Start Docker Compose services for integration tests."""
    # Use docker-compose up
    yield
    # Use docker-compose down
```

## Git Workflow

### Commit Messages

**Use conventional commits:**

```
feat: Add dynamic role system
fix: Correct ArangoDB connection error
docs: Update architecture diagram
refactor: Simplify extractor initialization
test: Add unit tests for RoleRegistry
```

### Branch Naming

- `feature/role-system` - New features
- `fix/cortex-timeout` - Bug fixes
- `docs/architecture` - Documentation updates
- `refactor/extractor` - Code refactoring

## Code Review Checklist

- [ ] Type hints on all functions
- [ ] Google-style docstrings
- [ ] Error handling for all AI/API calls
- [ ] Structured logging (JSON format)
- [ ] No hardcoded URLs or credentials
- [ ] Functional naming (no mythological metaphors)
- [ ] Tests added/updated
- [ ] Documentation updated

## Common Pitfalls

### ❌ Browser APIs in Server Code

```typescript
// Wrong: btoa is browser-only
const encoded = btoa(credentials);

// Correct: Use Node.js Buffer
const encoded = Buffer.from(credentials).toString("base64");
```

### ❌ Missing Error Handling

```python
# Wrong: No error handling
response = requests.post(url, json=data)
result = response.json()

# Correct: Try/except with fallback
try:
    response = requests.post(url, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
except requests.exceptions.RequestException as e:
    logger.error(f"Request failed: {e}")
    result = {"error": str(e), "fallback": True}
```

### ❌ Hardcoded Service Names

```python
# Wrong: Hardcoded service name
url = "http://supervisor:30000"

# Correct: Environment variable
url = os.getenv("CORTEX_URL", "http://vyasa-cortex:30000")
```

## Resources

- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [SGLang Documentation](https://sglang.readthedocs.io/)
- [ArangoDB Python Driver](https://python-arango.readthedocs.io/)

