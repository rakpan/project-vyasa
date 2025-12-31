#!/usr/bin/env python3
"""
Build a tone dataset from recent manuscript blocks (offline).

- Reads from a JSONL export of manuscript blocks or ArtifactManifests.
- If no input is provided, best-effort read from ArangoDB (manuscript_blocks).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.orchestrator.guards.tone_guard import scan_text


def label_block(block: Dict[str, Any]) -> str:
    flags = scan_text(block.get("content", "") or "")
    if any(f.severity == "hard" for f in flags):
        return "sensational"
    return "neutral"


def iter_blocks_from_file(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fin:
        for line in fin:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Support ArtifactManifest shape
            if isinstance(obj, dict) and "blocks" in obj and isinstance(obj["blocks"], list):
                for b in obj["blocks"]:
                    if isinstance(b, dict):
                        yield b
            elif isinstance(obj, dict):
                yield obj


def iter_blocks_from_arango() -> Iterable[Dict[str, Any]]:
    try:
        from arango import ArangoClient  # type: ignore
        from src.shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
    except Exception:
        return []

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        if not db.has_collection("manuscript_blocks"):
            return []
        cursor = db.collection("manuscript_blocks").all()
        return cursor
    except Exception:
        return []


def main(input_path: Optional[str], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if input_path:
        src = Path(input_path)
        if not src.exists():
            print(f"Input file not found: {src}", file=sys.stderr)
            sys.exit(1)
        blocks_iter = iter_blocks_from_file(src)
    else:
        blocks_iter = iter_blocks_from_arango()
        if not blocks_iter:
            print("No input and Arango unavailable; nothing to do.", file=sys.stderr)
            sys.exit(0)

    count = 0
    with out.open("w", encoding="utf-8") as fout:
        for block in blocks_iter:
            if not isinstance(block, dict):
                continue
            label = label_block(block)
            record = {
                "text": block.get("content", ""),
                "label": label,
                "job_id": block.get("job_id"),
                "block_id": block.get("block_id"),
                "rigor_level": block.get("rigor_level", "exploratory"),
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    print(f"Wrote {count} tone records to {out}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: build_tone_dataset.py [input_jsonl] <output_jsonl>", file=sys.stderr)
        sys.exit(1)
    input_arg = sys.argv[1] if len(sys.argv) == 3 else None
    output_arg = sys.argv[2] if len(sys.argv) == 3 else sys.argv[1]
    main(input_arg, output_arg)
