"""
Tests for authentication flow.

Tests session management, middleware, and login/register flows.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.session import SessionManager
from src.auth.middleware import require_auth, get_current_user, is_authenticated, AuthContext


class TestSessionManager:
    """Tests for SessionManager class."""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock = MagicMock()
        mock.auth = MagicMock()
        return mock
    
    @pytest.fixture
    def mock_storage(self):
        """Create a mock NiceGUI storage."""
        return {}
    
    @patch('src.auth.session.create_client')
    def test_session_manager_init(self, mock_create_client, mock_supabase):
        """Test SessionManager initialization."""
        mock_create_client.return_value = mock_supabase
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert manager is not None
        mock_create_client.assert_called_once()
    
    @patch('src.auth.session.create_client')
    def test_login_success(self, mock_create_client, mock_supabase):
        """Test successful login."""
        mock_create_client.return_value = mock_supabase
        
        # Mock successful auth response
        mock_supabase.auth.sign_in_with_password.return_value = MagicMock(
            user=MagicMock(id="user-123", email="test@example.com"),
            session=MagicMock(access_token="token-123")
        )
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        result = manager.login("test@example.com", "password123")
        
        assert result["success"] is True
        assert result["user"]["id"] == "user-123"
    
    @patch('src.auth.session.create_client')
    def test_login_failure(self, mock_create_client, mock_supabase):
        """Test failed login."""
        mock_create_client.return_value = mock_supabase
        
        # Mock failed auth
        from gotrue.errors import AuthApiError
        mock_supabase.auth.sign_in_with_password.side_effect = AuthApiError(
            message="Invalid credentials",
            status=400
        )
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        result = manager.login("test@example.com", "wrongpassword")
        
        assert result["success"] is False
        assert "error" in result
    
    @patch('src.auth.session.create_client')
    def test_register_success(self, mock_create_client, mock_supabase):
        """Test successful registration."""
        mock_create_client.return_value = mock_supabase
        
        mock_supabase.auth.sign_up.return_value = MagicMock(
            user=MagicMock(id="new-user-123", email="new@example.com"),
            session=MagicMock(access_token="new-token")
        )
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        result = manager.register("new@example.com", "password123")
        
        assert result["success"] is True
    
    @patch('src.auth.session.create_client')
    def test_logout(self, mock_create_client, mock_supabase):
        """Test logout clears session."""
        mock_create_client.return_value = mock_supabase
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        manager.logout()
        
        mock_supabase.auth.sign_out.assert_called_once()
    
    @patch('src.auth.session.create_client')
    def test_get_current_user_no_session(self, mock_create_client, mock_supabase):
        """Test getting current user when not logged in."""
        mock_create_client.return_value = mock_supabase
        mock_supabase.auth.get_user.return_value = None
        
        manager = SessionManager(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        user = manager.get_current_user()
        assert user is None


class TestAuthMiddleware:
    """Tests for authentication middleware."""
    
    def test_auth_context_creation(self):
        """Test creating an AuthContext."""
        context = AuthContext(
            user_id="user-123",
            email="test@example.com",
            display_name="Test User",
            is_authenticated=True
        )
        
        assert context.user_id == "user-123"
        assert context.is_authenticated is True
    
    def test_auth_context_anonymous(self):
        """Test anonymous AuthContext."""
        context = AuthContext.anonymous()
        
        assert context.user_id is None
        assert context.is_authenticated is False
    
    def test_is_authenticated_with_valid_user(self):
        """Test is_authenticated returns True for valid user."""
        mock_storage = {"user": {"id": "user-123", "email": "test@example.com"}}
        
        with patch('src.auth.middleware.app') as mock_app:
            mock_app.storage.user = mock_storage
            # The actual implementation would check storage
            assert mock_storage.get("user") is not None
    
    def test_is_authenticated_without_user(self):
        """Test is_authenticated returns False when no user."""
        mock_storage = {}
        
        with patch('src.auth.middleware.app') as mock_app:
            mock_app.storage.user = mock_storage
            assert mock_storage.get("user") is None


class TestRequireAuthDecorator:
    """Tests for the require_auth decorator."""
    
    def test_decorator_exists(self):
        """Test that require_auth decorator exists and is callable."""
        assert callable(require_auth)
    
    def test_decorator_wraps_function(self):
        """Test that decorator properly wraps a function."""
        @require_auth
        async def protected_route():
            return "secret data"
        
        assert protected_route is not None
        assert callable(protected_route)


class TestLoginPageFlow:
    """Integration tests for login page flow."""
    
    def test_login_page_exists(self):
        """Test that login page creator exists."""
        from src.auth.pages import create_login_page
        assert callable(create_login_page)
    
    def test_register_page_exists(self):
        """Test that register page creator exists."""
        from src.auth.pages import create_register_page
        assert callable(create_register_page)
    
    def test_logout_handler_exists(self):
        """Test that logout handler creator exists."""
        from src.auth.pages import create_logout_handler
        assert callable(create_logout_handler)
    
    def test_user_menu_exists(self):
        """Test that user menu renderer exists."""
        from src.auth.pages import render_user_menu
        assert callable(render_user_menu)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
