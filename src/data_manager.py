import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger(__name__)

class DataManager:
    """
    Manages global graph structure and per-user state files.
    
    Structure:
    - db/nodes/*: Source of truth for Nodes (UUID, Label, Parent).
    - db/data/{user}.json: User state (UUID -> {Interested, Metadata}).
    
    The 'get_graph' method performs a join between global structure and user files.
    """

    def __init__(self, data_dir: str = "db/data"):
        self.data_dir = Path(data_dir)
        self.nodes_dir = self.data_dir.parent / "nodes"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        
    # --- File I/O Helpers ---

    def _load_global(self) -> Dict[str, Any]:
        """
        Load the global graph structure.
        Nodes are loaded from individual files in db/nodes/.
        """
        # Load nodes from individual files
        nodes = {}
        for node_file in self.nodes_dir.glob("*.json"):
            try:
                with open(node_file, "r", encoding="utf-8") as f:
                    node_data = json.load(f)
                    node_id = node_data.get("id", node_file.stem)
                    nodes[node_id] = node_data
            except Exception as e:
                logger.warning(f"Failed to load node file {node_file}: {e}")
        
        return {"nodes": nodes}

    def _save_global(self, data: Dict[str, Any]) -> None:
        """
        Save the global graph structure.
        Nodes are saved to individual files in db/nodes/.
        """
        nodes = data.get("nodes", {})
        
        # Save each node to its own file
        for node_id, node_data in nodes.items():
            self._save_node(node_id, node_data)
    
    def _save_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """Save a single node to its individual file."""
        node_path = self.nodes_dir / f"{node_id}.json"
        with open(node_path, "w", encoding="utf-8") as f:
            json.dump(node_data, f, indent=2, ensure_ascii=False)
    
    def _delete_node_file(self, node_id: str) -> None:
        """Delete a node's individual file."""
        node_path = self.nodes_dir / f"{node_id}.json"
        if node_path.exists():
            node_path.unlink()

    def load_user(self, user_id: str) -> Dict[str, Any]:
        """
        Load user file. Returns dict with 'nodes' as a Dictionary (UUID->State).
        The user_id field is always set to match the requested user_id (filename).
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
                # CRITICAL: Ensure user_id matches the filename, not what's stored inside
                # This prevents bugs when files are copied/renamed
                data["user_id"] = user_id
                # Helper: If 'nodes' is a list (legacy leftover), handle gracefully-ish
                if isinstance(data.get("nodes"), list):
                    # We can't easily auto-fix on read without logic, so let's assume
                    # the dict is the source of truth, or return empty if corrupted.
                    data["nodes"] = {} 
                return data
        except Exception:
            return schema

    def save_user(self, data: Dict[str, Any]) -> None:
        """Save user data to file."""
        user_id = data.get("user_id")
        if not user_id:
            raise ValueError("User data missing user_id")
        
        path = self.data_dir / f"{user_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_users(self) -> List[str]:
        """Return list of user names based on files."""
        return [f.stem for f in self.data_dir.glob("*.json")]

    def cleanup_orphan_nodes(self) -> int:
        """
        Remove nodes that have zero votes from any user.
        
        A node is considered an orphan if no user has an entry for it
        (neither interested nor rejected).
        
        Returns:
            Number of nodes removed.
        """
        g_data = self._load_global()
        g_nodes = g_data.get("nodes", {})
        
        if not g_nodes:
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
        orphan_ids = [nid for nid in g_nodes.keys() if nid not in voted_nodes]
        
        if not orphan_ids:
            return 0
        
        # Remove orphans - delete individual node files
        for nid in orphan_ids:
            self._delete_node_file(nid)
            del g_nodes[nid]
            logger.info(f"Removed orphan node: {nid}")
        
        # Also update parent_id references for any nodes that pointed to removed nodes
        for nid, node in g_nodes.items():
            if node.get("parent_id") in orphan_ids:
                node["parent_id"] = None
                self._save_node(nid, node)  # Save updated parent reference
        
        # Save updated metadata (orphan removal doesn't need full _save_global)
        return len(orphan_ids)

    # --- Core Graph Logic ---

    def get_graph(self) -> Dict[str, Any]:
        """
        Aggregates global structure with all user states.
        Returns format compatible with UI:
        {
            'nodes': [{id, label, parent_id, interested_users, rejected_users, metadata...}, ...],
            'edges': [{source, target}, ...]
        }
        """
        g_data = self._load_global()
        g_nodes = g_data.get("nodes", {}) # Dict: uuid -> {id, label, parent_id}
        
        users = self.list_users()
        user_states = {u: self.load_user(u).get("nodes", {}) for u in users}
        
        result_nodes = []
        
        for nid, g_node in g_nodes.items():
            # Create the enriched node object
            # We copy g_node to avoid mutating the cache
            node_out = dict(g_node)
            
            # Ensure description exists for backward compatibility
            if 'description' not in node_out:
                node_out['description'] = ""
            
            interested = []
            rejected = []
            
            # Metadata merge strategy: First user with content wins, or empty.
            combined_metadata = ""
            
            for u in users:
                u_node = user_states[u].get(nid)
                if u_node:
                    # Explicit state
                    if u_node.get("interested", True):
                        interested.append(u)
                    else:
                        rejected.append(u)
                    
                    # Capture metadata if strictly present
                    if not combined_metadata and u_node.get("metadata"):
                        combined_metadata = u_node.get("metadata")
                else:
                    # Implied state? 
                    # If user has no record, they are NOT in interested list yet (Pending).
                    # They are NOT in rejected list.
                    pass
            
            node_out['interested_users'] = interested
            node_out['rejected_users'] = rejected
            node_out['metadata'] = combined_metadata
            
            result_nodes.append(node_out)

        # Build Edges
        edges = []
        for n in result_nodes:
            pid = n.get('parent_id')
            if pid and pid in g_nodes:
                 edges.append({'source': pid, 'target': n['id']})
                 
        return {'nodes': result_nodes, 'edges': edges}

    # --- Write Operations ---

    def add_node(self, label: str, parent_id: str = None, users: List[str] = None, interested: bool = True, description: str = "") -> Dict[str, Any]:
        """
        Adds node to Global graph.
        Optionally initializes user states (e.g. setting them as interested).
        """
        # 1. Create and save node directly to its own file
        node_id = str(uuid.uuid4())
        
        new_node_global = {
            "id": node_id,
            "label": label,
            "parent_id": parent_id,
            "description": description
        }
        self._save_node(node_id, new_node_global)
        
        # 2. Update Users
        target_users = users if users else []
        for u in target_users:
            u_data = self.load_user(u)
            if "nodes" not in u_data: u_data["nodes"] = {}
            
            # Create entry
            u_data["nodes"][node_id] = {
                "interested": interested,
                "metadata": ""
            }
            self.save_user(u_data)
            
        # Return format similar to get_graph node for immediate UI use
        return {
            **new_node_global,
            "interested_users": target_users if interested else [],
            "rejected_users": target_users if not interested else [],
            "metadata": ""
        }

    def update_user_node(self, user_id: str, node_id: str, **kwargs) -> None:
        """
        Updates a specific user's state for a node (e.g. status, metadata).
        """
        u_data = self.load_user(user_id)
        if "nodes" not in u_data: u_data["nodes"] = {}
        
        # Get existing or create default
        # If default is created, it means user is interacting with a pending node
        curr = u_data["nodes"].get(node_id, {"interested": True, "metadata": ""})
        
        # Apply updates
        if "interested" in kwargs:
            curr["interested"] = kwargs["interested"]
        if "metadata" in kwargs:
            curr["metadata"] = kwargs["metadata"]
            
        u_data["nodes"][node_id] = curr
        self.save_user(u_data)

    def update_shared_node(self, node_id: str, **kwargs) -> None:
        """
        Updates global structure (Label, Parent, Description).
        """
        g_data = self._load_global()
        if node_id in g_data["nodes"]:
            node = g_data["nodes"][node_id]
            changed = False
            if "label" in kwargs:
                node["label"] = kwargs["label"]
                changed = True
            if "parent_id" in kwargs:
                node["parent_id"] = kwargs["parent_id"]
                changed = True
            if "description" in kwargs:
                node["description"] = kwargs["description"]
                changed = True
            
            if changed:
                self._save_node(node_id, node)

    def remove_user_node(self, user_id: str, node_id: str) -> None:
        """
        Removes user's specific state for a node (Reset to Pending).
        Does NOT delete the node from Global.
        """
        u_data = self.load_user(user_id)
        if "nodes" in u_data and node_id in u_data["nodes"]:
            del u_data["nodes"][node_id]
            self.save_user(u_data)

    def update_node(self, node_id: str, **kwargs) -> None:
        """
        Legacy/Convenience method. Routes updates to Global or User files based on keys.
        WARNING: If updating status/metadata without a specific user context, 
        this might be ambiguous.
        Legacy behavior was 'apply to all'. We will try to preserve that if possible.
        """
        # Shared props
        shared_keys = ['label', 'parent_id']
        if any(k in kwargs for k in shared_keys):
            self.update_shared_node(node_id, **kwargs)
            
        # User props (interested, metadata)
        # Check for legacy 'status' -> 'interested'
        if 'status' in kwargs:
            val = kwargs.pop('status')
            kwargs['interested'] = (val == 'accepted')
            
        user_keys = ['interested', 'metadata']
        if any(k in kwargs for k in user_keys):
             for u in self.list_users():
                # We update all users, mimicking old 'broadcast' behavior
                self.update_user_node(u, node_id, **kwargs)

    def get_user_node(self, user_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the raw user state dict or None.
        Enriched with global data for convenience? 
        Legacy returned enriched.
        """
        u_data = self.load_user(user_id)
        u_node = u_data.get("nodes", {}).get(node_id)
        
        if not u_node:
            return None
            
        # Enrich with global lookup
        g_data = self._load_global()
        g_node = g_data["nodes"].get(node_id)
        if g_node:
            # Merge: Global props + User props
            return {**g_node, **u_node}
        return u_node

    def seed_demo_data(self):
        """Populate with initial data if empty."""
        g_nodes = self._load_global().get("nodes", {})
        if not g_nodes:
            # Get existing users or create a default user
            existing_users = self.list_users()
            if not existing_users:
                # Create a default user if none exist
                self.load_user("User1")  # creates file
                existing_users = ["User1"]
                
            print("Seeding demo data...")
            root = self.add_node("Thesis Idea", users=existing_users)
            
            root_id = root['id']
            # Update root metadata for all
            self.update_node(root_id, metadata='# The Central Thesis\n\nThis is the core concept we are exploring.')

            # Create child nodes - assign to first user if only one exists
            first_user = existing_users[0] if existing_users else None
            if first_user:
                n1 = self.add_node("Serious Games", parent_id=root_id, users=[first_user])
                n2 = self.add_node("Human-Computer Interaction", parent_id=root_id, users=[first_user])
                n3 = self.add_node("ML for Creativity", parent_id=root_id, users=[first_user])
                
                self.add_node("Generative Art Tools", parent_id=n3['id'], users=[first_user])

