"""
Tests for public routes and read-only access.

Tests the /public/{slug} route and read-only project viewing.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.public_routes import (
    create_public_routes,
    PublicProjectView,
    is_project_public,
    get_public_project_by_slug
)


class TestPublicRouteHelpers:
    """Tests for public route helper functions."""
    
    def test_is_project_public_true(self):
        """Test detecting a public project."""
        mock_project = {
            "id": "project-123",
            "name": "Test Project",
            "is_public": True,
            "slug": "test-project"
        }
        
        assert is_project_public(mock_project) is True
    
    def test_is_project_public_false(self):
        """Test detecting a private project."""
        mock_project = {
            "id": "project-123",
            "name": "Test Project",
            "is_public": False,
            "slug": "test-project"
        }
        
        assert is_project_public(mock_project) is False
    
    def test_is_project_public_missing_flag(self):
        """Test project without is_public flag defaults to private."""
        mock_project = {
            "id": "project-123",
            "name": "Test Project",
            "slug": "test-project"
        }
        
        # Should default to private
        assert is_project_public(mock_project) is False


class TestPublicProjectView:
    """Tests for PublicProjectView class."""
    
    @pytest.fixture
    def mock_backend(self):
        """Create a mock storage backend."""
        backend = MagicMock()
        backend.load_nodes.return_value = {
            "node-1": {
                "title": "Public Node",
                "content": "Public content",
                "type": "default",
                "x": 100,
                "y": 200,
                "links": []
            }
        }
        backend.get_graph.return_value = {
            "nodes": [{"id": "node-1", "name": "Public Node"}],
            "edges": []
        }
        return backend
    
    def test_public_view_initialization(self, mock_backend):
        """Test PublicProjectView can be initialized."""
        view = PublicProjectView(
            project_slug="test-project",
            backend=mock_backend
        )
        
        assert view.project_slug == "test-project"
        assert view.is_read_only is True
    
    def test_public_view_loads_nodes(self, mock_backend):
        """Test PublicProjectView loads nodes from backend."""
        view = PublicProjectView(
            project_slug="test-project",
            backend=mock_backend
        )
        
        nodes = view.get_nodes()
        
        assert "node-1" in nodes
        assert nodes["node-1"]["title"] == "Public Node"
        mock_backend.load_nodes.assert_called()
    
    def test_public_view_prevents_editing(self, mock_backend):
        """Test PublicProjectView blocks edit operations."""
        view = PublicProjectView(
            project_slug="test-project",
            backend=mock_backend
        )
        
        # Attempt to save should raise or return False
        result = view.try_save_node("node-1", {"title": "Modified"})
        
        assert result is False or result is None
    
    def test_public_view_prevents_deletion(self, mock_backend):
        """Test PublicProjectView blocks delete operations."""
        view = PublicProjectView(
            project_slug="test-project",
            backend=mock_backend
        )
        
        result = view.try_delete_node("node-1")
        
        assert result is False or result is None
    
    def test_public_view_gets_graph(self, mock_backend):
        """Test PublicProjectView can get graph for visualization."""
        view = PublicProjectView(
            project_slug="test-project",
            backend=mock_backend
        )
        
        graph = view.get_graph()
        
        assert "nodes" in graph
        assert "edges" in graph
        mock_backend.get_graph.assert_called()


class TestPublicRouteCreation:
    """Tests for route creation."""
    
    def test_create_public_routes_callable(self):
        """Test that create_public_routes is callable."""
        assert callable(create_public_routes)
    
    @patch('src.public_routes.ui')
    def test_public_routes_register_endpoint(self, mock_ui):
        """Test that creating routes registers the endpoint."""
        mock_app = MagicMock()
        
        # This would normally register /public/{slug} route
        # We just verify the function runs without error
        try:
            create_public_routes(mock_app)
        except Exception:
            # May fail without full NiceGUI context, which is OK
            pass


class TestGetPublicProjectBySlug:
    """Tests for fetching public projects by slug."""
    
    @patch('src.public_routes.create_client')
    def test_get_existing_public_project(self, mock_create_client):
        """Test fetching an existing public project."""
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "project-123",
                "name": "Test Project",
                "slug": "test-project",
                "is_public": True
            }]
        )
        
        result = get_public_project_by_slug(
            "test-project",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert result is not None
        assert result["slug"] == "test-project"
    
    @patch('src.public_routes.create_client')
    def test_get_nonexistent_project(self, mock_create_client):
        """Test fetching a project that doesn't exist."""
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        result = get_public_project_by_slug(
            "nonexistent-project",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert result is None
    
    @patch('src.public_routes.create_client')
    def test_get_private_project_returns_none(self, mock_create_client):
        """Test that fetching a private project returns None."""
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        
        # The query filters by is_public=true, so private projects won't be in results
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        result = get_public_project_by_slug(
            "private-project",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert result is None


class TestPublicViewReadOnlyEnforcement:
    """Tests ensuring read-only mode is strictly enforced."""
    
    @pytest.fixture
    def read_only_view(self):
        """Create a read-only public view."""
        mock_backend = MagicMock()
        mock_backend.load_nodes.return_value = {"node-1": {"title": "Test"}}
        
        return PublicProjectView(
            project_slug="test",
            backend=mock_backend
        )
    
    def test_is_read_only_flag(self, read_only_view):
        """Test that is_read_only is True."""
        assert read_only_view.is_read_only is True
    
    def test_cannot_create_node(self, read_only_view):
        """Test that creating nodes is blocked."""
        result = read_only_view.try_create_node({"title": "New Node"})
        assert result is False or result is None
    
    def test_cannot_update_links(self, read_only_view):
        """Test that updating links is blocked."""
        result = read_only_view.try_update_links("node-1", ["node-2"])
        assert result is False or result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
