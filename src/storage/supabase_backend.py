"""
Supabase Storage Backend for PRISM.

Implements the StorageBackend protocol using Supabase PostgreSQL
for cloud storage with real-time synchronization.

Requires: pip install supabase
"""

import logging
import os
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache settings
CACHE_TTL_SECONDS = 5  # How long to cache graph data before re-fetching

# Try to import supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


class SupabaseBackend:
    """
    Cloud-based storage backend using Supabase.
    
    Features:
    - PostgreSQL storage for nodes and votes
    - Real-time subscriptions for live updates
    - Row Level Security for access control
    - JWT-based authentication
    """
    
    def __init__(
        self,
        project_id: str,
        client: Optional["Client"] = None,
        auth_provider=None,
        read_only: bool = False,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        project_slug: Optional[str] = None
    ):
        """
        Initialize SupabaseBackend.
        
        Args:
            project_id: UUID of the project in Supabase (or slug if project_slug not set)
            client: Optional pre-configured Supabase client
            auth_provider: Optional auth provider for user info
            read_only: If True, disable write operations (public view)
            supabase_url: Supabase project URL (or use SUPABASE_URL env)
            supabase_key: Supabase publishable key (or use SUPABASE_KEY env)
            project_slug: If provided, resolve to UUID from database
        """
        if not SUPABASE_AVAILABLE:
            raise ImportError(
                "supabase-py is required for SupabaseBackend. "
                "Install with: pip install supabase"
            )
        
        self._project_id_or_slug = project_id
        self._project_slug = project_slug or project_id  # Use project_id as slug if not specified
        self._resolved_project_id: Optional[str] = None  # Will be resolved lazily
        self._read_only = read_only
        self._auth_provider = auth_provider
        self._subscriptions = []
        
        # Cache for graph data to reduce network calls
        self._graph_cache: Optional[Dict[str, Any]] = None
        self._graph_cache_time: float = 0
        self._members_cache: Optional[List[Dict[str, Any]]] = None
        self._members_cache_time: float = 0
        
        # Create client if not provided
        if client:
            self._client = client
        else:
            url = supabase_url or os.environ.get("SUPABASE_URL")
            key = supabase_key or os.environ.get("SUPABASE_KEY")
            
            if not url or not key:
                raise ValueError(
                    "Supabase URL and key required. "
                    "Set SUPABASE_URL and SUPABASE_KEY environment variables."
                )
            
            self._client = create_client(url, key)
    
    @property
    def project_id(self) -> str:
        """Get the resolved project UUID, looking up by slug if needed."""
        if self._resolved_project_id:
            return self._resolved_project_id
        
        # Check if it looks like a UUID already
        if self._is_uuid(self._project_id_or_slug):
            self._resolved_project_id = self._project_id_or_slug
            return self._resolved_project_id
        
        # Try to look up by slug
        try:
            response = self._client.table("projects")\
                .select("id")\
                .eq("slug", self._project_slug)\
                .single()\
                .execute()
            
            if response.data:
                self._resolved_project_id = response.data["id"]
                logger.info(f"Resolved project slug '{self._project_slug}' to UUID: {self._resolved_project_id}")
                return self._resolved_project_id
        except Exception as e:
            logger.warning(f"Failed to resolve project slug '{self._project_slug}': {e}")
        
        # If lookup failed, return the original value (will fail on queries, but that's expected)
        logger.error(f"Could not resolve project slug '{self._project_slug}' to UUID")
        return self._project_id_or_slug
    
    def _is_uuid(self, value: str) -> bool:
        """Check if a string looks like a UUID."""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))
    
    # --- Backend Information ---
    
    def _ensure_auth_token(self) -> None:
        """
        Ensure we're using the authenticated Supabase client.
        
        This is critical for RLS policies to work - they check auth.uid()
        which is NULL unless the client is authenticated.
        
        The auth_provider (SessionManager) has an already-authenticated client
        after login(), so we just swap to use that client.
        """
        if not self._auth_provider:
            logger.debug("No auth provider configured")
            return
        
        try:
            # Get the authenticated client from SessionManager
            # This is the SAME client that was used for login, already has session
            if hasattr(self._auth_provider, 'get_authenticated_client'):
                auth_client = self._auth_provider.get_authenticated_client()
                if auth_client:
                    self._client = auth_client
                    logger.debug("Switched to authenticated client from SessionManager")
                    return
                else:
                    logger.warning("SessionManager has no authenticated client (user may not be logged in)")
            else:
                logger.warning("Auth provider doesn't support get_authenticated_client()")
        except Exception as e:
            logger.warning(f"Failed to get authenticated client: {e}")

    @property
    def backend_type(self) -> str:
        """Return the backend type identifier."""
        return "supabase"
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        if self._auth_provider:
            return self._auth_provider.get_current_user() is not None
        # Check Supabase session
        try:
            session = self._client.auth.get_session()
            return session is not None and session.user is not None
        except Exception:
            return False
    
    @property
    def supports_realtime(self) -> bool:
        """Supabase supports real-time sync."""
        return True
    
    @property
    def is_read_only(self) -> bool:
        """Check if session is read-only."""
        return self._read_only or not self.is_authenticated
    
    def ensure_project_membership(self) -> bool:
        """
        Ensure the current user is a member of this project.
        
        For public projects, automatically joins the user if not already a member.
        
        Returns:
            True if user is a member (or just joined), False otherwise
        """
        if not self.is_authenticated:
            logger.warning("ensure_project_membership: Not authenticated")
            return False
        
        # Ensure auth token is set for RLS
        self._ensure_auth_token()
        
        user_id = self._get_current_user_id()
        if not user_id:
            logger.warning("ensure_project_membership: Could not get user ID")
            return False
        
        try:
            # Check if already a member (simple query, no RPC)
            logger.info(f"Checking project membership: user={user_id}, project={self.project_id}")
            response = self._client.table("project_members")\
                .select("user_id")\
                .eq("project_id", self.project_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"User {user_id} is already a member of project {self.project_id}")
                return True
            
            # Not a member yet - try to join via RPC (works for public projects)
            logger.info(f"User {user_id} is not a member, attempting to join public project {self.project_id}")
            try:
                join_response = self._client.rpc(
                    "join_public_project",
                    {"p_project_id": self.project_id}
                ).execute()
                
                if join_response.data:
                    logger.info(f"User {user_id} successfully joined project {self.project_id}")
                    return True
                else:
                    logger.warning(f"join_public_project returned False - project may not be public")
                    return False
            except Exception as rpc_error:
                logger.warning(f"Failed to call join_public_project RPC: {rpc_error}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to check project membership: {e}")
            return False

    def get_project_members(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all members of this project with their profile info.
        Uses caching to avoid repeated network calls.
        
        Returns a list of dicts with: id, username, display_name, role
        """
        # Check cache first
        if not force_refresh and self._members_cache is not None:
            cache_age = time.time() - self._members_cache_time
            if cache_age < CACHE_TTL_SECONDS * 6:  # Members cache lasts longer (30s)
                return self._members_cache
        
        try:
            # Query project_members joined with profiles
            response = self._client.table("project_members")\
                .select("user_id, role, profiles(id, username, display_name)")\
                .eq("project_id", self.project_id)\
                .execute()
            
            members = []
            for row in response.data:
                profile = row.get("profiles", {}) or {}
                members.append({
                    "id": row["user_id"],
                    "username": profile.get("username", "Unknown"),
                    "display_name": profile.get("display_name", ""),
                    "role": row.get("role", "member")
                })
            
            # Update cache
            self._members_cache = members
            self._members_cache_time = time.time()
            
            logger.debug(f"get_project_members: found {len(members)} members")
            return members
        except Exception as e:
            logger.error(f"Failed to get project members: {e}")
            return self._members_cache or []

    def _get_current_user_id(self) -> Optional[str]:
        """Get the current authenticated user's ID."""
        if self._auth_provider:
            user = self._auth_provider.get_current_user()
            return user.get("id") if user else None
        try:
            session = self._client.auth.get_session()
            return session.user.id if session and session.user else None
        except Exception:
            return None
    
    # --- Node Operations ---
    
    def load_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Load all nodes for this project from Supabase."""
        try:
            response = self._client.table("nodes")\
                .select("*")\
                .eq("project_id", self.project_id)\
                .execute()
            
            nodes = {}
            for row in response.data:
                node_id = row["id"]
                nodes[node_id] = {
                    "id": node_id,
                    "label": row["label"],
                    "parent_id": row["parent_id"],
                    "description": row.get("description", ""),
                    "node_type": row.get("node_type", "default"),
                    # Include any custom fields from JSONB column if present
                    **(row.get("custom_fields") or {})
                }
            
            return nodes
        except Exception as e:
            logger.error(f"Failed to load nodes: {e}")
            return {}
    
    def save_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """Save or update a node in Supabase."""
        if self.is_read_only:
            raise PermissionError("Cannot save in read-only mode")
        
        # Ensure auth token is set for RLS policies
        self._ensure_auth_token()
        
        # Separate core fields from custom fields
        core_fields = {"id", "label", "parent_id", "description", "node_type"}
        custom_fields = {k: v for k, v in node_data.items() if k not in core_fields}
        
        row = {
            "id": node_id,
            "project_id": self.project_id,
            "label": node_data.get("label", ""),
            "parent_id": node_data.get("parent_id"),
            "description": node_data.get("description", ""),
            "node_type": node_data.get("node_type", "default"),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if custom_fields:
            row["custom_fields"] = custom_fields
        
        # Add created_by for new nodes
        user_id = self._get_current_user_id()
        if user_id:
            row["created_by"] = user_id
        
        try:
            self._client.table("nodes").upsert(row).execute()
            self.invalidate_cache()  # Invalidate cache after write
        except Exception as e:
            logger.error(f"Failed to save node {node_id}: {e}")
            raise
    
    def delete_node(self, node_id: str) -> None:
        """Delete a node from Supabase."""
        if self.is_read_only:
            raise PermissionError("Cannot delete in read-only mode")
        
        try:
            self._client.table("nodes")\
                .delete()\
                .eq("id", node_id)\
                .eq("project_id", self.project_id)\
                .execute()
            self.invalidate_cache()  # Invalidate cache after write
        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
            raise
    
    # --- User Operations ---
    
    def list_users(self) -> List[str]:
        """List all users who are members of this project."""
        try:
            response = self._client.table("project_members")\
                .select("user_id, profiles(username)")\
                .eq("project_id", self.project_id)\
                .execute()
            
            users = []
            for row in response.data:
                # Use username if available, otherwise user_id
                if row.get("profiles") and row["profiles"].get("username"):
                    users.append(row["profiles"]["username"])
                else:
                    users.append(row["user_id"])
            
            return sorted(users)
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []
    
    def load_user(self, user_id: str) -> Dict[str, Any]:
        """Load a user's vote data for this project."""
        try:
            # Get user's votes for nodes in this project
            response = self._client.table("user_node_votes")\
                .select("node_id, interested, metadata")\
                .eq("user_id", self._resolve_user_id(user_id))\
                .execute()
            
            nodes = {}
            for row in response.data:
                nodes[row["node_id"]] = {
                    "interested": row.get("interested"),
                    "metadata": row.get("metadata", "")
                }
            
            return {"user_id": user_id, "nodes": nodes}
        except Exception as e:
            logger.error(f"Failed to load user {user_id}: {e}")
            return {"user_id": user_id, "nodes": {}}
    
    def save_user(self, user_data: Dict[str, Any]) -> None:
        """Save user data (votes) to Supabase."""
        if self.is_read_only:
            raise PermissionError("Cannot save in read-only mode")
        
        user_id = self._resolve_user_id(user_data["user_id"])
        nodes = user_data.get("nodes", {})
        
        for node_id, vote_data in nodes.items():
            self.set_user_node_vote(
                user_id=user_id,
                node_id=node_id,
                interested=vote_data.get("interested"),
                metadata=vote_data.get("metadata")
            )
    
    def create_user(self, user_id: str) -> Dict[str, Any]:
        """Add a user to this project."""
        if self.is_read_only:
            raise PermissionError("Cannot create user in read-only mode")
        
        resolved_id = self._resolve_user_id(user_id)
        
        try:
            self._client.table("project_members").upsert({
                "project_id": self.project_id,
                "user_id": resolved_id,
                "role": "member",
                "joined_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to add user to project: {e}")
        
        return {"user_id": user_id, "nodes": {}}
    
    def _resolve_user_id(self, user_id: str) -> str:
        """
        Resolve a username to a user UUID.
        
        For compatibility, this checks if user_id is already a UUID,
        otherwise looks up by username.
        """
        # If it looks like a UUID, return as-is
        if len(user_id) == 36 and user_id.count("-") == 4:
            return user_id
        
        # Look up by username
        try:
            logger.debug(f"Looking up username: {user_id}")
            response = self._client.table("profiles")\
                .select("id")\
                .eq("username", user_id)\
                .single()\
                .execute()
            
            resolved = response.data["id"]
            logger.debug(f"Resolved {user_id} to {resolved}")
            return resolved
        except Exception as e:
            logger.warning(f"Failed to resolve username {user_id}: {e}")
            # Fallback: try current authenticated user
            current_id = self._get_current_user_id()
            if current_id:
                logger.info(f"Using current authenticated user {current_id} instead of {user_id}")
                return current_id
            # Last resort: return as-is (will likely fail on insert)
            logger.error(f"Could not resolve {user_id}, returning as-is")
            return user_id
    
    # --- User-Node Relationship Operations ---
    
    def get_user_node_vote(self, user_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a user's vote for a specific node."""
        try:
            resolved_id = self._resolve_user_id(user_id)
            response = self._client.table("user_node_votes")\
                .select("interested, metadata")\
                .eq("user_id", resolved_id)\
                .eq("node_id", node_id)\
                .single()\
                .execute()
            
            return {
                "interested": response.data.get("interested"),
                "metadata": response.data.get("metadata", "")
            }
        except Exception:
            return None
    
    def set_user_node_vote(
        self, 
        user_id: str, 
        node_id: str,
        interested: Optional[bool] = None,
        metadata: Optional[str] = None
    ) -> None:
        """Set a user's vote for a node."""
        if self.is_read_only:
            raise PermissionError("Cannot vote in read-only mode")
        
        # Ensure auth token is set for RLS policies
        self._ensure_auth_token()
        
        # For Supabase, we MUST use the authenticated user's UUID
        # RLS policy requires auth.uid() = user_id
        resolved_id = self._get_current_user_id()
        if not resolved_id:
            # Fallback to resolution (for backwards compatibility)
            resolved_id = self._resolve_user_id(user_id)
        
        logger.info(f"set_user_node_vote: input user_id={user_id}, resolved_id={resolved_id}")
        
        row = {
            "user_id": resolved_id,
            "node_id": node_id,
            "voted_at": datetime.utcnow().isoformat()
        }
        
        if interested is not None:
            row["interested"] = interested
        
        if metadata is not None:
            row["metadata"] = metadata
        
        try:
            self._client.table("user_node_votes").upsert(row).execute()
            self.invalidate_cache()  # Invalidate cache after write
        except Exception as e:
            logger.error(f"Failed to set vote: {e}")
            raise
    
    def remove_user_node_vote(self, user_id: str, node_id: str) -> None:
        """Remove a user's vote for a node."""
        if self.is_read_only:
            raise PermissionError("Cannot remove vote in read-only mode")
        
        # Ensure auth token is set for RLS policies
        self._ensure_auth_token()
        
        # For Supabase, use authenticated user's UUID (RLS requires auth.uid() = user_id)
        resolved_id = self._get_current_user_id()
        if not resolved_id:
            resolved_id = self._resolve_user_id(user_id)
        
        logger.info(f"remove_user_node_vote: input user_id={user_id}, resolved_id={resolved_id}")
        
        try:
            self._client.table("user_node_votes")\
                .delete()\
                .eq("user_id", resolved_id)\
                .eq("node_id", node_id)\
                .execute()
            self.invalidate_cache()  # Invalidate cache after write
        except Exception as e:
            logger.error(f"Failed to remove vote: {e}")
    
    # --- Aggregated Data ---
    
    def get_node_with_votes(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node with aggregated vote information."""
        nodes = self.load_nodes()
        node = nodes.get(node_id)
        if not node:
            return None
        
        # Get all votes for this node
        try:
            response = self._client.table("user_node_votes")\
                .select("user_id, interested, metadata, profiles(username)")\
                .eq("node_id", node_id)\
                .execute()
            
            interested = []
            rejected = []
            metadata_by_user = {}
            
            for row in response.data:
                username = row.get("profiles", {}).get("username") or row["user_id"]
                
                if row.get("interested") is True:
                    interested.append(username)
                elif row.get("interested") is False:
                    rejected.append(username)
                
                if row.get("metadata"):
                    metadata_by_user[username] = row["metadata"]
            
            return {
                **node,
                "interested_users": interested,
                "rejected_users": rejected,
                "metadata_by_user": metadata_by_user,
                "metadata": next(iter(metadata_by_user.values()), "") if metadata_by_user else ""
            }
        except Exception as e:
            logger.error(f"Failed to get node votes: {e}")
            return node
    
    def invalidate_cache(self) -> None:
        """Invalidate all caches. Called after writes to ensure fresh data."""
        self._graph_cache = None
        self._graph_cache_time = 0
        logger.debug("Cache invalidated")

    def get_graph(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the full graph with all nodes and edges.
        Uses caching to avoid repeated network calls on every UI refresh.
        """
        # Check cache first (unless force refresh requested)
        if not force_refresh and self._graph_cache is not None:
            cache_age = time.time() - self._graph_cache_time
            if cache_age < CACHE_TTL_SECONDS:
                logger.debug(f"Returning cached graph (age: {cache_age:.1f}s)")
                return self._graph_cache
        
        logger.debug("Fetching fresh graph from Supabase")
        nodes = self.load_nodes()
        
        # Get all votes for the project
        try:
            response = self._client.table("user_node_votes")\
                .select("node_id, user_id, interested, metadata, profiles(username)")\
                .execute()
            
            # Index votes by node_id
            votes_by_node: Dict[str, List] = {}
            for row in response.data:
                node_id = row["node_id"]
                if node_id not in votes_by_node:
                    votes_by_node[node_id] = []
                votes_by_node[node_id].append(row)
        except Exception as e:
            logger.error(f"Failed to load votes: {e}")
            votes_by_node = {}
        
        result_nodes = []
        
        for nid, node in nodes.items():
            node_out = dict(node)
            
            interested = []
            rejected = []
            metadata_by_user = {}
            combined_metadata = ""
            
            for vote in votes_by_node.get(nid, []):
                username = vote.get("profiles", {}).get("username") or vote["user_id"]
                
                if vote.get("interested") is True:
                    interested.append(username)
                elif vote.get("interested") is False:
                    rejected.append(username)
                
                if vote.get("metadata"):
                    metadata_by_user[username] = vote["metadata"]
                    if not combined_metadata:
                        combined_metadata = vote["metadata"]
            
            node_out["interested_users"] = interested
            node_out["rejected_users"] = rejected
            node_out["metadata"] = combined_metadata
            node_out["metadata_by_user"] = metadata_by_user
            
            result_nodes.append(node_out)
        
        # Build edges
        edges = []
        for n in result_nodes:
            pid = n.get("parent_id")
            if pid and pid in nodes:
                edges.append({"source": pid, "target": n["id"]})
        
        result = {"nodes": result_nodes, "edges": edges}
        
        # Update cache
        self._graph_cache = result
        self._graph_cache_time = time.time()
        
        return result
    
    # --- Node Encumbrance ---
    
    def get_node_external_users(self, node_id: str, active_user_id: str) -> List[Dict[str, Any]]:
        """Get list of users (other than active user) who have data on this node."""
        resolved_active = self._resolve_user_id(active_user_id)
        
        try:
            response = self._client.table("user_node_votes")\
                .select("user_id, interested, metadata, profiles(username)")\
                .eq("node_id", node_id)\
                .neq("user_id", resolved_active)\
                .execute()
            
            external_users = []
            for row in response.data:
                username = row.get("profiles", {}).get("username") or row["user_id"]
                external_users.append({
                    "user_id": username,
                    "has_vote": row.get("interested") is not None,
                    "interested": row.get("interested"),
                    "has_metadata": bool(row.get("metadata"))
                })
            
            return external_users
        except Exception as e:
            logger.error(f"Failed to get external users: {e}")
            return []
    
    def is_node_encumbered(self, node_id: str, active_user_id: str) -> bool:
        """Check if a node has external user data."""
        return len(self.get_node_external_users(node_id, active_user_id)) > 0
    
    # --- Synchronization ---
    
    def sync(self) -> Dict[str, Any]:
        """No-op for Supabase (real-time sync)."""
        return {"success": True, "message": "Real-time sync active"}
    
    def push(self) -> Dict[str, Any]:
        """No-op for Supabase (auto-save)."""
        return {"success": True, "message": "Changes saved automatically"}
    
    def has_unpushed_changes(self) -> bool:
        """Always False for Supabase (auto-save)."""
        return False
    
    # --- Real-time Subscriptions ---
    
    def subscribe(
        self,
        on_node_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        on_vote_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
    ) -> None:
        """Subscribe to real-time updates for this project."""
        
        def handle_node_change(payload):
            if on_node_change:
                event_type = payload.get("eventType", "UPDATE")
                record = payload.get("new") or payload.get("old", {})
                node_id = record.get("id", "")
                on_node_change(event_type, node_id, record)
        
        def handle_vote_change(payload):
            if on_vote_change:
                event_type = payload.get("eventType", "UPDATE")
                record = payload.get("new") or payload.get("old", {})
                node_id = record.get("node_id", "")
                on_vote_change(event_type, node_id, record)
        
        try:
            # Subscribe to nodes table
            if on_node_change:
                channel = self._client.channel(f"nodes:{self.project_id}")
                channel.on_postgres_changes(
                    event="*",
                    schema="public",
                    table="nodes",
                    filter=f"project_id=eq.{self.project_id}",
                    callback=handle_node_change
                ).subscribe()
                self._subscriptions.append(channel)
            
            # Subscribe to votes table
            if on_vote_change:
                channel = self._client.channel(f"votes:{self.project_id}")
                channel.on_postgres_changes(
                    event="*",
                    schema="public",
                    table="user_node_votes",
                    callback=handle_vote_change
                ).subscribe()
                self._subscriptions.append(channel)
                
        except Exception as e:
            logger.error(f"Failed to subscribe to real-time updates: {e}")
    
    def unsubscribe(self) -> None:
        """Unsubscribe from all real-time updates."""
        for channel in self._subscriptions:
            try:
                channel.unsubscribe()
            except Exception:
                pass
        self._subscriptions.clear()
    
    # --- Node Types ---
    
    def get_node_types_dir(self) -> Optional[str]:
        """Supabase stores node types in DB, not filesystem."""
        return None
    
    def load_node_types(self) -> List[Dict[str, Any]]:
        """Load node type definitions from Supabase."""
        try:
            response = self._client.table("node_types")\
                .select("*")\
                .eq("project_id", self.project_id)\
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to load node types: {e}")
            return []
    
    def load_prompts(self, node_type_id: str) -> List[Dict[str, Any]]:
        """Load prompts for a node type."""
        try:
            response = self._client.table("prompts")\
                .select("*")\
                .eq("node_type_id", node_type_id)\
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            return []
