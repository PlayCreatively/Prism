"""
Edit Handlers - Event handlers for manual editing in app.py

This module extracts all the edit mode event handling from app.py
to keep the main application file focused on routing and layout.
"""

from nicegui import ui
from typing import Dict, Any, Callable

from src.edit.controller import EditController
from src.edit.overlay import EditOverlay
from src.edit.actions import EditActions


def setup_edit_handlers(
    state: Dict[str, Any],
    data_manager,
    edit_controller: EditController,
    edit_overlay: EditOverlay,
    edit_actions: EditActions,
    normalize_click_payload: Callable,
    resolve_node_id_from_payload: Callable,
    refresh_chart_ui: Callable,
    reset_selection: Callable,
    check_git_status: Callable,
):
    """
    Set up all edit mode event handlers.
    
    Args:
        state: App state dictionary
        data_manager: DataManager instance
        edit_controller: EditController instance
        edit_overlay: EditOverlay instance
        edit_actions: EditActions instance
        normalize_click_payload: Function to normalize chart event payloads
        resolve_node_id_from_payload: Function to resolve node IDs from payloads
        refresh_chart_ui: Function to refresh the chart display
        reset_selection: Function to clear node selection
        check_git_status: Function to check git status
        
    Returns:
        Dict with handler functions for binding to UI events
    """
    
    def on_edit_state_change(edit_state):
        """Called whenever edit controller state changes - update overlay."""
        edit_overlay.update(edit_state)
    
    edit_controller.set_on_state_change(on_edit_state_change)
    
    def sync_controller_data():
        """Sync graph data to edit controller. Positions come from ECharts via JS."""
        graph = data_manager.get_graph()
        
        node_sizes = {}
        for node in graph.get('nodes', []):
            nid = node.get('id')
            users = node.get('interested_users', [])
            size = 20 + (5 * len(users))
            node_sizes[nid] = size
        
        edit_controller.update_graph_data(
            nodes=graph.get('nodes', []),
            edges=graph.get('edges', []),
            positions={},  # Not used - JS fetches live from ECharts
            node_sizes=node_sizes,
            active_user=state['active_user']
        )
        edit_overlay.set_active_user(state['active_user'])
        
        ui.run_javascript('if (window.updateEditOverlayPositions) window.updateEditOverlayPositions();')
    
    def handle_keyboard(e):
        """Track Ctrl key state for manual editing mode."""
        if e.key == 'Control':
            prev_state = state.get('is_ctrl_pressed', False)
            is_pressed = e.action.keydown
            state['is_ctrl_pressed'] = is_pressed
            
            if is_pressed and not prev_state:
                sync_controller_data()
                ui.notify('Manual edit mode active', position='bottom', timeout=500, color='info')
            
            edit_controller.set_ctrl_pressed(is_pressed)
    
    def handle_mouse_move(event):
        """Track mouse position for preview calculations."""
        if not state.get('is_ctrl_pressed'):
            return
            
        raw = event.args if hasattr(event, 'args') else event
        
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            x, y = raw[0], raw[1]
        elif isinstance(raw, dict):
            x = raw.get('offsetX', raw.get('x', 0))
            y = raw.get('offsetY', raw.get('y', 0))
        else:
            return
        
        state['mouse_position'] = (x, y)
        edit_controller.set_mouse_position(x, y)
    
    def handle_mouse_down(event):
        """Detect drag start on nodes."""
        if not state.get('is_ctrl_pressed'):
            return
        
        raw = event.args if hasattr(event, 'args') else event
        payload = normalize_click_payload(raw)
        
        try:
            node_id = resolve_node_id_from_payload(payload, data_manager)
            if node_id:
                state['dragging_node_id'] = node_id
                edit_controller.start_drag(node_id)
        except Exception:
            pass
    
    async def handle_mouse_up(event):
        """Execute manual edit action on mouse release."""
        if not state.get('is_ctrl_pressed'):
            state['dragging_node_id'] = None
            return
        
        try:
            js_action = await ui.run_javascript('''
                return window.editOverlayState?.lastAction || null;
            ''')
        except Exception as e:
            print(f"Error querying JS action: {e}")
            js_action = None
        
        if js_action and js_action.get('action'):
            try:
                action = js_action['action']
                preview_pos = js_action.get('preview_position', [0, 0])
                data_pos = js_action.get('data_position')
                target_edge = js_action.get('target_edge')
                target_node_id = js_action.get('target_node_id')
                dragging_node_id = state.get('dragging_node_id')
                
                preview_state = {'action': action}
                
                if data_pos:
                    preview_state['data_position'] = tuple(data_pos)
                
                if action == 'create_node':
                    preview_state['new_node_pos'] = tuple(preview_pos)
                    
                elif action == 'create_and_connect':
                    preview_state['new_node_pos'] = tuple(preview_pos)
                    preview_state['target_id'] = target_node_id
                    
                elif action == 'create_intermediary':
                    preview_state['new_node_pos'] = tuple(preview_pos)
                    preview_state['source_id'] = target_edge[0] if target_edge else None
                    preview_state['target_id'] = target_edge[1] if target_edge else None
                    
                elif action == 'delete_node':
                    preview_state['target_node_id'] = target_node_id
                    
                elif action == 'make_intermediary':
                    preview_state['dragging_node_id'] = dragging_node_id
                    preview_state['source_id'] = target_edge[0] if target_edge else None
                    preview_state['target_id'] = target_edge[1] if target_edge else None
                    
                elif action == 'connect':
                    preview_state['action'] = 'connect_nodes'
                    preview_state['source_id'] = dragging_node_id
                    preview_state['target_id'] = target_node_id
                    
                elif action == 'cut_edge':
                    preview_state['source_id'] = target_edge[0] if target_edge else None
                    preview_state['target_id'] = target_edge[1] if target_edge else None
                
                edit_actions.commit_preview_action(
                    preview_state,
                    state['active_user']
                )
                
                if action == 'delete_node' and target_node_id:
                    if state.get('selected_node_id') == target_node_id:
                        reset_selection()
                
                ui.notify('Edit applied', type='positive', position='bottom', timeout=1000)
                ui.timer(0.5, check_git_status, once=True)
                
                refresh_chart_ui()
                sync_controller_data()
                
            except Exception as e:
                ui.notify(f'Edit failed: {e}', type='negative', position='bottom')
                import traceback
                traceback.print_exc()
        
        state['dragging_node_id'] = None
        edit_controller.end_drag()
    
    return {
        'handle_keyboard': handle_keyboard,
        'handle_mouse_move': handle_mouse_move,
        'handle_mouse_down': handle_mouse_down,
        'handle_mouse_up': handle_mouse_up,
        'sync_controller_data': sync_controller_data,
    }
