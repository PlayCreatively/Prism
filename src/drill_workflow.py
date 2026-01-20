from nicegui import ui, run
from typing import Dict, List, Any, Callable, Tuple, Optional
from src.ui_common import render_tri_state_buttons
from src.node_type_manager import get_node_type_manager
from src.components import render_markdown_textarea

def build_ancestry_chain(node_id: str, graph: Dict[str, Any]) -> str:
    """Build full ancestry chain from root to current node (e.g., 'game design → minimalism → functional minimalism')"""
    nodes_by_id = {n['id']: n for n in graph.get('nodes', [])}
    edges_by_target = {e['target']: e['source'] for e in graph.get('edges', [])}
    
    chain = []
    current_id = node_id
    while current_id in nodes_by_id:
        node = nodes_by_id[current_id]
        chain.insert(0, node.get('label', 'Untitled'))
        current_id = edges_by_target.get(current_id)
        if not current_id:
            break
    
    return " → ".join(chain)

def separate_approved_rejected(
    children_ids: List[str], 
    graph: Dict[str, Any], 
    data_manager: Any, 
    active_user: str
) -> Tuple[List[str], List[str]]:
    """Separate children into approved (interested: true) and rejected (interested: false)"""
    approved = []
    rejected = []
    
    for cid in children_ids:
        cnode = next((n for n in graph.get('nodes', []) if n['id'] == cid), None)
        if not cnode:
            continue
        
        # Get the active user's stance on this child
        u_node = data_manager.get_user_node(active_user, cid)
        if u_node:
            interested = u_node.get('interested')
            if interested is True:
                approved.append(cnode.get('label', 'Untitled'))
                approved.append(cnode.get('description'))
                
            elif interested is False:
                rejected.append(cnode.get('label', 'Untitled'))
                
            # If `interested` is missing/None, do not classify the child
    
    return approved, rejected

