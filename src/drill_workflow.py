from nicegui import ui, run
from typing import Dict, List, Any, Callable

async def start_drill_process(
    node_id: str,
    data_manager: Any,
    ai_agent: Any,
    active_user: str,
    on_complete: Callable[[], None]
):
    ui.notify("Consulting AI...", timeout=2000)
    
    # 1. Gather Context
    graph = data_manager.get_graph()
    node = next((n for n in graph.get('nodes', []) if n['id'] == node_id), None)
    if not node: return
    
    # Get existing children for dedup
    children_ids = [e['target'] for e in graph.get('edges', []) if e['source'] == node_id]
    existing_children = []
    for cid in children_ids:
        cnode = next((n for n in graph.get('nodes', []) if n['id'] == cid), None)
        if cnode: existing_children.append(cnode.get('label'))

    # 2. Call AI (IO Bound)
    try:
        candidates = await run.io_bound(
            ai_agent.generate_drill_candidates,
            node.get('label', ''),
            node.get('metadata', ''),
            existing_children
        )
    except Exception as e:
        ui.notify(f"AI Error: {e}", color='negative')
        return

    if not candidates:
        ui.notify("No ideas generated.", color='warning')
        return

    # 3. Present UI
    selection_state = {c: 'ignore' for c in candidates}

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg bg-slate-900 border border-slate-700'):
        ui.label(f"Drill Down: {node.get('label')}").classes('text-xl font-bold text-white')
        ui.label("Select ideas to add to the graph.").classes('text-sm text-gray-400')
        
        with ui.scroll_area().classes('h-64 w-full border border-slate-800 rounded p-2'):
            for suggestion in candidates:
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label(suggestion).classes('text-gray-200 text-sm')
                    # Tri-state toggles: Reject / Ignore / Accept
                    t = ui.toggle(
                        {'reject': 'X', 'ignore': '-', 'accept': 'V'}, 
                        value='ignore'
                    ).props('dense flat')
                    # Update state closure
                    t.on_value_change(lambda e, s=suggestion: selection_state.update({s: e.value}))

        def finish():
            count = 0
            count_declined = 0
            for text, status in selection_state.items():
                if status == 'accept':
                    data_manager.add_node(
                        label=text, 
                        parent_id=node_id, 
                        users=[active_user],
                        interested=True
                    )
                    count += 1
                elif status == 'reject':
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
            dialog.close()

        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('Cancel', on_click=dialog.close).props('flat color=grey')
            ui.button('Commit', on_click=finish).props('color=primary')
    
    dialog.open()
