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
