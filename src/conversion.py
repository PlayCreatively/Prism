from typing import Dict, Any, List, Optional
import json

def build_label_tree(nodes: List[Dict[str, Any]], root_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recursively builds a tree structure from a flat list of nodes.
    UUIDs are STRIPPED. Only Labels and Structure remain.
    
    Format:
    [
      {
        "label": "Root Name",
        "children": [
            { "label": "Child Name", "children": [] }
        ]
      }
    ]
    """
    # 1. Index by parent_id
    children_map = {}
    node_map = {}
    
    for n in nodes:
        node_map[n['id']] = n
        pid = n.get('parent_id')
        if pid not in children_map:
            children_map[pid] = []
        children_map[pid].append(n)

    # 2. Find roots
    # If root_id provided, start there. Else find nodes with no parent (or parent not in list)
    roots = []
    if root_id:
        if root_id in node_map:
            roots = [node_map[root_id]]
    else:
        # Nodes where parent_id is None OR parent_id points to missing node
        for n in nodes:
            pid = n.get('parent_id')
            if not pid or pid not in node_map:
                roots.append(n)

    # 3. Recursive Builder
    def _recruit(current_node):
        return {
            "label": current_node.get('label', 'Untitled'),
            "children": [
                _recruit(child) 
                for child in children_map.get(current_node['id'], [])
            ]
        }

    return [_recruit(r) for r in roots]

def import_label_tree(data_manager, tree_list: List[Dict[str, Any]], parent_id: Optional[str] = None):
    """
    Imports a label tree into the DataManager.
    Generates NEW UUIDs for every node.
    """
    for node in tree_list:
        label = node.get('label')
        children = node.get('children', [])
        
        # Create Node
        new_node = data_manager.add_node(label=label, parent_id=parent_id)
        new_id = new_node['id']
        
        # Recurse
        if children:
            import_label_tree(data_manager, children, parent_id=new_id)

def export_project_to_json(data_manager) -> str:
    """
    Full export of the Global Graph Structure as a portable JSON string.
    """
    graph = data_manager.get_graph()
    nodes = graph.get('nodes', [])
    tree = build_label_tree(nodes)
    return json.dumps(tree, indent=2)
