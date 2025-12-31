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

- **Classes**: PascalCase (`KnowledgeExtractor`, `RoleRegistry`)
- **Functions**: snake_case (`extract_knowledge_graph`, `get_role`)
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
class KnowledgeExtractor:
    """Extracts knowledge graph entities and relations from text using SGLang.
    
    This class connects to the Cortex service (SGLang) and uses constrained
    decoding (regex) to strictly enforce JSON schema compliance.
    
    Attributes:
        cortex_url: URL of the Cortex service endpoint.
        role_name: Name of the role to use for extraction.
        role_registry: Registry for fetching dynamic role profiles.
    """
    
    def extract_knowledge_graph(self, text: str) -> KnowledgeGraph:
        """Extract knowledge graph entities and relations from text.
        
        Args:
            text: Input text to extract from.
            
        Returns:
            KnowledgeGraph object containing entities, relations, and triples.
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

### Logging Standards

**All production logs must use JSON format for easy parsing by log aggregation tools (Splunk, Datadog, jq).**

The logger automatically detects the format via `LOG_FORMAT` environment variable:
- `LOG_FORMAT=json` (default in Docker): Structured JSON logs
- `LOG_FORMAT=text` (default in local dev): Human-readable text logs

**Structured Logging Example:**

```python
from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Good: Structured logging with context binding
logger.info(
    "Extraction completed",
    extra={
        "payload": {
            "project_id": "550e8400-e29b-41d4-a716-446655440000",
            "document_id": doc_id,
            "entities_count": len(entities),
            "relations_count": len(relations),
            "duration_ms": duration
        }
    }
)

# Good: Direct key promotion (project_id, job_id, etc. are promoted to top-level)
logger.info(
    "Job started",
    extra={
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
        "job_id": "job-123",
        "duration_ms": 150
    }
)

# Bad: String formatting (not parseable)
logger.info(f"Extracted {len(entities)} entities from document {doc_id}")
```

**JSON Output (LOG_FORMAT=json):**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "service": "orchestrator",
  "level": "INFO",
  "message": "Extraction completed",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_id": "doc-456",
  "entities_count": 42,
  "relations_count": 18,
  "duration_ms": 1250
}
```

**Text Output (LOG_FORMAT=text):**
```
2024-01-15 10:30:00,123 - orchestrator - INFO - Extraction completed
```

**Context Binding:**
- Keys in `extra={"payload": {...}}` are merged into top-level JSON fields
- Common keys (`project_id`, `job_id`, `document_id`, `error`, `duration_ms`) are automatically promoted
- This enables easy filtering: `jq 'select(.project_id == "123")' logs.json`

## TypeScript/Next.js Code Style

## Handling Proprietary Expertise

- The public repo ships a **Factory Engine** only. Generic role prompts live in `src/scripts/defaults.json`.
- To inject proprietary prompts or domain logic, create `data/private/expertise.json` (git-ignored) with a `roles` map. Matching role names override the defaults; new names are inserted.
- Run `python -m src.scripts.seed_roles` (or `./deploy/start.sh` in Docker) to sync merged roles into ArangoDB. This lets you keep private expertise local while contributing to the shared engine.

### Type Safety

**Use TypeScript interfaces matching Python Pydantic models:**

```typescript
// types/knowledge.ts
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

### Mock LLM Server

**For UI/Integration tests without GPU resources:**

Project Vyasa includes a mock LLM server that mimics the SGLang/OpenAI API. This allows you to run tests without requiring GPU resources or actual model servers.

**Start the mock server:**
```bash
./scripts/run_mock_llm.sh
# Or manually:
python -m uvicorn src.mocks.server:app --host 0.0.0.0 --port 9000
```

**Use in tests:**
Set environment variables to point to the mock server:
```bash
export WORKER_URL=http://localhost:9000
export BRAIN_URL=http://localhost:9000
export VISION_URL=http://localhost:9000
```

**Mock server behavior:**
- **Cartographer scenario**: Detects "Cartographer" in system prompt, returns valid JSON with `triples` array
- **Critic scenario**: Detects "Critic" in system prompt, returns `{"status": "pass", "critiques": []}`
- **Default**: Returns generic mock response
- **Vision endpoint**: Returns dummy vision extraction result

**Example test setup:**
```python
import os
os.environ["WORKER_URL"] = "http://localhost:9000"
os.environ["BRAIN_URL"] = "http://localhost:9000"
# Run your tests...
```

### Debug Prompt Logging

**To persist full prompts and responses for debugging:**

Set `DEBUG_PROMPTS=true` in your environment. This will write all LLM requests and responses to `logs/debug/req_{timestamp}_{uuid}.json`.

**Enable debug logging:**
```bash
export DEBUG_PROMPTS=true
# Or in .env:
DEBUG_PROMPTS=true
```

**Debug log format:**
```json
{
  "url": "http://cortex-worker:30001/v1/chat/completions",
  "request": {
    "payload": {
      "model": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5",
      "messages": [...],
      "temperature": 0.1
    }
  },
  "response": {
    "choices": [...],
    "usage": {...}
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

**Security:** Sensitive keys (api_key, authorization, password, etc.) are automatically redacted from debug logs.

**Note:** Debug logs are written to `logs/debug/` which is gitignored. Always review logs before sharing.

### Unit Tests

**Test individual functions with mocked dependencies:**

```python
import pytest
from unittest.mock import Mock, patch
from src.ingestion.extractor import KnowledgeExtractor

def test_extract_knowledge_graph_success():
    """Test successful extraction."""
    extractor = KnowledgeExtractor(cortex_url="http://mock-cortex:30000")
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": '{"entities": []}'}}]
        }
        
        result = extractor.extract_knowledge_graph("Test text")
        assert isinstance(result, KnowledgeGraph)
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
