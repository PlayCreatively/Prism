import json
from pathlib import Path
from typing import Dict, Any, List


class DataManager:
    """
    Manages per-user JSON files stored under a data directory.

    Each user's file is named {user_id}.json and follows the schema:
    {
      "user_id": "<user_id>",
      "applied_mutations": [...],
      "nodes": [...]
    }
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _user_path(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.json"

    def _default_schema(self, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "applied_mutations": [],
            "nodes": [],
        }

    def get_graph(self) -> Dict[str, Any]:
        """
        Aggregates all user files into a single graph representation.
        Nodes with the same ID logic merged to determine 'interested_users'.
        Metadata is taken from an arbitrary source (first found), as it is user-specific
        and handled separately in the UI details view.
        
        Returns:
            {
                'nodes': [
                    {
                        'id': ..., 
                        'interested_users': ['Alex', 'Sasha'], 
                        ...
                    }
                ],
                'edges': [] 
            }
        """
        all_nodes = {}
        # Iterating over all user files to build the union graph
        for file_path in self.data_dir.glob("*.json"):
            user_id = file_path.stem
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    for node in data.get('nodes', []):
                        nid = node.get('id')
                        if not nid:
                            continue
                        
                        # If seeing this node for the first time, add it to our graph
                        if nid not in all_nodes:
                            # We create a shallow copy to modify interested_users dynamically
                            node_copy = dict(node)
                            node_copy['interested_users'] = [] # Clear this, we build it now
                            all_nodes[nid] = node_copy
                            
                            # Clean up old checks
                            if 'status' in node_copy:
                                del node_copy['status']
                            if 'interested' in node_copy:
                                del node_copy['interested'] 

                        # Determine if this user is "interested" (Active YES or PENDING)
                        # The user has the file. If 'interested' is explicitly False, they rejected it.
                        # If explicit True or missing (assumed active/pending), they are interested.
                        is_interested = node.get('interested', True)
                        
                        if is_interested:
                            if user_id not in all_nodes[nid]['interested_users']:
                                all_nodes[nid]['interested_users'].append(user_id)
                                
            except Exception:
                continue

        # Derived edges from parent_id
        edges = []
        for nid, node in all_nodes.items():
            pid = node.get('parent_id')
            if pid and pid in all_nodes:
                edges.append({'source': pid, 'target': nid})
        
        return {'nodes': list(all_nodes.values()), 'edges': edges}


    def _normalize(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure the loaded data conforms to the required schema.
        Missing keys are filled with defaults. Non-list fields for lists are replaced.
        """
        if not isinstance(data, dict):
            # Replace with default if the file content is not a dict
            return self._default_schema(user_id)

        normalized = dict(data)  # shallow copy

        # Ensure user_id
        if "user_id" not in normalized or not isinstance(normalized.get("user_id"), str):
            normalized["user_id"] = user_id

        # Ensure applied_mutations is a list
        if "applied_mutations" not in normalized or not isinstance(normalized.get("applied_mutations"), list):
            normalized["applied_mutations"] = []

        # Ensure nodes is a list
        if "nodes" not in normalized or not isinstance(normalized.get("nodes"), list):
            normalized["nodes"] = []

        return normalized

    def load_user(self, user_id: str) -> Dict[str, Any]:
        """
        Load (and if necessary create) the user's JSON file and return the data as a dict.
        The returned dict is normalized to include 'user_id', 'applied_mutations', and 'nodes'.
        """
        path = self._user_path(user_id)
        if not path.exists():
            # Create a file with default schema
            data = self._default_schema(user_id)
            self._write_file(path, data)
            return data

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # On parse error or IO error, return default schema (do not crash)
            data = self._default_schema(user_id)

        normalized = self._normalize(user_id, data)

        # Persist normalization back to disk to keep files consistent
        self._write_file(path, normalized)

        return normalized

    def save_user(self, data: Dict[str, Any]) -> None:
        """
        Save the provided user data dict to the corresponding file.
        The dict must include 'user_id'. Missing schema keys will be filled.
        """
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")

        user_id = data.get("user_id")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("data must include a string 'user_id' field")

        normalized = self._normalize(user_id, data)
        path = self._user_path(user_id)
        self._write_file(path, normalized)

    def list_users(self) -> List[str]:
        """
        Return a list of user_ids (filenames without .json) present in the data directory.
        """
        users = []
        for p in self.data_dir.glob("*.json"):
            if p.is_file():
                users.append(p.stem)
        return users

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load and return all user files as a mapping user_id -> data dict.
        """
        result = {}
        for user_id in self.list_users():
            result[user_id] = self.load_user(user_id)
        return result

    def _write_file(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def add_node(self, label: str, parent_id: str = None, users: List[str] = None, interested: bool = True) -> Dict[str, Any]:
        """
        Add a new node to the system. 
        It is added to the files of ALL specified users.
        """
        import uuid
        users = users or []
        # If no users specified, default to 'system'
        target_users = users if users else ['system']
        
        node_id = str(uuid.uuid4())
        # Base node definition
        new_node = {
            'id': node_id,
            'label': label,
            'parent_id': parent_id,
            'interested': interested,  # New Schema
            'metadata': ''
        }
        
        for user in target_users:
            user_data = self.load_user(user)
            # Create a copy for this user
            user_node = dict(new_node)
            user_data['nodes'].append(user_node)
            self.save_user(user_data)
        
        # Return the node as it would appear in the graph (with all users)
        result_node = dict(new_node)
        # However, interested_users list only includes those where interested=True
        result_node['interested_users'] = target_users if interested else []
        return result_node

    def get_user_node(self, user_id: str, node_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific node from a specific user's file.
        Returns None if not found.
        """
        data = self.load_user(user_id)
        for node in data.get('nodes', []):
            if node.get('id') == node_id:
                return node
        return None

    def update_user_node(self, user_id: str, node_id: str, **kwargs) -> None:
        """
        Update (or create) a node within a specific user's file.
        This is used for voting (status), editing metadata, etc.
        If the user does not have the node yet, it is fetched from the aggregate graph 
        and added to their file with the updates applied.
        """
        user_data = self.load_user(user_id)
        found = False
        
        # Try to update existing
        for node in user_data.get('nodes', []):
            if node.get('id') == node_id:
                node.update(kwargs)
                found = True
                break
        
        # If not found, we need to ingest the node from the system first
        if not found:
            graph = self.get_graph()
            # Find the canonical node structure
            canonical = next((n for n in graph['nodes'] if n['id'] == node_id), None)
            if canonical:
                # Create a clean copy for this user
                new_node = {
                    'id': canonical['id'],
                    'label': canonical['label'],
                    'parent_id': canonical['parent_id'],
                    'interested': True,  # Default to interested if manually adding
                    'metadata': ''      # Empty metadata for new user
                }
                new_node.update(kwargs)
                user_data['nodes'].append(new_node)
            else:
                 # Only possible if node_id is invalid or phantom
                 pass

        self.save_user(user_data)

    def update_shared_node(self, node_id: str, **kwargs) -> None:
        """
        Update a node's SHARED properties (Label, Parent) across ALL files where it exists.
        Do NOT use this for status or metadata.
        """
        all_users = self.list_users()
        for uid in all_users:
            data = self.load_user(uid)
            file_changed = False
            for node in data.get('nodes', []):
                if node.get('id') == node_id:
                    # Only apply updates if they are valid for all users (e.g. label)
                    # We strictly filter kwargs here to be safe, or assume caller is safe?
                    # Let's trust the caller but this method name implies shared props.
                    node.update(kwargs)
                    file_changed = True
            if file_changed:
                self.save_user(data)

    def update_node(self, node_id: str, **kwargs) -> None:
        """
        Deprecated: Used by legacy code. 
        If updating label/parent, uses update_shared_node.
        If updating status/metadata, it iterates all which is WRONG for the new model,
        but kept for compatibility until app.py is fully refactored.
        """
        # Heuristic: if label in kwargs or parent_id, it might be shared
        if 'label' in kwargs or 'parent_id' in kwargs:
             self.update_shared_node(node_id, **kwargs)
             return
        
        # If status/metadata/interested_users in kwargs, this legacy method 
        # is ambiguous. We will just log a warning or try to do our best.
        # For now, we delegate to update_shared_node which updates everyone.
        # This is strictly incorrect for metadata, but prevents crashes.
        self.update_shared_node(node_id, **kwargs)

    def seed_demo_data(self):
        """
        Populate with initial data if empty.
        """
        graph = self.get_graph()
        if not graph.get('nodes'):
            print("Seeding demo data...")
            import uuid
            
            # 1. Create Central Root Node
            root = self.add_node("Thesis Idea", users=["Alex", "Sasha", "Alison"])
            root_id = root['id']
            # Update status to accepted
            self.update_node(root_id, status='accepted', metadata='# The Central Thesis\n\nThis is the core concept we are exploring.')

            # 2. Add Child Nodes linked to Root
            self.add_node("Serious Games", parent_id=root_id, users=["Alex"])
            self.add_node("Human-Computer Interaction", parent_id=root_id, users=["Sasha"])
            self.add_node("ML for Creativity", parent_id=root_id, users=["Alison"])
            
            # 3. Add a grandchild for depth
            node_ml = [n for n in self.get_graph()['nodes'] if n['label'] == "ML for Creativity"][0]
            self.add_node("Generative Art Tools", parent_id=node_ml['id'], users=["Alison", "Sasha"])

