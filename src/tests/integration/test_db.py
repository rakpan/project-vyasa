"""
Integration tests for database connections (ArangoDB and Qdrant).

These tests require running Docker services and should be marked with
@pytest.mark.integration to allow skipping when services are unavailable.
"""

import pytest
from arango.exceptions import DocumentInsertError


@pytest.mark.integration
class TestArangoDB:
    """Integration tests for ArangoDB connection and operations."""
    
    def test_arango_connection(self, real_arango):
        """Test that we can connect to ArangoDB."""
        db = real_arango
        assert db is not None
        
        # Test connection with version check
        version = db.version()
        assert version is not None
        assert isinstance(version, dict)
    
    def test_arango_write_read_delete(self, real_arango):
        """Test write, read, and delete operations on ArangoDB."""
        db = real_arango
        
        # Ensure test collection exists
        collection_name = "test_nodes"
        if not db.has_collection(collection_name):
            db.create_collection(collection_name)
        
        collection = db.collection(collection_name)
        
        # Write a test document
        test_doc = {
            "_key": "test_node_123",
            "name": "Test Node",
            "type": "Test",
            "description": "This is a test node for integration testing"
        }
        
        try:
            # Insert
            meta = collection.insert(test_doc)
            assert meta["_key"] == "test_node_123"
            
            # Read
            retrieved = collection.get("test_node_123")
            assert retrieved is not None
            assert retrieved["name"] == "Test Node"
            assert retrieved["type"] == "Test"
            
            # Update
            collection.update({"_key": "test_node_123", "name": "Updated Test Node"})
            updated = collection.get("test_node_123")
            assert updated["name"] == "Updated Test Node"
            
            # Delete
            collection.delete("test_node_123")
            deleted = collection.get("test_node_123")
            assert deleted is None
            
        except DocumentInsertError:
            # Document might already exist from previous test run
            # Clean up and retry
            try:
                collection.delete("test_node_123")
            except:
                pass
            # Re-insert
            meta = collection.insert(test_doc)
            assert meta["_key"] == "test_node_123"
            
            # Clean up
            collection.delete("test_node_123")
    
    def test_arango_aql_query(self, real_arango):
        """Test AQL query execution."""
        db = real_arango
        
        # Simple AQL query
        cursor = db.aql.execute("RETURN { test: 'value', number: 42 }")
        result = list(cursor)
        
        assert len(result) == 1
        assert result[0]["test"] == "value"
        assert result[0]["number"] == 42
    
    def test_arango_collection_creation(self, real_arango):
        """Test collection creation and deletion."""
        db = real_arango
        
        test_collection = "test_collection_temp"
        
        # Create collection if it doesn't exist
        if db.has_collection(test_collection):
            db.delete_collection(test_collection)
        
        # Create
        db.create_collection(test_collection)
        assert db.has_collection(test_collection)
        
        # Delete
        db.delete_collection(test_collection)
        assert not db.has_collection(test_collection)


@pytest.mark.integration
class TestQdrant:
    """Integration tests for Qdrant connection and operations."""
    
    def test_qdrant_connection(self, real_qdrant):
        """Test that we can connect to Qdrant."""
        client = real_qdrant
        assert client is not None
        
        # Test connection with get_collections
        collections = client.get_collections()
        assert isinstance(collections, dict)
        assert "collections" in collections
    
    def test_qdrant_collection_operations(self, real_qdrant):
        """Test collection creation and deletion in Qdrant."""
        from qdrant_client.models import Distance, VectorParams
        
        client = real_qdrant
        test_collection = "test_collection_integration"
        
        # Delete collection if it exists
        try:
            client.delete_collection(test_collection)
        except:
            pass
        
        # Create collection
        client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        # Verify it exists
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert test_collection in collection_names
        
        # Delete collection
        client.delete_collection(test_collection)
        
        # Verify it's gone
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert test_collection not in collection_names
    
    def test_qdrant_point_operations(self, real_qdrant):
        """Test point insertion and retrieval in Qdrant."""
        from qdrant_client.models import Distance, VectorParams, PointStruct
        
        client = real_qdrant
        test_collection = "test_points_integration"
        
        # Clean up
        try:
            client.delete_collection(test_collection)
        except:
            pass
        
        # Create collection
        client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        try:
            # Insert a point
            test_vector = [0.1] * 384
            point = PointStruct(
                id=1,
                vector=test_vector,
                payload={"name": "test_point", "type": "test"}
            )
            
            client.upsert(
                collection_name=test_collection,
                points=[point]
            )
            
            # Retrieve the point
            retrieved = client.retrieve(
                collection_name=test_collection,
                ids=[1]
            )
            
            assert len(retrieved) == 1
            assert retrieved[0].payload["name"] == "test_point"
            
        finally:
            # Clean up
            try:
                client.delete_collection(test_collection)
            except:
                pass

