"""
Edit Actions Module for Manual Node Editing

Executes graph mutations based on user interactions.
Translates preview states into concrete DataManager operations.
"""

import os
import uuid
from typing import Dict, Any, Optional

from src.data_manager import DataManager
from src.edit.constants import CHART_WIDTH, CHART_HEIGHT


class EditActions:
    """
    Handles execution of manual editing actions.
    
    Each method takes a preview state and commits the changes to the DataManager.
    """
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
    
    def create_node(self, position: tuple, label: str, parent_id: Optional[str], 
                   active_user: str) -> str:
        """
        Create a new node at the specified position.
        
        Args:
            position: (x, y) in normalized coordinates [0, 1]
            label: Node label text
            parent_id: Parent node ID for connection, or None
            active_user: User who created the node
            
        Returns:
            Created node ID
        """
        node_id = str(uuid.uuid4())
        
        # Create new node and save directly to its own file
        new_node = {
            'id': node_id,
            'label': label,
            'parent_id': parent_id,
            'description': ''
        }
        
        self.data_manager._save_node(node_id, new_node)
        
        # Set user vote (auto-vote interested)
        user_data = self.data_manager.load_user(active_user)
        if 'nodes' not in user_data:
            user_data['nodes'] = {}
        
        user_data['nodes'][node_id] = {
            'interested': True,
            'metadata': ''
        }
        
        self.data_manager.save_user(user_data)
        
        return node_id
    
    def create_intermediary_node(self, source_id: str, target_id: str, 
                                position: tuple, active_user: str) -> str:
        """
        Create an intermediary node on an edge.
        
        Edge format: source_id is the PARENT (upstream), target_id is the CHILD (downstream).
        The edge data comes as {source: parent, target: child} from the data manager.
        
        Original: parent(source_id) → child(target_id)  means child.parent_id = parent
        After:    parent → intermediary → child         means I.parent_id = parent, child.parent_id = I
        """
        # Generate label from source and target
        global_data = self.data_manager._load_global()
        nodes = global_data.get('nodes', {})
        
        source_label = nodes.get(source_id, {}).get('label', source_id[:8] if source_id else 'src')
        target_label = nodes.get(target_id, {}).get('label', target_id[:8] if target_id else 'tgt')
        
        label = f"{source_label}→{target_label}"
        
        # Create the intermediary node with source (parent) as its parent
        # This inserts I between parent and child: parent → I
        intermediary_id = self.create_node(position, label, source_id, active_user)
        
        # RELOAD global_data since create_node modified it
        global_data = self.data_manager._load_global()
        nodes = global_data.get('nodes', {})
        
        # Update the child (target) to point to intermediary instead of original parent
        # This completes: I → child  (by setting child.parent_id = I)
        if target_id in nodes:
            old_parent = nodes[target_id].get('parent_id')
            print(f"[create_intermediary_node] source={source_id[:8]}..., target={target_id[:8]}..., pos={position}")
            print(f"[create_intermediary_node] Created intermediary node: {intermediary_id[:8]}...")
            print(f"[create_intermediary_node] Updated target's parent: {old_parent[:8] if old_parent else 'None'}... -> {intermediary_id[:8]}...")
            nodes[target_id]['parent_id'] = intermediary_id
            self.data_manager._save_node(target_id, nodes[target_id])
        
        return intermediary_id
    
    def connect_nodes(self, source_id: str, target_id: str) -> bool:
        """Connect two existing nodes by making target the parent of source."""
        global_data = self.data_manager._load_global()
        nodes = global_data.get('nodes', {})
        
        if source_id not in nodes:
            return False
        
        nodes[source_id]['parent_id'] = target_id
        self.data_manager._save_node(source_id, nodes[source_id])
        
        return True
    
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all references to it."""
        global_data = self.data_manager._load_global()
        nodes = global_data.get('nodes', {})
        
        if node_id not in nodes:
            return False
        
        # Update any children that reference this node as parent
        for nid, node in nodes.items():
            if node.get('parent_id') == node_id:
                node['parent_id'] = None
                self.data_manager._save_node(nid, node)
        
        # Remove the node file
        self.data_manager._delete_node_file(node_id)
        
        # Remove from all user files
        users_dir = self.data_manager.data_dir
        if users_dir.exists():
            for filepath in users_dir.glob('*.json'):
                user_name = filepath.stem
                try:
                    user_data = self.data_manager.load_user(user_name)
                    if 'nodes' in user_data and node_id in user_data['nodes']:
                        del user_data['nodes'][node_id]
                        self.data_manager.save_user(user_data)
                except Exception:
                    pass
        
        return True
    
    def disconnect_nodes(self, source_id: str, target_id: str) -> bool:
        """Remove connection between two nodes (cut edge)."""
        global_data = self.data_manager._load_global()
        nodes = global_data.get('nodes', {})
        
        if source_id not in nodes:
            # Try swapping - maybe the edge direction is reversed
            if target_id in nodes and nodes[target_id].get('parent_id') == source_id:
                nodes[target_id]['parent_id'] = None
                self.data_manager._save_node(target_id, nodes[target_id])
                return True
            return False
        
        # Only disconnect if target is actually the parent
        actual_parent = nodes[source_id].get('parent_id')
        
        if actual_parent == target_id:
            nodes[source_id]['parent_id'] = None
            self.data_manager._save_node(source_id, nodes[source_id])
            return True
        
        # Try swapping if the edge direction is reversed
        if target_id in nodes and nodes[target_id].get('parent_id') == source_id:
            nodes[target_id]['parent_id'] = None
            self.data_manager._save_node(target_id, nodes[target_id])
            return True
        
        return False
    
    def update_node_position(self, node_id: str, position: tuple) -> bool:
        """Update a node's position in the layout (no-op, positions not persisted)."""
        # Positions are managed by ECharts force layout, not persisted
        return True
    
    def commit_preview_action(self, preview_state: Dict[str, Any], 
                             active_user: str,
                             chart_width: float = CHART_WIDTH,
                             chart_height: float = CHART_HEIGHT) -> Optional[str]:
        """Execute the action described by a preview state."""
        action = preview_state.get('action')
        
        def get_norm_position():
            # First try data_position (already in ECharts data coords)
            data_pos = preview_state.get('data_position')
            if data_pos:
                return (data_pos[0] / chart_width, data_pos[1] / chart_height)
            # Fallback to new_node_pos (legacy)
            pos_px = preview_state.get('new_node_pos', (0, 0))
            return (pos_px[0] / chart_width, pos_px[1] / chart_height)
        
        if action == 'create_node':
            pos_norm = get_norm_position()
            return self.create_node(pos_norm, 'New Idea', None, active_user)
        
        elif action == 'create_and_connect':
            pos_norm = get_norm_position()
            target_id = preview_state['target_id']
            return self.create_node(pos_norm, 'New Idea', target_id, active_user)
        
        elif action == 'create_intermediary':
            pos_norm = get_norm_position()
            source_id = preview_state['source_id']
            target_id = preview_state['target_id']
            return self.create_intermediary_node(source_id, target_id, pos_norm, active_user)
        
        elif action == 'delete_node':
            node_id = preview_state.get('target_node_id')
            if node_id:
                self.delete_node(node_id)
            return None
        
        elif action == 'make_intermediary':
            # Dragging an existing node onto an edge to make it an intermediary
            # Edge: source_id (parent) → target_id (child)
            # Result: source_id → dragging_id → target_id
            dragging_id = preview_state['dragging_node_id']
            source_id = preview_state['source_id']  # parent node
            target_id = preview_state['target_id']  # child node
            
            global_data = self.data_manager._load_global()
            nodes = global_data.get('nodes', {})
            
            if dragging_id in nodes:
                # Dragged node's parent becomes the original parent (source)
                nodes[dragging_id]['parent_id'] = source_id
                self.data_manager._save_node(dragging_id, nodes[dragging_id])
                # Child's parent becomes the dragged node
                if target_id in nodes:
                    print(f"[make_intermediary] Inserting {dragging_id[:8]}... between {source_id[:8]}... and {target_id[:8]}...")
                    nodes[target_id]['parent_id'] = dragging_id
                    self.data_manager._save_node(target_id, nodes[target_id])
                return dragging_id
        
        elif action == 'connect_nodes':
            source_id = preview_state['source_id']
            target_id = preview_state['target_id']
            self.connect_nodes(source_id, target_id)
            return source_id
        
        elif action == 'cut_edge':
            source_id = preview_state['source_id']
            target_id = preview_state['target_id']
            self.disconnect_nodes(source_id, target_id)
            return None
        
        elif action == 'move_node':
            node_id = preview_state['node_id']
            pos_px = preview_state['new_position']
            pos_norm = (pos_px[0] / chart_width, pos_px[1] / chart_height)
            self.update_node_position(node_id, pos_norm)
            return node_id
        
        return None
