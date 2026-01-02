from src.orchestrator.guards.precision_contract import validate_table_precision
from src.shared.schema import PrecisionContract, PrecisionFlag


def test_reject_or_correct_excess_decimals():
    contract = PrecisionContract(max_sig_figs=5, max_decimals=2, rounding_rule="half_up")
    table = {"table_id": "t1", "rows": [{"a": "1.2345"}, {"a": "2.3456"}]}
    rewritten, flags, _warnings = validate_table_precision(table, contract, rigor="exploratory")
    assert all(row["a"].endswith("00") or row["a"].count(".") == 1 for row in rewritten["rows"])
    assert any(f.issue == "EXCESSIVE_PRECISION" for f in flags)


def test_sig_figs_enforced():
    contract = PrecisionContract(max_sig_figs=3, max_decimals=4, rounding_rule="half_up")
    table = {"table_id": "t1", "rows": [{"a": "1234.567"}]}
    rewritten, flags, _warnings = validate_table_precision(table, contract, rigor="exploratory")
    assert rewritten["rows"][0]["a"].startswith("123")
    assert any(f.issue == "EXCESSIVE_PRECISION" for f in flags)


def test_per_column_consistency():
    contract = PrecisionContract(max_sig_figs=5, max_decimals=3, rounding_rule="half_up")
    table = {"table_id": "t1", "rows": [{"a": "1.0"}, {"a": "1.23"}, {"a": "1.234"}]}
    rewritten, flags, _warnings = validate_table_precision(table, contract, rigor="exploratory")
    # All rows should be formatted consistently to max_decimals
    assert all(row["a"].endswith("000") or row["a"].count(".") == 1 for row in rewritten["rows"])
    assert any(f.issue == "INCONSISTENT_DECIMALS" for f in flags)


def test_deterministic_output_stable():
    contract = PrecisionContract(max_sig_figs=4, max_decimals=2, rounding_rule="half_up")
    table = {"table_id": "t1", "rows": [{"a": "123.456"}]}
    rewritten1, flags1, _warnings1 = validate_table_precision(table, contract, rigor="exploratory")
    rewritten2, flags2, _warnings2 = validate_table_precision(rewritten1, contract, rigor="exploratory")
    assert rewritten1 == rewritten2
    assert flags1 == flags2


def test_rigor_behavior():
    contract = PrecisionContract(max_sig_figs=4, max_decimals=2, rounding_rule="half_up")
    # Non-numeric values should be left as-is; conservative should only flag but not rewrite non-numeric
    table = {"table_id": "t1", "rows": [{"a": "not-a-number"}]}
    rewritten, flags, warnings = validate_table_precision(table, contract, rigor="conservative")
    assert rewritten["rows"][0]["a"] == "not-a-number"
    assert warnings or flags
