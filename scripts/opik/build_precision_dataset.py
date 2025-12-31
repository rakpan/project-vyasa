#!/usr/bin/env python3
"""
Build a precision dataset from table artifacts (offline).

- Reads from a JSONL export of tables or ArtifactManifests.
- If no input is provided, best-effort read from ArangoDB (artifact_manifests).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def iter_tables_from_file(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fin:
        for line in fin:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "tables" in obj and isinstance(obj["tables"], list):
                for t in obj["tables"]:
                    if isinstance(t, dict):
                        yield t
            elif isinstance(obj, dict):
                yield obj


def iter_tables_from_arango() -> Iterable[Dict[str, Any]]:
    try:
        from arango import ArangoClient  # type: ignore
        from src.shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
    except Exception:
        return []

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        if not db.has_collection("artifact_manifests"):
            return []
        cursor = db.collection("artifact_manifests").all()
        tables: List[Dict[str, Any]] = []
        for doc in cursor:
            for t in doc.get("tables", []) or []:
                if isinstance(t, dict):
                    t.setdefault("rigor_level", doc.get("rigor_level", "exploratory"))
                    tables.append(t)
        return tables
    except Exception:
        return []


def build_records(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    flags = table.get("precision_flags") or []
    rows = table.get("rows", [])
    records: List[Dict[str, Any]] = []
    for flag in flags:
        col = flag.get("column")
        values = []
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and col in r:
                    values.append(str(r.get(col)))
        records.append(
            {
                "table_id": table.get("table_id"),
                "column": col,
                "issue": flag.get("issue"),
                "values": values,
                "rigor_level": table.get("rigor_level", "exploratory"),
            }
        )
    if not flags:
        records.append(
            {
                "table_id": table.get("table_id"),
                "column": None,
                "issue": None,
                "values": [],
                "rigor_level": table.get("rigor_level", "exploratory"),
            }
        )
    return records


def main(input_path: Optional[str], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if input_path:
        src = Path(input_path)
        if not src.exists():
            print(f"Input file not found: {src}", file=sys.stderr)
            sys.exit(1)
        tables_iter = iter_tables_from_file(src)
    else:
        tables_iter = iter_tables_from_arango()
        if not tables_iter:
            print("No input and Arango unavailable; nothing to do.", file=sys.stderr)
            sys.exit(0)

    count = 0
    with out.open("w", encoding="utf-8") as fout:
        for table in tables_iter:
            if not isinstance(table, dict):
                continue
            for rec in build_records(table):
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
    print(f"Wrote {count} precision records to {out}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: build_precision_dataset.py [input_jsonl] <output_jsonl>", file=sys.stderr)
        sys.exit(1)
    input_arg = sys.argv[1] if len(sys.argv) == 3 else None
    output_arg = sys.argv[2] if len(sys.argv) == 3 else sys.argv[1]
    main(input_arg, output_arg)
