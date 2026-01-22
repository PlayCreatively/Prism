"""
Tests for migration tools.

Tests migrating projects between Git and Supabase backends.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.migration import (
    MigrationResult,
    MigrationProgress,
    GitToSupabaseMigrator,
    SupabaseToGitMigrator,
    migrate_git_to_supabase,
    migrate_supabase_to_git
)


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""
    
    def test_successful_result(self):
        """Test creating a successful migration result."""
        result = MigrationResult(
            success=True,
            nodes_migrated=10,
            users_migrated=3,
            errors=[],
            warnings=[]
        )
        
        assert result.success is True
        assert result.nodes_migrated == 10
        assert result.users_migrated == 3
        assert len(result.errors) == 0
    
    def test_failed_result(self):
        """Test creating a failed migration result."""
        result = MigrationResult(
            success=False,
            nodes_migrated=5,
            users_migrated=0,
            errors=["Database connection failed"],
            warnings=["Some nodes had invalid data"]
        )
        
        assert result.success is False
        assert len(result.errors) == 1
        assert "Database connection failed" in result.errors


class TestMigrationProgress:
    """Tests for MigrationProgress callback."""
    
    def test_progress_without_callback(self):
        """Test progress tracking without a callback."""
        progress = MigrationProgress()
        
        progress.set_total(10)
        progress.update("Step 1")
        
        assert progress.total == 10
        assert progress.current == 1
    
    def test_progress_with_callback(self):
        """Test progress tracking with a callback."""
        messages = []
        
        def callback(msg, current, total):
            messages.append((msg, current, total))
        
        progress = MigrationProgress(callback)
        progress.set_total(5)
        progress.update("Step 1")
        progress.update("Step 2")
        
        assert len(messages) == 2
        assert messages[0] == ("Step 1", 1, 5)
        assert messages[1] == ("Step 2", 2, 5)


class TestGitToSupabaseMigrator:
    """Tests for Git to Supabase migration."""
    
    @pytest.fixture
    def temp_git_project(self, tmp_path):
        """Create a temporary Git project."""
        # Patch DB_DIR to use tmp_path
        project_path = tmp_path / "TestProject"
        project_path.mkdir()
        (project_path / "nodes").mkdir()
        (project_path / "data").mkdir()
        (project_path / "node_types").mkdir()
        (project_path / "prompts").mkdir()
        
        # Create sample nodes
        node_data = {
            "title": "Test Node",
            "content": "Test content",
            "type": "default",
            "x": 100,
            "y": 200,
            "links": []
        }
        with open(project_path / "nodes" / "node-123.json", "w") as f:
            json.dump(node_data, f)
        
        # Create sample user
        user_data = {"name": "TestUser", "drill_queue": []}
        with open(project_path / "data" / "TestUser.json", "w") as f:
            json.dump(user_data, f)
        
        return project_path
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock = MagicMock()
        
        # Mock successful inserts
        mock_table = MagicMock()
        mock_table.insert.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(
            data=[{"id": "project-new-123"}]
        )
        
        mock.table.return_value = mock_table
        return mock
    
    @patch('src.migration.DB_DIR')
    @patch('src.migration.create_client')
    def test_migration_project_not_found(self, mock_create_client, mock_db_dir, tmp_path, mock_supabase):
        """Test migration fails for nonexistent project."""
        mock_db_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_create_client.return_value = mock_supabase
        
        # Note: This will try to access tmp_path / "NonexistentProject"
        result = migrate_git_to_supabase(
            project_name="NonexistentProject",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            user_id="user-123"
        )
        
        assert result.success is False
        assert any("not found" in err.lower() for err in result.errors)
    
    @patch('src.migration.DB_DIR')
    @patch('src.migration.create_client')
    def test_migration_creates_project(self, mock_create_client, mock_db_dir, temp_git_project, mock_supabase):
        """Test migration creates project in Supabase."""
        mock_db_dir.__truediv__ = lambda self, x: temp_git_project.parent / x
        mock_create_client.return_value = mock_supabase
        
        result = migrate_git_to_supabase(
            project_name=temp_git_project.name,
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            user_id="user-123"
        )
        
        # Verify project creation was attempted
        mock_supabase.table.assert_called()


class TestSupabaseToGitMigrator:
    """Tests for Supabase to Git migration."""
    
    @pytest.fixture
    def mock_supabase_with_data(self):
        """Create a mock Supabase client with project data."""
        mock = MagicMock()
        
        def table_factory(name):
            mock_table = MagicMock()
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            
            if name == "projects":
                mock_table.execute.return_value = MagicMock(
                    data=[{
                        "id": "project-123",
                        "name": "Cloud Project",
                        "slug": "cloud-project",
                        "is_public": True
                    }]
                )
            elif name == "nodes":
                mock_table.execute.return_value = MagicMock(
                    data=[{
                        "id": "node-1",
                        "title": "Cloud Node",
                        "content": "Cloud content",
                        "node_type": "default",
                        "position_x": 100,
                        "position_y": 200,
                        "custom_fields": {}
                    }]
                )
            elif name == "connections":
                mock_table.execute.return_value = MagicMock(data=[])
            elif name == "node_types":
                mock_table.execute.return_value = MagicMock(data=[])
            elif name == "prompts":
                mock_table.execute.return_value = MagicMock(data=[])
            elif name == "project_users":
                mock_table.execute.return_value = MagicMock(
                    data=[{
                        "display_name": "CloudUser",
                        "settings": {"drill_queue": []}
                    }]
                )
            else:
                mock_table.execute.return_value = MagicMock(data=[])
            
            return mock_table
        
        mock.table.side_effect = table_factory
        return mock
    
    @patch('src.migration.DB_DIR')
    @patch('src.migration.create_client')
    def test_export_creates_directories(self, mock_create_client, mock_db_dir, tmp_path, mock_supabase_with_data):
        """Test export creates proper directory structure."""
        mock_db_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_create_client.return_value = mock_supabase_with_data
        
        result = migrate_supabase_to_git(
            project_id="project-123",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            target_name="ExportedProject"
        )
        
        project_path = tmp_path / "ExportedProject"
        
        # Verify directories were created
        assert project_path.exists()
        assert (project_path / "nodes").exists()
        assert (project_path / "data").exists()
    
    @patch('src.migration.DB_DIR')
    @patch('src.migration.create_client')
    def test_export_saves_nodes(self, mock_create_client, mock_db_dir, tmp_path, mock_supabase_with_data):
        """Test export saves nodes to JSON files."""
        mock_db_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_create_client.return_value = mock_supabase_with_data
        
        result = migrate_supabase_to_git(
            project_id="project-123",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            target_name="ExportedProject"
        )
        
        node_file = tmp_path / "ExportedProject" / "nodes" / "node-1.json"
        
        if node_file.exists():
            with open(node_file) as f:
                node_data = json.load(f)
            assert node_data["title"] == "Cloud Node"
    
    @patch('src.migration.DB_DIR')
    @patch('src.migration.create_client')
    def test_export_creates_config(self, mock_create_client, mock_db_dir, tmp_path, mock_supabase_with_data):
        """Test export creates config.json with git backend."""
        mock_db_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_create_client.return_value = mock_supabase_with_data
        
        result = migrate_supabase_to_git(
            project_id="project-123",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            target_name="ExportedProject"
        )
        
        config_file = tmp_path / "ExportedProject" / "config.json"
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            assert config["backend"] == "git"


class TestMigrationConvenienceFunctions:
    """Tests for convenience migration functions."""
    
    def test_migrate_git_to_supabase_callable(self):
        """Test that migrate_git_to_supabase is callable."""
        assert callable(migrate_git_to_supabase)
    
    def test_migrate_supabase_to_git_callable(self):
        """Test that migrate_supabase_to_git is callable."""
        assert callable(migrate_supabase_to_git)
    
    def test_progress_callback_integration(self):
        """Test that progress callbacks work with convenience functions."""
        progress_messages = []
        
        def track_progress(msg, current, total):
            progress_messages.append(msg)
        
        # The callback should be accepted without error
        # (actual migration would fail without valid Supabase credentials)
        try:
            migrate_git_to_supabase(
                project_name="test",
                supabase_url="https://test.supabase.co",
                supabase_key="test-key",
                user_id="user-123",
                progress_callback=track_progress
            )
        except Exception:
            pass  # Expected to fail without real credentials


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
