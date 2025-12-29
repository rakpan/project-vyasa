# ADR 001: Replace Pinecone with Local Qdrant

**Status**: Accepted  
**Date**: 2025-01-XX  
**Deciders**: Project Vyasa Team

## Context

Project Vyasa requires a vector database for semantic search over research documents. The original architecture used **Pinecone**, a managed cloud service, for vector storage and similarity search.

### Requirements

1. **Data Privacy**: All research data must remain on the DGX system—no cloud dependencies
2. **Zero Latency**: Vector search must be fast enough for interactive use
3. **Self-Contained**: The entire stack must run in Docker Compose
4. **Cost Control**: No per-API-call costs or subscription fees
5. **Offline Capability**: System must work without internet connectivity

### Problems with Pinecone

- **Cloud Dependency**: Required external API calls to Pinecone cloud service
- **Data Privacy Risk**: Embeddings leave the DGX system
- **API Costs**: Per-query pricing model
- **Network Latency**: Round-trip to cloud service adds delay
- **Internet Required**: Cannot operate in air-gapped environments

## Decision

We will **replace Pinecone with Qdrant**, running locally in a Docker container.

### Implementation Details

- **Service Name**: `vyasa-qdrant` (container name)
- **Port**: 6333 (configurable via `PORT_QDRANT` in `.env`)
- **Image**: `qdrant/qdrant:latest`
- **Storage**: Docker volume `qdrant_data` for persistence
- **Collections**: 
  - `document-embeddings` (384 dimensions, Cosine distance)
  - `entity-embeddings` (384 dimensions, Cosine distance)

### Migration Steps Taken

1. ✅ Removed `@pinecone-database/pinecone` dependency from `src/console/package.json`
2. ✅ Deleted `setup-pinecone` scripts
3. ✅ Created `src/console/lib/qdrant.ts` as drop-in replacement for `PineconeService`
4. ✅ Updated all service references to use `QdrantService` instead of `PineconeService`
5. ✅ Added Qdrant service to `deploy/docker-compose.yml`
6. ✅ Created initialization script `deploy/scripts/qdrant-init.sh`
7. ✅ Updated environment variables to use `QDRANT_URL` instead of `PINECONE_*`

## Consequences

### Positive

- ✅ **Total Data Privacy**: All embeddings stay on the DGX system
- ✅ **Zero Latency**: Local network calls within Docker network (<1ms)
- ✅ **No API Costs**: No per-query or subscription fees
- ✅ **Offline Capable**: Works without internet connectivity
- ✅ **Full Control**: We manage backups, scaling, and configuration
- ✅ **Docker Native**: Integrates seamlessly with existing Docker Compose stack

### Negative

- ⚠️ **Storage Management**: We must manage Qdrant volume backups ourselves
- ⚠️ **No Managed Scaling**: Unlike Pinecone, we handle scaling manually
- ⚠️ **Initial Setup**: Requires Docker volume initialization (handled by init script)

### Neutral

- **API Compatibility**: Qdrant REST API is similar to Pinecone, making migration straightforward
- **Performance**: Qdrant performance is comparable to Pinecone for our use case
- **Features**: Qdrant supports all features we need (similarity search, metadata filtering)

## Implementation Notes

### Service Configuration

The Qdrant service is configured in `deploy/docker-compose.yml`:

```yaml
qdrant:
  image: ${VECTOR_IMAGE}  # qdrant/qdrant:latest
  container_name: ${CONTAINER_QDRANT}  # vyasa-qdrant
  ports:
    - "${PORT_QDRANT}:${PORT_QDRANT}"  # 6333:6333
  volumes:
    - qdrant_data:/qdrant/storage
```

### Client Usage

The frontend uses `QdrantService` (in `src/console/lib/qdrant.ts`) which provides the same interface as the old `PineconeService`:

```typescript
const qdrantService = QdrantService.getInstance();
await qdrantService.initialize();
await qdrantService.storeEmbeddings(embeddings, metadata);
const results = await qdrantService.findSimilarEntities(queryVector, k);
```

### Data Migration

If migrating from an existing Pinecone deployment:

1. Export embeddings from Pinecone
2. Import into Qdrant using the Qdrant REST API
3. Update environment variables to point to Qdrant
4. Restart services

## Alternatives Considered

### 1. Keep Pinecone (Rejected)
- **Why**: Violates data privacy requirement
- **Cost**: API calls add operational expense

### 2. Milvus (Rejected)
- **Why**: More complex setup, overkill for our needs
- **Complexity**: Requires additional components (etcd, MinIO)

### 3. Weaviate (Rejected)
- **Why**: More features than needed, heavier resource footprint
- **Complexity**: GraphQL API adds learning curve

### 4. Chroma (Rejected)
- **Why**: Less mature, smaller community
- **Stability**: Qdrant has better production track record

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Qdrant Docker Image](https://hub.docker.com/r/qdrant/qdrant)
- [Migration Guide](./001-qdrant-selection.md) (original selection decision)

## Related Decisions

- [ADR 001: Qdrant Selection](./001-qdrant-selection.md) - Original decision to choose Qdrant
- [System Architecture](../architecture/system-map.md) - How Qdrant fits into the overall system

## Implementation History

- **2025-01-XX**: Migrated from Pinecone to Qdrant
  - Removed `@pinecone-database/pinecone` dependency
  - Created `src/console/lib/qdrant.ts` as replacement
  - Updated all service references
  - Added Qdrant service to `deploy/docker-compose.yml`
  - Created initialization script `deploy/scripts/qdrant-init.sh`

