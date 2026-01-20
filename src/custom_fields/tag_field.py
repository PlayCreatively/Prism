"""
Tag field renderer.

Handles both:
- Enum tags: Dropdown selection from predefined options
- Free-form tags: Chip display with add/remove capability
"""

from nicegui import ui
from typing import Any, Callable, List, Optional

from .base import show_missing_indicator, make_change_handler


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
    Render a tag selection field.
    
    Args:
        field_key: Unique key for this field
        field_label: Display label
        field_value: Current value (string or list)
        field_config: Field configuration from type definition
        values_dict: Dictionary to store values for autosave
        schedule_save: Callback to trigger autosave
        is_missing: Whether to show missing required field warning
    """
    selection: Optional[List[str]] = field_config.get('selection')
    multiple = field_config.get('multiple', True)
    
    with ui.row().classes('w-full items-center gap-2'):
        if is_missing:
            show_missing_indicator()
        ui.label(field_label).classes('text-sm text-gray-300 min-w-24')
        
        if selection:
            # Enum dropdown with predefined options
            _render_enum_tags(field_key, field_value, selection, multiple, values_dict, schedule_save)
        else:
            # Free-form tags as editable chips
            _render_freeform_tags(field_key, field_value, values_dict, schedule_save)


def _render_enum_tags(
    field_key: str,
    field_value: Any,
    selection: List[str],
    multiple: bool,
    values_dict: dict,
    schedule_save: Callable[[], None]
) -> None:
    """Render a dropdown for enum-style tag selection."""
    current_val = field_value if field_value else ([] if multiple else None)
    
    if multiple:
        sel = ui.select(selection, multiple=True, value=current_val if isinstance(current_val, list) else []).classes('flex-1')
    else:
        sel = ui.select(selection, value=current_val).classes('flex-1')
    
    sel.props('outlined dense')
    sel.on_value_change(make_change_handler(field_key, values_dict, schedule_save))


def _render_freeform_tags(
    field_key: str,
    field_value: Any,
    values_dict: dict,
    schedule_save: Callable[[], None]
) -> None:
    """Render free-form tags as editable chips."""
    tags = list(field_value) if isinstance(field_value, list) else []
    
    # Container for chips - will be refreshed when tags change
    chips_container = ui.row().classes('flex-wrap gap-1')
    
    def refresh_chips():
        """Rebuild the chips display."""
        chips_container.clear()
        with chips_container:
            for tag in tags:
                _render_removable_chip(tag, field_key, tags, values_dict, schedule_save, refresh_chips)
            
            if not tags:
                ui.label('No tags').classes('text-gray-500 text-xs italic')
    
    # Initial render
    refresh_chips()
    
    # Add new tag input
    with ui.row().classes('items-center gap-1'):
        new_tag_input = ui.input(placeholder='Add tag...').classes('w-32')
        new_tag_input.props('dense outlined size=sm')
        
        def add_tag():
            new_val = new_tag_input.value.strip()
            if new_val and new_val not in tags:
                tags.append(new_val)
                values_dict[field_key] = tags.copy()
                schedule_save()
                new_tag_input.value = ''
                refresh_chips()
        
        ui.button(icon='add', on_click=add_tag).props('flat dense size=sm')


def _render_removable_chip(
    tag: str,
    field_key: str,
    tags: List[str],
    values_dict: dict,
    schedule_save: Callable[[], None],
    refresh_callback: Callable[[], None]
) -> None:
    """Render a single removable chip for a tag."""
    with ui.chip(tag, color='primary', removable=True).props('outline size=sm') as chip:
        def remove_tag(t=tag):
            if t in tags:
                tags.remove(t)
                values_dict[field_key] = tags.copy()
                schedule_save()
                refresh_callback()
        chip.on('remove', lambda: remove_tag())
