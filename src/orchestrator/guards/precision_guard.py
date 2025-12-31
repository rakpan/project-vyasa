"""Precision guard for table artifacts."""

from typing import Any, Dict, List, Optional

from ...shared.schema import PrecisionFlag


def _normalize_numeric(val: Any) -> Optional[str]:
    try:
        text = str(val).strip()
    except Exception:
        return None
    if "%" in text:
        return None
    # Strip commas for standard numeric formats
    text = text.replace(",", "")
    # Reject units/letters except scientific notation e/E
    letters = [c for c in text if c.isalpha() and c.lower() != "e"]
    if letters:
        return None
    return text


def infer_decimal_places(value: Any) -> int:
    """Infer decimal places for numeric-like values."""
    text_norm = _normalize_numeric(value)
    if text_norm is None:
        return 0
    try:
        if "e" in text_norm.lower():
            base = text_norm.lower().split("e", 1)[0]
            if "." in base:
                return len(base.split(".")[1])
            return 0
        if "." in text_norm:
            return len(text_norm.split(".")[1])
        return 0
    except Exception:
        return 0


def _is_numeric(val: Any) -> bool:
    norm = _normalize_numeric(val)
    if norm is None:
        return False
    try:
        float(norm)
        return True
    except Exception:
        return False


def check_table_precision(table_json: Dict[str, Any], max_decimals_default: int = 2) -> List[PrecisionFlag]:
    """
    Evaluate numeric columns in a table for precision consistency.

    table_json is expected to have:
    {
        "table_id": "...",
        "rows": [
            {"colA": "1.23", "colB": "foo"},
            ...
        ]
    }
    """
    flags: List[PrecisionFlag] = []
    table_id = table_json.get("table_id", "unknown_table")
    rows = table_json.get("rows") or []
    if not isinstance(rows, list) or not rows:
        return flags

    # Collect per-column values
    columns: Dict[str, List[Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for col, val in row.items():
            columns.setdefault(col, []).append(val)

    for col, vals in columns.items():
        numeric_vals = [v for v in vals if _is_numeric(v)]
        if not numeric_vals:
            continue
        decimals: List[int] = []
        has_scientific = False
        has_commas = False
        for v in numeric_vals:
            text = str(v)
            if "e" in text.lower():
                has_scientific = True
            if "," in text:
                has_commas = True
            decimals.append(infer_decimal_places(v))
        if not decimals:
            continue
        # Excessive precision
        if any(d > max_decimals_default for d in decimals):
            flags.append(
                PrecisionFlag(
                    table_id=table_id,
                    column=col,
                    issue="EXCESSIVE_PRECISION",  # type: ignore[arg-type]
                    details=f"Value exceeds {max_decimals_default} decimal places",
                )
            )
        # Inconsistent decimals (skip when formats are mixed scientific/commas to avoid noisy flags)
        if len(set(decimals)) > 1 and not (has_scientific or has_commas):
            flags.append(
                PrecisionFlag(
                    table_id=table_id,
                    column=col,
                    issue="INCONSISTENT_DECIMALS",  # type: ignore[arg-type]
                    details=f"Inconsistent decimal places in column {col}",
                )
            )

    return flags
