"""
User field renderer.

Handles user selection from project users, single or multiple.
"""

from nicegui import ui
from typing import Any, Callable, List

from .base import show_missing_indicator, make_change_handler


def render_field(
    field_key: str,
    field_label: str,
    field_value: Any,
    field_config: dict,
    values_dict: dict,
    schedule_save: Callable[[], None],
    all_users: List[str],
    is_missing: bool = False
) -> None:
    """
    Render a user selection field.
    
    Args:
        field_key: Unique key for this field
        field_label: Display label
        field_value: Current value (user id or list of user ids)
        field_config: Field configuration from type definition
        values_dict: Dictionary to store values for autosave
        schedule_save: Callback to trigger autosave
        all_users: List of all available user ids
        is_missing: Whether to show missing required field warning
    """
    multiple = field_config.get('multiple', False)
    current_val = field_value if field_value else ([] if multiple else None)
    
    with ui.row().classes('w-full items-center gap-2'):
        if is_missing:
            show_missing_indicator()
        ui.label(field_label).classes('text-sm text-gray-300 min-w-24')
        
        # Build options with empty option for optional single-select
        user_options = [''] + all_users
        
        if multiple:
            # Filter to only valid users
            valid_vals = [v for v in (current_val if isinstance(current_val, list) else []) if v in all_users]
            sel = ui.select(user_options, multiple=True, value=valid_vals).classes('flex-1')
        else:
            # Validate single selection
            valid_val = current_val if current_val in all_users else ''
            sel = ui.select(user_options, value=valid_val, clearable=True).classes('flex-1')
        
        sel.props('outlined dense')
        sel.on_value_change(make_change_handler(field_key, values_dict, schedule_save))
