from nicegui import ui
from typing import Callable, Literal

# Unify on adjectives: accepted, rejected, maybe
# (Legacy support for 'ignore' or verbs depending on usage, but we prefer adjectives)
VoteState = Literal['accepted', 'maybe', 'rejected']

def render_tri_state_buttons(
    current_state: str,
    on_change: Callable[[str], None],
    flat: bool = True
):
    """
    Renders a group of 3 buttons: Accept (Green), Maybe (Blue), Reject (Red).
    state: 'accepted' | 'maybe' | 'rejected'
    """
    
    with ui.button_group().props('flat' if flat else ''):
        btn_acc = ui.button(icon='check').props('flat')
        btn_ign = ui.button(icon='help_outline').props('flat')
        btn_rej = ui.button(icon='close').props('flat')
        
        def update_visuals(state_val):
            # Normalize for comparison
            s = state_val.lower() if state_val else ''
            
            # Flexible matching for 'accepted'/'accept' and 'rejected'/'reject'
            is_acc = s in ('accepted', 'accept')
            is_may = s in ('maybe', 'ignore')
            is_rej = s in ('rejected', 'reject')

            # Reset props
            # Note: We must be careful not to remove ALL props if others exist, 
            # but here we rely on the component rebuild cycle usually.
            # However, safely removing color-related props:
            for b in [btn_acc, btn_ign, btn_rej]:
                b.props(remove='text-color') 
                b.props(remove='color')

            # Apply
            btn_acc.props(f'flat color={"green" if is_acc else "grey"}')
            btn_ign.props(f'flat color={"blue" if is_may else "grey"}')
            btn_rej.props(f'flat color={"red" if is_rej else "grey"}')

        # Logic wrapper
        def handle_click(new_state):
            update_visuals(new_state)
            on_change(new_state)

        # Bind - standardize on returning 'accepted', 'maybe', 'rejected'
        btn_acc.on_click(lambda _: handle_click('accepted'))
        btn_ign.on_click(lambda _: handle_click('maybe'))
        btn_rej.on_click(lambda _: handle_click('rejected'))
        
        # Init
        update_visuals(current_state)


def render_editable_notes(
    text: str,
    on_change: Callable[[str], None],
    label: str = "Notes",
    editable: bool = True,
    placeholder: str = "_No context yet_",
    max_height_class: str = "max-h-60"
):
    """
    Renders a markdown note area.
    If editable=True, clicking switches to a textarea editor.
    Includes scrolling for long content in both modes.
    """
    
    # Header
    if label:
        ui.label(label).classes('text-xs font-bold text-gray-400 mt-4')
    
    # 1. Preview (Markdown) - Wrapper for scrolling
    # We use a wrapper column to handle the toggle logic cleanly
    container = ui.column().classes('w-full').style('gap: 0;')
    
    with container:
        # Preview Mode
        # Note: 'cursor-pointer' implies interactivity, so only show if editable.
        # Custom styling for markdown headers within the note
        preview_classes = (
            f'w-full bg-slate-800 rounded p-2 text-sm text-gray-200 {max_height_class} overflow-y-auto '
            f'{"cursor-pointer hover:bg-slate-700 transition-colors" if editable else ""} '
            '[&_h1]:text-lg [&_h1]:mt-0 [&_h1]:pt-0 [&_h1]:mb-2 [&_h1]:font-bold'
        )
        
        display_text = text if text and text.strip() else placeholder
        preview = ui.markdown(display_text).classes(preview_classes)

        # Editor Mode (only if editable)
        if editable:
            # Init as hidden
            editor = ui.textarea(value=text).props('filled rows=8').classes(f'w-full text-sm {max_height_class} overflow-y-auto hidden')
            
            def show_editor():
                preview.set_visibility(False)
                editor.set_visibility(True)
                editor.classes(remove='hidden') # visibility helper might not be enough for textarea props sometimes, ensures consistency
                editor.run_method('focus')

            def hide_editor():
                editor.set_visibility(False)
                editor.classes(add='hidden')
                preview.set_visibility(True)
                
                # Update Preview
                new_text = editor.value or ''
                preview.set_content(new_text if new_text.strip() else placeholder)
                
                # Verify change
                if new_text != text: # Simple check, but caller handles actual diff
                    on_change(new_text)

            # Bindings
            preview.on('click', show_editor)
            editor.on('blur', hide_editor)
            
            # Trigger on_change while typing to support auto-save/debounce
            editor.on_value_change(lambda e: on_change(e.value))


def render_other_users_notes(
    node_id: str,
    active_user: str,
    data_manager,
    users: list = None
):
    """
    Renders notes from other users (not the active user) for a given node.
    Colors the header/border green for accepted users, red for rejected users.
    """
    if users is None:
        users = data_manager.list_users() if hasattr(data_manager, 'list_users') else []
    
    other_users = [u for u in users if u != active_user]
    
    has_any_notes = False
    
    for user in other_users:
        user_node = data_manager.get_user_node(user, node_id)
        if not user_node:
            continue
        
        metadata = user_node.get('metadata', '')
        if not metadata or not metadata.strip():
            continue
        
        has_any_notes = True
        
        # Determine vote status for coloring
        is_interested = user_node.get('interested', True)
        if is_interested:
            # Accepted - green
            border_color = 'border-green-500'
            text_color = 'text-green-400'
            bg_color = 'bg-green-900/20'
        else:
            # Rejected - red
            border_color = 'border-red-500'
            text_color = 'text-red-400'
            bg_color = 'bg-red-900/20'
        
        # Render user's notes with colored styling
        # Determine icon based on vote status
        icon = 'check' if is_interested else 'close'
        
        with ui.element('div').classes(f'w-full rounded border-l-4 {border_color} {bg_color} p-2 mt-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon(icon).classes(f'{text_color}')
                ui.label(f"{user}'s notes").classes(f'text-xs font-bold {text_color}')
            ui.markdown(metadata).classes('text-sm text-gray-300 mt-1 [&_h1]:text-lg [&_h1]:mt-0 [&_h1]:pt-0 [&_h1]:mb-2 [&_h1]:font-bold')
    
    if not has_any_notes:
        # No other users have notes - optionally show nothing or a placeholder
        pass
