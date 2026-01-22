"""
Tests for storage backends.

Tests both GitBackend and SupabaseBackend implementations.
"""

import json
import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Test imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.protocol import StorageBackend
from src.storage.git_backend import GitBackend
from src.storage.factory import create_backend, get_backend_type


class TestGitBackend:
    """Tests for GitBackend file-based storage."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory structure."""
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        (project_path / "nodes").mkdir()
        (project_path / "data").mkdir()
        (project_path / "node_types").mkdir()
        
        # Create a sample node
        node_id = "test-node-123"
        node_data = {
            "title": "Test Node",
            "content": "Test content",
            "type": "default",
            "x": 100,
            "y": 200,
            "links": []
        }
        with open(project_path / "nodes" / f"{node_id}.json", "w") as f:
            json.dump(node_data, f)
        
        # Create a sample user
        user_data = {
            "name": "TestUser",
            "color": "#ff0000",
            "drill_queue": []
        }
        with open(project_path / "data" / "TestUser.json", "w") as f:
            json.dump(user_data, f)
        
        return project_path
    
    def test_load_nodes(self, temp_project):
        """Test loading all nodes from project."""
        backend = GitBackend(temp_project)
        nodes = backend.load_nodes()
        
        assert len(nodes) == 1
        assert "test-node-123" in nodes
        assert nodes["test-node-123"]["title"] == "Test Node"
    
    def test_save_node(self, temp_project):
        """Test saving a new node."""
        backend = GitBackend(temp_project)
        
        node_id = "new-node-456"
        node_data = {
            "title": "New Node",
            "content": "New content",
            "type": "default",
            "x": 300,
            "y": 400,
            "links": []
        }
        
        backend.save_node(node_id, node_data)
        
        # Verify file was created
        node_file = temp_project / "nodes" / f"{node_id}.json"
        assert node_file.exists()
        
        with open(node_file) as f:
            saved_data = json.load(f)
        assert saved_data["title"] == "New Node"
    
    def test_delete_node(self, temp_project):
        """Test deleting a node."""
        backend = GitBackend(temp_project)
        
        # Verify node exists
        node_file = temp_project / "nodes" / "test-node-123.json"
        assert node_file.exists()
        
        # Delete it
        result = backend.delete_node("test-node-123")
        assert result is True
        assert not node_file.exists()
    
    def test_delete_nonexistent_node(self, temp_project):
        """Test deleting a node that doesn't exist."""
        backend = GitBackend(temp_project)
        result = backend.delete_node("nonexistent-node")
        assert result is False
    
    def test_list_users(self, temp_project):
        """Test listing all users in project."""
        backend = GitBackend(temp_project)
        users = backend.list_users()
        
        assert "TestUser" in users
    
    def test_load_user(self, temp_project):
        """Test loading user data."""
        backend = GitBackend(temp_project)
        user_data = backend.load_user("TestUser")
        
        assert user_data is not None
        assert user_data["name"] == "TestUser"
        assert user_data["color"] == "#ff0000"
    
    def test_load_nonexistent_user(self, temp_project):
        """Test loading a user that doesn't exist."""
        backend = GitBackend(temp_project)
        user_data = backend.load_user("NonexistentUser")
        assert user_data is None
    
    def test_save_user(self, temp_project):
        """Test saving user data."""
        backend = GitBackend(temp_project)
        
        user_data = {
            "name": "NewUser",
            "color": "#00ff00",
            "drill_queue": ["node1", "node2"]
        }
        
        backend.save_user("NewUser", user_data)
        
        # Verify file was created
        user_file = temp_project / "data" / "NewUser.json"
        assert user_file.exists()
    
    def test_get_graph(self, temp_project):
        """Test getting graph data for visualization."""
        backend = GitBackend(temp_project)
        graph = backend.get_graph()
        
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 1
    
    def test_is_node_encumbered_no_users(self, temp_project):
        """Test encumbrance check when no other users reference node."""
        backend = GitBackend(temp_project)
        
        # Node should not be encumbered since no user has it in queue
        is_encumbered, users = backend.is_node_encumbered("test-node-123", "TestUser")
        assert is_encumbered is False
        assert len(users) == 0
    
    def test_is_node_encumbered_with_other_user(self, temp_project):
        """Test encumbrance check when another user has node in queue."""
        # Create another user with the node in their queue
        other_user = {
            "name": "OtherUser",
            "drill_queue": ["test-node-123"]
        }
        with open(temp_project / "data" / "OtherUser.json", "w") as f:
            json.dump(other_user, f)
        
        backend = GitBackend(temp_project)
        is_encumbered, users = backend.is_node_encumbered("test-node-123", "TestUser")
        
        assert is_encumbered is True
        assert "OtherUser" in users


