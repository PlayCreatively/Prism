"""
Main NiceGUI application for PRISM.
Integrates DataManager and DrillEngine, renders the graph with ui.echart,
and provides interaction controls with ui.card / ui.row.

This file attempts to import the project modules from src.*. If those imports
fail (for example in isolated test environments), lightweight fallback
implementations are provided so the app can still start for testing.
"""

from nicegui import ui
from typing import Dict, List, Any
import uuid
import time
import threading
try:
    import networkx as nx
except ImportError:
    nx = None

# Attempt to import real project modules; provide minimal fallbacks if missing.
try:
    from src.data_manager import DataManager
except Exception:  # pragma: no cover - fallback for test environments
    class DataManager:
        """Fallback DataManager: keeps an in-memory graph for basic demo/testing."""
        def __init__(self, data_dir='data'):
            self.data_dir = data_dir
            self.nodes = {}
            self.edges = []
            self._seed_demo()

        def _seed_demo(self):
            # Create three root-ish nodes for Alex, Sasha, Alison demonstration.
            for name, users in [('Serious Games', ['Alex']),
                                ('Human-Computer Interaction', ['Sasha']),
                                ('ML for Creativity', ['Alison']),
                                ('Collaborative Storytelling', ['Alex','Sasha','Alison'])]:
                node_id = str(uuid.uuid4())
                self.nodes[node_id] = {
                    'id': node_id,
                    'label': name,
                    'parent_id': None,
                    'status': 'accepted',
                    'metadata': f'Auto-seeded node: {name}',
                    'interested_users': users
                }
            # create links between them
            ids = list(self.nodes.keys())
            if len(ids) >= 2:
                self.edges.append({'source': ids[0], 'target': ids[3]})
                self.edges.append({'source': ids[1], 'target': ids[3]})
                self.edges.append({'source': ids[2], 'target': ids[3]})

        def load(self):
            # In real implementation, would read JSON files. Here it's a no-op.
            return

        def get_graph(self) -> Dict[str, Any]:
            return {'nodes': list(self.nodes.values()), 'edges': list(self.edges)}

        def add_node(self, label: str, parent_id: str = None, users: List[str] = None):
            node_id = str(uuid.uuid4())
            self.nodes[node_id] = {
                'id': node_id,
                'label': label,
                'parent_id': parent_id,
                'status': 'pending',
                'metadata': '',
                'interested_users': users or []
            }
            if parent_id:
                self.edges.append({'source': node_id, 'target': parent_id})
            return self.nodes[node_id]

        def update_node(self, node_id: str, **kwargs):
            if node_id in self.nodes:
                self.nodes[node_id].update(kwargs)
                return self.nodes[node_id]
            raise KeyError('node not found')

        def save(self):
            # No-op for fallback
            return

try:
    from src.drill_engine import DrillEngine
except Exception:  # pragma: no cover - fallback
    class DrillEngine:
        """Fallback DrillEngine: simulates drilling by creating a child node."""
        def __init__(self, data_manager: DataManager):
            self.dm = data_manager

        def drill(self, node_id: str) -> Dict[str, Any]:
            # Create a new "drilled down" child node under node_id
            label = f"Drill: details about {node_id[:8]}"
            users = ['Alex']  # simulated action
            new_node = self.dm.add_node(label=label, parent_id=node_id, users=users)
            # Mark the parent as 'accepted' to simulate consensus movement
            try:
                self.dm.update_node(node_id, status='accepted')
            except Exception:
                pass
            return new_node

try:
    from src.graph_viz import node_to_echart_node  # optional helper
except Exception:
    # We'll build our own conversion below if helper not present.
    node_to_echart_node = None

# Helper: compute color from interested_users list
def color_from_users(users: List[str]) -> str:
    # Map user presence to RGB-ish colors per project documentation
    # Alex -> Red, Sasha -> Green, Alison -> Blue
    r = 255 if 'Alex' in users else 0
    g = 255 if 'Sasha' in users else 0
    b = 255 if 'Alison' in users else 0
    # If none selected, return light gray
    if r == g == b == 0:
        return '#d0d0d0'
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

