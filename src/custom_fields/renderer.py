"""
Main custom fields renderer.

Orchestrates rendering of all custom fields for a node type.
Field renderers are auto-discovered from *_field.py files in this folder.
"""

import importlib
import pkgutil
from pathlib import Path
from nicegui import ui
from typing import Any, Callable, Dict, List

from .base import is_field_missing


def _discover_field_renderers() -> Dict[str, Callable]:
    """
    Auto-discover field renderers from *_field.py files in this folder.
    
    Each file should have a render_field function.
    E.g., text_field.py should export render_field.
    
    Returns:
        Dict mapping field type names to their render functions.
    """
    renderers = {}
    package_dir = Path(__file__).parent
    
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        module_name = module_info.name
        
        # Only process *_field.py files
        if not module_name.endswith('_field'):
            continue
        
        # Extract field type from filename (e.g., "text_field" -> "text")
        field_type = module_name.rsplit('_field', 1)[0]
        
        try:
            # Import the module
            module = importlib.import_module(f'.{module_name}', package='src.custom_fields')
            
            # Look for render_field function
            if hasattr(module, 'render_field'):
                renderers[field_type] = getattr(module, 'render_field')
        except Exception as e:
            print(f"Warning: Failed to load field renderer '{module_name}': {e}")
    
    return renderers


# Auto-discover field renderers on module load
FIELD_RENDERERS = _discover_field_renderers()


def render_custom_fields(
    fields: List[dict],
    node_data: Dict[str, Any],
    schedule_save: Callable[[], None],
    all_users: List[str],
    values_dict: Dict[str, Any]
) -> None:
    """
    Render all custom fields for a node.
    
    Args:
        fields: List of field definitions from node type
        node_data: Current node data containing field values
        schedule_save: Callback to trigger autosave
        all_users: List of all available user ids (for user fields)
        values_dict: Dictionary to store field values (modified in-place by handlers)
    """
    if not fields:
        return
    
    ui.label('CUSTOM FIELDS').classes('text-xs font-bold text-gray-400 mt-3')
    
    for field in fields:
        field_key = field.get('key')
        field_type = field.get('type')
        field_label = field.get('label', field_key.replace('_', ' ').title())
        field_value = node_data.get(field_key)
        required = field.get('required', False)
        
        # Store initial value in the shared dict
        values_dict[field_key] = field_value
        
        # Check for missing required fields
        is_missing = is_field_missing(required, field_value)
        
        # Get renderer for this field type
        renderer = FIELD_RENDERERS.get(field_type)
        
        if renderer:
            if field_type == 'user':
                # User fields need the users list
                renderer(
                    field_key=field_key,
                    field_label=field_label,
                    field_value=field_value,
                    field_config=field,
                    values_dict=values_dict,
                    schedule_save=schedule_save,
                    all_users=all_users,
                    is_missing=is_missing
                )
            else:
                renderer(
                    field_key=field_key,
                    field_label=field_label,
                    field_value=field_value,
                    field_config=field,
                    values_dict=values_dict,
                    schedule_save=schedule_save,
                    is_missing=is_missing
                )
        else:
            # Unknown field type - show warning
            with ui.row().classes('w-full items-center gap-2'):
                ui.icon('help_outline', color='gray').tooltip(f'Unknown field type: {field_type}')
                ui.label(f'{field_label}: {field_value}').classes('text-sm text-gray-500')
