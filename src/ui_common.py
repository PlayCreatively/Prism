from nicegui import ui
from typing import Callable, Literal

from .components import render_markdown_textarea

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
    Renders a markdown note area using the markdown textarea component.
    If editable=True, clicking switches to a textarea editor.
    """
    # Header
    if label:
        ui.label(label).classes('text-xs font-bold text-gray-400 mt-4')
    
    render_markdown_textarea(
        value=text,
        placeholder=placeholder.replace('_', ''),  # Remove markdown italics
        on_change=on_change,
        editable=editable
    )


def render_other_users_notes(
    node_id: str,
    active_user: str,
    data_manager,
    users: list,
    user_map: dict = None,
    is_supabase: bool = False
):
    """
    Renders notes from other users (not the active user) for a given node.
    Colors the header/border green for accepted users, red for rejected users and unsure for unvoted users.
    
    Args:
        user_map: Optional dict mapping user IDs to display names (for Supabase)
        is_supabase: Whether using Supabase backend
    """
    if user_map is None:
        user_map = {}
    
    other_users = [u for u in users if u != active_user]
    
    has_any_notes = False
    
    for user in other_users:
        user_node = data_manager.get_user_node(user, node_id)
        if not user_node:
            continue
        print(f"[UI] Rendering notes for user '{user}' keys '{user_node.get('interested')}'")
        
        metadata = user_node.get('metadata', '')
        if not metadata or not metadata.strip():
            continue
        
        has_any_notes = True
        
        # Get display name for user (handle both UUID and username)
        if is_supabase and user in user_map:
            user_display = user_map[user]
        else:
            user_display = user
        
        # Determine vote status for coloring
        is_interested = user_node.get('interested', True)
        if is_interested:
            # Accepted - green
            border_color = 'border-green-500'
            text_color = 'text-green-400'
            bg_color = 'bg-green-900/20'
        elif is_interested is False:
            # Rejected - red
            border_color = 'border-red-500'
            text_color = 'text-red-400'
            bg_color = 'bg-red-900/20'
        else:
            # Unsure - gray
            border_color = 'border-gray-500'
            text_color = 'text-gray-400'
            bg_color = 'bg-gray-900/20'
        
        # Render user's notes with colored styling
        # Determine icon based on vote status
        icon = 'check' if is_interested else 'close' if is_interested is False else 'help_outline'
        
        with ui.element('div').classes(f'w-full rounded border-l-4 {border_color} {bg_color} p-2 mt-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon(icon).classes(f'{text_color}')
                ui.label(f"{user_display}'s notes").classes(f'text-xs font-bold {text_color}')
            ui.markdown(metadata).classes('text-sm text-gray-300 mt-1 [&_h1]:text-lg [&_h1]:mt-0 [&_h1]:pt-0 [&_h1]:mb-2 [&_h1]:font-bold')
    
    if not has_any_notes:
        # No other users have notes - optionally show nothing or a placeholder
        pass
