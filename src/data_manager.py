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
    - db/global.json: Source of truth for Nodes (UUID, Label, Parent).
    - db/data/{user}.json: User state (UUID -> {Interested, Metadata}).
    
    The 'get_graph' method performs a join between global structure and user files.
    """

    def __init__(self, data_dir: str = "db/data"):
        self.data_dir = Path(data_dir)
        self.global_path = self.data_dir.parent / "global.json"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    # --- File I/O Helpers ---

    def _load_global(self) -> Dict[str, Any]:
        """Load the global graph structure."""
        if not self.global_path.exists():
            return {"nodes": {}}
        try:
            with open(self.global_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"nodes": {}}

    def _save_global(self, data: Dict[str, Any]) -> None:
        """Save the global graph structure."""
        with open(self.global_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_user(self, user_id: str) -> Dict[str, Any]:
        """
        Load user file. Returns dict with 'nodes' as a Dictionary (UUID->State).
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

    def add_node(self, label: str, parent_id: str = None, users: List[str] = None, interested: bool = True) -> Dict[str, Any]:
        """
        Adds node to Global graph.
        Optionally initializes user states (e.g. setting them as interested).
        """
        # 1. Update Global
        g_data = self._load_global()
        node_id = str(uuid.uuid4())
        
        new_node_global = {
            "id": node_id,
            "label": label,
            "parent_id": parent_id
        }
        g_data["nodes"][node_id] = new_node_global
        self._save_global(g_data)
        
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
        Updates global structure (Label, Parent).
        """
        g_data = self._load_global()
        if node_id in g_data["nodes"]:
            changed = False
            if "label" in kwargs:
                g_data["nodes"][node_id]["label"] = kwargs["label"]
                changed = True
            if "parent_id" in kwargs:
                g_data["nodes"][node_id]["parent_id"] = kwargs["parent_id"]
                changed = True
            
            if changed:
                self._save_global(g_data)

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
            # Create Users if not exist
            for u in ["Alex", "Sasha", "Alison"]:
                self.load_user(u) # creates file
                
            print("Seeding demo data...")
            root = self.add_node("Thesis Idea", users=["Alex", "Sasha", "Alison"])
            
            root_id = root['id']
            # Update root metadata for all
            self.update_node(root_id, metadata='# The Central Thesis\n\nThis is the core concept we are exploring.')

            n1 = self.add_node("Serious Games", parent_id=root_id, users=["Alex"])
            n2 = self.add_node("Human-Computer Interaction", parent_id=root_id, users=["Sasha"])
            n3 = self.add_node("ML for Creativity", parent_id=root_id, users=["Alison"])
            
            self.add_node("Generative Art Tools", parent_id=n3['id'], users=["Alison", "Sasha"])

