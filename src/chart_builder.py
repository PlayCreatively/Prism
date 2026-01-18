"""
ECharts options builder for PRISM graph visualization.

This module handles conversion of graph data into ECharts-compatible options,
including node styling, solid edge colors, and layout configuration.
"""

from typing import Dict, List, Any, Optional
from src.utils import color_from_users, darken_hex, lerp_hex, hex_to_rgba, get_visible_users


# Event keys we request from ECharts click events
REQUESTED_EVENT_KEYS = ['componentType', 'name', 'seriesType', 'value']


def build_echart_options(
    graph: Dict[str, Any],
    active_user: str = None,
    positions: Dict[str, Any] = None,
    show_dead: bool = False,
    visible_users: List[str] = None,
    data_dir: str = "db/data"
) -> Dict[str, Any]:
    """
    Build ECharts options from internal graph representation.
    
    Args:
        graph: Graph dict with 'nodes' and 'edges' lists
        active_user: Currently active user for filtering/styling
        positions: Dict mapping node_id -> [x, y] coordinates
        show_dead: Whether to show nodes with no interested users
        visible_users: List of users to consider visible (None = compute dynamically)
        data_dir: Path to user data directory for color calculations
        
    Returns:
        ECharts options dict ready for ui.echart()
    """
    # Get visible users for color calculations
    if visible_users is None:
        visible_users = get_visible_users(data_dir)
    
    # If no visible users, return empty chart
    if not visible_users:
        return {
            'series': [{
                'type': 'graph',
                'data': [],
                'links': [],
                'label': {'show': True, 'formatter': 'No visible users'},
            }]
        }
    
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    active_user = (active_user or '').strip()

    e_nodes = []
    node_map = {}
    
    # 1. First pass to map nodes
    for n in nodes:
        nid = n.get('id')
        node_map[nid] = n
    
    # Calculate hierarchy depth for each node
    def get_depth(node_id: str, visited=None) -> int:
        """Calculate how high up a node is in the hierarchy (root = 0)."""
        if visited is None:
            visited = set()
        if node_id in visited:
            return 0  # Prevent cycles
        visited.add(node_id)
        
        node = node_map.get(node_id)
        if not node:
            return 0
        parent_id = node.get('parent_id')
        if not parent_id:
            return 0  # Root node
        return 1 + get_depth(parent_id, visited)
    
    # Precompute depths
    node_depths = {n.get('id'): get_depth(n.get('id')) for n in nodes}

    for n in nodes:
        nid = n.get('id')
        label = n.get('label') or nid
        all_interested = n.get('interested_users', [])
        all_rejected = n.get('rejected_users', [])
        
        # Filter to only visible users
        users = [u for u in all_interested if u in visible_users]
        rejected = [u for u in all_rejected if u in visible_users]
        
        # --- State Logic ---
        is_dead = len(users) == 0
        
        # Dead Node Rule
        if is_dead and not show_dead:
            continue

        # Hide nodes rejected by any user (unless showing dead/hidden)
        if rejected and not active_user in users and not show_dead:
            continue

        color = color_from_users(users, visible_users=visible_users)
        # Size depends on hierarchy depth (higher up = larger)
        # Depth 0 (root) is largest, deeper nodes are progressively smaller
        depth = node_depths.get(nid, 0)
        base_size = 40 - (depth * 6) + (2 * len(users))  # Larger for higher hierarchy, plus user boost
        base_size = max(15, base_size)  # Ensure minimum size
        
        # Default Style
        opacity = 1.0
        border_type = 'solid'
        border_width = 0
        border_color = 'transparent'
        background_color = '#312e2a'
        has_rejections = False
        
        # Apply Active User Context Rules
        has_rejections = len(rejected) > 0
        is_interested = active_user in users
            
        if has_rejections:
            # Deprioritized: Anyone rejected it
            # We use darkening instead of opacity to avoid additive transparency artifacts
            color = lerp_hex(color, background_color, 0.9)
            base_size = base_size * 0.6
        elif not is_interested and not is_dead:
            # Pending: No rejections, Active User hasn't voted (isn't in interested)
            # Visual: Thick White Solid Border
            border_width = 4
            border_color = '#FFFFFF' 
                
        # Scaling
        size = base_size
        
        # Style Object
        item_style = {
            'color': color, 
            'opacity': opacity,
            'borderColor': border_color, 
            'borderWidth': border_width
        }
        
        # Store computed opacity and color in node_map for edge color usage later
        node_map[nid]['_computed_opacity'] = opacity
        node_map[nid]['_computed_color'] = color
        
        label_cfg = {
            'show': True,
            'formatter': label,
            'fontSize': 14,
            'fontWeight': 'bold',
            'position': 'inside',
            'color': color,
            'textBorderColor': background_color,
            'textBorderWidth': 6
        }

        # Root Node Logic (Overrrides)
        is_root = depth == 0
        if is_root:
            item_style['borderColor'] = '#ffd700'
            item_style['borderWidth'] = 5
            item_style['borderType'] = 'solid'
            item_style['opacity'] = 1.0
            size = 60
            label_cfg['fontSize'] = 18

        # Store description for tooltip
        description = n.get('description', '')
        tooltip_text = label
        if description:
            tooltip_text += f"<br/><span style='color:#999;font-size:11px'>{description}</span>"
        
        e_node = {
            'id': nid,
            'name': nid, 
            'value': label,
            'description': description,  # Store for reference
            'symbol': 'circle',
            'symbolSize': size,
            'itemStyle': item_style,
            'label': label_cfg,
            'draggable': True,
            'tooltip': {'formatter': tooltip_text}
        }
            
        e_nodes.append(e_node)

    e_links = []
    # Consensus is when all visible users are interested
    consensus_set = set(visible_users)
    seen_pairs = set()  # Track for undirected deduplication

    for e in edges:
        s = e.get('source')
        t = e.get('target')
        if s not in node_map or t not in node_map:
            continue

        # Treat graph as undirected for improved visualization
        # Sort IDs to create a unique key for the connection regardless of direction
        pair = tuple(sorted((s, t)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # Check for Consensus Path (Edge between two white/full-consensus nodes)
        src_id, tgt_id = s, t
        s_node = node_map[src_id]
        t_node = node_map[tgt_id]
        
        s_users = set(s_node.get('interested_users', []))
        t_users = set(t_node.get('interested_users', []))
        
        is_consensus_edge = consensus_set.issubset(s_users) and consensus_set.issubset(t_users)
        
        # Determine Style
        line_style = {
            'curveness': 0,
            'opacity': 0.8
        }

        if is_consensus_edge:
            # Thick glowing line for Golden Path
            line_style.update({
                'width': 6, 
                'opacity': 1.0,
                'color': '#ffffff'  # Consensus white
            })
        else:
            # Standard transition with solid color inherited from child (target) node
            line_style['width'] = 4
            
            # We use the cached values from the node loop to ensure edge color matches node state
            c_target = t_node.get('_computed_color', color_from_users(list(t_node.get('interested_users', []))))
            op_target = t_node.get('_computed_opacity', 1.0)
            
            # Use RGBA for precise color with opacity
            rgba_target = hex_to_rgba(c_target, op_target)
            
            line_style['opacity'] = 1.0
            line_style['color'] = rgba_target

        e_links.append({
            'source': src_id, 
            'target': tgt_id, 
            'lineStyle': line_style,
            'symbol': ['none', 'none'],  # No arrows
            'tooltip': {'show': False}
        })

    # Use 'none' if we have positions, else 'force'
    layout_mode = 'none' if positions else 'force'

    options = {
        'backgroundColor': background_color, 
        'tooltip': {},
        'animation': True,
        'animationDurationUpdate': 0,  # Prevent animated repositioning on updates
        'series': [{
            'type': 'graph',
            'layout': layout_mode,
            'roam': True,
            'label': {'position': 'bottom', 'distance': 5},
            'force': {
                'repulsion': 800,
                'gravity': 0.1,
                'edgeLength': 80,
                'friction': 0.3,  # Higher = slower/calmer (0-1, default ~0.6)
                'layoutAnimation': True
            },
            'data': e_nodes,
            'links': e_links,
            # Note: zoom and center are only set on initial render, not updates
            # to prevent the graph from jumping back to initial position
        }]
    }
    return options


def normalize_click_payload(raw_payload: Any) -> Dict[str, Any]:
    """Normalize NiceGUI chart click payloads into a dictionary for easier parsing."""
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, (list, tuple)):
        return {
            REQUESTED_EVENT_KEYS[i]: raw_payload[i]
            for i in range(min(len(raw_payload), len(REQUESTED_EVENT_KEYS)))
        }
    if isinstance(raw_payload, str):
        return {'name': raw_payload}
    return {}


def resolve_node_id_from_payload(payload: Dict[str, Any], data_manager) -> Optional[str]:
    """Return a node_id from a normalized payload by validating against DataManager data."""
    if not isinstance(payload, dict):
        return None
    component = payload.get('componentType')
    if component != 'series':
        return None

    node_id = payload.get('name')
    if not node_id:
        return None

    graph_nodes = data_manager.get_graph().get('nodes', [])
    if any(n.get('id') == node_id for n in graph_nodes):
        return node_id

    for node in graph_nodes:
        if node.get('label') == node_id:
            return node.get('id')
    return None
