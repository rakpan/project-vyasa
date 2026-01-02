# Embedder Service - Project Vyasa

The Embedder service provides text-to-vector conversion using Sentence Transformers. It's used by the Console for generating embeddings that are stored in Qdrant for semantic search.

## Features

- **CUDA Support**: Automatically detects and uses NVIDIA GPUs if available
- **CPU Fallback**: Falls back to CPU if CUDA is not available
- **Model**: Uses `all-MiniLM-L6-v2` by default (384 dimensions)
- **API Endpoints**:
  - `GET /health` - Health check
  - `POST /embed` - Generate embeddings (primary endpoint)
  - `POST /embeddings` - Alternative endpoint for compatibility

## API Usage

### Generate Embeddings

```bash
curl -X POST http://embedder:30010/embed \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["This is a sample text", "Another text to embed"],
    "batch_size": 32
  }'
```

**Response:**
```json
{
  "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "model": "all-MiniLM-L6-v2",
  "processing_time": 0.123
}
```

## Environment Variables

- `MODEL_NAME`: Model to use (default: `all-MiniLM-L6-v2`)
- `PORT`: Server port (default: `80`)

## Docker Build

```bash
cd src/embedder
docker build -t vyasa-embedder .
```

## CUDA Support

The service automatically detects CUDA availability:
- If CUDA is available, it uses GPU acceleration
- If CUDA is not available, it falls back to CPU
- Logs indicate which device is being used

## Integration with Console

The Console service calls this embedder via:
- Environment variable: `SENTENCE_TRANSFORMER_URL=http://embedder:30010`
- Endpoint: `POST /embed` with `{ texts: string[], batch_size?: number }`
- Response: `{ embeddings: number[][], model: string, processing_time: number }`

