#!/usr/bin/env bash
# Local test runner for Project Vyasa.
# Description : Runs unit/integration tests and API smoke checks locally.
# Dependencies: python3, pytest, curl
# Usage:
#   ./scripts/test_local.sh                      # Run unit tests only
#   ./scripts/test_local.sh --with-integration   # Run unit + integration tests
#   ./scripts/test_local.sh --smoke-api <pdf> [base_url]  # Project-first API smoke
#

set -euo pipefail

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"
. "$SCRIPT_DIR/lib/env.sh"
load_env_defaults

# Set PYTHONPATH to include src/
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

# Check if pytest is installed
if [[ "${1:-}" == "--smoke-api" ]]; then
    PDF_PATH="${2:-}"
    BASE_URL="${3:-http://localhost:8000}"
    if [[ -z "$PDF_PATH" || ! -f "$PDF_PATH" ]]; then
        echo "Error: provide a valid PDF path. Usage: ./scripts/test_local.sh --smoke-api <pdf> [base_url]" >&2
        exit 1
    fi

    echo "Running API smoke against ${BASE_URL} with PDF ${PDF_PATH}"
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required for smoke test." >&2
        exit 1
    fi

    create_resp="$(curl -s -X POST "${BASE_URL}/api/projects" \
        -H "Content-Type: application/json" \
        -d '{"title":"Test Project","thesis":"Smoke Test","research_questions":["RQ1"]}')"
    PROJECT_ID="$(python3 - <<'PY'
import json,sys
data=json.loads(sys.stdin.read() or "{}")
pid=data.get("id")
if not pid:
    raise SystemExit("Project creation failed or missing id")
print(pid)
PY <<<"$create_resp")"

    echo "Created project: $PROJECT_ID"

    echo "Ingesting PDF preview (deprecated endpoint, preview only)..."
    curl -s -X POST "${BASE_URL}/ingest/pdf" \
        -F "file=@${PDF_PATH}" \
        -F "project_id=${PROJECT_ID}" >/dev/null

    echo "Submitting workflow job..."
    submit_resp="$(curl -s -X POST "${BASE_URL}/workflow/submit" \
        -F "file=@${PDF_PATH}" \
        -F "project_id=${PROJECT_ID}")"
    JOB_ID="$(python3 - <<'PY'
import json,sys
data=json.loads(sys.stdin.read() or "{}")
job=data.get("job_id")
if not job:
    raise SystemExit("Job submission failed or missing job_id")
print(job)
PY <<<"$submit_resp")"
    status="$(python3 - <<'PY'
import json,sys
data=json.loads(sys.stdin.read() or "{}")
print(data.get("status","unknown"))
PY <<<"$submit_resp")"

    echo "Job submitted: id=${JOB_ID}, status=${status}"
    exit 0
fi

# Check if pytest is installed as a Python module (since we use python3 -m pytest)
if ! python3 -m pytest --version >/dev/null 2>&1; then
    echo "Error: pytest is not installed."
    echo ""
    echo "Install dependencies from requirements.txt:"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Or install pytest directly:"
    echo "  pip install pytest pytest-asyncio httpx"
    exit 1
fi

# Default to unit tests only
INTEGRATION_FLAG=""

# Parse arguments
if [[ "${1:-}" == "--with-integration" ]]; then
    INTEGRATION_FLAG="-m integration"
    shift
    echo "Running unit tests + integration tests..."
else
    echo "Running unit tests only (use --with-integration for integration tests)..."
fi

# Run pytest
cd "$PROJECT_ROOT"
python3 -m pytest "$SRC_DIR/tests/" \
    -v \
    --tb=short \
    --strict-markers \
    $INTEGRATION_FLAG \
    "$@"

echo ""
echo "✅ Tests completed!"
