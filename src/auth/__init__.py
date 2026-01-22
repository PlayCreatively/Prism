"""
Authentication module for PRISM.

Provides Supabase-based authentication with login/register pages
and session management for protected routes.
"""

from src.auth.session import SessionManager, get_session_manager
from src.auth.middleware import require_auth, get_current_user, is_authenticated
from src.auth.pages import create_login_page, create_register_page, create_logout_handler

__all__ = [
    'SessionManager',
    'get_session_manager',
    'require_auth',
    'get_current_user',
    'is_authenticated',
    'create_login_page',
    'create_register_page',
    'create_logout_handler',
]