async def start_drill_process(
    node_id: str,
    data_manager: Any,
    ai_agent: Any,
    active_user: str,
    on_complete: Callable[[], None],
    temperature: float = 1.0,
    container: Any = None,
    prompt_filename: str = 'drill_down.md'
):
    """
    Start the drill process for a node using a specific prompt.
    
    Args:
        node_id: The node to drill from
        data_manager: DataManager instance
        ai_agent: AIAgent instance
        active_user: Current user ID
        on_complete: Callback when done
        temperature: AI temperature parameter
        container: Optional UI container
        prompt_filename: Which prompt file to use (e.g., 'drill_down.md')
    """
    # Create a persistent notification that we can dismiss later
    loading_notification = None
    node_type_manager = get_node_type_manager()
    
    if container:
        container.clear()
        with container:
             ui.spinner('dots', size='lg').classes('w-full text-center')
             ui.label("Consulting AI...").classes('w-full text-center text-gray-500 animate-pulse')
    else:
        # Create a floating notification card that stays until we dismiss it
        loading_notification = ui.notification(
            message="Consulting AI...",
            spinner=True,
            timeout=None,  # Stays until dismissed
            close_button=False
        )
    
    def dismiss_loading():
        """Dismiss the loading notification if it exists"""
        nonlocal loading_notification
        if loading_notification:
            try:
                loading_notification.dismiss()
            except:
                pass
            loading_notification = None
    
    # 1. Gather Context
    try:
        graph = data_manager.get_graph()
        node = next((n for n in graph.get('nodes', []) if n['id'] == node_id), None)
        if not node: 
            dismiss_loading()
            ui.notify("Node not found", color='negative')
            if container: on_complete()
            return
        
        # Build full ancestry chain for context
        full_ancestry = build_ancestry_chain(node_id, graph)
        
        # Get node type for prompt loading
        node_type = node.get('node_type', 'default')
        
        # Get node description
        node_description = node.get('description', '')
        
        # Get existing children and separate into approved/rejected
        children_ids = [e['target'] for e in graph.get('edges', []) if e['source'] == node_id]
        approved_children, rejected_children = separate_approved_rejected(children_ids, graph, data_manager, active_user)

        # Gather metadata from ALL users to give AI full context
        combined_notes = []
        all_users = data_manager.list_users()
        for user in all_users:
            u_node = data_manager.get_user_node(user, node_id)
            if u_node and u_node.get('metadata'):
                combined_notes.append(f"[{user}]: {u_node['metadata']}")
        
        full_context_str = "\n".join(combined_notes) if combined_notes else ""
    except Exception as e:
        dismiss_loading()
        ui.notify(f"Context Error: {e}", color='negative')
        print(f"Drill context gathering error: {e}")
        if container:
             container.clear()
             with container:
                  ui.label(f"Context Error: {e}").classes('text-red-500')
                  ui.button('Back', on_click=on_complete).props('flat')
        return

    # 2. Call AI (IO Bound)
    try:
        print(f"[Drill] Calling AI with ancestry: {full_ancestry}")
        print(f"[Drill] Node type: {node_type}, Prompt: {prompt_filename}")
        print(f"[Drill] Description: {node_description}")
        print(f"[Drill] Approved: {approved_children}")
        print(f"[Drill] Rejected: {rejected_children}")
        
        # Build full node data for the AI
        node_data = dict(node)
        node_data['label'] = full_ancestry  # Use ancestry chain as label
        node_data['metadata'] = full_context_str
        
        candidates = await run.io_bound(
            ai_agent.generate_candidates_for_prompt,
            node_type,
            prompt_filename,
            node_data,
            approved_children,
            rejected_children,
            temperature
        )
        
        # Get the produces_type from the first candidate (all should have same type)
        produces_type = 'default'
        if candidates and '_produces_type' in candidates[0]:
            produces_type = candidates[0]['_produces_type']
        
        print(f"[Drill] AI returned {len(candidates) if candidates else 0} candidates of type '{produces_type}'")
        dismiss_loading()  # Success - dismiss loading notification
    except Exception as e:
        dismiss_loading()
        error_msg = str(e)
        ui.notify(f"AI Error: {error_msg}", color='negative', timeout=10000)
        print(f"[Drill] AI Error Details: {e}")
        import traceback
        traceback.print_exc()
        if container:
             container.clear()
             with container:
                  ui.label('AI Error').classes('text-red-500 font-bold')
                  ui.label(error_msg).classes('text-red-400 text-sm')
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
    # Extract labels and descriptions from candidates
    # Candidates are now [{"label": "...", "description": "..."}, ...]
    selection_state = {}
    description_state = {}
    
    for candidate in candidates:
        if isinstance(candidate, dict):
            label = candidate.get('label', '')
            desc = candidate.get('description', '')
        else:
            # Fallback for old format (plain strings)
            label = candidate
            desc = ''
        
        if label:
            selection_state[label] = 'maybe'
            description_state[label] = desc
    
    def render_interface(parent, dialog_ref=None):
        with parent:
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(full_ancestry).classes('text-lg font-bold text-white')
                if not dialog_ref:
                     pass 

            ui.label("Select ideas to add and provide descriptions.").classes('text-xs text-gray-400 mb-2')
            
            
            def render_row(suggestion):
                 with ui.column().classes('w-full mb-3 bg-slate-800/40 p-3 rounded border border-slate-700/50'):
                    with ui.row().classes('w-full items-center justify-between mb-2'):
                        ui.label(suggestion).classes('text-gray-200 text-sm font-bold flex-1 mr-2 leading-tight').style('word-wrap: break-word')
                        
                        # Direct mapping: UI component returns 'accepted'/'rejected'/'maybe'
                        def on_change(new_val):
                            selection_state[suggestion] = new_val

                        render_tri_state_buttons(selection_state[suggestion], on_change)
                    
                    # Description with markdown preview
                    def on_desc_change(new_val, s=suggestion):
                        description_state[s] = new_val
                    
                    render_markdown_textarea(
                        value=description_state[suggestion],
                        label='Description',
                        placeholder='Click to edit description...',
                        on_change=on_desc_change
                    )

            with ui.scroll_area().classes('h-96 w-full border border-slate-700 rounded p-2 bg-slate-900'):
                for label in selection_state.keys():
                    render_row(label)

            def finish():
                count = 0
                count_declined = 0
                for text, status in selection_state.items():
                    # Get the candidate data for custom fields
                    candidate_data = next(
                        (c for c in candidates if isinstance(c, dict) and c.get('label') == text),
                        None
                    )
                    
                    # Extract custom fields (everything except reserved keys)
                    custom_fields = {}
                    if candidate_data:
                        reserved = {'label', 'description', 'id', 'parent_id', 'node_type', '_produces_type'}
                        for key, value in candidate_data.items():
                            if key not in reserved:
                                custom_fields[key] = value
                    
                    if status == 'accepted':
                        data_manager.add_node(
                            label=text, 
                            parent_id=node_id, 
                            users=[active_user],
                            interested=True,
                            description=description_state.get(text, ''),
                            node_type=produces_type,
                            custom_fields=custom_fields
                        )
                        count += 1
                    elif status == 'rejected':
                        data_manager.add_node(
                            label=text, 
                            parent_id=node_id, 
                            users=[active_user],
                            interested=False,
                            description=description_state.get(text, ''),
                            node_type=produces_type,
                            custom_fields=custom_fields
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
