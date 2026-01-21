"""
Material Icon Picker Component

A searchable autocomplete field for selecting Material Design icons
with a preview of the icon next to each option.
"""

from nicegui import ui
from typing import Callable, Optional, List
from pathlib import Path
import json

# Default curated list used as a fallback if no cached file exists
DEFAULT_ICONS: List[str] = [
    # Navigation & Actions
    'account_tree', 'add', 'add_circle', 'arrow_back', 'arrow_forward',
    'cancel', 'check', 'check_circle', 'close', 'delete', 'edit',
    'expand_less', 'expand_more', 'home', 'menu', 'more_horiz', 'more_vert',
    'refresh', 'save', 'search', 'settings', 'undo', 'redo',
    
    # Content & Files
    'article', 'book', 'bookmark', 'content_copy', 'create', 'description',
    'draft', 'file_copy', 'folder', 'folder_open', 'insert_drive_file',
    'library_books', 'note', 'note_add', 'text_snippet',
    
    # Communication
    'chat', 'comment', 'email', 'forum', 'message', 'question_answer',
    'send', 'share', 'thumb_up', 'thumb_down',
    
    # Data & Charts
    'analytics', 'bar_chart', 'bubble_chart', 'data_usage', 'insights',
    'pie_chart', 'show_chart', 'timeline', 'trending_up', 'trending_down',
    
    # Science & Research
    'biotech', 'calculate', 'category', 'code', 'developer_board',
    'dns', 'extension', 'hub', 'integration_instructions', 'lightbulb',
    'memory', 'psychology', 'science', 'school', 'smart_toy',
    
    # Gaming & Entertainment
    'casino', 'extension', 'games', 'gamepad', 'sports_esports',
    'videogame_asset', 'widgets',
    
    # People & Groups
    'group', 'groups', 'people', 'person', 'person_add', 'supervisor_account',
    
    # Status & Info
    'check_box', 'error', 'help', 'info', 'label', 'priority_high',
    'report', 'star', 'verified', 'warning',
    
    # Misc
    'auto_awesome', 'bolt', 'build', 'construction', 'explore',
    'favorite', 'flag', 'grade', 'grid_view', 'layers', 'lens',
    'link', 'list', 'local_offer', 'lock', 'map', 'palette',
    'push_pin', 'rocket_launch', 'route', 'rule', 'scatter_plot',
    'schema', 'source', 'speed', 'storage', 'style', 'sync',
    'tag', 'task', 'tips_and_updates', 'token', 'tune',
    'view_list', 'view_module', 'visibility', 'work', 'workspaces',
]

# Try to load a generated material_icons.json next to this module. If not present,
# fall back to the curated `DEFAULT_ICONS` list above.
try:
    _json_path = Path(__file__).parent / 'material_icons.json'
    if _json_path.exists():
        with open(_json_path, 'r', encoding='utf-8') as _f:
            COMMON_ICONS = json.load(_f)
            # ensure it's a list of strings
            if not isinstance(COMMON_ICONS, list):
                raise ValueError('material_icons.json did not contain a list')
    else:
        COMMON_ICONS = DEFAULT_ICONS
except Exception:
    COMMON_ICONS = DEFAULT_ICONS


def render_icon_picker(
    value: str = 'smart_toy',
    label: str = 'Icon',
    on_change: Optional[Callable[[str], None]] = None,
    classes: str = '',
) -> dict:
    """
    Render a searchable icon picker with autocomplete and preview.
    
    Args:
        value: Initial icon name
        label: Label for the field
        on_change: Callback when icon changes (receives icon name)
        classes: Additional CSS classes
    
    Returns:
        Dict with 'get_value' function to retrieve current value
    """
    current_value = {'icon': value or 'smart_toy'}
    
    container = ui.row().classes(f'w-full items-center gap-2 {classes}')
    
    with container:
        # Icon preview
        preview_icon = ui.icon(current_value['icon']).classes('text-2xl text-blue-400')
        
        # Create a searchable select with all icons
        # Build options dict: {icon_name: icon_name}
        options_dict = {icon: icon for icon in COMMON_ICONS}
        
        select = ui.select(
            options=options_dict,
            value=current_value['icon'],
            label=label,
            with_input=True,
        ).classes('flex-1').props('outlined dense use-input hide-selected')
        
        def on_select_change(e):
            new_value = e.value if hasattr(e, 'value') else e
            if new_value and new_value in COMMON_ICONS:
                current_value['icon'] = new_value
                preview_icon.props(f'name={new_value}')
                if on_change:
                    on_change(new_value)
        
        select.on_value_change(on_select_change)
    
    def get_value() -> str:
        return current_value['icon']
    
    def set_value(icon: str):
        current_value['icon'] = icon
        select.value = icon
        preview_icon.props(f'name={icon}')
    
    return {
        'get_value': get_value,
        'set_value': set_value,
        'container': container,
    }
