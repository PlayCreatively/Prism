"""
Git-based Storage Backend for PRISM.

Implements the StorageBackend protocol using local file storage
with git for synchronization between collaborators.

This is the default/original storage mechanism.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class GitBackend:
    """
    Local file-based storage backend with git sync.
    
    Structure:
    - {project}/nodes/{uuid}.json: Node files
    - {project}/data/{user}.json: User state files
    - {project}/node_types/: Node type definitions
    - {project}/.git/: Git repository
    """
    
    def __init__(self, project_path: str, git_manager=None):
        """
        Initialize GitBackend for a project.
        
        Args:
            project_path: Path to the project folder
            git_manager: Optional GitManager instance for sync operations
        """
        self.project_path = Path(project_path)
        self.data_dir = self.project_path / "data"
        self.nodes_dir = self.project_path / "nodes"
        self.node_types_dir_path = self.project_path / "node_types"
        self._git_manager = git_manager
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.node_types_dir_path.mkdir(parents=True, exist_ok=True)
    
    # --- Backend Information ---
    
    @property
    def backend_type(self) -> str:
        """Return the backend type identifier."""
        return "git"
    
    @property
    def is_authenticated(self) -> bool:
        """Git backend doesn't require authentication."""
        return True  # Always "authenticated" locally
    
    @property
    def supports_realtime(self) -> bool:
        """Git backend doesn't support real-time sync."""
        return False
    
    @property
    def is_read_only(self) -> bool:
        """Git backend is never read-only for local user."""
        return False
    
    # --- Node Operations ---
    
    def load_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Load all nodes from individual JSON files."""
        nodes = {}
        for node_file in self.nodes_dir.glob("*.json"):
            try:
                with open(node_file, "r", encoding="utf-8") as f:
                    node_data = json.load(f)
                    node_id = node_data.get("id", node_file.stem)
                    
                    # Auto-migrate: add node_type if missing
                    if "node_type" not in node_data:
                        node_data["node_type"] = "default"
                        self.save_node(node_id, node_data)
                        logger.info(f"Migrated node {node_id}: added node_type=default")
                    
                    nodes[node_id] = node_data
            except Exception as e:
                logger.warning(f"Failed to load node file {node_file}: {e}")
        
        return nodes
    
    def save_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """Save a single node to its individual file."""
        node_path = self.nodes_dir / f"{node_id}.json"
        with open(node_path, "w", encoding="utf-8") as f:
            json.dump(node_data, f, indent=2, ensure_ascii=False)
    
    def delete_node(self, node_id: str) -> None:
        """Delete a node's individual file."""
        node_path = self.nodes_dir / f"{node_id}.json"
        if node_path.exists():
            node_path.unlink()
    
    # --- User Operations ---
    
    def list_users(self) -> List[str]:
        """Return list of user names based on files."""
        return [f.stem for f in self.data_dir.glob("*.json")]
    
    def load_user(self, user_id: str) -> Dict[str, Any]:
        """
        Load user file. Returns dict with 'nodes' as a Dictionary (UUID->State).
        Creates empty user file if it doesn't exist.
        """
        path = self.data_dir / f"{user_id}.json"
        schema = {"user_id": user_id, "nodes": {}}
        
        if not path.exists():
            # Init empty file if new user
            self.save_user(schema)
            return schema
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure user_id matches the filename
                data["user_id"] = user_id
                # Handle legacy list format
                if isinstance(data.get("nodes"), list):
                    data["nodes"] = {}
                return data
        except Exception:
            return schema
    
    def save_user(self, user_data: Dict[str, Any]) -> None:
        """Save user data to file."""
        user_id = user_data.get("user_id")
        if not user_id:
            raise ValueError("User data missing user_id")
        
        path = self.data_dir / f"{user_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
    
    def create_user(self, user_id: str) -> Dict[str, Any]:
        """Create a new user in the project."""
        user_data = {"user_id": user_id, "nodes": {}}
        self.save_user(user_data)
        return user_data
    
    # --- User-Node Relationship Operations ---
    
    def get_user_node_vote(self, user_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a user's vote/state for a specific node."""
        user_data = self.load_user(user_id)
        return user_data.get("nodes", {}).get(node_id)
    
    def set_user_node_vote(self, user_id: str, node_id: str, 
                           interested: Optional[bool] = None, 
                           metadata: Optional[str] = None) -> None:
        """Set a user's vote/state for a specific node."""
        user_data = self.load_user(user_id)
        if "nodes" not in user_data:
            user_data["nodes"] = {}
        
        # Get existing or create new
        curr = user_data["nodes"].get(node_id, {})
        
        # Apply updates
        if interested is not None:
            curr["interested"] = interested
        elif "interested" in curr and interested is None:
            # Explicitly remove vote if None passed
            del curr["interested"]
        
        if metadata is not None:
            if metadata.strip():
                curr["metadata"] = metadata
            else:
                curr.pop("metadata", None)
        
        # If empty, remove the entry entirely
        if not curr:
            user_data["nodes"].pop(node_id, None)
        else:
            user_data["nodes"][node_id] = curr
        
        self.save_user(user_data)
    
    def remove_user_node_vote(self, user_id: str, node_id: str) -> None:
        """Remove a user's vote/state for a node entirely."""
        user_data = self.load_user(user_id)
        if "nodes" in user_data and node_id in user_data["nodes"]:
            del user_data["nodes"][node_id]
            self.save_user(user_data)
    
    # --- Aggregated Data ---
    
    def get_node_with_votes(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node with aggregated vote information from all users."""
        nodes = self.load_nodes()
        node = nodes.get(node_id)
        if not node:
            return None
        
        users = self.list_users()
        interested = []
        rejected = []
        metadata_by_user = {}
        
        for user_id in users:
            user_data = self.load_user(user_id)
            user_node = user_data.get("nodes", {}).get(node_id)
            if user_node:
                if user_node.get("interested") is True:
                    interested.append(user_id)
                elif user_node.get("interested") is False:
                    rejected.append(user_id)
                if user_node.get("metadata"):
                    metadata_by_user[user_id] = user_node["metadata"]
        
        return {
            **node,
            "interested_users": interested,
            "rejected_users": rejected,
            "metadata_by_user": metadata_by_user,
            "metadata": next(iter(metadata_by_user.values()), "") if metadata_by_user else ""
        }
    
    def get_graph(self) -> Dict[str, Any]:
        """Get the full graph with all nodes and edges, including vote aggregation."""
        nodes = self.load_nodes()
        users = self.list_users()
        user_states = {u: self.load_user(u).get("nodes", {}) for u in users}
        
        result_nodes = []
        
        for nid, node in nodes.items():
            node_out = dict(node)
            
            # Ensure description exists
            if 'description' not in node_out:
                node_out['description'] = ""
            
            interested = []
            rejected = []
            combined_metadata = ""
            metadata_by_user = {}
            
            for user_id in users:
                user_node = user_states[user_id].get(nid)
                if user_node:
                    if user_node.get("interested") is True:
                        interested.append(user_id)
                    elif user_node.get("interested") is False:
                        rejected.append(user_id)
                    if user_node.get("metadata"):
                        metadata_by_user[user_id] = user_node["metadata"]
                        if not combined_metadata:
                            combined_metadata = user_node["metadata"]
            
            node_out['interested_users'] = interested
            node_out['rejected_users'] = rejected
            node_out['metadata'] = combined_metadata
            node_out['metadata_by_user'] = metadata_by_user
            
            result_nodes.append(node_out)
        
        # Build edges from parent_id relationships
        edges = []
        for n in result_nodes:
            pid = n.get('parent_id')
            if pid and pid in nodes:
                edges.append({'source': pid, 'target': n['id']})
        
        return {'nodes': result_nodes, 'edges': edges}
    
    # --- Node Encumbrance (Shared Data Editing Rules) ---
    
    def get_node_external_users(self, node_id: str, active_user_id: str) -> List[Dict[str, Any]]:
        """Get list of users (other than active user) who have data on this node."""
        users = self.list_users()
        external_users = []
        
        for user_id in users:
            if user_id == active_user_id:
                continue
            
            user_data = self.load_user(user_id)
            user_node = user_data.get("nodes", {}).get(node_id)
            
            if user_node:
                has_vote = user_node.get("interested") is not None
                external_users.append({
                    "user_id": user_id,
                    "has_vote": has_vote,
                    "interested": user_node.get("interested"),
                    "has_metadata": bool(user_node.get("metadata"))
                })
        
        return external_users
    
    def is_node_encumbered(self, node_id: str, active_user_id: str) -> bool:
        """Check if a node has external user data (other than active user)."""
        return len(self.get_node_external_users(node_id, active_user_id)) > 0
    
    # --- Synchronization ---
    
    def sync(self) -> Dict[str, Any]:
        """Pull latest changes from git remote."""
        if not self._git_manager:
            return {"success": True, "message": "No git manager configured"}
        
        try:
            result = self._git_manager.pull_rebase()
            if result is None:
                return {"success": True, "message": "No upstream configured yet"}
            return {"success": True, "message": "Synced successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def push(self) -> Dict[str, Any]:
        """Push local changes to git remote."""
        if not self._git_manager:
            return {"success": True, "message": "No git manager configured"}
        
        try:
            self._git_manager.add_all()
            self._git_manager.commit("Update from PRISM")
            self._git_manager.push()
            return {"success": True, "message": "Pushed successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def has_unpushed_changes(self) -> bool:
        """Check if there are local changes that haven't been pushed."""
        if not self._git_manager:
            return False
        
        try:
            # Check git status
            import subprocess
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=str(self.project_path),
                capture_output=True,
                text=True
            )
            return bool(result.stdout.strip())
        except Exception:
            return False
    
    # --- Real-time Subscriptions (no-op for git) ---
    
    def subscribe(self, 
                  on_node_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
                  on_vote_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None) -> None:
        """No-op for git backend (no real-time support)."""
        pass
    
    def unsubscribe(self) -> None:
        """No-op for git backend."""
        pass
    
    # --- Node Types ---
    
    def get_node_types_dir(self) -> Optional[str]:
        """Get the path to the node_types directory."""
        return str(self.node_types_dir_path)
    
    # --- Utility Methods ---
    
    def cleanup_orphan_nodes(self) -> int:
        """
        Remove nodes that have zero votes from any user.
        
        Returns:
            Number of nodes removed.
        """
        nodes = self.load_nodes()
        
        if not nodes:
            return 0
        
        users = self.list_users()
        if not users:
            return 0
        
        # Collect all node IDs that have at least one user vote
        voted_nodes = set()
        for user_id in users:
            user_data = self.load_user(user_id)
            user_nodes = user_data.get("nodes", {})
            voted_nodes.update(user_nodes.keys())
        
        # Find orphans (nodes with no votes)
        orphan_ids = [nid for nid in nodes.keys() if nid not in voted_nodes]
        
        if not orphan_ids:
            return 0
        
        # Remove orphans
        for nid in orphan_ids:
            self.delete_node(nid)
            logger.info(f"Removed orphan node: {nid}")
        
        # Update parent_id references
        remaining_nodes = self.load_nodes()
        for nid, node in remaining_nodes.items():
            if node.get("parent_id") in orphan_ids:
                node["parent_id"] = None
                self.save_node(nid, node)
        
        return len(orphan_ids)
