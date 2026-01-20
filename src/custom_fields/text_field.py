"""
Text field renderer.

Handles both single-line text inputs and multiline markdown textareas.
"""

from nicegui import ui
from typing import Any, Callable

from .base import show_missing_indicator
from ..components import render_markdown_textarea


def render_field(
    field_key: str,
    field_label: str,
    field_value: Any,
    field_config: dict,
    values_dict: dict,
    schedule_save: Callable[[], None],
    is_missing: bool = False
) -> None:
    """
    Render a text input field.
    
    Args:
        field_key: Unique key for this field
        field_label: Display label
        field_value: Current value
        field_config: Field configuration from type definition
        values_dict: Dictionary to store values for autosave
        schedule_save: Callback to trigger autosave
        is_missing: Whether to show missing required field warning
    """
    multiline = field_config.get('multiline', True)
    display_val = field_value or ''
    
    with ui.row().classes('w-full items-start gap-2'):
        if is_missing:
            show_missing_indicator()
        
        if multiline:
            # Use markdown textarea for multiline fields
            def on_text_change(new_val):
                values_dict[field_key] = new_val
                schedule_save()
            
            render_markdown_textarea(
                value=display_val,
                label=field_label,
                placeholder=f'Enter {field_label.lower()}...',
                on_change=on_text_change,
                classes='flex-1'
            )
        else:
            inp = ui.input(field_label, value=display_val).classes('flex-1')
            inp.props('outlined dense')
            
            def make_handler(fk):
                def handler(e):
                    values_dict[fk] = e.value
                    schedule_save()
                return handler
            inp.on_value_change(make_handler(field_key))
