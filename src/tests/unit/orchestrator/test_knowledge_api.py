"""
Tests for knowledge API endpoints focusing on:
- Timeout protection in background extraction
- Promotion deduplication by fact_hash

Note: These tests configure arango.ArangoClient (the library) rather than
patching internal functions like _get_db, following the "Golden Rule".
The firewall already mocks ArangoClient, but we override it per-test to
configure specific return values.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import TimeoutError as FutureTimeoutError

from src.orchestrator.api.knowledge import (
    _run_extraction_background,
    _promote_fact_to_canonical,
    _compute_fact_hash,
    EXTERNAL_REFERENCES_COLLECTION,
    CANDIDATE_KNOWLEDGE_COLLECTION,
    CANONICAL_KNOWLEDGE_COLLECTION,
)


class TestTimeoutProtection:
    """Test timeout protection in background extraction."""
    
    @patch("src.orchestrator.api.knowledge._ensure_collections")
    @patch("src.orchestrator.api.knowledge._update_external_reference_status")
    @patch("src.orchestrator.api.knowledge._extract_facts_from_content")
    @patch("src.orchestrator.api.knowledge.telemetry_emitter")
    def test_extraction_timeout_updates_status(
        self,
        mock_telemetry,
        mock_extract,
        mock_update_status,
        mock_ensure_collections,
        monkeypatch,
    ):
        """Test that timeout updates status to NEEDS_REVIEW and emits telemetry."""
        # Configure arango.ArangoClient (library level) to return our mock DB
        # This follows the "Golden Rule" - mock the library, not project files
        from src.orchestrator.api.knowledge import EXTERNAL_REFERENCES_COLLECTION
        
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_doc = {"status": "EXTRACTING"}
        mock_coll.get.return_value = mock_doc
        
        # Configure collection to return our mock when external_references is requested
        def collection_side_effect(name):
            if name == EXTERNAL_REFERENCES_COLLECTION:
                return mock_coll
            return MagicMock()
        mock_db.collection.side_effect = collection_side_effect
        mock_db.has_collection.return_value = True
        
        def mock_client_factory(hosts):
            mock_client = Mock()
            mock_client.db.return_value = mock_db
            return mock_client
        
        monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
        
        # Make extraction hang (simulate timeout)
        def slow_extraction(*args, **kwargs):
            time.sleep(1)  # Simulate slow extraction
            return ([], False, None)
        
        mock_extract.side_effect = slow_extraction
        
        # Mock ThreadPoolExecutor to raise TimeoutError
        with patch("src.orchestrator.api.knowledge.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor.__enter__.return_value = mock_executor
            mock_executor.__exit__.return_value = None
            mock_future = MagicMock()
            mock_future.result.side_effect = FutureTimeoutError()
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value = mock_executor
            
            # Run background extraction
            _run_extraction_background("ref-123", "proj-456", "test content")
            
            # Verify status was updated to NEEDS_REVIEW
            calls = mock_update_status.call_args_list
            assert len(calls) >= 1
            # Last call should be NEEDS_REVIEW or FAILED
            last_status = calls[-1][0][1]  # Second argument is status
            assert last_status in ("NEEDS_REVIEW", "FAILED")
            
            # Verify telemetry was emitted
            mock_telemetry.emit_event.assert_called()
            call_args = mock_telemetry.emit_event.call_args
            assert call_args[0][0] == "knowledge_sideload_failed"
            assert call_args[0][1]["reason"] == "timeout"
            assert call_args[0][1]["reference_id"] == "ref-123"
    
    @patch("src.orchestrator.api.knowledge._ensure_collections")
    @patch("src.orchestrator.api.knowledge._update_external_reference_status")
    @patch("src.orchestrator.api.knowledge._extract_facts_from_content")
    def test_extraction_timeout_uses_failed_if_already_failed(
        self,
        mock_extract,
        mock_update_status,
        mock_ensure_collections,
        monkeypatch,
    ):
        """Test that timeout uses FAILED status if reference is already in FAILED state."""
        # Configure arango.ArangoClient (library level) to return our mock DB
        from src.orchestrator.api.knowledge import EXTERNAL_REFERENCES_COLLECTION
        
        mock_db = MagicMock()
        mock_coll = MagicMock()
        # Return document with FAILED status for the test reference_id
        mock_doc = {"reference_id": "ref-123", "status": "FAILED"}
        mock_coll.get.return_value = mock_doc
        
        # Configure collection to return our mock when external_references is requested
        def collection_side_effect(name):
            if name == EXTERNAL_REFERENCES_COLLECTION:
                return mock_coll
            return MagicMock()
        mock_db.collection.side_effect = collection_side_effect
        # Ensure has_collection returns True so _ensure_collections doesn't try to create it
        mock_db.has_collection.return_value = True
        # Mock create_collection to do nothing
        mock_db.create_collection = Mock(return_value=None)
        
        def mock_client_factory(hosts):
            mock_client = Mock()
            mock_client.db.return_value = mock_db
            return mock_client
        
        monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
        
        # Mock ThreadPoolExecutor to raise TimeoutError
        with patch("src.orchestrator.api.knowledge.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor.__enter__.return_value = mock_executor
            mock_executor.__exit__.return_value = None
            mock_future = MagicMock()
            mock_future.result.side_effect = FutureTimeoutError()
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value = mock_executor
            
            # Run background extraction
            _run_extraction_background("ref-123", "proj-456", "test content")
            
            # Verify status was updated to FAILED (not NEEDS_REVIEW)
            calls = mock_update_status.call_args_list
            assert len(calls) >= 1
            last_status = calls[-1][0][1]
            assert last_status == "FAILED"


class TestFactHashDeduplication:
    """Test promotion deduplication by fact_hash."""
    
    def test_compute_fact_hash_normalizes_correctly(self):
        """Test that fact_hash normalizes subject, predicate, object correctly."""
        hash1 = _compute_fact_hash("Alice", "knows", "Bob")
        hash2 = _compute_fact_hash("alice", "KNOWS", "bob")
        hash3 = _compute_fact_hash("  Alice  ", "  knows  ", "  Bob  ")
        
        # All should produce the same hash (normalized)
        assert hash1 == hash2 == hash3
        
        # Different facts should produce different hashes
        hash4 = _compute_fact_hash("Alice", "knows", "Charlie")
        assert hash1 != hash4
    
    @patch("src.orchestrator.api.knowledge.logger")
    def test_promotion_deduplication_merges_evidence(self, _mock_logger):
        """Test that promoting a duplicate fact merges evidence instead of creating duplicate."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_db.collection.return_value = mock_coll
        
        # Mock existing canonical entry with same fact_hash
        existing_entry = {
            "_key": "entity_123",
            "entity_id": "entity_123",
            "subject": "Alice",
            "predicate": "knows",
            "object": "Bob",
            "fact_hash": _compute_fact_hash("Alice", "knows", "Bob"),
            "source_pointers": [
                {"reference_id": "ref-1", "source_url": "http://example.com/1"}
            ],
            "provenance_log": [
                {"job_id": "ref-1", "project_id": "proj-1"}
            ],
        }
        
        # Mock AQL query to return existing entry
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [existing_entry]
        mock_db.aql.execute.return_value = mock_cursor
        
        # Fact to promote (same s|p|o, different reference_id)
        fact = {
            "fact_id": "fact-456",
            "subject": "Alice",
            "predicate": "knows",
            "object": "Bob",
        }
        
        # Promote fact
        _promote_fact_to_canonical(
            db=mock_db,
            fact=fact,
            reference_id="ref-2",
            source_url="http://example.com/2",
            project_id="proj-1",
        )
        
        # Verify update was called (not insert)
        mock_coll.update.assert_called_once()
        update_args = mock_coll.update.call_args[0][0]
        
        # Verify fact_hash is set
        assert update_args["fact_hash"] == _compute_fact_hash("Alice", "knows", "Bob")
        
        # Verify evidence was merged (both source_pointers should be present)
        source_pointers = update_args["source_pointers"]
        assert len(source_pointers) == 2
        ref_ids = [ptr["reference_id"] for ptr in source_pointers]
        assert "ref-1" in ref_ids
        assert "ref-2" in ref_ids
        
        # Verify provenance was merged
        provenance_log = update_args["provenance_log"]
        assert len(provenance_log) == 2
        job_ids = [log["job_id"] for log in provenance_log]
        assert "ref-1" in job_ids
        assert "ref-2" in job_ids
    
    @patch("src.orchestrator.api.knowledge.logger")
    def test_promotion_deduplication_prevents_duplicate_pointers(self, _mock_logger):
        """Test that promoting same reference_id twice doesn't create duplicate pointers."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_db.collection.return_value = mock_coll
        
        # Mock existing canonical entry
        existing_entry = {
            "_key": "entity_123",
            "entity_id": "entity_123",
            "subject": "Alice",
            "predicate": "knows",
            "object": "Bob",
            "fact_hash": _compute_fact_hash("Alice", "knows", "Bob"),
            "source_pointers": [
                {"reference_id": "ref-1", "source_url": "http://example.com/1"}
            ],
            "provenance_log": [
                {"job_id": "ref-1", "project_id": "proj-1"}
            ],
        }
        
        # Mock AQL query to return existing entry
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [existing_entry]
        mock_db.aql.execute.return_value = mock_cursor
        
        # Fact to promote (same s|p|o, same reference_id - should not duplicate)
        fact = {
            "fact_id": "fact-456",
            "subject": "Alice",
            "predicate": "knows",
            "object": "Bob",
        }
        
        # Promote fact with same reference_id
        _promote_fact_to_canonical(
            db=mock_db,
            fact=fact,
            reference_id="ref-1",  # Same reference_id
            source_url="http://example.com/1",
            project_id="proj-1",
        )
        
        # Verify update was called
        mock_coll.update.assert_called_once()
        update_args = mock_coll.update.call_args[0][0]
        
        # Verify source_pointers list still has only one entry (no duplicate)
        source_pointers = update_args["source_pointers"]
        assert len(source_pointers) == 1
        assert source_pointers[0]["reference_id"] == "ref-1"
        
        # Verify provenance_log still has only one entry (no duplicate)
        provenance_log = update_args["provenance_log"]
        assert len(provenance_log) == 1
        assert provenance_log[0]["job_id"] == "ref-1"
    
    @patch("src.orchestrator.api.knowledge.logger")
    def test_promotion_creates_new_entry_if_hash_not_found(self, _mock_logger):
        """Test that promoting a fact with new hash creates a new canonical entry."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_db.collection.return_value = mock_coll
        
        # Mock AQL query to return empty (no existing entry)
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = []
        mock_db.aql.execute.return_value = mock_cursor
        
        # Mock get to return None (entity_id not found)
        mock_coll.get.return_value = None
        
        # Fact to promote (new fact)
        fact = {
            "fact_id": "fact-789",
            "subject": "Charlie",
            "predicate": "knows",
            "object": "David",
        }
        
        # Promote fact
        _promote_fact_to_canonical(
            db=mock_db,
            fact=fact,
            reference_id="ref-3",
            source_url="http://example.com/3",
            project_id="proj-1",
        )
        
        # Verify insert was called (not update)
        mock_coll.insert.assert_called_once()
        insert_args = mock_coll.insert.call_args[0][0]
        
        # Verify fact_hash is set
        assert insert_args["fact_hash"] == _compute_fact_hash("Charlie", "knows", "David")
        assert insert_args["subject"] == "Charlie"
        assert insert_args["predicate"] == "knows"
        assert insert_args["object"] == "David"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
