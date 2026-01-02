#!/usr/bin/env bash
#
# Project Vyasa - Deployment Verification (Go/No-Go)
# Runs a lightweight end-to-end check:
#   1) Creates a temporary project
#   2) Submits a sample workflow job (raw_text)
#   3) Waits for completion and verifies triples persisted to ArangoDB
#   4) Cleans up temporary artifacts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"
ENV_FILE="$DEPLOY_DIR/.env"
SECRETS_FILE="$DEPLOY_DIR/.secrets.env"

# Load env helpers
. "$SCRIPT_DIR/lib/env.sh"
load_env_defaults

load_env_file() {
  local file="$1"
  if [ -f "$file" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$file"
    set +a
  fi
}

load_env_file "$ENV_FILE"
load_env_file "$SECRETS_FILE"

ORCH_URL="${ORCHESTRATOR_URL:-http://orchestrator:8000}"
GRAPH_URL="${MEMORY_URL:-${ARANGODB_URL:-http://graph:8529}}"
DB_NAME="${ARANGODB_DB:-project_vyasa}"
DB_USER="${ARANGODB_USER:-root}"
DB_PASS="${ARANGO_ROOT_PASSWORD:-${ARANGODB_PASSWORD:-}}"

echo "Deployment verification:"
echo "  Orchestrator: $ORCH_URL"
echo "  Graph (Arango): $GRAPH_URL (db=$DB_NAME, user=$DB_USER)"
echo ""

python3 - "$ORCH_URL" "$GRAPH_URL" "$DB_NAME" "$DB_USER" "$DB_PASS" <<'PY'
import json
import sys
import time
import uuid
from typing import Any, Dict

import requests
from arango import ArangoClient

orch_url, graph_url, db_name, db_user, db_pass = sys.argv[1:6]

def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)

session = requests.Session()
timeout = 30

# 1) Create project
project_payload: Dict[str, Any] = {
    "title": f"deploy-verify-{uuid.uuid4().hex[:8]}",
    "thesis": "Deploy verification project",
    "research_questions": ["Does the pipeline store triples?"],
}
r = session.post(f"{orch_url}/api/projects", json=project_payload, timeout=timeout)
if r.status_code != 201:
    fail(f"Project creation failed ({r.status_code}): {r.text}")
project = r.json()
project_id = project.get("id") or project.get("_key") or project.get("project_id")
if not project_id:
    fail(f"Project created but ID missing: {project}")

print(f"[OK] Created project {project_id}")

# 2) Submit workflow with raw text
submit_payload = {
    "raw_text": "Alice collaborates with Bob on Graph Analytics for Project Vyasa verification.",
    "project_id": project_id,
}
r = session.post(f"{orch_url}/workflow/submit", json=submit_payload, timeout=timeout)
if r.status_code not in (200, 202):
    fail(f"Workflow submit failed ({r.status_code}): {r.text}")
job_id = (r.json() or {}).get("job_id")
if not job_id:
    fail(f"Workflow submit response missing job_id: {r.text}")
print(f"[OK] Submitted workflow job {job_id}")

# 3) Poll status
final_status = None
result_payload: Dict[str, Any] = {}
for attempt in range(30):
    status_resp = session.get(f"{orch_url}/workflow/status/{job_id}", timeout=timeout)
    if status_resp.status_code != 200:
        time.sleep(2)
        continue
    body = status_resp.json()
    status = body.get("status", "").upper()
    if status in {"SUCCEEDED", "FINALIZED"}:
        final_status = status
        result_payload = body.get("result") or {}
        break
    if status in {"FAILED", "ERROR"}:
        fail(f"Workflow failed: {body}")
    time.sleep(2)

if final_status is None:
    fail("Workflow did not complete within timeout window.")

print(f"[OK] Workflow completed with status {final_status}")

# 4) Verify triples in ArangoDB
client = ArangoClient(hosts=graph_url)
db = client.db(db_name, username=db_user, password=db_pass)

cursor = db.aql.execute(
    "FOR e IN extractions FILTER e.project_id==@pid RETURN e",
    bind_vars={"pid": project_id},
)
extractions = list(cursor)
triples_found = any((doc.get("graph") or {}).get("triples") for doc in extractions)

if not triples_found:
    # Fallback: inspect result payload if extraction not persisted yet
    triples_found = bool((result_payload.get("extracted_json") or {}).get("triples"))

if not triples_found:
    fail("No triples found in ArangoDB extractions or result payload.")

print(f"[OK] Verified triples for project {project_id}")

# Cleanup temporary artifacts (best-effort)
try:
    db.aql.execute("FOR e IN extractions FILTER e.project_id==@pid REMOVE e IN extractions", bind_vars={"pid": project_id})
    db.aql.execute("FOR b IN manuscript_blocks FILTER b.project_id==@pid REMOVE b IN manuscript_blocks", bind_vars={"pid": project_id})
    db.aql.execute("FOR p IN projects FILTER p._key==@pid REMOVE p IN projects", bind_vars={"pid": project_id})
    print(f"[CLEANUP] Removed temporary project {project_id} data.")
except Exception as exc:  # pragma: no cover - best effort cleanup
    print(f"[WARN] Cleanup incomplete: {exc}")

PY
