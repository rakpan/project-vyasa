#!/bin/bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Vyasa Model Preload
# - HF models: downloaded into HF cache dir
# - NVIDIA nv-embedqa-e5-v5: downloaded from NVIDIA NGC API
# -----------------------------------------------------------------------------

CACHE_DIR="/raid/vyasa/hf_cache"
PROJECT_ROOT="/home/rakpan/Code/project-vyasa"

mkdir -p "$CACHE_DIR"
if [ ! -w "$CACHE_DIR" ] 2>/dev/null; then
  echo "⚠️  Permission issue: Cannot write to $CACHE_DIR"
  echo "  Fix: sudo chown -R \$USER:\$USER $CACHE_DIR"
  exit 1
fi

cd "$PROJECT_ROOT" 2>/dev/null || true

# -----------------------------
# Detect Python / pip
# -----------------------------
PYTHON_CMD=""
PIP_CMD=""

if [ -n "${VIRTUAL_ENV:-}" ]; then
  PYTHON_CMD="$VIRTUAL_ENV/bin/python"
  PIP_CMD="$VIRTUAL_ENV/bin/pip"
  echo "✅ Using active virtual environment: $VIRTUAL_ENV"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
  PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
  PIP_CMD="$PROJECT_ROOT/.venv/bin/pip"
  echo "✅ Using project virtual environment: $PROJECT_ROOT/.venv"
elif command -v python3 >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
  PIP_CMD="pip3"
  echo "⚠️  Using system Python (installs may use --user)"
else
  echo "❌ python3/pip3 not found"
  exit 1
fi

# -----------------------------
# Load env/secrets (optional)
# -----------------------------
if [ -f "$PROJECT_ROOT/deploy/.env" ]; then
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/deploy/.env"
fi
if [ -f "$PROJECT_ROOT/deploy/.secrets.env" ]; then
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/deploy/.secrets.env"
fi

# Tokens
if [ -n "${HF_TOKEN:-}" ]; then
  echo "✅ HF_TOKEN found in environment"
  export HF_TOKEN
else
  echo "⚠️  HF_TOKEN not set (OK for public repos; gated repos will fail)"
fi

if [ -n "${NVIDIA_API_KEY:-}" ]; then
  echo "✅ NVIDIA_API_KEY found in environment"
  export NVIDIA_API_KEY
else
  echo "⚠️  NVIDIA_API_KEY not set (nv-embedqa-e5-v5 NIM pull may fail if not already present)"
fi

# -----------------------------
# Install deps WITHOUT breaking transformers
# -----------------------------
echo ""
echo "Installing/validating Python dependencies..."

# Pin huggingface-hub so it stays compatible with transformers 4.57.1 (hub must be < 1.0)
HF_HUB_SPEC="huggingface-hub>=0.34.0,<1.0"
REQ_SPEC="requests>=2.28.0"

if [ -n "${VIRTUAL_ENV:-}" ] || [ -d "$PROJECT_ROOT/.venv" ]; then
  "$PIP_CMD" install -q "$HF_HUB_SPEC" "$REQ_SPEC"
else
  "$PIP_CMD" install -q --user "$HF_HUB_SPEC" "$REQ_SPEC"
  export PATH="$HOME/.local/bin:$PATH"
fi

# -----------------------------------------------------------------------------
# Model list (aligned to deploy/.env)
# -----------------------------------------------------------------------------
TEXT_MODEL_ID="${TEXT_MODEL_ID:-nvidia/Llama-3_3-Nemotron-Super-49B-v1_5}"
VISION_MODEL_ID="${VISION_MODEL_ID:-Qwen/Qwen2-VL-7B-Instruct}"
EMBEDDER_MODEL_ID="${EMBEDDER_MODEL_ID:-nvidia/nv-embedqa-e5-v5}"
RERANKER_MODEL_ID="${RERANKER_MODEL_ID:-nvidia/llama-3.2-nv-rerankqa-1b-v2}"

HF_MODELS=(
  "${TEXT_MODEL_ID}:TEXT:100GB+"
  "${VISION_MODEL_ID}:VISION:15-20GB"
  "${RERANKER_MODEL_ID}:RERANKER:1-2GB"
)

echo ""
echo "=== HF Model Cache Bootstrap ==="
echo "Cache dir: $CACHE_DIR"
echo ""

for model_info in "${HF_MODELS[@]}"; do
  IFS=':' read -r model_id model_type size_hint <<< "$model_info"

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📦 $model_type (HF): $model_id"
  echo "   Estimated size: $size_hint"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  "$PYTHON_CMD" <<PY
import os, sys
from pathlib import Path
from huggingface_hub import snapshot_download

