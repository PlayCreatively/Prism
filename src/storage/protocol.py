"""
StorageBackend Protocol Definition.

This module defines the abstract interface that all storage backends must implement.
Both GitBackend (local files) and SupabaseBackend (cloud) conform to this protocol.
"""

from typing import Protocol, Dict, Any, List, Optional, Callable, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """
    Abstract protocol for storage backends.
    
    All storage backends must implement these methods to provide
    CRUD operations for nodes, users, and synchronization.
    """
    
    # --- Backend Information ---
    
    @property
    def backend_type(self) -> str:
        """Return the backend type identifier ('git' or 'supabase')."""
        ...
    
    @property
    def is_authenticated(self) -> bool:
        """Return True if the backend requires and has valid authentication."""
        ...
    
    @property
    def supports_realtime(self) -> bool:
        """Return True if the backend supports real-time sync (e.g., Supabase)."""
        ...
    
    @property
    def is_read_only(self) -> bool:
        """Return True if the current session is read-only (e.g., unauthenticated public view)."""
        ...
    
    # --- Node Operations ---
    
    def load_nodes(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all nodes from storage.
        
        Returns:
            Dict mapping node_id -> node_data dict with keys:
            - id: str (UUID)
            - label: str
            - parent_id: Optional[str]
            - description: str
            - node_type: str
            - [custom_fields]: Any additional fields
        """
        ...
    
    def save_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """
        Save a single node to storage.
        
        Args:
            node_id: The node's UUID
            node_data: Full node data dict
        """
        ...
    
    def delete_node(self, node_id: str) -> None:
        """
        Delete a node from storage.
        
        Args:
            node_id: The node's UUID to delete
        """
        ...
    
    # --- User Operations ---
    
    def list_users(self) -> List[str]:
        """
        List all users in the project.
        
        Returns:
            List of user identifiers (usernames or UUIDs depending on backend)
        """
        ...
    
    def load_user(self, user_id: str) -> Dict[str, Any]:
        """
        Load a user's state data.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with keys:
            - user_id: str
            - nodes: Dict[node_id -> {interested: Optional[bool], metadata: str}]
        """
        ...
    
    def save_user(self, user_data: Dict[str, Any]) -> None:
        """
        Save a user's state data.
        
        Args:
            user_data: User data dict with user_id and nodes
        """
        ...
    
    def create_user(self, user_id: str) -> Dict[str, Any]:
        """
        Create a new user in the project.
        
        Args:
            user_id: User identifier to create
            
        Returns:
            The created user data dict
        """
        ...
    
    # --- User-Node Relationship Operations ---
    
    def get_user_node_vote(self, user_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's vote/state for a specific node.
        
        Args:
            user_id: User identifier
            node_id: Node UUID
            
        Returns:
            Dict with 'interested' and 'metadata' if exists, None otherwise
        """
        ...
    
    def set_user_node_vote(self, user_id: str, node_id: str, 
                           interested: Optional[bool] = None, 
                           metadata: Optional[str] = None) -> None:
        """
        Set a user's vote/state for a specific node.
        
        Args:
            user_id: User identifier
            node_id: Node UUID
            interested: True=accept, False=reject, None=remove vote
            metadata: User's private notes (None to leave unchanged)
        """
        ...
    
    def remove_user_node_vote(self, user_id: str, node_id: str) -> None:
        """
        Remove a user's vote/state for a node entirely.
        
        Args:
            user_id: User identifier
            node_id: Node UUID
        """
        ...
    
    # --- Aggregated Data ---
    
    def get_node_with_votes(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a node with aggregated vote information from all users.
        
        Args:
            node_id: Node UUID
            
        Returns:
            Node dict with additional keys:
            - interested_users: List[str]
            - rejected_users: List[str]
            - metadata_by_user: Dict[user_id -> metadata]
        """
        ...
    
    def get_graph(self) -> Dict[str, Any]:
        """
        Get the full graph with all nodes and edges, including vote aggregation.
        
        Returns:
            Dict with:
            - nodes: List of node dicts (with interested_users, rejected_users)
            - edges: List of {source, target} dicts
        """
        ...
    
    # --- Node Encumbrance (Shared Data Editing Rules) ---
    
    def get_node_external_users(self, node_id: str, active_user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of users (other than active user) who have data on this node.
        
        Used to enforce shared data editing rules:
        - If empty, node is unencumbered (free to edit/delete)
        - If non-empty, node is encumbered (protected)
        
        Args:
            node_id: Node UUID
            active_user_id: Current active user's identifier
            
        Returns:
            List of dicts with:
            - user_id: str
            - has_vote: bool (True if interested is not None)
            - interested: Optional[bool]
            - has_metadata: bool
        """
        ...
    
    def is_node_encumbered(self, node_id: str, active_user_id: str) -> bool:
        """
        Check if a node has external user data (other than active user).
        
        Args:
            node_id: Node UUID
            active_user_id: Current active user's identifier
            
        Returns:
            True if other users have data on this node
        """
        ...
    
    # --- Synchronization ---
    
    def sync(self) -> Dict[str, Any]:
        """
        Pull latest changes from remote (git pull or no-op for realtime).
        
        Returns:
            Dict with:
            - success: bool
            - message: str
            - conflicts: Optional[List] (if any merge conflicts)
        """
        ...
    
    def push(self) -> Dict[str, Any]:
        """
        Push local changes to remote (git push or no-op for realtime).
        
        Returns:
            Dict with:
            - success: bool
            - message: str
        """
        ...
    
    def has_unpushed_changes(self) -> bool:
        """
        Check if there are local changes that haven't been pushed.
        
        Returns:
            True if there are unpushed changes (always False for realtime backends)
        """
        ...
    
    # --- Real-time Subscriptions (optional, for Supabase) ---
    
    def subscribe(self, 
                  on_node_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
                  on_vote_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None) -> None:
        """
        Subscribe to real-time updates (no-op for git backend).
        
        Args:
            on_node_change: Callback(event_type, node_id, node_data)
                           event_type: 'INSERT', 'UPDATE', 'DELETE'
            on_vote_change: Callback(event_type, node_id, vote_data)
        """
        ...
    
    def unsubscribe(self) -> None:
        """Unsubscribe from real-time updates."""
        ...
    
    # --- Node Types (project-specific) ---
    
    def get_node_types_dir(self) -> Optional[str]:
        """
        Get the path to the node_types directory for this project.
        
        Returns:
            Path string for git backend, None for Supabase (uses DB instead)
        """
        ...


class AuthProvider(Protocol):
    """
    Protocol for authentication providers.
    Used by SupabaseBackend for user authentication.
    """
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get the currently authenticated user, or None."""
        ...
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with email and password.
        
        Returns:
            Dict with 'success', 'user', 'error'
        """
        ...
    
    def logout(self) -> None:
        """Log out the current user."""
        ...
    
    def register(self, email: str, password: str, username: str) -> Dict[str, Any]:
        """
        Register a new user.
        
        Returns:
            Dict with 'success', 'user', 'error'
        """
        ...
    
    def get_session_token(self) -> Optional[str]:
        """Get the current session JWT token."""
        ...
    
    def refresh_session(self) -> bool:
        """Refresh the session token. Returns True if successful."""
        ...
