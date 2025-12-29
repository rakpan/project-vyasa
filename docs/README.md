# Project Vyasa: The AI Research Factory

**Project Vyasa** is a high-performance AI research factory designed to run on NVIDIA DGX systems. It provides a complete pipeline for extracting structured knowledge from research documents, building knowledge graphs, and enabling semantic search—all running locally with zero cloud dependencies.

## Overview

Project Vyasa implements the **Fusion Architecture**, a modular system where each service has a specific, well-defined role:

- **Console** (Port 3000): The UI/Cockpit - Next.js frontend for document upload, visualization, and interaction
- **Cortex** (Port 30000): The Brain - SGLang + Nemotron for structured JSON extraction and routing
- **Drafter** (Port 11434): The Writer - Ollama for prose generation and summarization
- **Memory** (Port 8529): The Knowledge Graph - ArangoDB for storing entities and relationships
- **Vector** (Port 6333): The Search Index - Qdrant for storing embeddings and enabling semantic search
- **Embedder** (Port 8000): The Vectorizer - Sentence Transformers for converting text to vectors

## Quick Reference: Service Ports

| Service | Port | Container Name | Description |
|---------|------|----------------|-------------|
| **Console** | 3000 | `vyasa-console` | Next.js frontend UI |
| **Cortex** | 30000 | `vyasa-cortex` | SGLang (structured extraction) |
| **Drafter** | 11434 | `vyasa-drafter` | Ollama (prose generation) |
| **Memory** | 8529 | `vyasa-memory` | ArangoDB (knowledge graph) |
| **Vector** | 6333 | `vyasa-qdrant` | Qdrant (vector database) |
| **Embedder** | 8000 | `vyasa-embedder` | Sentence Transformers (embeddings) |

## Documentation Structure

### 📐 [Architecture](./architecture/)
- **[System Map](./architecture/system-map.md)**: Visual diagrams of data flows and system interactions
- **[System Context](./architecture/system-context.md)**: High-level architecture overview

### 📋 [Decisions](./decisions/)
- **[001: Qdrant Selection](./decisions/001-qdrant-selection.md)**: Why we chose Qdrant for vector storage
- **[001: Local Vector DB](./decisions/001-local-vector-db.md)**: Decision to replace Pinecone with local Qdrant

### 📖 [Runbooks](./runbooks/)
- **[Getting Started](./runbooks/getting-started.md)**: Step-by-step guide for new developers

## Key Principles

1. **Functional Naming**: All services use descriptive, functional names (no mythological metaphors)
2. **Strict JSON**: Cortex uses SGLang regex constraints for guaranteed structured output
3. **Graph-First**: State is written to ArangoDB immediately, not stored in variables
4. **Local-Only**: Zero external API dependencies—everything runs within the Docker network
5. **Type Safety**: Pydantic models ensure data consistency across services

## Getting Started

For new developers, start with the [Getting Started Guide](./runbooks/getting-started.md).

Quick start:
```bash
cd deploy
cp .env.example .env
docker-compose up -d
```

Then access the Console at http://localhost:3000

## Architecture Highlights

- **Extraction Flow**: PDF → Console → Cortex → ArangoDB (Knowledge Graph)
- **Search Flow**: User Query → Console → Embedder → Qdrant → Results
- **Generation Flow**: Context → Drafter → Prose Output

All services communicate via Docker's internal DNS using functional container names.

## Technology Stack

- **Frontend**: Next.js 15, React 19, TypeScript
- **Backend**: Python 3.11, SGLang, LangGraph
- **Databases**: ArangoDB (graph), Qdrant (vector)
- **ML Models**: NVIDIA Nemotron-3-Nano-30B (Cortex), Sentence Transformers (Embedder)
- **Infrastructure**: Docker Compose, NVIDIA GPU runtime

## Contributing

See the [Getting Started Guide](./runbooks/getting-started.md) for development setup instructions.

