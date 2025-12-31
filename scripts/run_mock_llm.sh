#!/usr/bin/env bash
# scripts/run_mock_llm.sh - Start Mock LLM Server for Testing
# Description : Launches a mock LLM HTTP server for local tests (no GPU needed).
# Dependencies: docker
# Usage       : ./scripts/run_mock_llm.sh

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

PORT=${MOCK_LLM_PORT:-9000}

echo "Starting Mock LLM Server on port ${PORT}..."
echo "This server mimics SGLang/OpenAI API for testing without GPUs."
echo ""
echo "To use in tests, set:"
echo "  WORKER_URL=http://localhost:${PORT}"
echo "  BRAIN_URL=http://localhost:${PORT}"
echo "  VISION_URL=http://localhost:${PORT}"
echo ""
echo "Press Ctrl+C to stop."
echo ""

cd "$PROJECT_ROOT"
python3 -m uvicorn src.mocks.server:app --host 0.0.0.0 --port "$PORT" --reload
