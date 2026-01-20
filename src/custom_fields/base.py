"""
Base utilities for custom field rendering.
"""

from nicegui import ui
from typing import Any, Callable


def show_missing_indicator():
    """Display a warning icon for required fields that are empty."""
    ui.icon('warning', color='orange').tooltip('Required field is missing')


def is_field_missing(required: bool, value: Any) -> bool:
    """Check if a required field is missing its value."""
    if not required:
        return False
    return value is None or value == '' or value == []


def make_change_handler(field_key: str, values_dict: dict, schedule_save: Callable[[], None]) -> Callable:
    """
    Create a value change handler that updates the values dict and triggers save.
    
    Args:
        field_key: The key to update in values_dict
        values_dict: Dictionary storing current field values
        schedule_save: Callback to schedule an autosave
    
    Returns:
        Event handler function
    """
    def handler(e):
        values_dict[field_key] = e.value
        schedule_save()
    return handler
