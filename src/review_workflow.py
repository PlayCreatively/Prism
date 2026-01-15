from nicegui import ui
from typing import Callable, Any, List, Dict

def get_pending_nodes(data_manager: Any, active_user: str) -> List[Dict]:
    """
    Fetch nodes that are:
    1. Not dead (have interested users).
    2. Not rejected by ANYONE (no Veto).
    3. Not yet voted on by Active User.
    """
    graph = data_manager.get_graph()
    pending = []
    
    for node in graph.get('nodes', []):
        interested = node.get('interested_users', [])
        rejected = node.get('rejected_users', [])
        
        # Rule 1: Must have at least one interested user
        if not interested:
            continue
            
        # Rule 2: Must have ZERO rejections (Strict Consensus / Veto)
        if len(rejected) > 0:
            continue
            
        # Rule 3: Active User is not involved yet
        if active_user not in interested:
             pending.append(node)
             
    return pending

async def start_review_process(
    data_manager: Any,
    active_user: str,
    on_complete: Callable[[], None]
):
    pending = get_pending_nodes(data_manager, active_user)
    
    if not pending:
        ui.notify("No pending nodes to review.", type='info')
        return

    # Dialog State
    # We use a mutable index to track progress through the queue
    state = {'index': 0, 'queue': pending}

    with ui.dialog() as dialog, ui.card().classes('w-96 bg-slate-900 border border-slate-700'):
        
        # Container for the card content. We clear and rebuild this for each item.
        content_area = ui.column().classes('w-full gap-4')

        def render_current():
            content_area.clear()
            
            if state['index'] >= len(state['queue']):
                ui.notify("Review complete!")
                if on_complete: on_complete()
                dialog.close()
                return

            node = state['queue'][state['index']]
            
            with content_area:
                # Header
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label('Review Pending').classes('text-xs font-bold text-gray-500')
                    ui.label(f"{state['index'] + 1} / {len(state['queue'])}").classes('text-xs text-gray-400')
                
                # Card Body
                ui.label(node.get('label', 'Untitled')).classes('text-xl font-bold text-white')
                
                # Metadata (Context)
                meta = node.get('metadata', '')
                if meta:
                    ui.markdown(meta).classes('w-full bg-slate-800 p-2 rounded text-sm text-gray-300 max-h-40 overflow-y-auto')
                else:
                    ui.label('No context provided.').classes('text-sm text-gray-500 italic')
                
                # Proponents
                with ui.row().classes('gap-1'):
                    ui.label('Proposed by:').classes('text-xs text-gray-500')
                    for u in node.get('interested_users', []):
                         ui.chip(u, color='grey').props('outline size=xs')

                ui.separator().classes('my-2')
                
                # Actions
                with ui.row().classes('w-full justify-between'):
                    # Reject -> interested=False
                    ui.button('Reject', on_click=lambda: process('reject'), color='red').props('flat icon=close')
                    # Skip -> Do nothing
                    ui.button('Skip', on_click=lambda: process('skip'), color='grey').props('flat')
                    # Accept -> interested=True
                    ui.button('Accept', on_click=lambda: process('accept'), color='green').props('icon=check')

        def process(action: str):
            node = state['queue'][state['index']]
            node_id = node.get('id')
            
            if action == 'accept':
                # Use update_user_node, which handles ingesting the EXISTING node into the user's file
                data_manager.update_user_node(
                    user_id=active_user,
                    node_id=node_id,
                    interested=True
                )
                ui.notify("Accepted.")
            elif action == 'reject':
                # Use update_user_node to add the node with interested=False to the user's file
                data_manager.update_user_node(
                    user_id=active_user,
                    node_id=node_id,
                    interested=False
                )
                ui.notify("Rejected.")
            
            # Move to next
            state['index'] += 1
            
            # Only refresh UI if actual data changed (accept/reject)
            if action != 'skip' and on_complete: 
                on_complete()
                
            render_current()

        # Initial Render
        render_current()
        
    dialog.open()
