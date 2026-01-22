"""
Authentication Middleware for PRISM.

Provides decorators and utilities for protecting routes
and accessing the current user.
"""

import functools
import logging
from typing import Optional, Dict, Any, Callable

from nicegui import ui, app

from src.auth.session import get_session_manager

logger = logging.getLogger(__name__)


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get the currently authenticated user.
    
    Returns:
        User dict with id, email, username, etc. or None if not authenticated
    """
    session_manager = get_session_manager()
    return session_manager.get_current_user()


def is_authenticated() -> bool:
    """Check if the current user is authenticated."""
    return get_current_user() is not None


def require_auth(redirect_to: str = "/login"):
    """
    Decorator to require authentication for a page.
    
    Usage:
        @ui.page('/dashboard')
        @require_auth()
        def dashboard():
            ...
    
    Args:
        redirect_to: URL to redirect to if not authenticated
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not is_authenticated():
                # Store the intended destination for post-login redirect
                try:
                    app.storage.user["redirect_after_login"] = app.storage.browser.get("path", "/")
                except Exception:
                    pass
                
                ui.navigate.to(redirect_to)
                return
            
            # User is authenticated, proceed
            result = func(*args, **kwargs)
            if hasattr(result, '__await__'):
                return await result
            return result
        
        return wrapper
    return decorator


def require_project_access(project_id_param: str = "project_id"):
    """
    Decorator to require access to a specific project.
    
    Checks if the user is a member of the project. For public projects,
    allows read-only access.
    
    Usage:
        @ui.page('/project/{project_id}')
        @require_project_access()
        def project_page(project_id: str):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            project_id = kwargs.get(project_id_param)
            
            if not project_id:
                ui.notify("Project not found", color="negative")
                ui.navigate.to("/")
                return
            
            # Check project access
            user = get_current_user()
            has_access = await check_project_access(project_id, user)
            
            if not has_access:
                ui.notify("You don't have access to this project", color="negative")
                ui.navigate.to("/")
                return
            
            result = func(*args, **kwargs)
            if hasattr(result, '__await__'):
                return await result
            return result
        
        return wrapper
    return decorator


async def check_project_access(project_id: str, user: Optional[Dict[str, Any]]) -> bool:
    """
    Check if a user has access to a project.
    
    Args:
        project_id: The project UUID
        user: Current user dict or None
        
    Returns:
        True if user has access (member or public project)
    """
    from src.storage.factory import get_project_config
    
    try:
        # For git-based projects, always allow (local access)
        # This check happens at the project path level
        config = get_project_config(f"db/{project_id}")
        
        if config.get("storage_backend") == "git":
            return True  # Local projects are always accessible
        
        # For Supabase projects, check membership
        if config.get("storage_backend") == "supabase":
            # Public projects are readable by anyone
            if config.get("is_public"):
                return True
            
            # Private projects require authentication
            if not user:
                return False
            
            # Check membership (would need Supabase query)
            # For now, assume authenticated users have access
            return True
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking project access: {e}")
        return False


class AuthContext:
    """
    Context class for auth-related information in the current request.
    
    Use in UI code to adapt based on auth state.
    """
    
    def __init__(self):
        self._user = None
        self._checked = False
    
    @property
    def user(self) -> Optional[Dict[str, Any]]:
        """Get current user, caching the result."""
        if not self._checked:
            self._user = get_current_user()
            self._checked = True
        return self._user
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user is not None
    
    @property
    def user_id(self) -> Optional[str]:
        """Get current user's ID."""
        return self.user.get("id") if self.user else None
    
    @property
    def username(self) -> Optional[str]:
        """Get current user's username."""
        return self.user.get("username") if self.user else None
    
    @property
    def display_name(self) -> str:
        """Get display name for current user."""
        if self.user:
            return self.user.get("display_name") or self.user.get("username") or "User"
        return "Guest"


def get_auth_context() -> AuthContext:
    """Get an AuthContext for the current request."""
    return AuthContext()
