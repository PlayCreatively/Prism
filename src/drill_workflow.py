from nicegui import ui, run
from typing import Dict, List, Any, Callable
from src.ui_common import render_tri_state_buttons

async def start_drill_process(
    node_id: str,
    data_manager: Any,
    ai_agent: Any,
    active_user: str,
    on_complete: Callable[[], None],
    temperature: float = 1.0,
    container: Any = None
):
    if container:
        container.clear()
        with container:
             ui.spinner('dots', size='lg').classes('w-full text-center')
             ui.label("Consulting AI...").classes('w-full text-center text-gray-500 animate-pulse')
    else:
        ui.notify("Consulting AI...", timeout=2000)
    
    # 1. Gather Context
    graph = data_manager.get_graph()
    node = next((n for n in graph.get('nodes', []) if n['id'] == node_id), None)
    if not node: 
        if container: on_complete()
        return
    
    # Get existing children for dedup
    children_ids = [e['target'] for e in graph.get('edges', []) if e['source'] == node_id]
    existing_children = []
    for cid in children_ids:
        cnode = next((n for n in graph.get('nodes', []) if n['id'] == cid), None)
        if cnode: existing_children.append(cnode.get('label'))

    # Gather metadata from ALL users to give AI full context
    combined_notes = []
    all_users = data_manager.list_users()
    for user in all_users:
        u_node = data_manager.get_user_node(user, node_id)
        if u_node and u_node.get('metadata'):
            combined_notes.append(f"[{user}]: {u_node['metadata']}")
    
    full_context_str = "\n".join(combined_notes) if combined_notes else ""

    # 2. Call AI (IO Bound)
    try:
        candidates = await run.io_bound(
            ai_agent.generate_drill_candidates,
            node.get('label', ''),
            full_context_str,
            existing_children,
            temperature
        )
    except Exception as e:
        ui.notify(f"AI Error: {e}", color='negative')
        if container:
             container.clear()
             with container:
                  ui.label(f"AI Error: {e}").classes('text-red-500')
                  ui.button('Back', on_click=on_complete).props('flat')
        return

    if not candidates:
        ui.notify("No ideas generated.", color='warning')
        if container:
             container.clear()
             with container:
                  ui.label("No ideas generated.").classes('text-warning')
                  ui.button('Back', on_click=on_complete).props('flat')
        return

    # 3. Present UI
    # Default to 'maybe' (which was 'ignore')
    selection_state = {c: 'maybe' for c in candidates}
    
    def render_interface(parent, dialog_ref=None):
        with parent:
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(f"Drill: {node.get('label')[:15]}...").classes('text-lg font-bold text-white')
                if not dialog_ref:
                     pass 

            ui.label("Select ideas to add.").classes('text-xs text-gray-400 mb-2')
            
            
            def render_row(suggestion):
                 with ui.row().classes('w-full items-center justify-between mb-2 bg-slate-800/40 p-2 rounded border border-slate-700/50'):
                    ui.label(suggestion).classes('text-gray-200 text-sm flex-1 mr-2 leading-tight').style('word-wrap: break-word')
                    
                    # Direct mapping: UI component returns 'accepted'/'rejected'/'maybe'
                    def on_change(new_val):
                        selection_state[suggestion] = new_val

                    render_tri_state_buttons(selection_state[suggestion], on_change)

            with ui.scroll_area().classes('h-96 w-full border border-slate-700 rounded p-2 bg-slate-900'):
                for suggestion in candidates:
                    render_row(suggestion)

            def finish():
                count = 0
                count_declined = 0
                for text, status in selection_state.items():
                    if status == 'accepted':
                        data_manager.add_node(
                            label=text, 
                            parent_id=node_id, 
                            users=[active_user],
                            interested=True
                        )
                        count += 1
                    elif status == 'rejected':
                        data_manager.add_node(
                            label=text, 
                            parent_id=node_id, 
                            users=[active_user],
                            interested=False
                        )
                        count_declined += 1
                
                ui.notify(f"Added {count} nodes. Recorded {count_declined} rejections.")
                if on_complete:
                    on_complete()
                if dialog_ref:
                    dialog_ref.close()

            with ui.row().classes('w-full justify-end mt-4 gap-2'):
                if dialog_ref:
                     ui.button('Cancel', on_click=dialog_ref.close).props('flat color=grey')
                else:
                     ui.button('Cancel', on_click=on_complete).props('flat color=grey')
                
                ui.button('Commit', on_click=finish).props('color=primary')

    if container:
        container.clear()
        render_interface(container)
    else:
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg bg-slate-900 border border-slate-700') as card:
             render_interface(card, dialog_ref=dialog)
        dialog.open()
