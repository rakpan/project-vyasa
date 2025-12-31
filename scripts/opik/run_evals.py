#!/usr/bin/env python3
"""
Offline-friendly Opik eval runner scaffold.

Loads a dataset JSONL and, if Opik is configured, submits for evaluation.
Otherwise prints a local summary for manual inspection.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

from src.shared.config import OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY, OPIK_TIMEOUT_SECONDS, OPIK_PROJECT_NAME


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    data = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data


def submit_to_opik(records: List[Dict[str, Any]]) -> None:
    if not OPIK_ENABLED or not OPIK_BASE_URL:
        print("Opik not configured; skipping remote eval submission.")
        return
    url = f"{OPIK_BASE_URL.rstrip('/')}/api/evals"
    headers = {
        "Content-Type": "application/json",
    }
    if OPIK_API_KEY:
        headers["Authorization"] = f"Bearer {OPIK_API_KEY}"
    payload = {"project": OPIK_PROJECT_NAME, "records": records}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=OPIK_TIMEOUT_SECONDS)
        resp.raise_for_status()
        print(f"Submitted {len(records)} records to Opik evals.")
    except Exception as exc:
        print(f"Opik submission failed (ignored): {exc}", file=sys.stderr)


def print_summary(records: List[Dict[str, Any]]) -> None:
    print(f"Loaded {len(records)} records.")
    labels = {}
    for rec in records:
        lbl = rec.get("label") or rec.get("flags")
        labels[str(lbl)] = labels.get(str(lbl), 0) + 1
    print("Label/flag distribution:")
    for k, v in labels.items():
        print(f"  {k}: {v}")


def main(dataset_path: str):
    path = Path(dataset_path)
    if not path.exists():
        print(f"Dataset not found: {path}", file=sys.stderr)
        sys.exit(1)
    records = load_dataset(path)
    print_summary(records)
    try:
        submit_to_opik(records)
    except Exception:
        # best effort only
        pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: run_evals.py <dataset_jsonl>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
