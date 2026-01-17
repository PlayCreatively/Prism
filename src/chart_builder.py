"""
ECharts options builder for PRISM graph visualization.

This module handles conversion of graph data into ECharts-compatible options,
including node styling, edge gradients, and layout configuration.
"""

from typing import Dict, List, Any, Optional
from src.utils import color_from_users, darken_hex, hex_to_rgba


# Event keys we request from ECharts click events
REQUESTED_EVENT_KEYS = ['componentType', 'name', 'seriesType', 'value']


def build_echart_options(
    graph: Dict[str, Any],
    active_user: str = None,
    positions: Dict[str, Any] = None,
    show_dead: bool = False,
    all_users_view: bool = False
) -> Dict[str, Any]:
    """
    Build ECharts options from internal graph representation.
    
    Args:
        graph: Graph dict with 'nodes' and 'edges' lists
        active_user: Currently active user for filtering/styling
        positions: Dict mapping node_id -> [x, y] coordinates
        show_dead: Whether to show nodes with no interested users
        all_users_view: Whether in "all users" view mode (no filtering)
        
    Returns:
        ECharts options dict ready for ui.echart()
    """
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    active_user = (active_user or '').strip()

    e_nodes = []
    node_map = {}
    
    # 1. First pass to map nodes
    for n in nodes:
        nid = n.get('id')
        node_map[nid] = n

    for n in nodes:
        nid = n.get('id')
        label = n.get('label') or nid
        users = n.get('interested_users', [])
        rejected = n.get('rejected_users', [])
        
        # --- State Logic ---
        is_dead = len(users) == 0
        
        # Dead Node Rule
        if is_dead and not show_dead:
            continue

        if not all_users_view:
            # Hide nodes rejected by valid active user (unless showing dead/hidden)
            if active_user in rejected and not show_dead:
                continue

        color = color_from_users(users)
        base_size = 20 + (5 * len(users))
        
        # Default Style
        opacity = 1.0
        border_type = 'solid'
        border_width = 0
        border_color = 'transparent'
        has_rejections = False
        
        if not all_users_view:
            # Apply Active User Context Rules
            has_rejections = len(rejected) > 0
            is_interested = active_user in users
            
            if has_rejections:
                # Deprioritized: Anyone rejected it
                # We use darkening instead of opacity to avoid additive transparency artifacts
                color = darken_hex(color, 0.7) 
                base_size = base_size * 0.6
            elif not is_interested and not is_dead:
                # Pending: No rejections, Active User hasn't voted (isn't in interested)
                # Visual: Thick Yellow Dashed Border
                border_width = 4
                border_color = '#FFFF00' 
                
        # Scaling
        size = base_size
        
        # Style Object
        item_style = {
            'color': color, 
            'opacity': opacity,
            'borderColor': border_color, 
            'borderWidth': border_width
        }
        
        # Store computed opacity in node_map for edge gradient usage later
        node_map[nid]['_computed_opacity'] = opacity
        node_map[nid]['_computed_color'] = color
        
        label_cfg = {
            'show': True,
            'formatter': label,
            'fontSize': 14,
            'fontWeight': 'bold',
            'position': 'inside',
            'color': '#888888' if has_rejections else color,
            'textBorderColor': '#312e2a',
            'textBorderWidth': 6
        }

        # Root Node Logic (Overrrides)
        is_root = label == "Thesis Idea"
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
    CONSENSUS_SET = {'Alex', 'Sasha', 'Alison'}
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
        
        is_consensus_edge = CONSENSUS_SET.issubset(s_users) and CONSENSUS_SET.issubset(t_users)
        
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
            # Standard transition
            line_style['width'] = 4
            
            # Default to manual gradient calculation based on positions
            # 'source-target' can produce black edges in some setups, causing "wrong colors".
            # To fix "inconsistent order", we must use node positions to orient the gradient.
            
            # Default coordinates (Left -> Right)
            gx, gy, gx2, gy2 = 0, 0, 1, 0
            
            if positions:
                # Retrieve coordinates to determine relative direction
                # positions maps id -> [x, y]
                s_pos = positions.get(src_id)
                t_pos = positions.get(tgt_id)
                
                if s_pos is not None and t_pos is not None:
                    sx, sy = s_pos
                    tx, ty = t_pos
                    
                    # Logic: In ECharts gradient relative coords (0..1), 
                    # 0 is Min(x/y) (Left/Top), 1 is Max(x/y) (Right/Bottom).
                    # If sx < tx (Left->Right): start=0, end=1
                    # If sx > tx (Right->Left): start=1, end=0
                    gx = 0 if sx < tx else 1
                    gx2 = 1 if sx < tx else 0
                    
                    gy = 0 if sy < ty else 1
                    gy2 = 1 if sy < ty else 0
            
            # Reconstruct colors/opacity for gradient
            # We use the cached values from the node loop to ensure edge opacity matches node state
            c_source = s_node.get('_computed_color', color_from_users(list(s_node.get('interested_users', []))))
            c_target = t_node.get('_computed_color', color_from_users(list(t_node.get('interested_users', []))))
            
            op_source = s_node.get('_computed_opacity', 1.0)
            op_target = t_node.get('_computed_opacity', 1.0)
            
            # Use RGBA for precise gradient opacity interpolation
            rgba_source = hex_to_rgba(c_source, op_source)
            rgba_target = hex_to_rgba(c_target, op_target)
            
            # Reset global opacity to 1.0 (defaults usually 1), handle alpha in color stops
            line_style['opacity'] = 1.0
            
            line_style['color'] = {
                'type': 'linear',
                'x': gx, 'y': gy, 'x2': gx2, 'y2': gy2,
                'colorStops': [
                    {'offset': 0, 'color': rgba_source},
                    {'offset': 0.1, 'color': rgba_source},
                    {'offset': 0.9, 'color': rgba_target},
                    {'offset': 1, 'color': rgba_target}
                ],
                'global': False
            }

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
        'backgroundColor': "#312e2a", 
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