cache_dir = Path("${CACHE_DIR}")
repo_id = "${model_id}"
token = os.getenv("HF_TOKEN")

def is_cached(cache_dir: Path, repo_id: str) -> bool:
    safe = repo_id.replace("/", "--")
    repo_root = cache_dir / f"models--{safe}"
    snaps = repo_root / "snapshots"
    if not snaps.exists():
        return False
    for snap in snaps.glob("*"):
        if snap.is_dir():
            files = [p for p in snap.rglob("*") if p.is_file()]
            if files:
                print(f"✅ Already cached (HF): {repo_id} at {snap}")
                return True
    return False

if is_cached(cache_dir, repo_id):
    sys.exit(0)

snapshot_download(
    repo_id=repo_id,
    cache_dir=str(cache_dir),
    token=token if token else None,
    local_files_only=False,
    resume_download=True,
)
print(f"✅ Downloaded (HF): {repo_id} into {cache_dir}")
PY

  echo ""
done

# -----------------------------------------------------------------------------
# NVIDIA nv-embedqa-e5-v5 (NGC download)
# -----------------------------------------------------------------------------
echo "=== NVIDIA Embedder Preload ==="
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 EMBEDDER (NVIDIA NGC): ${EMBEDDER_MODEL_ID}"
echo "   Action: download via NGC API into ${CACHE_DIR}/nvidia/nv-embedqa-e5-v5"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "${EMBEDDER_MODEL_ID}" = "nvidia/nv-embedqa-e5-v5" ]; then
  if [ -z "${NVIDIA_API_KEY:-}" ]; then
    echo "❌ NVIDIA_API_KEY is required to download nv-embedqa-e5-v5 from NVIDIA."
    exit 1
  fi

  "$PYTHON_CMD" <<PY
import json
import os
import sys
from pathlib import Path
import requests

cache_dir = "${CACHE_DIR}"
model_id = "${EMBEDDER_MODEL_ID}"
api_key = os.getenv("NVIDIA_API_KEY")
version_override = os.getenv("NVIDIA_EMBEDDER_VERSION")

if not api_key:
    print("❌ NVIDIA_API_KEY is required to download nv-embedqa-e5-v5 from NVIDIA.")
    sys.exit(1)

base_url = "https://api.ngc.nvidia.com/v2/models/nvidia/nv-embedqa-e5-v5"
headers = {"Authorization": f"Bearer {api_key}"}

def pick_version(payload, override=None):
    if override:
        return override
    candidates = (
        payload.get("modelVersions")
        or payload.get("model_versions")
        or payload.get("versions")
        or []
    )
    if not candidates:
        return None
    first = candidates[0]
    return (
        first.get("versionId")
        or first.get("version")
        or first.get("name")
        or first.get("id")
    )

try:
    resp = requests.get(f"{base_url}/versions", headers=headers, timeout=30)
    resp.raise_for_status()
    version_payload = resp.json()
    version = pick_version(version_payload, version_override)
    if not version:
        raise RuntimeError("No version found for nv-embedqa-e5-v5. Set NVIDIA_EMBEDDER_VERSION.")

    files_resp = requests.get(f"{base_url}/versions/{version}/files", headers=headers, timeout=30)
    files_resp.raise_for_status()
    files_payload = files_resp.json()
    files = files_payload.get("files") or files_payload.get("modelFiles") or []
    if not files:
        raise RuntimeError("No files listed for nv-embedqa-e5-v5.")

    target_dir = Path(cache_dir) / "nvidia" / "nv-embedqa-e5-v5" / str(version)
    target_dir.mkdir(parents=True, exist_ok=True)

    for entry in files:
        filename = entry.get("name") or entry.get("fileName") or entry.get("path")
        if not filename:
            continue
        url = f"{base_url}/versions/{version}/files/{filename}?redirect=true"
        out_path = target_dir / filename
        if out_path.exists():
            continue
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

    with open(target_dir / "ngc_manifest.json", "w") as f:
        json.dump({"model": model_id, "version": version, "files": files}, f, indent=2)

    print(f"✅ {model_id} downloaded successfully from NVIDIA (version {version})!")
except Exception as e:
    print(f"❌ Error downloading {model_id} from NVIDIA: {e}")
    sys.exit(1)
PY
else
  echo "ℹ️  EMBEDDER_MODEL_ID is not nv-embedqa-e5-v5. Skipping NVIDIA download."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Preload complete."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "HF cache:   $CACHE_DIR"
echo "NVIDIA embedder: ${EMBEDDER_MODEL_ID}"
echo ""
echo "Restart containers to use cached models:"
echo "  cd /home/rakpan/Code/project-vyasa/deploy"
echo "  docker compose restart cortex-brain cortex-worker embedder"
echo "  # (and cortex-vision if enabled)"