# Build ECharts options from internal graph
def build_echart_options(graph: Dict[str, Any], active_user: str = None, positions: Dict[str, Any] = None) -> Dict[str, Any]:
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    filter_user = (active_user or '').strip().lower()
    highlight_user = filter_user if filter_user and filter_user != 'all' else None

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
        normalized_users = [str(u).strip().lower() for u in users if isinstance(u, str)]
        color = color_from_users(users)
        size = 20 + (5 * len(users)) # Increased base size

        # Style
        symbol = 'circle'
        item_style = {'color': color, 'borderColor': 'transparent', 'borderWidth': 0}
        label_cfg = {
            'show': True,
            'formatter': label,
            'fontSize': 14,
            'fontWeight': 'bold',
            'position': 'inside',
            'color': color,
            'textBorderColor': '#312e2a',
            'textBorderWidth': 6
        }

        # Root Node Logic
        is_root = label == "Thesis Idea"
        if is_root:
            item_style['borderColor'] = '#ffd700'
            item_style['borderWidth'] = 5
            size = 60
            label_cfg['fontSize'] = 18

        e_node = {
            'id': nid,
            'name': nid, 
            'value': label,
            'symbol': symbol,
            'symbolSize': size,
            'itemStyle': item_style,
            'label': label_cfg,
            'draggable': True,
            'tooltip': {'formatter': '{c}'}
        }
        
        # Inject Layout Positions
        if positions and nid in positions:
            # Map -1..1 to pixels. ECharts coord system center is 0,0? No, top-left.
            # We map to a reasonable canvas size (e.g. 1000x800)
            px, py = positions[nid]
            e_node['x'] = (px * 500) 
            e_node['y'] = (py * 350)
            e_node['fixed'] = True # Ensure they stay put
            
        e_nodes.append(e_node)

    e_links = []
    CONSENSUS_SET = {'Alex', 'Sasha', 'Alison'}
    seen_pairs = set() # Track for undirected deduplication

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
                'color': '#ffffff' # Consensus white
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
            
            # Reconstruct colors (need to fetch original hex since we are building gradient manually)
            c_source = color_from_users(list(s_node.get('interested_users', [])))
            c_target = color_from_users(list(t_node.get('interested_users', [])))
            
            line_style['color'] = {
                'type': 'linear',
                'x': gx, 'y': gy, 'x2': gx2, 'y2': gy2,
                'colorStops': [
                    {'offset': 0, 'color': c_source},
                    {'offset': 1, 'color': c_target}
                ],
                'global': False
            }

        e_links.append({
            'source': src_id, 
            'target': tgt_id, 
            'lineStyle': line_style,
            'symbol': ['none', 'none'], # No arrows
            'tooltip': {'show': False}
        })

    # Use 'none' if we have positions, else 'force'
    layout_mode = 'none' if positions else 'force'

    options = {
        'backgroundColor': "#312e2a", 
        'tooltip': {},
        'series': [{
            'type': 'graph',
            'layout': layout_mode,
            'roam': True,
            'label': {'position': 'bottom', 'distance': 5},
            'force': {
                'repulsion': 1000,
                'gravity': 0.1,
                'edgeLength': 80,
                'layoutAnimation': True
            },
            'data': e_nodes,
            'links': e_links,
            'zoom': 0.6,
            'center': [0, 0] # Center the view on 0,0 where we put the nodes
        }]
    }
    return options

_REQUESTED_EVENT_KEYS = ['componentType', 'name', 'seriesType', 'value']

def normalize_click_payload(raw_payload: Any) -> Dict[str, Any]:
    """Normalize NiceGUI chart click payloads into a dictionary for easier parsing."""
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, (list, tuple)):
        return {
            _REQUESTED_EVENT_KEYS[i]: raw_payload[i]
            for i in range(min(len(raw_payload), len(_REQUESTED_EVENT_KEYS)))
        }
    if isinstance(raw_payload, str):
        return {'name': raw_payload}
    return {}

def resolve_node_id_from_payload(payload: Dict[str, Any], data_manager: DataManager) -> str:
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

# Initialize core managers
data_manager = DataManager()
# DrillEngine expects a list of users, not the DataManager instance directly
drill_engine = DrillEngine(users=['Alex', 'Sasha', 'Alison'])
# We might need to manually inject the data manager if the engine depends on it, 
# but based on the class def, it manages its own state or needs to be synced.
# For this integration, we'll sync them manually in the event handlers.


# Load data at startup
try:
    print("Initializing DataManager...")
    if hasattr(data_manager, 'seed_demo_data'):
        # Only seed if empty
        g_check = data_manager.get_graph()
        if not g_check.get('nodes'):
             data_manager.seed_demo_data()
    
    # Real DataManager doesn't need explicit load(), it reads from disk on get_graph
    if hasattr(data_manager, 'load'):
        data_manager.load()
        
    print("Data init complete.")
    g = data_manager.get_graph()
    print(f"Graph stats: {len(g.get('nodes', []))} nodes, {len(g.get('edges', []))} edges")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error loading data: {e}")



