import pytest

from src.orchestrator.guards.precision_guard import infer_decimal_places, check_table_precision


def test_infer_decimal_places_basic():
    assert infer_decimal_places("1.23") == 2
    assert infer_decimal_places(3.1415) == 4
    assert infer_decimal_places("10") == 0
    assert infer_decimal_places("1.2e-3") == 1


def test_consistent_decimals_pass():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "1.23", "colB": "foo"},
            {"colA": "2.34", "colB": "bar"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=3)
    assert flags == []


def test_inconsistent_decimals_flagged():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "1.2", "colB": "foo"},
            {"colA": "2.345", "colB": "bar"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=3)
    issues = {(f.issue, f.column) for f in flags}
    assert ("INCONSISTENT_DECIMALS", "colA") in issues


def test_excessive_precision_flagged():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "1.23456", "colB": "foo"},
            {"colA": "2.23456", "colB": "bar"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=2)
    issues = {(f.issue, f.column) for f in flags}
    assert ("EXCESSIVE_PRECISION", "colA") in issues


def test_non_numeric_columns_ignored():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "abc", "colB": "foo"},
            {"colA": "def", "colB": "bar"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=2)
    assert flags == []


def test_scientific_notation_and_commas():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "1.23e-5"},
            {"colA": "1e-5"},
            {"colA": "1,234.56"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=5)
    issues = {(f.issue, f.column) for f in flags}
    # decimals inferred from base part; all consistent -> no inconsistent flag
    assert ("INCONSISTENT_DECIMALS", "colA") not in issues


def test_percent_and_units_ignored():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "12.5%"},
            {"colA": "12.5 kg"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=2)
    assert flags == []


def test_mixed_ints_and_floats():
    table = {
        "table_id": "t1",
        "rows": [
            {"colA": "1"},
            {"colA": "1.00"},
        ],
    }
    flags = check_table_precision(table, max_decimals_default=2)
    issues = {(f.issue, f.column) for f in flags}
    assert ("INCONSISTENT_DECIMALS", "colA") in issues


def test_empty_table_input():
    assert check_table_precision({"table_id": "t1", "rows": []}) == []
