"""Deterministic precision contract validator for tables."""

from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import Any, Dict, List, Tuple

from ...shared.schema import PrecisionContract, PrecisionFlag


def _normalize_numeric(val: Any) -> str | None:
    try:
        text = str(val).strip()
    except Exception:
        return None
    if not text:
        return None
    if "%" in text:
        return None
    text = text.replace(",", "")
    letters = [c for c in text if c.isalpha() and c.lower() != "e"]
    if letters:
        return None
    return text


def _format_number(val: Any, max_decimals: int, max_sig_figs: int, rounding_rule: str) -> str:
    """
    Format a number to target precision, idempotently.
    
    If the value is already a string with correct precision, return it unchanged.
    This prevents re-rounding already-rounded values (e.g., "123.46" should not become "123.50").
    """
    text = _normalize_numeric(val)
    if text is None:
        return str(val)
    
    # Idempotency check: if val is already a string with correct decimal places, return as-is
    # This prevents re-rounding already-rounded values (e.g., "123.46" should not become "123.50")
    # For already-formatted strings, we only check decimal places (not sig figs) to maintain idempotency
    # This ensures that a value formatted in a previous pass won't be re-formatted unnecessarily
    try:
        if isinstance(val, str) and "." in val:
            # Parse the string to check if it's already correctly formatted
            dec_existing = Decimal(text)
            fractional_part = val.split(".", 1)[1]
            decimal_places = len(fractional_part)
            
            # If decimal places already match target, check if rounding to that precision would change it
            if decimal_places == max_decimals:
                # Apply only the decimal places constraint (not sig figs) to check idempotency
                # This ensures already-formatted strings aren't re-rounded even if they slightly exceed sig figs
                quant = Decimal(1).scaleb(-max_decimals)
                rounded = dec_existing.quantize(
                    quant, 
                    rounding=ROUND_HALF_EVEN if rounding_rule == "bankers" else ROUND_HALF_UP
                )
                
                # If rounding to target decimals doesn't change the value, it's already correctly formatted
                # This is idempotent: a value that was already formatted won't be re-formatted
                if rounded == dec_existing:
                    return val
    except Exception:
        pass
    
    # Value needs formatting - proceed with normalization
    try:
        dec = Decimal(text)
    except Exception:
        return str(val)

    # Apply significant figures constraint first
    digits = len(dec.as_tuple().digits)
    if digits > max_sig_figs:
        shift = digits - max_sig_figs
        dec = dec.quantize(Decimal(1).scaleb(-shift), rounding=ROUND_HALF_EVEN if rounding_rule == "bankers" else ROUND_HALF_UP)

    # Apply decimal places constraint
    quant = Decimal(1).scaleb(-max_decimals)
    dec = dec.quantize(quant, rounding=ROUND_HALF_EVEN if rounding_rule == "bankers" else ROUND_HALF_UP)
    return f"{dec:.{max_decimals}f}"


def validate_table_precision(table: Dict[str, Any], contract: PrecisionContract, rigor: str) -> Tuple[Dict[str, Any], List[PrecisionFlag], List[str]]:
    """
    Apply deterministic precision rules to a table.

    Returns (rewritten_table, flags, warnings)
    """
    rows = table.get("rows") or []
    if not isinstance(rows, list):
        return table, [], ["invalid_rows"]

    flags: List[PrecisionFlag] = []
    warnings: List[str] = []
    rewritten_rows: List[Dict[str, Any]] = []

    per_column_decimals: Dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        new_row: Dict[str, Any] = {}
        for col, val in row.items():
            norm = _normalize_numeric(val)
            if norm is None:
                # Non-numeric value: leave as-is, but flag in conservative mode
                new_row[col] = val
                if rigor == "conservative":
                    warnings.append(f"non_numeric_value:{col}")
                continue
            decimals = 0
            if "." in norm:
                decimals = len(norm.split(".")[1])
            per_column_decimals.setdefault(col, decimals)
            if decimals != per_column_decimals[col] and contract.consistency_rule == "per_column":
                flags.append(
                    PrecisionFlag(
                        table_id=table.get("table_id", "unknown_table"),
                        column=col,
                        issue="INCONSISTENT_DECIMALS",
                        details=f"Inconsistent decimal places in column {col}",
                    )
                )
            formatted = _format_number(val, contract.max_decimals, contract.max_sig_figs, contract.rounding_rule)
            original_val_str = str(val)
            # Check if value was changed or if it violates the contract
            value_changed = formatted != original_val_str
            # Also check if the formatted value still violates sig figs (for idempotent values)
            try:
                from decimal import Decimal
                dec_formatted = Decimal(_normalize_numeric(formatted) or formatted)
                digits_formatted = len(dec_formatted.as_tuple().digits)
                still_violates_sig_figs = digits_formatted > contract.max_sig_figs
            except Exception:
                still_violates_sig_figs = False
            
            if value_changed or still_violates_sig_figs:
                # Value was changed or still violates contract, so generate flag
                flags.append(
                    PrecisionFlag(
                        table_id=table.get("table_id", "unknown_table"),
                        column=col,
                        issue="EXCESSIVE_PRECISION",
                        details=f"Normalized to {contract.max_decimals} decimals / {contract.max_sig_figs} sig figs",
                    )
                )
            new_row[col] = formatted
        rewritten_rows.append(new_row)

    rewritten_table = dict(table)
    rewritten_table["rows"] = rewritten_rows

    # In conservative mode, if flags exist that imply uncorrected issues, raise via caller
    if (flags or warnings) and rigor == "conservative":
        warnings.append("precision_contract_flags")

    return rewritten_table, flags, warnings