# UI Construction - encapsulated in page function to avoid global state issues
@ui.page('/')
def main_page():
    ui.dark_mode().enable()
    ui.query('body').style('margin: 0; padding: 0; overflow: hidden;')
    
    # --- State & Closures ---
    
    # We use a container for mutable state to be accessible in closures
    state = {
        'selected_node_id': None,
        'chart': None,
        'details_container': None,
        'last_graph_hash': 0,
        'active_user': 'Alex',
        'node_positions': {},
        'last_selection_time': 0
    }

    def run_layout(force_reset=False):
        if not nx: return
        graph = data_manager.get_graph()
        
        G = nx.Graph()
        for n in graph.get('nodes', []):
            G.add_node(n['id'])
        for e in graph.get('edges', []):
            G.add_edge(e['source'], e['target'])
            
        current_pos = state.get('node_positions', {})
        
        seed_pos = None
        fixed_nodes = None
        
        if not force_reset and current_pos:
            # Anchor existing nodes so they don't jump
            common = [n for n in G.nodes() if n in current_pos]
            if common:
                fixed_nodes = common
                seed_pos = current_pos
        
        try:
            # Run layout engine (NetworkX)
            # k=0.6 makes it spacious
            pos = nx.spring_layout(G, pos=seed_pos, fixed=fixed_nodes, k=0.6, iterations=50)
            state['node_positions'] = pos
        except Exception as e:
            print(f"Layout engine error: {e}")

    def get_current_options():
        graph = data_manager.get_graph()
        # Ensure layout exists
        if nx and not state.get('node_positions'):
            run_layout()
        return build_echart_options(graph, state.get('active_user'), state.get('node_positions'))

    def refresh_chart_ui():
        # Update layout if new nodes appear
        if nx and state['chart']:
            run_layout(force_reset=False)

        if state['chart']:
            options = get_current_options()
            # Valid update
            state['chart'].options.update(options)
            state['chart'].update()

    # Auto-refresh loop
    def auto_refresh_check():
        try:
            g = data_manager.get_graph()
            current_len = len(g.get('nodes', [])) + len(g.get('edges', []))
            # Just a heuristic to avoid spamming the frontend if idle
            if current_len != state['last_graph_hash']:
                refresh_chart_ui()
                state['last_graph_hash'] = current_len
        except Exception:
            pass

    # Start the timer immediately after definition to ensure scope visibility
    ui.timer(2.0, auto_refresh_check)

    # --- Actions ---

    def set_active_user(user: str):
        # Default to Alex if something goes wrong, never allow 'All'
        state['active_user'] = user or 'Alex'
        refresh_chart_ui()

    def reset_selection():
        state['selected_node_id'] = None
        if state.get('context_card'):
            state['context_card'].set_visibility(False)
        
        container = state['details_container']
        if container:
            container.clear()

    def handle_chart_click(event):
        node_id = None

        # Normalize NiceGUI event payloads: they can be dicts or a list of requested fields.
        raw_payload = event.args if hasattr(event, 'args') else event
        payload = normalize_click_payload(raw_payload)

        try:
            node_id = resolve_node_id_from_payload(payload, data_manager)
        except Exception as e:
            print(f"Error parsing click: {e}")
            pass

        if node_id:
            state['last_selection_time'] = time.time()
            state['selected_node_id'] = node_id
            if state.get('context_card'):
                state['context_card'].set_visibility(True)
            show_node_details(node_id)
        else:
            # Check if this is a "ghost" click immediately after a valid selection
            # This happens because 'click' events often fire after 'componentClick' events
            gap = time.time() - state.get('last_selection_time', 0)
            if gap < 0.5:
                print("Ignoring background click immediately after selection (ghost click)")
                return

            print("No node_id found in click (Background or Edge). Clearing selection.")
            reset_selection()
    
    
    def toggle_interest(node_id, user="Alex"):
        """
        Toggles the vote of 'user' on the node.
        If user 'Accept', interested -> True.
        If user 'Reject', interested -> False.
        """
        try:
            # Look up current state to know which way to toggle
            user_node = data_manager.get_user_node(user, node_id)
            
            new_interest = True
            
            if user_node:
                current_interest = user_node.get('interested', True) # Default to true if missing
                if current_interest is True:
                    new_interest = False
                else:
                    new_interest = True
            
            status_text = "Accepted" if new_interest else "Rejected"
            ui.notify(f"User {user} set status to {status_text}")
            data_manager.update_user_node(user, node_id, interested=new_interest)
                    
        except Exception as e:
            ui.notify(f"Error updating interest: {e}", color='negative')
            pass
            
        refresh_chart_ui()
        show_node_details(node_id)
        
    def do_drill_action(node_id):
        try:
            new_node = drill_engine.drill(node_id)
            data_manager.save_user(data_manager.load_user(state.get('active_user', 'Alex')))
        except Exception as e:
            ui.notify(f"Drill failed: {e}", color='negative')
            return
        
        refresh_chart_ui()
        if new_node and isinstance(new_node, dict):
            show_node_details(new_node.get('id'))
            
    def open_add_dialog():
        with ui.dialog() as dialog, ui.card():
            ui.label('Add New Node').classes('text-lg font-bold')
            input_label = ui.input('Label').classes('w-full')
            input_parent = ui.input('Parent ID').classes('w-full')
            input_users = ui.input('Users (csv)').classes('w-full')
            
            def save():
                label = input_label.value.strip() or "New Node"
                pid = input_parent.value.strip() or None
                users = [u.strip() for u in input_users.value.split(',') if u.strip()]
                newn = data_manager.add_node(label=label, parent_id=pid, users=users)
                # data_manager.add_node already saves
                refresh_chart_ui()
                dialog.close()
                show_node_details(newn.get('id'))

            ui.button('Save', on_click=save)
        dialog.open()

    def persist_node_changes(node_id: str, **changes):
        """
        Persist changes. 
        - Label/Parent changes are shared (update_shared_node).
        - Metadata/Interested are per-user (update_user_node).
        """
        active_user = state.get('active_user', 'Alex')
        
        # Split changes
        shared_upd = {}
        user_upd = {}
        
        for k, v in changes.items():
            if k in ['label', 'parent_id']:
                shared_upd[k] = v
            elif k in ['metadata', 'interested']:
                user_upd[k] = v
        
        try:
            if shared_upd:
                data_manager.update_shared_node(node_id, **shared_upd)
            if user_upd:
                data_manager.update_user_node(active_user, node_id, **user_upd)
                
        except Exception as exc:
            print(f"Error updating node {node_id}: {exc}")

    def show_node_details(node_id):

        container = state['details_container']
        if not container: return

        container.clear()
        
        # 1. Get the aggregate node for shared properties (Label, Neighbors, Interest List)
        graph_data = data_manager.get_graph()
        generic_node = next((n for n in graph_data.get('nodes', []) if n['id'] == node_id), None)
        
        # 2. Get the specific user node for private properties (Metadata, Status)
        active_user = state.get('active_user', 'Alex')
        user_node = data_manager.get_user_node(active_user, node_id)
        
        # Display logic needs valid generic_node at minimum
        if not generic_node:
            with container:
                ui.label('Node not found').classes('text-red-500')
            return
            
        # Use user-specific values if available
        # If user_node is MISSING, they are effectively 'pending' (haven't interacted).
        # If user_node exists, check 'interested' boolean.
        
        is_interested = user_node.get('interested', True) if user_node else True 
        
        if not user_node:
             status_label = "pending"
             status_color = "grey"
        elif is_interested:
             status_label = "accepted"
             status_color = "green"
        else:
             status_label = "rejected"
             status_color = "red"

        display_metadata = user_node.get('metadata', '') if user_node else ''
        display_label = generic_node.get('label', '') # Label is shared
        
        with container:
            # Header
            with ui.row().classes('w-full justify-between'):
                ui.badge(status_label.upper(), color=status_color)
                ui.label(node_id[:8]).classes('text-xs text-gray-400')

            ui.label('DETAILS').classes('text-xs font-bold text-gray-400 mt-2')
            label_input = ui.input('Label', value=display_label).classes('w-full')

            interested_users = generic_node.get('interested_users', [])
            if interested_users:
                with ui.row().classes('gap-1 flex-wrap text-xs text-gray-400'):
                    ui.label('Interested:').classes('text-xs text-gray-400')
                    # Map users to project colors
                    user_colors = {'Alex': 'red', 'Sasha': 'green', 'Alison': 'blue'}
                    for user in interested_users:
                        c = user_colors.get(user, 'primary')
                        ui.chip(user, color=c).props('outline size=sm')

            ui.label(f'CONTEXT ({active_user})').classes('text-xs font-bold text-gray-400 mt-4')
            metadata_input = ui.textarea(value=display_metadata).props('filled autogrow').classes('w-full text-sm')
            preview = ui.markdown(display_metadata or '_No context yet_').classes('w-full bg-slate-800 rounded p-2 text-sm text-gray-200') # Darker background, lighter text

            def sync_preview():
                content = metadata_input.value or ''
                preview.set_content(content or '_No context yet_')

            # --- Auto-Save Logic ---
            _save_timer = None
            save_status = ui.label('').classes('text-xs text-green-500 italic mt-1')

            def execute_autoresave():
                new_label = label_input.value or ''
                final_label = new_label.strip()
                if not final_label:
                    final_label = display_label
                
                persist_node_changes(node_id, label=final_label, metadata=metadata_input.value)
                refresh_chart_ui()
                
                # Update status
                save_status.text = 'Saved changes.'
                # Clear message
                ui.timer(2.0, lambda: setattr(save_status, 'text', ''), once=True)

            def schedule_save(e=None):
                nonlocal _save_timer
                save_status.text = 'Typing...'
                if _save_timer:
                    _save_timer.cancel()
                # Schedule save
                _save_timer = ui.timer(1.0, execute_autoresave, once=True)

            # Bind to on_value_change (throttle is built-in option but we want custom debounce)
            # 'input' event fires on every keystroke for input/textarea
            # IMPORTANT: We must accept the 'e' argument in lambda, even if unused, 
            # because on_value_change passes an event object.
            metadata_input.on_value_change(lambda e: (sync_preview(), schedule_save(e)))
            label_input.on_value_change(lambda e: schedule_save(e))

            # Actions
            ui.label('ACTIONS').classes('text-xs font-bold text-gray-400 mt-4')
            with ui.grid(columns=2).classes('w-full gap-2'):
                ui.button('Drill', on_click=lambda: do_drill_action(node_id))
                
                # Check active user status
                if status_label == 'accepted':
                     # If accepted, offer to Reject
                     ui.button('Reject', on_click=lambda: toggle_interest(node_id, active_user), color='red')
                elif status_label == 'rejected':
                     # If rejected, offer to Accept (Re-evaluate)
                     ui.button('Accept', on_click=lambda: toggle_interest(node_id, active_user), color='green')
                else:
                     # Pending -> Accept
                     ui.button('Accept', on_click=lambda: toggle_interest(node_id, active_user), color='green')

    # --- Layout Construction ---

    # 1. Full Screen Chart
    # Initialize WITH options to ensure rendering logic triggers immediately
    init_opts = get_current_options()
    state['chart'] = ui.echart(init_opts)
    state['chart'].style('width: 100vw; height: 100vh; position: absolute; top: 0; left: 0; z-index: 0;')
    
    # We use 'componentClick' to strictly capture NODE clicks.
    state['chart'].on('componentClick', handle_chart_click, _REQUESTED_EVENT_KEYS)
    
    # We use 'click' to capture BACKGROUND clicks (args will be empty for background).
    # Since handle_chart_click handles empty payloads by resetting, this works effectively.
    # Note: 'click' also fires when a node is clicked, but usually componentClick fires first or we just rely on the payload check.
    # To be safe, we bind 'click' to the SAME handler, because our handler checks for node_id.
    state['chart'].on('click', handle_chart_click, _REQUESTED_EVENT_KEYS)


    # 2. Floating Header
    with ui.row().classes('fixed top-4 left-4 z-10 bg-slate-900/90 p-3 rounded shadow-md backdrop-blur-sm items-center gap-2 border border-slate-700'):
        ui.icon('hub', size='md').classes('text-primary')
        with ui.column().classes('gap-0'):
            ui.label('PRISM').classes('text-lg font-bold leading-none text-white')
            ui.label('Consensus Graph').classes('text-xs text-gray-400 leading-none')
        user_select = ui.select(
            ['Alex', 'Sasha', 'Alison'], # Removed 'All'
            value=state['active_user'],
            label='Acting as User'
        ).props('dense outlined').classes('w-32')
        user_select.on('update:model-value', lambda e: set_active_user(user_select.value))
        
        # Layout Reset control
        if nx:
             ui.button(icon='grid_goldenratio', on_click=lambda: (run_layout(force_reset=True), refresh_chart_ui())).props('flat round dense color=grey').tooltip('Reset Graph Layout')

    # 3. Context Panel
    # Starts hidden (visible=False). content triggers visibility.
    state['context_card'] = ui.card().classes('fixed right-6 top-6 w-96 max-h-[90vh] overflow-y-auto z-20 shadow-2xl flex flex-col gap-4 bg-slate-900/95 backdrop-blur-md border-t-4 border-primary border-x border-b border-slate-700')
    state['context_card'].set_visibility(False)
    
    with state['context_card']:
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Context Window').classes('text-lg font-bold text-gray-100')
            with ui.row().classes('gap-1'):
                 ui.button(icon='close', on_click=reset_selection).props('flat round dense color=grey').tooltip('Close')
        
        ui.separator()
        state['details_container'] = ui.column().classes('w-full gap-3')
        # Empty init


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='PRISM', port=8081, reload=True)

