"""
Data Manager for PRISM.

Provides a high-level interface for graph operations, delegating
actual storage to a StorageBackend implementation (Git or Supabase).

This is the main interface used by the application - it handles:
- Graph composition (joining nodes with user votes)
- Node creation with automatic user voting
- Encumbrance checks (shared data editing rules)
- Legacy compatibility
"""

import logging
import uuid as uuid_module
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.protocol import StorageBackend

logger = logging.getLogger(__name__)


class DataManager:
    """
    High-level data manager that delegates to a storage backend.
    
    This class provides:
    - Graph composition (nodes + user votes)
    - Business logic for node creation/updates
    - Encumbrance checks for shared data editing rules
    - Backward compatibility with legacy code
    """

    def __init__(
        self, 
        data_dir: str = "db/data",
        backend: Optional["StorageBackend"] = None,
        project_path: Optional[str] = None
    ):
        """
        Initialize DataManager.
        
        Args:
            data_dir: Legacy parameter - path to data directory
            backend: StorageBackend instance to delegate to
            project_path: Path to project folder (used to create default backend)
        """
        self._backend = backend
        
        # Legacy compatibility: if no backend provided, create GitBackend
        if self._backend is None:
            from src.storage.git_backend import GitBackend
            
            # Determine project path from data_dir
            if project_path:
                proj_path = project_path
            else:
                # data_dir is typically "db/{project}/data"
                data_path = Path(data_dir)
                proj_path = str(data_path.parent)
            
            self._backend = GitBackend(project_path=proj_path)
        
        # Expose some backend properties for legacy compatibility
        self.data_dir = Path(data_dir) if data_dir else None
        self.nodes_dir = self.data_dir.parent / "nodes" if self.data_dir else None
    
    @property
    def backend(self) -> "StorageBackend":
        """Get the underlying storage backend."""
        return self._backend
    
    @property
    def backend_type(self) -> str:
        """Get the backend type ('git' or 'supabase')."""
        return self._backend.backend_type
    
    @property
    def is_read_only(self) -> bool:
        """Check if the current session is read-only."""
        return self._backend.is_read_only
    
    @property
    def supports_realtime(self) -> bool:
        """Check if the backend supports real-time sync."""
        return self._backend.supports_realtime
    
    # --- Legacy File I/O Compatibility ---
    
    def _load_global(self) -> Dict[str, Any]:
        """Legacy method - load all nodes."""
        return {"nodes": self._backend.load_nodes()}
    
    def _save_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """Legacy method - save a single node."""
        self._backend.save_node(node_id, node_data)
    
    def _delete_node_file(self, node_id: str) -> None:
        """Legacy method - delete a node file."""
        self._backend.delete_node(node_id)
    
    def load_user(self, user_id: str) -> Dict[str, Any]:
        """Load user data."""
        return self._backend.load_user(user_id)
    
    def save_user(self, data: Dict[str, Any]) -> None:
        """Save user data."""
        self._backend.save_user(data)
    
    def list_users(self) -> List[str]:
        """Return list of user names."""
        return self._backend.list_users()
    
    # --- Core Graph Logic ---
    
    def get_graph(self) -> Dict[str, Any]:
        """
        Get the full graph with all nodes and edges, including vote aggregation.
        
        Returns:
            Dict with 'nodes' (list) and 'edges' (list)
        """
        return self._backend.get_graph()
    
    def cleanup_orphan_nodes(self) -> int:
        """
        Remove nodes that have zero votes from any user.
        
        Returns:
            Number of nodes removed.
        """
        if hasattr(self._backend, 'cleanup_orphan_nodes'):
            return self._backend.cleanup_orphan_nodes()
        
        # Fallback implementation
        nodes = self._backend.load_nodes()
        if not nodes:
            return 0
        
        users = self._backend.list_users()
        if not users:
            return 0
        
        voted_nodes = set()
        for user_id in users:
            user_data = self._backend.load_user(user_id)
            voted_nodes.update(user_data.get("nodes", {}).keys())
        
        orphan_ids = [nid for nid in nodes.keys() if nid not in voted_nodes]
        
        for nid in orphan_ids:
            self._backend.delete_node(nid)
            logger.info(f"Removed orphan node: {nid}")
        
        # Update parent references
        remaining_nodes = self._backend.load_nodes()
        for nid, node in remaining_nodes.items():
            if node.get("parent_id") in orphan_ids:
                node["parent_id"] = None
                self._backend.save_node(nid, node)
        
        return len(orphan_ids)
    
    # --- Write Operations ---
    
    def add_node(
        self, 
        label: str, 
        parent_id: str = None, 
        users: List[str] = None, 
        interested: bool = True, 
        description: str = "", 
        node_type: str = "default", 
        custom_fields: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Add a new node to the graph.
        
        Args:
            label: Node title
            parent_id: Parent node UUID
            users: List of user IDs to set interest for
            interested: Whether users are interested (True) or rejected (False)
            description: Node description (markdown)
            node_type: Node type identifier
            custom_fields: Dict of custom field values
            
        Returns:
            The created node with vote info
        """
        if self._backend.is_read_only:
            raise PermissionError("Cannot add nodes in read-only mode")
        
        node_id = str(uuid_module.uuid4())
        
        new_node = {
            "id": node_id,
            "node_type": node_type,
            "label": label,
            "parent_id": parent_id,
            "description": description
        }
        
        # Add custom fields
        if custom_fields:
            reserved = {'id', 'parent_id', 'node_type', 'label', 'description', 'metadata'}
            for key, value in custom_fields.items():
                if key not in reserved:
                    new_node[key] = value
        
        # Save node
        self._backend.save_node(node_id, new_node)
        
        # Set user votes
        target_users = users or []
        for user_id in target_users:
            self._backend.set_user_node_vote(
                user_id=user_id,
                node_id=node_id,
                interested=interested,
                metadata=""
            )
        
        # Return enriched node
        return {
            **new_node,
            "interested_users": target_users if interested else [],
            "rejected_users": target_users if not interested else [],
            "metadata": "",
            "metadata_by_user": {}
        }
    
    def update_user_node(self, user_id: str, node_id: str, **kwargs) -> None:
        """
        Update a user's state for a node.
        
        Args:
            user_id: User identifier
            node_id: Node UUID
            **kwargs: Fields to update (interested, metadata)
        """
        if self._backend.is_read_only:
            raise PermissionError("Cannot update in read-only mode")
        
        # Handle the update
        interested = kwargs.get("interested")
        metadata = kwargs.get("metadata")
        
        if interested is None and "interested" in kwargs:
            # Explicit None = remove vote
            self._backend.remove_user_node_vote(user_id, node_id)
        else:
            self._backend.set_user_node_vote(
                user_id=user_id,
                node_id=node_id,
                interested=interested,
                metadata=metadata
            )
    
    def update_shared_node(self, node_id: str, **kwargs) -> None:
        """
        Update shared node properties (label, parent, description, etc.).
        
        Args:
            node_id: Node UUID
            **kwargs: Fields to update
        """
        if self._backend.is_read_only:
            raise PermissionError("Cannot update in read-only mode")
        
        nodes = self._backend.load_nodes()
        if node_id not in nodes:
            logger.warning(f"Node {node_id} not found for update")
            return
        
        node = nodes[node_id]
        user_keys = {'interested', 'metadata'}
        changed = False
        
        for key, value in kwargs.items():
            if key not in user_keys:
                node[key] = value
                changed = True
        
        if changed:
            self._backend.save_node(node_id, node)
    
    def remove_user_node(self, user_id: str, node_id: str) -> None:
        """Remove a user's vote/state for a node (reset to pending)."""
        if self._backend.is_read_only:
            raise PermissionError("Cannot remove in read-only mode")
        
        self._backend.remove_user_node_vote(user_id, node_id)
    
    def update_node(self, node_id: str, **kwargs) -> None:
        """
        Legacy method - routes updates to shared or user files.
        
        WARNING: If updating status/metadata without user context,
        applies to all users (legacy behavior).
        """
        if self._backend.is_read_only:
            raise PermissionError("Cannot update in read-only mode")
        
        # Shared props
        shared_keys = ['label', 'parent_id', 'description', 'node_type']
        if any(k in kwargs for k in shared_keys):
            self.update_shared_node(node_id, **kwargs)
        
        # Handle legacy 'status' -> 'interested'
        if 'status' in kwargs:
            val = kwargs.pop('status')
            kwargs['interested'] = (val == 'accepted')
        
        # User props - apply to all users (legacy behavior)
        user_keys = ['interested', 'metadata']
        if any(k in kwargs for k in user_keys):
            for user_id in self._backend.list_users():
                self.update_user_node(user_id, node_id, **kwargs)
    
    def get_user_node(self, user_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node enriched with user's vote data."""
        user_vote = self._backend.get_user_node_vote(user_id, node_id)
        if not user_vote:
            return None
        
        nodes = self._backend.load_nodes()
        node = nodes.get(node_id)
        if node:
            return {**node, **user_vote}
        return user_vote
    
    def delete_node(self, node_id: str, active_user_id: str = None) -> Dict[str, Any]:
        """
        Delete a node, respecting shared data editing rules.
        
        Args:
            node_id: Node UUID to delete
            active_user_id: Current user (for encumbrance check)
            
        Returns:
            Dict with 'success' and 'message', optionally 'affected_users'
        """
        if self._backend.is_read_only:
            return {"success": False, "message": "Cannot delete in read-only mode"}
        
        # Check encumbrance if user provided
        if active_user_id:
            external_users = self._backend.get_node_external_users(node_id, active_user_id)
            if external_users:
                user_names = [u["user_id"] for u in external_users]
                return {
                    "success": False,
                    "message": "Cannot delete: other users have data on this node",
                    "affected_users": external_users,
                    "affected_user_names": user_names
                }
        
        # Check for child nodes with external data
        nodes = self._backend.load_nodes()
        child_ids = [nid for nid, n in nodes.items() if n.get("parent_id") == node_id]
        
        for child_id in child_ids:
            if active_user_id and self._backend.is_node_encumbered(child_id, active_user_id):
                return {
                    "success": False,
                    "message": "Cannot delete: child nodes have external user data"
                }
        
        # Delete the node
        self._backend.delete_node(node_id)
        
        # Remove all user votes for this node
        for user_id in self._backend.list_users():
            self._backend.remove_user_node_vote(user_id, node_id)
        
        # Update children to become orphans
        for child_id in child_ids:
            child_node = nodes[child_id]
            child_node["parent_id"] = None
            self._backend.save_node(child_id, child_node)
        
        return {"success": True, "message": "Node deleted"}
    
    # --- Encumbrance Checks ---
    
    def get_node_external_users(self, node_id: str, active_user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of users (other than active user) who have data on this node.
        
        Returns:
            List of dicts with user_id, has_vote, interested, has_metadata
        """
        return self._backend.get_node_external_users(node_id, active_user_id)
    
    def is_node_encumbered(self, node_id: str, active_user_id: str) -> bool:
        """Check if a node has external user data."""
        return self._backend.is_node_encumbered(node_id, active_user_id)
    
    def check_edit_permission(
        self, 
        node_id: str, 
        active_user_id: str,
        operation: str = "edit"
    ) -> Dict[str, Any]:
        """
        Check if an edit operation is allowed and get affected users.
        
        Args:
            node_id: Node UUID
            active_user_id: Current user
            operation: 'edit' or 'delete'
            
        Returns:
            Dict with:
            - allowed: bool
            - requires_confirmation: bool
            - affected_users: List of affected user info
            - message: str
        """
        external_users = self._backend.get_node_external_users(node_id, active_user_id)
        
        if not external_users:
            return {
                "allowed": True,
                "requires_confirmation": False,
                "affected_users": [],
                "message": "No other users have data on this node"
            }
        
        if operation == "delete":
            return {
                "allowed": False,
                "requires_confirmation": False,
                "affected_users": external_users,
                "message": f"Cannot delete: {len(external_users)} other user(s) have data on this node"
            }
        
        # For edits, allow with confirmation
        user_names = [u["user_id"] for u in external_users]
        return {
            "allowed": True,
            "requires_confirmation": True,
            "affected_users": external_users,
            "message": f"This change will affect: {', '.join(user_names)}"
        }
    
    # --- Sync Operations ---
    
    def sync(self) -> Dict[str, Any]:
        """Pull latest changes from remote."""
        return self._backend.sync()
    
    def push(self) -> Dict[str, Any]:
        """Push local changes to remote."""
        return self._backend.push()
    
    def has_unpushed_changes(self) -> bool:
        """Check for unpushed changes."""
        return self._backend.has_unpushed_changes()
    
    # --- Real-time Subscriptions ---
    
    def subscribe(self, on_node_change=None, on_vote_change=None) -> None:
        """Subscribe to real-time updates."""
        self._backend.subscribe(on_node_change, on_vote_change)
    
    def unsubscribe(self) -> None:
        """Unsubscribe from real-time updates."""
        self._backend.unsubscribe()
    
    # --- Demo Data ---
    
    def seed_demo_data(self):
        """Populate with initial data if empty."""
        nodes = self._backend.load_nodes()
        if nodes:
            return  # Already has data
        
        existing_users = self._backend.list_users()
        if not existing_users:
            self._backend.create_user("User1")
            existing_users = ["User1"]
        
        logger.info("Seeding demo data...")
        root = self.add_node("Thesis Idea", users=existing_users)
        root_id = root['id']
        
        self.update_node(
            root_id, 
            metadata='# The Central Thesis\n\nThis is the core concept we are exploring.'
        )
        
        first_user = existing_users[0]
        n1 = self.add_node("Serious Games", parent_id=root_id, users=[first_user])
        n2 = self.add_node("Human-Computer Interaction", parent_id=root_id, users=[first_user])
        n3 = self.add_node("ML for Creativity", parent_id=root_id, users=[first_user])
        
        self.add_node("Generative Art Tools", parent_id=n3['id'], users=[first_user])
