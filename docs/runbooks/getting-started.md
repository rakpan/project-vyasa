# Getting Started Guide

This guide will help you set up and run Project Vyasa on your development machine or NVIDIA DGX system.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **NVIDIA GPU** with CUDA support (for Cortex, Drafter, and Embedder services)
- **Git** for cloning the repository
- **8GB+ RAM** recommended
- **50GB+ disk space** for models and data

## Step 1: Clone and Navigate

```bash
git clone <repository-url>
cd project-vyasa
```

## Step 2: Configure Environment

Create your environment configuration file:

```bash
cd deploy
cp .env.example .env
```

The `.env.example` file contains all necessary configuration variables. Edit `.env` if you need to customize:

- **Model paths**: Change `CORTEX_MODEL_PATH` or `EMBEDDER_MODEL_NAME` if using different models
- **Ports**: Adjust port mappings if defaults conflict with existing services
- **Database name**: Modify `GRAPH_DB_NAME` if needed

**Important**: If you change model paths, the models will be re-downloaded on first container start (this can take time).

## Step 3: Start Services

From the `deploy/` directory, start all services:

```bash
docker-compose up -d
```

Or if you prefer to see logs:

```bash
docker-compose up
```

**First Run**: The first time you start the services, Docker will:
1. Pull required images (this may take several minutes)
2. Download ML models on first use:
   - **Brain**: Large model (e.g., `nvidia/nemotron-3-nano-30b`, ~60GB)
   - **Worker**: Cheap model (e.g., `meta-llama/Llama-3.1-8B-Instruct`, ~16GB)
   - **Vision**: Large model (e.g., `nvidia/nemotron-3-nano-30b`, ~60GB)
   - **Embedder**: `all-MiniLM-L6-v2` (~90MB)
3. Initialize databases (ArangoDB and Qdrant)
4. Seed initial roles (if running seed script)

**Expected Output**: You should see all 9 services starting:
- ✅ `cortex-brain` (Brain - SGLang, Port 30000)
- ✅ `cortex-worker` (Worker - SGLang, Port 30001)
- ✅ `cortex-vision` (Vision - SGLang, Port 30002)
- ✅ `drafter` (Drafter - Ollama, Port 11434)
- ✅ `memory` (Memory - ArangoDB, Port 8529)
- ✅ `console` (Console - Next.js, Port 3000)
- ✅ `embedder` (Embedder - Sentence Transformers, Port 80)
- ✅ `vector` (Vector - Qdrant, Port 6333)
- ✅ `orchestrator` (Orchestrator - Python, Port 8000)

## Step 4: Verify Services

Check that all containers are running:

```bash
docker-compose ps
```

All services should show `Up` status. If any service is failing, check logs:

```bash
docker-compose logs <service-name>
# Example: docker-compose logs cortex
```

## Step 5: Access the Console

Open your browser and navigate to:

**http://localhost:3000**

You should see the Project Vyasa Console dashboard.

## Step 6: The Smoke Test

Verify the system is working end-to-end:

### 6.1 Upload a Test Document

1. In the Console, click **"Upload Document"** or drag-and-drop a PDF file
2. Wait for the upload to complete
3. The document should appear in the document list

### 6.2 Process the Document

1. Select the uploaded document
2. Click **"Process Document"** button
3. The system will:
   - Extract text from the PDF
   - Send it to Cortex for PACT ontology extraction
   - Store triples in ArangoDB
   - Generate embeddings and store in Qdrant

**Expected**: You should see a progress indicator, then a success message.

### 6.3 View the Knowledge Graph

1. Click **"View Graph"** or navigate to the Graph tab
2. You should see:
   - **Nodes**: Entities extracted from the document (Vulnerabilities, Mechanisms, etc.)
   - **Edges**: Relationships between entities (MITIGATES, ENABLES, REQUIRES)

**Success**: If you see nodes and edges, the extraction pipeline is working! 🎉

### 6.4 Test Search

1. Use the search bar in the Console
2. Enter a query related to your document (e.g., "security vulnerability")
3. You should see relevant document chunks returned

**Success**: If search returns results, the vector search pipeline is working! 🎉

## Troubleshooting

### Services Won't Start

**Check GPU availability:**
```bash
nvidia-smi
```

**Check Docker GPU runtime:**
```bash
docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```

### Cortex Services Fail (Brain/Worker/Vision)

**Check logs:**
```bash
docker-compose logs cortex-brain
docker-compose logs cortex-worker
docker-compose logs cortex-vision
```

**Common issues:**
- Model download failed: Check internet connection and disk space
- GPU not available: Verify `nvidia-smi` works and GPU IDs are correct in `.env`
- Port conflict: Change `PORT_BRAIN`, `PORT_WORKER`, or `PORT_VISION` in `.env`
- GPU reservation conflict: Ensure GPU IDs don't overlap between services

### Console Shows Connection Errors

**Verify service URLs:**
- Check that `CORTEX_SERVICE_URL`, `MEMORY_SERVICE_URL`, etc. are correct in `.env`
- Ensure all services are running: `docker-compose ps`

### Database Initialization Fails

**Reset databases (⚠️ deletes all data):**
```bash
docker-compose down -v
docker-compose up -d
```

## Next Steps

Once the smoke test passes:

1. **Read the Architecture Docs**: Understand how services interact
   - [System Map](../architecture/system-map.md)
   - [System Context](../architecture/system-context.md)

2. **Explore the Codebase**:
   - `src/console/` - Next.js frontend
   - `src/orchestrator/` - LangGraph workflows
   - `src/ingestion/` - PACT extraction logic
   - `src/shared/` - Shared schemas and config

3. **Review Decisions**: Understand why we made certain choices
   - [ADR 001: Local Vector DB](../decisions/001-local-vector-db.md)

## Development Workflow

### Making Changes

1. **Frontend changes**: Edit files in `src/console/`
   - Changes hot-reload in development mode
   - Rebuild: `docker-compose build console`

2. **Backend changes**: Edit files in `src/orchestrator/`, `src/ingestion/`
   - Changes require container restart: `docker-compose restart orchestrator`

3. **Configuration changes**: Edit `deploy/.env`
   - Restart affected services: `docker-compose restart <service>`

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f cortex

# Last 100 lines
docker-compose logs --tail=100 console
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

## Service Health Checks

### Manual Health Checks

```bash
# Brain
curl http://localhost:30000/health

# Worker
curl http://localhost:30001/health

# Vision
curl http://localhost:30002/health

# Orchestrator
curl http://localhost:8000/health

# Qdrant
curl http://localhost:6333/health

# ArangoDB
curl http://localhost:8529/_api/version
```

### Console Health

The Console UI includes a health status indicator. Check the settings panel for service connectivity.

## Common Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart cortex

# Rebuild a service
docker-compose build console

# Check service status
docker-compose ps

# Execute command in container
docker-compose exec cortex bash
```

## Getting Help

- **Documentation**: See [docs/README.md](../README.md) for full documentation index
- **Architecture**: Review [System Map](../architecture/system-map.md) for data flows
- **Issues**: Check service logs first: `docker-compose logs <service>`

## Success Criteria

You've successfully set up Project Vyasa when:

✅ All 9 services are running (`docker-compose ps`)  
✅ Console is accessible at http://localhost:3000  
✅ You can upload and process a PDF document  
✅ Knowledge graph visualization shows nodes and edges  
✅ Search functionality returns relevant results  
✅ Async job system works (submit job, poll status)  

Welcome to Project Vyasa! 🚀

