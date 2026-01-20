"""
Main NiceGUI application for PRISM.
Integrates DataManager and DrillEngine, renders the graph with ui.echart,
and provides interaction controls with ui.card / ui.row.

This file attempts to import the project modules from src.*. If those imports
fail (for example in isolated test environments), lightweight fallback
implementations are provided so the app can still start for testing.
"""

from nicegui import ui, run, app
import sys
import time
import asyncio
try:
    import networkx as nx
except ImportError:
    nx = None

from dotenv import load_dotenv
load_dotenv()
import multiprocessing

# Path and config initialization
from src.paths import ensure_db_dir
from src.config import get_api_key, set_api_key, validate_api_key, ensure_api_key_in_env

# Ensure required directories exist on startup
ensure_db_dir()

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
        
        h1, h2, h3, h4, h5, h6 {
            margin-top: 8px;
            margin-bottom: 0;
        }
        
        div :is(h1, h2, h3, h4, h5, h6):first-of-type {
            margin-top: 0;
        }
    </style>
''', shared=True)

from src.data_manager import DataManager
from src.drill_engine import DrillEngine
from src.node_type_manager import get_node_type_manager
from src.custom_fields import render_custom_fields
from src.components import render_markdown_textarea

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
    from src.git_manager import GitManager, GitError
except ImportError:
    print("GitManager missing")
    GitManager = None
    GitError = None

try:
    from src.graph_viz import node_to_echart_node  # optional helper
except Exception:
    # We'll build our own conversion below if helper not present.
    node_to_echart_node = None

from src.utils import get_all_users, get_visible_users, get_hidden_users, toggle_user_visibility, get_user_color
from src.ui_common import render_tri_state_buttons, render_editable_notes, render_other_users_notes
from src.edit import EditController, EditOverlay, EditActions, setup_edit_handlers
from src.chart_builder import build_echart_options, normalize_click_payload, resolve_node_id_from_payload, REQUESTED_EVENT_KEYS
from src.project_manager import (
    list_projects, 
    project_exists, 
    get_project_data_dir, 
    get_project_git_path,
    create_project,
    get_project_users,
    add_user_to_project
)


# Note: DataManager, DrillEngine, and GitManager are now initialized per-project
# inside the page function to support multi-project switching

# Check for API key and load into environment
if not ensure_api_key_in_env():
    print("[PRISM] No API key found. User will be prompted on first page load.")

# AI Agent is global (stateless) - initialized after API key is potentially loaded
ai_agent = AIAgent()



# Helper to show API key setup dialog
def show_api_key_dialog(on_complete=None, is_required=False):
    """Show modal dialog to configure OpenAI API key."""
    with ui.dialog() as dialog, ui.card().classes('w-[500px]'):
        if is_required:
            ui.label('API Key Required').classes('text-xl font-bold text-primary')
            ui.label('PRISM needs an OpenAI API key to generate ideas.').classes('text-gray-400 mb-2')
        else:
            ui.label('Configure API Key').classes('text-lg font-bold')
        
        current_key = get_api_key()
        masked_key = f"{current_key[:7]}...{current_key[-4:]}" if current_key and len(current_key) > 15 else ""
        
        if masked_key:
            ui.label(f'Current key: {masked_key}').classes('text-gray-500 text-sm mb-2')
        
        api_key_input = ui.input(
            'OpenAI API Key', 
            placeholder='sk-...',
            password=True,
            password_toggle_button=True
        ).classes('w-full')
        
        status_label = ui.label('').classes('text-sm')
        
        async def do_validate():
            key = api_key_input.value.strip()
            if not key:
                status_label.text = '❌ Please enter an API key'
                status_label.classes('text-red-500', remove='text-green-500 text-yellow-500')
                return
            
            status_label.text = '⏳ Validating...'
            status_label.classes('text-yellow-500', remove='text-red-500 text-green-500')
            
            # Run validation in background to not block UI
            is_valid, message = validate_api_key(key)
            
            if is_valid:
                status_label.text = f'✅ {message}'
                status_label.classes('text-green-500', remove='text-red-500 text-yellow-500')
                set_api_key(key)
                ui.notify('API key saved successfully!', type='positive')
                await asyncio.sleep(1)
                dialog.close()
                if on_complete:
                    on_complete()
            else:
                status_label.text = f'❌ {message}'
                status_label.classes('text-red-500', remove='text-green-500 text-yellow-500')
        
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            if not is_required:
                ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Validate & Save', on_click=do_validate).props('color=primary')
    
    dialog.open()
    return dialog


# Helper to show create project dialog
def show_create_project_dialog(on_created=None, is_first_project=False):
    """Show modal dialog to create a new project."""
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        if is_first_project:
            ui.label('Welcome to PRISM!').classes('text-xl font-bold text-primary')
            ui.label('Create your first project to get started.').classes('text-gray-400 mb-4')
        else:
            ui.label('Create New Project').classes('text-lg font-bold')
        
        project_name_input = ui.input('Project Name', placeholder='e.g., Research-Collab').classes('w-full')
        username_input = ui.input('Your Username', placeholder='e.g., Alex').classes('w-full')
        root_label_input = ui.input('Root Node Label', placeholder='e.g., Main Thesis').classes('w-full')
        root_desc_input = ui.textarea('Root Node Description (optional)').classes('w-full').props('outlined rows=2')
        
        error_label = ui.label('').classes('text-red-500 text-sm')
        
        def do_create():
            result = create_project(
                project_name=project_name_input.value,
                initial_username=username_input.value,
                root_node_label=root_label_input.value,
                root_node_description=root_desc_input.value or ""
            )
            if result['success']:
                ui.notify(result['message'], type='positive')
                dialog.close()
                if on_created:
                    on_created(project_name_input.value.strip())
            else:
                error_label.text = result['message']
        
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            if not is_first_project:
                ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Create Project', on_click=do_create).props('color=primary')
    
    dialog.open()
    return dialog


# UI Construction - encapsulated in page function to avoid global state issues
@ui.page('/')
def main_page():
    ui.dark_mode().enable()
    ui.query('body').style('margin: 0; padding: 0; overflow: hidden;')
    
    # --- API Key Check ---
    # Show setup dialog if no API key is configured
    if not get_api_key():
        with ui.column().classes('fixed inset-0 flex items-center justify-center bg-slate-900 z-50'):
            with ui.card().classes('w-[500px] p-8'):
                ui.icon('key', size='xl').classes('text-primary mb-4')
                ui.label('API Key Required').classes('text-2xl font-bold text-white')
                ui.label('PRISM needs an OpenAI API key to generate ideas.').classes('text-gray-400 mb-4')
                ui.label('Your key will be stored locally in config.json').classes('text-gray-500 text-sm mb-4')
                
                api_key_input = ui.input(
                    'OpenAI API Key', 
                    placeholder='sk-...',
                    password=True,
                    password_toggle_button=True
                ).classes('w-full')
                
                status_label = ui.label('').classes('text-sm mt-2')
                
                async def do_validate_and_continue():
                    key = api_key_input.value.strip()
                    if not key:
                        status_label.text = '❌ Please enter an API key'
                        status_label.classes('text-red-500', remove='text-green-500 text-yellow-500')
                        return
                    
                    status_label.text = '⏳ Validating...'
                    status_label.classes('text-yellow-500', remove='text-red-500 text-green-500')
                    
                    is_valid, message = validate_api_key(key)
                    
                    if is_valid:
                        status_label.text = f'✅ {message}'
                        status_label.classes('text-green-500', remove='text-red-500 text-yellow-500')
                        set_api_key(key)
                        ui.notify('API key saved! Reloading...', type='positive')
                        await asyncio.sleep(1)
                        ui.navigate.to('/')  # Reload to continue setup
                    else:
                        status_label.text = f'❌ {message}'
                        status_label.classes('text-red-500', remove='text-green-500 text-yellow-500')
                
                ui.button('Validate & Continue', on_click=do_validate_and_continue).props('color=primary size=lg').classes('mt-4')
        return  # Don't render the rest until API key is set
    
    # --- Project Selection ---
    # Check for available projects
    available_projects = list_projects()
    
    # Get stored project preference
    stored_project = app.storage.user.get('active_project')
    
    # Validate stored project still exists
    if stored_project and stored_project not in available_projects:
        stored_project = None
    
    # If no valid project, use first available or None
    current_project = stored_project or (available_projects[0] if available_projects else None)
    
    # Handle case where no projects exist - show welcome screen
    if not current_project:
        with ui.column().classes('fixed inset-0 flex items-center justify-center bg-slate-900'):
            with ui.card().classes('w-96 p-8'):
                ui.icon('hub', size='xl').classes('text-primary mb-4')
                ui.label('Welcome to PRISM').classes('text-2xl font-bold text-white')
                ui.label('Collaborative Consensus & Interest Mapping').classes('text-gray-400 mb-6')
                ui.label('No projects found. Create your first project to get started.').classes('text-gray-300 mb-4')
                
                def handle_project_created(project_name):
                    app.storage.user['active_project'] = project_name
                    ui.navigate.to('/')  # Reload page
                
                ui.button('Create First Project', on_click=lambda: show_create_project_dialog(
                    on_created=handle_project_created,
                    is_first_project=True
                )).props('color=primary size=lg')
        return  # Don't render the rest of the app
    
    # --- Project-specific initialization ---
    project_data_dir = get_project_data_dir(current_project)
    project_git_path = get_project_git_path(current_project)
    
    # Initialize project-specific managers
    data_manager = DataManager(data_dir=project_data_dir)
    drill_engine = DrillEngine(users=get_all_users(project_data_dir))
    
    # Initialize data for the project
    if multiprocessing.current_process().name == 'MainProcess':
        try:
            # Cleanup orphan nodes (nodes with zero votes from any user)
            if hasattr(data_manager, 'cleanup_orphan_nodes'):
                orphan_count = data_manager.cleanup_orphan_nodes()
                if orphan_count > 0:
                    print(f"[{current_project}] Cleaned up {orphan_count} orphan nodes")
            
            g = data_manager.get_graph()
            print(f"[{current_project}] Graph: {len(g.get('nodes', []))} nodes, {len(g.get('edges', []))} edges")
        except Exception as e:
            print(f"[{current_project}] Error loading data: {e}")
    
    # --- State & Closures ---
    
    # Determine default active user dynamically (for this project)
    all_users_list = get_all_users(project_data_dir)
    stored_user = app.storage.user.get('active_user')
    # Validate stored user still exists in this project, otherwise pick first available
    default_active_user = stored_user if stored_user in all_users_list else (all_users_list[0] if all_users_list else None)
    
    # We use a container for mutable state to be accessible in closures
    state = {
        'selected_node_id': None,
        'chart': None,
        'details_container': None,
        'last_graph_hash': 0,
        'active_user': default_active_user,
        'active_project': current_project,
        'show_dead': app.storage.user.get('show_dead', False),
        'last_selection_time': 0,
        'temperature': app.storage.user.get('temperature', 0.7),
        'is_ctrl_pressed': False,
        'mouse_position': (0, 0),
        'dragging_node_id': None,
        'edit_controller': EditController(),
        'edit_overlay': EditOverlay(),
        'edit_actions': EditActions(data_manager)
    }

    # --- Git State & Logic ---
    git_btn_ref = {}
    
    # Create git_manager for this project's repository
    git_manager = GitManager(repo_path=project_git_path) if GitManager else None

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
            error_msg = str(e)
            print(f"Git check error: {e}")
            ui.notify(
                f'Git status check failed: {error_msg}',
                type='warning',
                position='bottom-right',
                timeout=5000,
                close_button=True
            )

    async def do_git_push():
        if not git_manager: return
        user = state['active_user']
        ui.notify(f'Pushing changes for {user}...', position='bottom-right')
        try:
             await run.io_bound(git_manager.push_changes_for_user, user)
             ui.notify('Published to team!', type='positive', position='bottom-right')
             await check_git_status()
             if (user == 'Alex' or user == 'Sasha'):
                ui.notify(f'Don\'t forget to copy/paste your files, {user}! ', type='warning', position='bottom-right')
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
             # Show notification for pull failures - but throttle to avoid spam
             error_msg = str(e)
             print(f"Git auto-pull failed: {e}")
             # Only show notification if verbose (initial load) or if it's a critical error
             if verbose or (GitError and isinstance(e, GitError)):
                 ui.notify(
                     f'Git sync failed: {error_msg}',
                     type='warning',
                     position='bottom-right',
                     timeout=8000,
                     close_button=True
                 )

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
            data_dir=project_data_dir,
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
                active_user = state.get('active_user')
                count = len(get_pending_nodes(data_manager, active_user)) if active_user else 0
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
        # Default to first available user if something goes wrong
        all_users = get_all_users(project_data_dir)
        default_user = all_users[0] if all_users else None
        state['active_user'] = user or default_user
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
            # If there was a very recent mouse-down (tiny drag/hold), ignore
            # the background click to avoid unintentionally clearing selection.
            recent_md = time.time() - state.get('last_mouse_down_time', 0)
            if recent_md and recent_md > 0.1:
                print(f"Ignoring background click after recent mouse-down ({recent_md:.3f}s). Keeping selection.")
                return
                
            # Check if this is a "ghost" click immediately after a valid selection
            # This happens because 'click' events often fire after 'componentClick' events
            gap = time.time() - state.get('last_selection_time', 0)
            if gap < 0.05:
                print("Ignoring background click immediately after selection (ghost click)")
                return

            print("No node_id found in click (Background or Edge). Clearing selection.")
            reset_selection()
    
    
    def set_vote(node_id, status, user=None):
        """
        Sets the vote status for a user.
        status: 'accepted' | 'rejected' | 'maybe'
        
        'maybe' sets interested=None (pending) but preserves any existing metadata.
        """
        if user is None:
            user = state.get('active_user')
        if not user:
            ui.notify('No active user selected', type='warning')
            return
        try:
            if status == 'maybe':
                # Set interested to None (pending) but preserve metadata
                data_manager.update_user_node(user, node_id, interested=None)
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
    
    
    def toggle_interest(node_id, user=None):
        """Deprecated: Use set_vote instead"""
        if user is None:
            user = state.get('active_user')
        # ... logic preserved if any legacy calls remain, but redirecting to set_vote is safer
        # For now, implemented as compatibility wrapper if clicked blindly
        pass
        
    async def do_drill_action(node_id, prompt_filename: str = 'drill_down.md'):
        active_user = state.get('active_user')
        if not active_user:
            ui.notify('No active user selected', type='warning')
            return
        await start_drill_process(
            node_id=node_id,
            data_manager=data_manager,
            ai_agent=ai_agent,
            active_user=active_user,
            on_complete=refresh_chart_ui,
            temperature=state.get('temperature', 0.7),
            prompt_filename=prompt_filename
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
        
        User data is only saved when:
        - User has an explicit vote (interested key is present), OR
        - User has written non-empty metadata, OR
        - User already has an existing entry for this node
        """
        active_user = state.get('active_user')
        if not active_user:
            ui.notify('No active user selected', type='warning')
            return
        
        # Split changes
        shared_upd = {}
        user_upd = {}
        
        for k, v in changes.items():
            if k in ['label', 'parent_id', 'description']:
                shared_upd[k] = v
            elif k in ['metadata', 'interested']:
                user_upd[k] = v
            else:
                # Custom fields go to shared node data
                shared_upd[k] = v
        
        try:
            if shared_upd:
                data_manager.update_shared_node(node_id, **shared_upd)
            
            if user_upd:
                # Check if we should update user data:
                # - If there's an explicit vote (interested key), always update
                # - If metadata is non-empty, update
                # - If user already has an entry for this node, update (to potentially clear values)
                # 
                # update_user_node handles cleanup:
                # - Empty metadata is removed (absence = blank)
                # - interested=None removes the key (absence = pending)
                # - If both are absent, the entire node entry is removed
                has_explicit_vote = 'interested' in user_upd
                has_metadata = user_upd.get('metadata', '').strip() != ''
                user_already_has_entry = data_manager.get_user_node(active_user, node_id) is not None
                
                if has_explicit_vote or has_metadata or user_already_has_entry:
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
        active_user = state.get('active_user')
        user_node = data_manager.get_user_node(active_user, node_id) if active_user else None
        
        # Display logic needs valid generic_node at minimum
        if not generic_node:
            with container:
                ui.label('Node not found').classes('text-red-500')
            return
            
        # Use user-specific values if available
        # interested can be: True (accepted), False (rejected), None (pending with notes)
        # If user_node is MISSING, they are effectively 'pending' (haven't interacted at all).
        
        interested_value = user_node.get('interested') if user_node else None
        
        if interested_value is True:
             status_label = "accepted"
             status_color = "green"
        elif interested_value is False:
             status_label = "rejected"
             status_color = "red"
        else:
             # None or missing = pending (whether they have notes or not)
             status_label = "pending"
             status_color = "grey"

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
                    
                    # Get all users and their dynamic colors
                    all_users = get_all_users(project_data_dir)
                    visible_users = get_visible_users(project_data_dir)

                    for user in all_users:
                        # Get user's dynamic color
                        user_color = get_user_color(user, visible_users, project_data_dir)
                        
                        if user in interested_set:
                            with ui.chip(icon='check', color='green').props('outline size=sm'):
                                ui.label(user).style(f'color: {user_color}')
                        elif user in rejected_set:
                            with ui.chip(icon='close', color='red').props('outline size=sm'):
                                ui.label(user).style(f'color: {user_color}')
                        else:
                            # Grayed out / Question mark
                            with ui.chip(icon='help_outline', color='grey').props('outline size=sm').classes('opacity-40'):
                                ui.label(user).classes('text-gray-400')  # Gray for pending/unknown state

            # Description (shared across all users) - rendered after schedule_save is defined
            description_container = ui.column().classes('w-full')
            description_value = {'text': generic_node.get('description', '')}

            # --- Prepare custom fields data (render after schedule_save is defined) ---
            node_type = generic_node.get('node_type', 'default')
            node_type_manager = get_node_type_manager()
            type_def = node_type_manager.load_type(node_type)
            custom_fields = type_def.get('fields', []) if type_def else []
            all_users_list = get_all_users(project_data_dir)
            
            # Placeholder for custom field values - will be populated after schedule_save is defined
            custom_field_values = {}

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
                
                new_description = description_value['text']
                
                # Include custom field values in the save
                persist_node_changes(node_id, label=final_label, description=new_description, metadata=current_metadata, **custom_field_values)
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

            # --- Description Field (rendered after schedule_save is available) ---
            with description_container:
                def on_description_change(new_val):
                    description_value['text'] = new_val
                    schedule_save()
                
                render_markdown_textarea(
                    value=description_value['text'],
                    label='DESCRIPTION',
                    placeholder='Click to add description...',
                    on_change=on_description_change
                )

            # --- Custom Fields Section (rendered after schedule_save is available) ---
            if custom_fields:
                render_custom_fields(
                    fields=custom_fields,
                    node_data=generic_node,
                    schedule_save=schedule_save,
                    all_users=all_users_list,
                    values_dict=custom_field_values
                )

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
                data_manager=data_manager,
                users=all_users_list
            )
            
            save_status = ui.label('').classes('text-xs text-green-500 italic mt-1')
            # Bind label input to auto-save
            # IMPORTANT: We must accept the 'e' argument in lambda, even if unused, 
            # because on_value_change passes an event object.
            label_input.on_value_change(lambda e: schedule_save(e))


            # Actions - Dynamic Prompt Buttons
            ui.label('ACTIONS').classes('text-xs font-bold text-gray-400 mt-4')
            with ui.row().classes('w-full gap-2 flex-wrap'):
                # Get node type and load its prompts
                node_type = generic_node.get('node_type', 'default')
                node_type_manager = get_node_type_manager()
                prompts = node_type_manager.load_prompts(node_type)
                
                # Render a button for each prompt
                for prompt in prompts:
                    prompt_filename = prompt['filename']
                    prompt_name = prompt['name']
                    prompt_icon = prompt.get('material_logo', 'smart_toy')
                    prompt_desc = prompt.get('description', '')
                    
                    # Create button with closure to capture prompt_filename
                    def make_handler(pf):
                        return lambda: do_drill_action(node_id, pf)
                    
                    btn = ui.button(prompt_name, on_click=make_handler(prompt_filename)).props(f'icon={prompt_icon}')
                    if prompt_desc:
                        btn.tooltip(prompt_desc)
            
            # Voting row
            with ui.row().classes('w-full gap-2 justify-end mt-2'):
                # Determine current vote state for visual highlighting
                # interested can be True, False, or None
                interested_val = user_node.get('interested') if user_node else None
                if interested_val is True:
                    curr_vote = 'accepted'
                elif interested_val is False: 
                    curr_vote = 'rejected'
                else:
                    curr_vote = 'maybe'
                
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
                    
                    // Intentionally do NOT force-set `center`/`zoom` here.
                    // Forcing an initial center can be reapplied during later
                    // option merges and cause the viewport to jump to (0,0).
                    console.log('PRISM: Chart ready — skipping forced initial center/zoom to preserve user viewport');
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
        
        ui.separator().props('vertical')
        
        # --- Project Selector ---
        def handle_project_change(project_name):
            if project_name == '__create_new__':
                # Show create project dialog
                def on_project_created(new_project):
                    app.storage.user['active_project'] = new_project
                    ui.navigate.to('/')  # Reload page
                show_create_project_dialog(on_created=on_project_created, is_first_project=False)
            else:
                app.storage.user['active_project'] = project_name
                ui.navigate.to('/')  # Reload page to switch project
        
        # Build project options
        project_options = {p: p for p in available_projects}
        
        project_select = ui.select(
            project_options,
            value=current_project,
            label='Project'
        ).props('dense outlined').classes('w-48')
        project_select.on('update:model-value', lambda e: handle_project_change(project_select.value))
        
        ui.button(icon='add', on_click=lambda: handle_project_change('__create_new__')).props('flat dense round color=primary').tooltip('Create New Project')
        
        ui.separator().props('vertical')
        
        # --- User Selector ---
        # "Acting as User" dropdown - dynamically populated
        all_users = get_all_users(project_data_dir)
        default_user = state['active_user'] if state['active_user'] in all_users else (all_users[0] if all_users else None)
        if default_user and default_user != state['active_user']:
            state['active_user'] = default_user
            app.storage.user['active_user'] = default_user
        
        user_select = ui.select(
            all_users,
            value=state['active_user'],
            label='Acting as User'
        ).props('dense outlined').classes('w-32')
        user_select.on('update:model-value', lambda e: set_active_user(user_select.value))
        
        # Add User button
        def show_add_user_dialog():
            with ui.dialog() as dialog, ui.card().classes('w-80'):
                ui.label('Add User to Project').classes('text-lg font-bold')
                username_input = ui.input('Username', placeholder='e.g., NewUser').classes('w-full')
                error_label = ui.label('').classes('text-red-500 text-sm')
                
                def do_add_user():
                    result = add_user_to_project(current_project, username_input.value)
                    if result['success']:
                        ui.notify(result['message'], type='positive')
                        dialog.close()
                        ui.navigate.to('/')  # Reload to show new user
                    else:
                        error_label.text = result['message']
                
                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=dialog.close).props('flat')
                    ui.button('Add User', on_click=do_add_user).props('color=primary')
            dialog.open()
        
        ui.button(icon='person_add', on_click=show_add_user_dialog).props('flat dense round color=primary').tooltip('Add User to Project')
        
        # User Visibility Filter dropdown
        def build_user_filter_options():
            """Build options for user visibility filter with colored labels."""
            all_u = get_all_users(project_data_dir)
            visible_u = get_visible_users(project_data_dir)
            hidden_u = get_hidden_users()
            options = []
            for u in all_u:
                is_hidden = u in hidden_u
                color = '#808080' if is_hidden else get_user_color(u, visible_u, project_data_dir)
                options.append({'label': u, 'value': u, 'color': color, 'hidden': is_hidden})
            return options
        
        # Custom filter dropdown using expansion
        with ui.dropdown_button('Filter Users', icon='filter_alt').props('flat dense color=secondary'):
            filter_container = ui.column().classes('gap-0 min-w-32')
            
            def rebuild_filter_ui():
                filter_container.clear()
                all_u = get_all_users(project_data_dir)
                visible_u = get_visible_users(project_data_dir)
                hidden_u = get_hidden_users()
                
                if not all_u:
                    with filter_container:
                        ui.label('No users found').classes('text-gray-400 text-sm p-2')
                    return
                
                with filter_container:
                    for u in all_u:
                        is_hidden = u in hidden_u
                        color = '#808080' if is_hidden else get_user_color(u, visible_u, project_data_dir)
                        
                        def make_toggle_handler(user_id):
                            def handler():
                                toggle_user_visibility(user_id)
                                rebuild_filter_ui()
                                refresh_chart_ui()
                            return handler
                        
                        with ui.item(on_click=make_toggle_handler(u)).classes('cursor-pointer'):
                            with ui.item_section().props('avatar'):
                                ui.icon('visibility' if not is_hidden else 'visibility_off').style(f'color: {color}')
                            with ui.item_section():
                                ui.label(u).style(f'color: {color}')
            
            rebuild_filter_ui()
        
        # Git Push Button (Context sensitive)
        with ui.button(on_click=do_git_push).props('flat dense color=accent icon=cloud_upload').classes('hidden') as btn:
            btn.tooltip('Push local changes')
            git_btn_ref['btn'] = btn

        # --- Global Controls ---
        ui.separator().props('vertical')
        
        # Review Pending Button (Placeholder for now)
        async def do_review():
             active_user = state.get('active_user')
             if not active_user:
                 ui.notify('No active user selected', type='warning')
                 return
             await start_review_process(
                 data_manager, 
                 active_user, 
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
            
            def update_temp(e):
                state['temperature'] = e.value
                app.storage.user['temperature'] = e.value

            ui.switch('Dead', value=state['show_dead'], on_change=toggle_dead).props('dense color=grey').tooltip('Show/Hide Dead Nodes')
            
            with ui.row().classes('items-center gap-1'):
                ui.label('Temp:').classes('text-xs text-gray-400')
                ui.number(value=state['temperature'], min=0.0, max=2.0, step=0.1, on_change=update_temp).props('dense outlined style="width: 60px"').tooltip('AI Temperature')

    # 3. Context Panel
    # Starts hidden (visible=False). content triggers visibility.
    state['context_card'] = ui.card().classes('fixed right-6 top-6 w-96 max-h-[90vh] overflow-y-auto z-20 shadow-2xl flex flex-col gap-4 bg-slate-900/95 backdrop-blur-md border-t-4 border-primary border-x border-b border-slate-700')
    state['context_card'].set_visibility(False)
    
    with state['context_card']:
        with ui.element('div').classes('w-full h-full flex flex-col gap-4'):
            state['details_container'] = ui.column().classes('w-full gap-3')
            # Empty init


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title='PRISM',
        port=8081,
        reload=not getattr(sys, 'frozen', False),
        storage_secret='prism_secret_key_123',
        # native=True,  # Run as native desktop app
        # window_size=(1280, 720),
        # fullscreen=True,
    )

