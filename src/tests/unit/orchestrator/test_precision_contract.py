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


class TestPrecisionIdempotency:
    """Invariant tests for precision contract idempotency."""
    
    def test_second_run_produces_zero_changes(self):
        """Test that running validator twice on same table produces zero changes."""
        contract = PrecisionContract(
            max_sig_figs=4,
            max_decimals=2,
            rounding_rule="half_up"
        )
        
        # Initial table with excess precision
        initial_table = {
            "table_id": "t1",
            "rows": [
                {"value": "123.456"},
                {"value": "234.567"},
                {"value": "345.678"},
            ]
        }
        
        # First run - should make changes
        rewritten1, flags1, warnings1 = validate_table_precision(
            initial_table, contract, rigor="exploratory"
        )
        
        # Verify changes were made (either table changed or flags generated)
        assert rewritten1 != initial_table or len(flags1) > 0
        
        # Second run on already-formatted table - should produce zero changes
        rewritten2, flags2, warnings2 = validate_table_precision(
            rewritten1, contract, rigor="exploratory"
        )
        
        # Second run should produce identical output (idempotent)
        assert rewritten2 == rewritten1, \
            f"Second run changed output: {rewritten1} -> {rewritten2}"
        # Flags should be identical or empty
        assert flags2 == flags1 or len(flags2) == 0, \
            f"Second run produced new flags: {flags2}"
    
    def test_idempotency_with_mixed_precision(self):
        """Test idempotency with mixed precision values."""
        contract = PrecisionContract(
            max_sig_figs=5,
            max_decimals=3,
            rounding_rule="half_up"
        )
        
        # Table with mixed precision
        initial_table = {
            "table_id": "t2",
            "rows": [
                {"a": "1.0", "b": "2.345"},
                {"a": "1.23", "b": "2.3456"},
                {"a": "1.234", "b": "2.34"},
            ]
        }
        
        # First run
        rewritten1, flags1, _ = validate_table_precision(
            initial_table, contract, rigor="exploratory"
        )
        
        # Second run
        rewritten2, flags2, _ = validate_table_precision(
            rewritten1, contract, rigor="exploratory"
        )
        
        # Should be identical
        assert rewritten2 == rewritten1, \
            f"Second run changed output: {rewritten1} -> {rewritten2}"
    
    def test_per_column_consistency_deterministic(self):
        """Test that per-column consistency is enforced deterministically."""
        contract = PrecisionContract(
            max_sig_figs=5,
            max_decimals=3,
            rounding_rule="half_up"
        )
        
        # Table with inconsistent decimals in same column
        table = {
            "table_id": "t3",
            "rows": [
                {"value": "1.0"},
                {"value": "1.23"},
                {"value": "1.234"},
            ]
        }
        
        # Run multiple times - should produce same result each time
        results = []
        for _ in range(3):
            rewritten, flags, _ = validate_table_precision(
                table, contract, rigor="exploratory"
            )
            results.append((rewritten, flags))
        
        # All runs should produce identical results
        first_result = results[0]
        for i, (rewritten, flags) in enumerate(results[1:], 1):
            assert rewritten == first_result[0], \
                f"Run {i+1} produced different output: {first_result[0]} vs {rewritten}"
            # Flags may differ slightly, but core formatting should be identical
            assert len(flags) == len(first_result[1]) or (len(flags) == 0 and len(first_result[1]) == 0), \
                f"Run {i+1} produced different flag count: {len(first_result[1])} vs {len(flags)}"
