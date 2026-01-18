"""
UI Components for PRISM - NiceGUI state generation helpers.

This module provides functions to convert the internal node/edge representation
into a UI-friendly structure for NiceGUI, including:
- color mapping based on interested users (RGB model)
- edge styling (consensus path highlighting)
- floating context window computation (parent/children/siblings within radius)

Public functions:
- color_for_interested_users(interested_users) -> str (hex color)
- node_to_ui(node) -> dict (ui-ready node)
- edge_to_ui(edge, nodes_by_id) -> dict (ui-ready edge)
- build_ui_state(nodes, edges, context_radius=1) -> dict with keys:
    - nodes: list of ui nodes
    - edges: list of ui edges
    - context_windows: dict mapping node_id -> list of node_ids in that context
"""

from typing import List, Dict, Iterable, Set, Optional
from src.utils import color_from_users, get_visible_users


# Default colors
_DEFAULT_NODE_COLOR = '#cccccc'  # fallback gray for unknown/missing lists
_STANDARD_EDGE_COLOR = '#888888'  # thin gray
_CONSENSUS_EDGE_COLOR = '#ffd700' # golden glow for consensus path


def _normalize_users(interested_users: Optional[Iterable[str]]) -> Set[str]:
    if not interested_users:
        return set()
    return {u.strip() for u in interested_users if isinstance(u, str) and u.strip()}


def color_for_interested_users(interested_users: Optional[Iterable[str]], visible_users: Optional[List[str]] = None) -> str:
    """
    Return a hex color string representing the combination of interested users.
    
    Uses the dynamic color system from utils.py that assigns colors based on
    hue rotation through the visible users list. When all visible users are
    interested, the color approaches white.

    If no users are interested, returns a gray.
    """
    users_list = list(_normalize_users(interested_users))
    return color_from_users(users_list, visible_users=visible_users)


def node_to_ui(node: Dict) -> Dict:
    """
    Convert an internal node dict to a UI node dict.

    Expected input node keys (partial):
      - id (str)
      - label (str)
      - parent_id (str or None)
      - status (str) e.g., 'accepted', 'rejected', 'pending' (optional)
      - metadata (str) (optional)
      - interested_users (Iterable[str]) (optional)

    Output keys:
      - id, label, color, status, metadata, parent_id, ui (style info)
    """
    node_id = node.get('id')
    label = node.get('label', '')
    parent_id = node.get('parent_id')
    status = node.get('status')
    metadata = node.get('metadata', '')
    interested = node.get('interested_users') or node.get('interested') or []

    color = color_for_interested_users(interested)

    # Size/radius logic: accepted nodes slightly larger than pending/rejected
    size = 36
    if status == 'accepted':
        size = 44
    elif status == 'rejected':
        size = 28
    elif status == 'pending':
        size = 36

    ui = {
        'color': color,
        'size': size,
        # A convenience flag for "full consensus" white nodes
        'is_full_consensus': color.lower() == '#ffffff'
    }

    return {
        'id': node_id,
        'label': label,
        'parent_id': parent_id,
        'status': status,
        'metadata': metadata,
        'interested_users': list(_normalize_users(interested)),
        'ui': ui
    }


def edge_to_ui(edge: Dict, nodes_by_id: Dict[str, Dict]) -> Dict:
    """
    Convert an internal edge dict to a UI edge dict.

    Expected input edge keys:
      - source (str) node id
      - target (str) node id

    The consensus path (thick glowing line) is applied when both endpoints are full consensus (white).
    """
    source = edge.get('source')
    target = edge.get('target')

    # Default style
    color = _STANDARD_EDGE_COLOR
    width = 1
    glow = False

    src_node = nodes_by_id.get(source)
    tgt_node = nodes_by_id.get(target)

    if src_node and tgt_node:
        src_consensus = src_node.get('ui', {}).get('is_full_consensus', False)
        tgt_consensus = tgt_node.get('ui', {}).get('is_full_consensus', False)
        if src_consensus and tgt_consensus:
            color = _CONSENSUS_EDGE_COLOR
            width = 4
            glow = True

    return {
        'source': source,
        'target': target,
        'color': color,
        'width': width,
        'glow': glow
    }