class TestBackendFactory:
    """Tests for the backend factory."""
    
    def test_get_backend_type_default(self, tmp_path):
        """Test that default backend type is git."""
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        
        backend_type = get_backend_type(project_path)
        assert backend_type == "git"
    
    def test_get_backend_type_from_config(self, tmp_path):
        """Test reading backend type from config.json."""
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        
        config = {"backend": "supabase", "supabase_url": "https://test.supabase.co"}
        with open(project_path / "config.json", "w") as f:
            json.dump(config, f)
        
        backend_type = get_backend_type(project_path)
        assert backend_type == "supabase"
    
    def test_create_git_backend(self, tmp_path):
        """Test creating a Git backend via factory."""
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        (project_path / "nodes").mkdir()
        (project_path / "data").mkdir()
        
        backend = create_backend(project_path)
        assert isinstance(backend, GitBackend)


class TestSupabaseBackendMocked:
    """Tests for SupabaseBackend using mocks."""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock = MagicMock()
        
        # Mock table operations
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.delete.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        
        mock.table.return_value = mock_table
        return mock
    
    def test_supabase_backend_import(self):
        """Test that SupabaseBackend can be imported."""
        try:
            from src.storage.supabase_backend import SupabaseBackend
            assert SupabaseBackend is not None
        except ImportError as e:
            # Skip if supabase not installed
            pytest.skip(f"Supabase not installed: {e}")
    
    @patch('src.storage.supabase_backend.create_client')
    def test_supabase_load_nodes(self, mock_create_client, mock_supabase):
        """Test loading nodes from Supabase."""
        mock_create_client.return_value = mock_supabase
        
        # Setup mock response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "node-1",
                    "title": "Test Node",
                    "content": "Content",
                    "node_type": "default",
                    "position_x": 100,
                    "position_y": 200,
                    "custom_fields": {}
                }
            ]
        )
        
        try:
            from src.storage.supabase_backend import SupabaseBackend
            
            backend = SupabaseBackend(
                project_id="test-project",
                supabase_url="https://test.supabase.co",
                supabase_key="test-key"
            )
            
            nodes = backend.load_nodes()
            assert "node-1" in nodes
            
        except ImportError:
            pytest.skip("Supabase not installed")


class TestStorageProtocol:
    """Tests to verify backends implement the protocol correctly."""
    
    def test_git_backend_implements_protocol(self, tmp_path):
        """Verify GitBackend implements StorageBackend protocol."""
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        (project_path / "nodes").mkdir()
        (project_path / "data").mkdir()
        
        backend = GitBackend(project_path)
        
        # Check all required methods exist
        assert hasattr(backend, 'load_nodes')
        assert hasattr(backend, 'save_node')
        assert hasattr(backend, 'delete_node')
        assert hasattr(backend, 'list_users')
        assert hasattr(backend, 'load_user')
        assert hasattr(backend, 'save_user')
        assert hasattr(backend, 'get_graph')
        assert hasattr(backend, 'is_node_encumbered')
        assert hasattr(backend, 'subscribe')
        assert hasattr(backend, 'unsubscribe')
        
        # Check methods are callable
        assert callable(backend.load_nodes)
        assert callable(backend.save_node)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
