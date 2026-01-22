"""
Session Management for PRISM.

Handles Supabase JWT tokens, session storage, and user state.
Sessions are stored in NiceGUI's app.storage for persistence.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Try to import supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


class SessionManager:
    """
    Manages user sessions with Supabase authentication.
    
    Uses NiceGUI's storage system for session persistence.
    """
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        session_expiry_hours: int = 168  # 7 days
    ):
        """
        Initialize SessionManager.
        
        Args:
            supabase_url: Supabase project URL (or use SUPABASE_URL env)
            supabase_key: Supabase publishable key (or use SUPABASE_KEY env)
            session_expiry_hours: How long sessions remain valid
        """
        self._supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self._supabase_key = supabase_key or os.environ.get("SUPABASE_KEY")
        self._session_expiry = timedelta(hours=session_expiry_hours)
        self._client: Optional["Client"] = None
    
    @property
    def is_available(self) -> bool:
        """Check if Supabase auth is available."""
        return (
            SUPABASE_AVAILABLE and 
            bool(self._supabase_url) and 
            bool(self._supabase_key)
        )
    
    def _get_client(self) -> "Client":
        """Get or create Supabase client."""
        if not self.is_available:
            raise RuntimeError("Supabase not configured")
        
        if self._client is None:
            self._client = create_client(self._supabase_url, self._supabase_key)
        
        return self._client
    
    def _get_storage(self) -> Dict[str, Any]:
        """Get NiceGUI storage for current user."""
        try:
            from nicegui import app
            storage = app.storage.user
            logger.debug(f"_get_storage: got app.storage.user, id={id(storage)}")
            return storage
        except Exception as e:
            logger.warning(f"_get_storage: failed to get app.storage.user: {e}")
            # Fallback for testing
            return {}
    
    # --- Authentication ---
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with email and password.
        
        Returns:
            Dict with 'success', 'user', 'error'
        """
        try:
            client = self._get_client()
            response = client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Store session
                self._store_session(response)
                
                return {
                    "success": True,
                    "user": self._format_user(response.user),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "user": None,
                    "error": "Invalid credentials"
                }
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return {
                "success": False,
                "user": None,
                "error": str(e)
            }
    
    def register(self, email: str, password: str, username: str) -> Dict[str, Any]:
        """
        Register a new user.
        
        Returns:
            Dict with 'success', 'user', 'error'
        """
        try:
            client = self._get_client()
            
            # Sign up with Supabase
            response = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username
                    }
                }
            })
            
            if response.user:
                # Create profile record
                # Note: email is stored in auth.users, not in profiles table
                try:
                    client.table("profiles").insert({
                        "id": response.user.id,
                        "username": username,
                        "display_name": username
                    }).execute()
                except Exception as profile_error:
                    logger.warning(f"Failed to create profile: {profile_error}")
                
                # Store session
                self._store_session(response)
                
                return {
                    "success": True,
                    "user": self._format_user(response.user),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "user": None,
                    "error": "Registration failed"
                }
                
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            error_msg = str(e)
            
            # Parse common errors
            if "already registered" in error_msg.lower():
                error_msg = "This email is already registered"
            elif "password" in error_msg.lower():
                error_msg = "Password must be at least 6 characters"
            
            return {
                "success": False,
                "user": None,
                "error": error_msg
            }
    
    def logout(self) -> None:
        """Log out the current user."""
        try:
            client = self._get_client()
            client.auth.sign_out()
        except Exception as e:
            logger.warning(f"Logout error: {e}")
        
        # Clear stored session
        storage = self._get_storage()
        storage.pop("supabase_session", None)
        storage.pop("user", None)
    
    def get_oauth_url(self, provider: str, redirect_url: str) -> Dict[str, Any]:
        """
        Get OAuth URL for a provider (github, google, etc.).
        
        Args:
            provider: OAuth provider name ('github', 'google', 'discord', etc.)
            redirect_url: URL to redirect to after OAuth completes
            
        Returns:
            Dict with 'success', 'url', 'error'
        """
        try:
            client = self._get_client()
            response = client.auth.sign_in_with_oauth({
                "provider": provider,
                "options": {
                    "redirect_to": redirect_url
                }
            })
            
            if response and response.url:
                return {
                    "success": True,
                    "url": response.url,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "url": None,
                    "error": f"Failed to get {provider} OAuth URL"
                }
        except Exception as e:
            logger.error(f"OAuth URL error for {provider}: {e}")
            return {
                "success": False,
                "url": None,
                "error": str(e)
            }
    
    def handle_oauth_callback(self, access_token: str, refresh_token: str) -> Dict[str, Any]:
        """
        Handle OAuth callback with tokens from URL.
        
        Args:
            access_token: Access token from OAuth callback
            refresh_token: Refresh token from OAuth callback
            
        Returns:
            Dict with 'success', 'user', 'error'
        """
        try:
            client = self._get_client()
            response = client.auth.set_session(access_token, refresh_token)
            
            if response and response.user:
                # Store session
                self._store_session(response)
                
                return {
                    "success": True,
                    "user": self._format_user(response.user),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "user": None,
                    "error": "Failed to set session from OAuth"
                }
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return {
                "success": False,
                "user": None,
                "error": str(e)
            }
    
    # --- Session Management ---
    
    def _store_session(self, auth_response) -> None:
        """Store session data in NiceGUI storage."""
        storage = self._get_storage()
        
        session_data = {
            "access_token": auth_response.session.access_token if auth_response.session else None,
            "refresh_token": auth_response.session.refresh_token if auth_response.session else None,
            "expires_at": (datetime.utcnow() + self._session_expiry).isoformat(),
            "user_id": auth_response.user.id if auth_response.user else None
        }
        
        storage["supabase_session"] = session_data
        storage["user"] = self._format_user(auth_response.user) if auth_response.user else None
        
        logger.info(f"_store_session: stored session in storage id={id(storage)}, has_access_token={session_data['access_token'] is not None}")
    
    def _format_user(self, user) -> Dict[str, Any]:
        """Format Supabase user object for storage."""
        return {
            "id": user.id,
            "email": user.email,
            "username": user.user_metadata.get("username", user.email.split("@")[0]),
            "display_name": user.user_metadata.get("display_name", ""),
            "avatar_url": user.user_metadata.get("avatar_url", "")
        }
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get the currently authenticated user, or None."""
        storage = self._get_storage()
        logger.info(f"get_current_user: storage id={id(storage)}, keys={list(storage.keys()) if storage else 'empty'}")
        
        # Check for stored user
        user = storage.get("user")
        session = storage.get("supabase_session")
        
        logger.info(f"get_current_user: user={user is not None}, session={session is not None}")
        
        if not user or not session:
            return None
        
        # Check if session expired
        expires_at = session.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if datetime.utcnow() > expiry:
                    self.logout()
                    return None
            except Exception:
                pass
        
        return user
    
    def get_session_token(self) -> Optional[str]:
        """Get the current session access token."""
        storage = self._get_storage()
        session = storage.get("supabase_session")
        return session.get("access_token") if session else None
    
    def refresh_session(self) -> bool:
        """Refresh the session token. Returns True if successful."""
        storage = self._get_storage()
        session = storage.get("supabase_session")
        
        if not session or not session.get("refresh_token"):
            return False
        
        try:
            client = self._get_client()
            response = client.auth.refresh_session(session["refresh_token"])
            
            if response.session:
                self._store_session(response)
                return True
        except Exception as e:
            logger.error(f"Session refresh failed: {e}")
        
        return False
    
    def get_authenticated_client(self) -> Optional["Client"]:
        """
        Get the Supabase client with current session.
        
        If the internal client exists (from a recent login), return it.
        Otherwise, create a new client and restore the session from storage.
        """
        if not self.is_available:
            logger.warning("get_authenticated_client: Supabase not available")
            return None
        
        logger.info(f"get_authenticated_client: _client exists = {self._client is not None}")
        
        # If we have an existing client with a session, return it
        if self._client is not None:
            try:
                session = self._client.auth.get_session()
                logger.info(f"get_authenticated_client: existing client session = {session is not None}, user = {session.user.id if session and session.user else None}")
                if session and session.user:
                    logger.info("Returning existing authenticated client")
                    return self._client
            except Exception as e:
                logger.warning(f"get_authenticated_client: error checking existing client: {e}")
        
        # Try to restore session from storage
        storage = self._get_storage()
        logger.info(f"get_authenticated_client: storage keys = {list(storage.keys()) if storage else 'empty'}")
        session_data = storage.get("supabase_session", {})
        logger.info(f"get_authenticated_client: session_data keys = {list(session_data.keys()) if session_data else 'empty'}")
        access_token = session_data.get("access_token")
        refresh_token = session_data.get("refresh_token")
        
        if not access_token or not refresh_token:
            logger.warning(f"No session tokens in storage (access={access_token is not None}, refresh={refresh_token is not None})")
            return None
        
        try:
            # Create/get client and set the session
            client = self._get_client()
            client.auth.set_session(access_token, refresh_token)
            logger.info("Restored session on client from storage")
            return client
        except Exception as e:
            logger.warning(f"Failed to restore session: {e}")
            return None


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager()
    
    return _session_manager


def configure_session_manager(
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None
) -> SessionManager:
    """Configure and return the global session manager."""
    global _session_manager
    
    _session_manager = SessionManager(
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )
    
    return _session_manager