def _build_parent_children_index(nodes: List[Dict]) -> Dict[str, Dict[str, List[str]]]:
    """
    Build fast lookup indices for parent->children and id->parent.
    Returns dict with keys:
      - children: {parent_id: [child_id, ...]}
      - parent: {node_id: parent_id}
    """
    children = {}
    parent = {}
    for n in nodes:
        nid = n.get('id')
        pid = n.get('parent_id') or None
        parent[nid] = pid
        if pid is not None:
            children.setdefault(pid, []).append(nid)
    return {'children': children, 'parent': parent}


def compute_context_window(node_id: str,
                           nodes_by_id: Dict[str, Dict],
                           parent_index: Dict[str, Optional[str]],
                           children_index: Dict[str, List[str]],
                           radius: int = 1) -> List[str]:
    """
    Compute a floating context window (list of node ids) around a node.
    The window includes:
      - the node itself
      - its parent (if any)
      - its children (direct)
      - its siblings (other children of the same parent)
      - optionally, ancestors/descendants up to given radius
    The radius controls how many levels up/down are included. radius=1 includes parent+children.

    Returns a list of unique node ids (order is not important).
    """
    if node_id not in nodes_by_id:
        return []

    collected = set()
    frontier_up = {node_id}
    frontier_down = {node_id}

    # Include node itself
    collected.add(node_id)

    # Upwards traversal (ancestors)
    for _ in range(radius):
        new_frontier = set()
        for nid in frontier_up:
            parent = parent_index.get(nid)
            if parent and parent not in collected:
                collected.add(parent)
                new_frontier.add(parent)
                # siblings:
                siblings = children_index.get(parent, [])
                for s in siblings:
                    if s not in collected:
                        collected.add(s)
        frontier_up = new_frontier

    # Downwards traversal (descendants)
    for _ in range(radius):
        new_frontier = set()
        for nid in frontier_down:
            children = children_index.get(nid, [])
            for c in children:
                if c not in collected:
                    collected.add(c)
                    new_frontier.add(c)
        frontier_down = new_frontier

    return list(collected)


def build_ui_state(nodes: List[Dict],
                   edges: List[Dict],
                   context_radius: int = 1) -> Dict:
    """
    Build the complete UI state needed by the NiceGUI front-end.

    Returns:
      {
        'nodes': [ui_node, ...],
        'edges': [ui_edge, ...],
        'context_windows': { node_id: [node_id, parent_id, child_id, ...], ... }
      }
    """
    # First convert nodes to ui nodes
    ui_nodes = [node_to_ui(n) for n in nodes]
    nodes_by_id = {n['id']: n for n in ui_nodes}

    # Build indices
    indices = _build_parent_children_index(nodes)
    children_index = indices['children']
    parent_index = indices['parent']

    # Build context windows
    context_windows = {}
    for nid in nodes_by_id.keys():
        context = compute_context_window(nid, nodes_by_id, parent_index, children_index, radius=context_radius)
        context_windows[nid] = context

    # Convert edges to ui edges
    ui_edges = [edge_to_ui(e, nodes_by_id) for e in edges]

    return {
        'nodes': ui_nodes,
        'edges': ui_edges,
        'context_windows': context_windows
    }


# Module can be used stand-alone for simple manual tests
if __name__ == '__main__':
    sample_nodes = [
        {'id': 'root', 'label': 'Root', 'parent_id': None, 'status': 'accepted', 'interested_users': ['Alex', 'Sasha', 'Alison']},
        {'id': 'a', 'label': 'Child A', 'parent_id': 'root', 'status': 'pending', 'interested_users': ['Alex']},
        {'id': 'b', 'label': 'Child B', 'parent_id': 'root', 'status': 'accepted', 'interested_users': ['Sasha', 'Alison']}
    ]
    sample_edges = [{'source': 'root', 'target': 'a'}, {'source': 'root', 'target': 'b'}]
    import json
    print(json.dumps(build_ui_state(sample_nodes, sample_edges), indent=2))
