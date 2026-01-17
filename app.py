"""
Main NiceGUI application for PRISM.
Integrates DataManager and DrillEngine, renders the graph with ui.echart,
and provides interaction controls with ui.card / ui.row.

This file attempts to import the project modules from src.*. If those imports
fail (for example in isolated test environments), lightweight fallback
implementations are provided so the app can still start for testing.
"""

from nicegui import ui, run, app
from typing import Dict, List, Any
import uuid
import time
import threading
try:
    import networkx as nx
except ImportError:
    nx = None

from dotenv import load_dotenv
load_dotenv()

# Global Styles
ui.add_head_html('''
    <style>
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: #475569; /* slate-600 */
            border-radius: 9999px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #334155; /* slate-700 */
        }
    </style>
    <script>
        // Prevent Ctrl key from triggering ECharts zoom/pan
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Control' || e.ctrlKey) {
                e.preventDefault();
            }
        }, { passive: false });
        
        document.addEventListener('keyup', function(e) {
            if (e.key === 'Control') {
                e.preventDefault();
            }
        }, { passive: false });
    </script>
''', shared=True)

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

        def add_node(self, label: str, parent_id: str = None, users: List[str] = None, interested: bool = True):
            node_id = str(uuid.uuid4())
            self.nodes[node_id] = {
                'id': node_id,
                'label': label,
                'parent_id': parent_id,
                'status': 'accepted' if interested else 'rejected',
                'metadata': '',
                'interested_users': (users or []) if interested else []
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

from src.drill_engine import DrillEngine

try:
    from src.ai_agent import AIAgent
except Exception:
    print("Warning: AIAgent could not be imported. AI features disabled.")
    class AIAgent:
        def generate_drill_candidates(self, *args, **kwargs):
            return ["Fallback Idea A", "Fallback Idea B", "Fallback Idea C"]

try:
    from src.drill_workflow import start_drill_process
except ImportError:
    from nicegui import ui
    async def start_drill_process(*args, **kwargs):
        ui.notify("Drill workflow module missing.", color='negative')

try:
    from src.review_workflow import start_review_process, get_pending_nodes
except ImportError:
    print("Review workflow missing")
    async def start_review_process(*args, **kwargs): pass
    def get_pending_nodes(*args): return []

try:
    from src.git_manager import GitManager
except ImportError:
    print("GitManager missing")
    GitManager = None

try:
    from src.graph_viz import node_to_echart_node  # optional helper
except Exception:
    # We'll build our own conversion below if helper not present.
    node_to_echart_node = None

from src.utils import color_from_users, lighten_hex, darken_hex, hex_to_rgba
from src.ui_common import render_tri_state_buttons, render_editable_notes, render_other_users_notes
from src.edit import EditController, EditOverlay, EditActions, setup_edit_handlers
from src.chart_builder import build_echart_options, normalize_click_payload, resolve_node_id_from_payload, REQUESTED_EVENT_KEYS


# Initialize core managers
data_manager = DataManager(data_dir="db/data")
# DrillEngine expects a list of users, not the DataManager instance directly
drill_engine = DrillEngine(users=['Alex', 'Sasha', 'Alison'])
ai_agent = AIAgent()
git_manager = GitManager(repo_path="db") if GitManager else None

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
        'active_user': app.storage.user.get('active_user', 'Alex'),
        'show_dead': app.storage.user.get('show_dead', False),
        'all_users_view': app.storage.user.get('all_users_view', False),
        'last_selection_time': 0,
        'temperature': app.storage.user.get('temperature', 0.7),
        'test_mode': app.storage.user.get('test_mode', False),
        'is_ctrl_pressed': False,
        'mouse_position': (0, 0),
        'dragging_node_id': None,
        'edit_controller': EditController(),
        'edit_overlay': EditOverlay(),
        'edit_actions': EditActions(data_manager)
    }

    # --- Git State & Logic ---
    git_btn_ref = {}

    async def check_git_status():
        if not git_manager: return
        btn = git_btn_ref.get('btn')
        if not btn: return
        
        user = state['active_user']
        try:
            # Check in background
            start_check = time.time()
            has_changes = await run.io_bound(git_manager.has_changes, user)
            if has_changes:
                btn.classes(remove='hidden')
            else:
                btn.classes(add='hidden')
        except Exception as e:
            print(f"Git check error: {e}")

    async def do_git_push():
        if not git_manager: return
        user = state['active_user']
        ui.notify(f'Pushing changes for {user}...', position='bottom-right')
        try:
             await run.io_bound(git_manager.push_changes_for_user, user)
             ui.notify('Published to team!', type='positive', position='bottom-right')
             await check_git_status()
        except Exception as e:
             ui.notify(f'Push failed: {e}', type='negative', position='bottom-right')

    async def auto_pull(verbose=False):
        if not git_manager: return
        
        # Health Check
        health = await run.io_bound(git_manager.validate_setup)
        if not health['ok']:
            # Silent return on repeated failures to avoid spam, 
            # or just log it to console
            # for issue in health['issues']:
            #     ui.notify(f"Git Config: {issue}", type='warning', timeout=0, close_button=True)
            return

        try:
             result = await run.io_bound(git_manager.pull_rebase)
             
             # Case 1: Pull failed appropriately (e.g. no remote), effectively "up to date" locally
             if result is None:
                 if verbose:
                      ui.notify('Git: Local only (no upstream)', position='bottom-right', color='grey')
                 return

             # Case 2: Standard execution
             if result.stdout:
                 # Check for various "up to date" messages
                 # "Already up to date." or "Current branch ... is up to date."
                 output = result.stdout.lower()
                 if 'up to date' not in output:
                     ui.notify('Git: Incoming changes applied.', type='positive', position='bottom-right')
                     refresh_chart_ui()
                 elif verbose:
                     ui.notify('Git: Up to date', position='bottom-right', color='positive')
             
        except Exception as e:
             # This often happens if no upstream is configured or network is down
             # We suppress this in the loop to avoid spamming the user
             print(f"Git auto-pull failed: {e}")

    # Run pull on load (immediately)
    ui.timer(0.1, lambda: auto_pull(verbose=True), once=True)
    # Run pull loop (every 10s)
    ui.timer(10.0, lambda: auto_pull(verbose=False))
    # Check local status (for Publish button) periodically
    ui.timer(5.0, check_git_status)

    def get_current_options():
        graph = data_manager.get_graph()
        return build_echart_options(
            graph, 
            state.get('active_user'), 
            positions=None,
            show_dead=state.get('show_dead', False),
            all_users_view=state.get('all_users_view', False)
        )

    def refresh_chart_ui():
        if state['chart']:
            options = get_current_options()
            
            # ECharts is the source of truth for positions.
            # We only update visual properties for existing nodes.
            # For NEW nodes, we pass their initial position from Python.
            import json
            series_data = options.get('series', [{}])[0].get('data', [])
            series_links = options.get('series', [{}])[0].get('links', [])
            
            # Build a map of ALL node data keyed by id
            # This includes visual properties AND positions for new nodes
            all_nodes_map = {}
            for node in series_data:
                nid = node.get('name') or node.get('id')
                all_nodes_map[nid] = {
                    'id': node.get('id'),
                    'name': node.get('name'),
                    'value': node.get('value'),
                    'itemStyle': node.get('itemStyle'),
                    'label': node.get('label'),
                    'symbolSize': node.get('symbolSize'),
                    'symbol': node.get('symbol'),
                    'tooltip': node.get('tooltip'),
                    'draggable': node.get('draggable', True),
                    # Include position for new nodes
                    'x': node.get('x'),
                    'y': node.get('y'),
                    'fixed': node.get('fixed'),
                }
            
            valid_ids_json = json.dumps(list(all_nodes_map.keys()))
            all_nodes_json = json.dumps(all_nodes_map)
            
            js_code = f'''
                if (window.prismChart) {{
                    const chart = window.prismChart;
                    const allNodesMap = {all_nodes_json};
                    const validNodeIds = new Set({valid_ids_json});
                    
                    // Get current option to find existing nodes
                    const opt = chart.getOption();
                    const currentData = (opt.series && opt.series[0] && opt.series[0].data) || [];
                    const existingIds = new Set(currentData.map(n => n.id || n.name));
                    
                    // For existing nodes: only update visual properties, don't touch position
                    // This prevents force layout from restarting
                    const updatedData = currentData
                        .filter(n => validNodeIds.has(n.id || n.name))
                        .map(n => {{
                            const nid = n.id || n.name;
                            const newProps = allNodesMap[nid];
                            if (newProps) {{
                                return {{
                                    ...n,  // Keep existing x, y, and other state
                                    itemStyle: newProps.itemStyle,
                                    label: newProps.label,
                                    symbolSize: newProps.symbolSize,
                                    symbol: newProps.symbol,
                                    tooltip: newProps.tooltip,
                                    value: newProps.value
                                }};
                            }}
                            return n;
                        }});
                    
                    // Add NEW nodes (not in ECharts yet)
                    const newNodes = [];
                    for (const [nid, props] of Object.entries(allNodesMap)) {{
                        if (!existingIds.has(nid)) {{
                            newNodes.push({{
                                id: props.id,
                                name: props.name,
                                value: props.value,
                                itemStyle: props.itemStyle,
                                label: props.label,
                                symbolSize: props.symbolSize,
                                symbol: props.symbol,
                                tooltip: props.tooltip,
                                draggable: props.draggable
                                // No x/y - let force layout place it naturally
                            }});
                        }}
                    }}
                    
                    chart.setOption({{
                        series: [{{
                            data: [...updatedData, ...newNodes],
                            links: {json.dumps(series_links)}
                        }}]
                    }}, {{notMerge: false, lazyUpdate: true}});
                }}
            '''
            ui.run_javascript(js_code)
            
        # Update Pending Badge
        if state.get('pending_badge_ui'):
            try:
                count = len(get_pending_nodes(data_manager, state.get('active_user', 'Alex')))
                state['pending_badge_ui'].text = str(count)
                state['pending_badge_ui'].set_visibility(count > 0)
            except Exception:
                pass

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
        app.storage.user['active_user'] = state['active_user']
        refresh_chart_ui()

    def reset_selection():
        state['selected_node_id'] = None
        if state.get('context_card'):
            state['context_card'].set_visibility(False)
        
        container = state['details_container']
        if container:
            container.clear()

    def handle_chart_click(event):
        # SKIP click handling in edit mode - let edit controller handle it
        if state.get('is_ctrl_pressed'):
            return
        
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
    
    
    def set_vote(node_id, status, user="Alex"):
        """
        Sets the vote status for a user.
        status: 'accepted' | 'rejected' | 'maybe'
        """
        try:
            if status == 'maybe':
                data_manager.remove_user_node(user, node_id)
                ui.notify(f"{user} reset vote (Maybe)", type='info')
            else:
                interested = (status == 'accepted')
                data_manager.update_user_node(user, node_id, interested=interested)
                ui.notify(f"{user} voted {status.upper()}", type='positive' if interested else 'negative')
            
            # Trigger git status check
            ui.timer(0.5, check_git_status, once=True)

        except Exception as e:
            ui.notify(f"Error updating vote: {e}", color='negative')
            pass
            
        refresh_chart_ui()
        show_node_details(node_id)
    
    
    def toggle_interest(node_id, user="Alex"):
        """Deprecated: Use set_vote instead"""
        # ... logic preserved if any legacy calls remain, but redirecting to set_vote is safer
        # For now, implemented as compatibility wrapper if clicked blindly
        pass
        
    async def do_drill_action(node_id):
        await start_drill_process(
            node_id=node_id,
            data_manager=data_manager,
            ai_agent=ai_agent,
            active_user=state.get('active_user', 'Alex'),
            on_complete=refresh_chart_ui,
            temperature=state.get('temperature', 0.7)
        )
            
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
                ui.timer(0.5, check_git_status, once=True)
                refresh_chart_ui()
                dialog.close()
                show_node_details(newn.get('id'))

            ui.button('Save', on_click=save)
        dialog.open()

    def persist_node_changes(node_id: str, **changes):
        """
        Persist changes. 
        - Label/Parent/Description changes are shared (update_shared_node).
        - Metadata/Interested are per-user (update_user_node).
        """
        active_user = state.get('active_user', 'Alex')
        
        # Split changes
        shared_upd = {}
        user_upd = {}
        
        for k, v in changes.items():
            if k in ['label', 'parent_id', 'description']:
                shared_upd[k] = v
            elif k in ['metadata', 'interested']:
                user_upd[k] = v
        
        try:
            if shared_upd:
                data_manager.update_shared_node(node_id, **shared_upd)
            if user_upd:
                data_manager.update_user_node(active_user, node_id, **user_upd)
            
            # Trigger git status check
            ui.timer(0.5, check_git_status, once=True)
                
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
            # Header row with label input and close button
            with ui.row().classes('w-full items-center justify-between -mt-4'):
                label_input = ui.input(value=display_label).classes('text-lg font-bold text-gray-100 flex-1').props('borderless')
                ui.button(icon='close', on_click=reset_selection).props('flat round dense color=grey').tooltip('Close')
            
            ui.separator().classes('-mt-3')
            
            # Status row
            with ui.row().classes('w-full justify-between items-center'):
                ui.badge(status_label.upper(), color=status_color)
                with ui.row().classes('gap-1 flex-wrap'):
                    interested_set = set(generic_node.get('interested_users', []))
                    rejected_set = set(generic_node.get('rejected_users', []))
                    
                    # User-specific text color classes (Tailwind)
                    user_text_colors = {
                        'Alex': 'text-red-400', 
                        'Sasha': 'text-green-400', 
                        'Alison': 'text-blue-400'
                    }

                    for user in ['Alex', 'Sasha', 'Alison']:
                        txt_cls = user_text_colors.get(user, '')
                        
                        if user in interested_set:
                            with ui.chip(icon='check', color='green').props('outline size=sm'):
                                ui.label(user).classes(txt_cls)
                        elif user in rejected_set:
                            with ui.chip(icon='close', color='red').props('outline size=sm'):
                                ui.label(user).classes(txt_cls)
                        else:
                            # Grayed out / Question mark
                            with ui.chip(icon='help_outline', color='grey').props('outline size=sm').classes('opacity-40'):
                                ui.label(user).classes('') # No specific user color for pending/gray state

            # Description (shared across all users)
            description_input = ui.textarea('Description', value=generic_node.get('description', '')).classes('w-full')
            description_input.props('outlined rows=3')

            # Local state for metadata since we use an external component
            current_metadata = display_metadata

            # --- Auto-Save Logic ---
            _save_timer = None

            def execute_autoresave():
                nonlocal current_metadata
                new_label = label_input.value or ''
                final_label = new_label.strip()
                if not final_label:
                    final_label = display_label
                
                new_description = description_input.value or ''
                
                persist_node_changes(node_id, label=final_label, description=new_description, metadata=current_metadata)
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

            def update_metadata(val):
                nonlocal current_metadata
                current_metadata = val
                schedule_save()

            render_editable_notes(
                text=display_metadata,
                on_change=update_metadata,
                label=f'{active_user}\'s notes',
                editable=True
            )
            
            # Show other users' notes with accept/reject coloring
            render_other_users_notes(
                node_id=node_id,
                active_user=active_user,
                data_manager=data_manager
            )
            
            save_status = ui.label('').classes('text-xs text-green-500 italic mt-1')
            # Bind to on_value_change (throttle is built-in option but we want custom debounce)
            # 'input' event fires on every keystroke for input/textarea
            # IMPORTANT: We must accept the 'e' argument in lambda, even if unused, 
            # because on_value_change passes an event object.
            label_input.on_value_change(lambda e: schedule_save(e))
            description_input.on_value_change(lambda e: schedule_save(e))


            # Actions
            ui.label('ACTIONS').classes('text-xs font-bold text-gray-400 mt-4')
            with ui.row().classes('w-full gap-2 justify-between'):
                # Drill only visible if full consensus (Alex, Sasha, Alison)
                current_interested = set(generic_node.get('interested_users', []))
                
                # Consensus Drill Button
                if state.get('test_mode') or {'Alex', 'Sasha', 'Alison'}.issubset(current_interested):
                    ui.button('Drill', on_click=lambda: do_drill_action(node_id)).props('icon=hub')
                
                # Voting Controls (Tri-state)
                # Determine current state for visual highlighting
                if not user_node:
                    curr_vote = 'maybe'
                elif user_node.get('interested', True):
                    curr_vote = 'accepted'
                else: 
                    curr_vote = 'rejected'



                render_tri_state_buttons(
                    curr_vote,
                    lambda action: set_vote(node_id, action, active_user)
                )

    # --- Manual Editing (New Controller-Based System) ---
    
    # Initialize the edit overlay and set up handlers
    edit_overlay = state['edit_overlay']
    edit_controller = state['edit_controller']
    edit_actions = state['edit_actions']
    
    # Set up all edit handlers (extracted to src/edit/handlers.py)
    edit_handlers = setup_edit_handlers(
        state=state,
        data_manager=data_manager,
        edit_controller=edit_controller,
        edit_overlay=edit_overlay,
        edit_actions=edit_actions,
        normalize_click_payload=normalize_click_payload,
        resolve_node_id_from_payload=resolve_node_id_from_payload,
        refresh_chart_ui=refresh_chart_ui,
        reset_selection=reset_selection,
        check_git_status=check_git_status,
    )
    
    handle_keyboard = edit_handlers['handle_keyboard']
    handle_mouse_move = edit_handlers['handle_mouse_move']
    handle_mouse_down = edit_handlers['handle_mouse_down']
    handle_mouse_up = edit_handlers['handle_mouse_up']
    
    # Global keyboard handler
    ui.keyboard(on_key=handle_keyboard)
    
    # --- Layout Construction ---

    # 1. Full Screen Chart
    # Initialize WITH options to ensure rendering logic triggers immediately
    init_opts = get_current_options()
    state['chart'] = ui.echart(init_opts)
    state['chart'].style('width: 100vw; height: 100vh; position: absolute; top: 0; left: 0; z-index: 0;')
    
    # We use 'componentClick' to strictly capture NODE clicks.
    state['chart'].on('componentClick', handle_chart_click, REQUESTED_EVENT_KEYS)
    
    # We use 'click' to capture BACKGROUND clicks (args will be empty for background).
    # Since handle_chart_click handles empty payloads by resetting, this works effectively.
    # Note: 'click' also fires when a node is clicked, but usually componentClick fires first or we just rely on the payload check.
    # To be safe, we bind 'click' to the SAME handler, because our handler checks for node_id.
    state['chart'].on('click', handle_chart_click, REQUESTED_EVENT_KEYS)
    
    # Manual editing: mouse events
    # Note: ECharts may not directly support these events via NiceGUI binding
    # This is a best-effort implementation - may need JavaScript injection
    try:
        state['chart'].on('mousemove', handle_mouse_move, ['offsetX', 'offsetY'])
        state['chart'].on('mousedown', handle_mouse_down, REQUESTED_EVENT_KEYS)
        state['chart'].on('mouseup', handle_mouse_up, REQUESTED_EVENT_KEYS)
    except Exception as e:
        print(f"Warning: Could not bind mouse events for manual editing: {e}")
    
    # Listen for pan/zoom to update cached positions
    def handle_roam(e):
        """Update overlay positions when chart is panned/zoomed."""
        ui.run_javascript('if(window.updateEditOverlayPositions) window.updateEditOverlayPositions();')
    
    state['chart'].on('chart:graphroam', handle_roam)

    # Setup the edit overlay (HTML layer on top of chart)
    edit_overlay.setup()
    
    # Expose the ECharts instance globally for our overlay JS to use
    # NiceGUI stores Vue components in refs with id prefix 'r', accessible via getElement()
    chart_id = state["chart"].id
    ui.run_javascript(f'''
        // Wait for chart to be ready, then store reference using NiceGUI's getElement
        setTimeout(function() {{
            try {{
                // NiceGUI provides getElement(id) which returns the Vue component
                const vueComponent = getElement({chart_id});
                if (vueComponent && vueComponent.chart) {{
                    window.prismChart = vueComponent.chart;
                    window.prismChartId = {chart_id};
                    console.log('PRISM: Chart reference stored via getElement, id={chart_id}');
                    
                    // Set initial zoom and center only once at startup
                    vueComponent.chart.setOption({{
                        series: [{{
                            center: [0, 0],
                            zoom: 0.6
                        }}]
                    }});
                }} else {{
                    console.log('PRISM: Vue component found but no chart property', vueComponent);
                }}
            }} catch(e) {{
                console.log('PRISM: Error getting chart:', e.message);
            }}
        }}, 500);
    ''')


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
        
        # Git Push Button (Context sensitive)
        with ui.button(on_click=do_git_push).props('flat dense color=accent icon=cloud_upload').classes('hidden') as btn:
            btn.tooltip('Push local changes')
            git_btn_ref['btn'] = btn

        # --- Global Controls ---
        ui.separator().props('vertical')
        
        # Review Pending Button (Placeholder for now)
        async def do_review():
             await start_review_process(
                 data_manager, 
                 state.get('active_user', 'Alex'), 
                 on_complete=refresh_chart_ui
             )

        with ui.button(on_click=do_review).props('flat dense color=warning icon=checklist').tooltip('Review Pending Keys'):
             state['pending_badge_ui'] = ui.badge('0', color='red').props('floating').classes('text-xs') # Placeholder count

        # Toggles
        with ui.row().classes('gap-1 items-center'):
            def toggle_dead(e):
                state['show_dead'] = e.value
                app.storage.user['show_dead'] = e.value
                refresh_chart_ui()
            
            def toggle_all(e):
                state['all_users_view'] = e.value
                app.storage.user['all_users_view'] = e.value
                refresh_chart_ui()

            def toggle_test(e):
                state['test_mode'] = e.value
                app.storage.user['test_mode'] = e.value
                # Refresh details if open, to show/hide Drill button
                if state['selected_node_id']:
                    show_node_details(state['selected_node_id'])
            
            def update_temp(e):
                state['temperature'] = e.value
                app.storage.user['temperature'] = e.value

            ui.switch('Dead', value=state['show_dead'], on_change=toggle_dead).props('dense color=grey').tooltip('Show/Hide Dead Nodes')
            ui.switch('God', value=state['all_users_view'], on_change=toggle_all).props('dense color=blue').tooltip('All Users View (God Mode)')
            ui.switch('Test', value=state['test_mode'], on_change=toggle_test).props('dense color=orange').tooltip('Enable Test Mode (Always Drill)')
            
            with ui.row().classes('items-center gap-1'):
                ui.label('Temp:').classes('text-xs text-gray-400')
                ui.number(value=state['temperature'], min=0.0, max=2.0, step=0.1, on_change=update_temp).props('dense outlined style="width: 60px"').tooltip('AI Temperature')

        # Layout Reset control
        if nx:
             ui.button(icon='grid_goldenratio', on_click=lambda: (run_layout(force_reset=True), refresh_chart_ui())).props('flat round dense color=grey').tooltip('Reset Graph Layout')

    # 3. Context Panel
    # Starts hidden (visible=False). content triggers visibility.
    state['context_card'] = ui.card().classes('fixed right-6 top-6 w-96 max-h-[90vh] overflow-y-auto z-20 shadow-2xl flex flex-col gap-4 bg-slate-900/95 backdrop-blur-md border-t-4 border-primary border-x border-b border-slate-700')
    state['context_card'].set_visibility(False)
    
    with state['context_card']:
        with ui.element('div').classes('w-full h-full flex flex-col gap-4'):
            state['details_container'] = ui.column().classes('w-full gap-3')
            # Empty init


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='PRISM', port=8081, reload=True, storage_secret='prism_secret_key_123')

