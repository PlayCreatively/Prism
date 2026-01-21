"""
Prompt Edit Modal Component

A modal dialog for editing or creating prompt files with:
- Name field (header style)
- Description field (single line)
- Icon picker
- Produces type dropdown
- Markdown body editor
- Save/Cancel/Delete buttons
"""

from nicegui import ui
from typing import Callable, Optional, Dict, Any, List
from .icon_picker import render_icon_picker
from .markdown_textarea import render_markdown_textarea
from ..ai_agent import PROMPT_PLACEHOLDERS


def render_prompt_edit_modal(
    node_type: str,
    available_types: List[str],
    node_type_manager,
    on_save: Optional[Callable[[], None]] = None,
    on_delete: Optional[Callable[[], None]] = None,
    existing_prompt: Optional[Dict[str, Any]] = None,
) -> 'ui.dialog':
    """
    Create and return a prompt edit modal dialog.
    
    Args:
        node_type: The node type folder where the prompt belongs
        available_types: List of available node types for produces_type dropdown
        node_type_manager: NodeTypeManager instance for CRUD operations
        on_save: Callback after successful save
        on_delete: Callback after successful delete
        existing_prompt: If editing, the existing prompt data (from load_prompts)
    
    Returns:
        The dialog instance (call dialog.open() to show)
    """
    is_new = existing_prompt is None
    
    # Default values for new prompt
    initial_name = existing_prompt.get('name', 'New Prompt') if existing_prompt else 'New Prompt'
    initial_desc = existing_prompt.get('description', '') if existing_prompt else ''
    initial_icon = existing_prompt.get('material_logo', 'smart_toy') if existing_prompt else 'smart_toy'
    initial_produces = existing_prompt.get('produces_type', node_type) if existing_prompt else node_type
    initial_body = existing_prompt.get('content', '') if existing_prompt else node_type_manager.get_default_prompt_template()
    existing_filename = existing_prompt.get('filename') if existing_prompt else None
    
    # State holders for field values
    field_state = {
        'name': initial_name,
        'description': initial_desc,
        'icon': initial_icon,
        'produces_type': initial_produces,
        'body': initial_body,
    }
    
    dialog = ui.dialog().props('maximized')
    
    with dialog:
        with ui.card().classes('w-full max-w-3xl mx-auto bg-slate-900 border border-slate-700'):
            # Header
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Edit Prompt' if not is_new else 'Create New Prompt').classes('text-sm text-gray-400')
                ui.button(icon='close', on_click=dialog.close).props('flat round dense color=grey').tooltip('Cancel')
            
            # Name field (header style - large editable input)
            name_input = ui.input(value=initial_name, placeholder='Prompt Name').classes(
                'w-full text-xl font-bold text-gray-100'
            ).props('borderless dense')
            name_input.on_value_change(lambda e: field_state.update({'name': e.value}))
            
            ui.separator().classes('my-2')
            
            # Two-column layout for metadata
            with ui.row().classes('w-full gap-4 flex-wrap'):
                # Left column
                with ui.column().classes('flex-1 min-w-[200px] gap-2'):
                    # Description (single line)
                    desc_input = ui.input(
                        value=initial_desc, 
                        label='Description',
                        placeholder='Brief description for tooltip'
                    ).classes('w-full').props('outlined dense')
                    desc_input.on_value_change(lambda e: field_state.update({'description': e.value}))
                    
                    # Produces type dropdown
                    # Build options dict, ensuring current value is always included
                    type_options = {t: node_type_manager.get_type_display_name(t) for t in available_types}
                    
                    # If the initial produces_type is not in the list (e.g., typo or renamed folder),
                    # add it to prevent ValueError and allow the user to fix it
                    if initial_produces and initial_produces not in type_options:
                        type_options[initial_produces] = f"{node_type_manager.get_type_display_name(initial_produces)} (not found)"
                    
                    # Fallback to node_type if initial_produces is somehow empty or still invalid
                    select_value = initial_produces if initial_produces in type_options else node_type
                    
                    produces_select = ui.select(
                        options=type_options,
                        value=select_value,
                        label='Produces Node Type'
                    ).classes('w-full').props('outlined dense')
                    produces_select.on_value_change(lambda e: field_state.update({'produces_type': e.value}))
                
                # Right column - Icon picker
                with ui.column().classes('flex-1 min-w-[200px] gap-2'):
                    icon_picker = render_icon_picker(
                        value=initial_icon,
                        label='Button Icon',
                        on_change=lambda v: field_state.update({'icon': v})
                    )
            
            ui.separator().classes('my-2')
            
            # Body editor (markdown textarea)
            ui.label('Prompt Body').classes('text-xs font-bold text-gray-400')
            
            # Display placeholder chips with tooltips (definitions imported from ai_agent)
            with ui.row().classes('gap-1 flex-wrap mb-1'):
                ui.label('Placeholders:').classes('text-xs text-gray-500')
                for key, desc in PROMPT_PLACEHOLDERS:
                    chip = ui.chip(key, color='slate').props('dense size=sm outline').classes(
                        'text-xs cursor-help'
                    )
                    chip.tooltip(desc)
            
            body_editor = render_markdown_textarea(
                value=initial_body,
                editable=True,
                min_rows=10,
                max_rows=20,
                placeholder='Enter your prompt template...',
                on_change=lambda v: field_state.update({'body': v})
            )
            
            ui.separator().classes('my-3')
            
            # Action buttons
            with ui.row().classes('w-full justify-between'):
                # Delete button (only for existing prompts)
                if not is_new:
                    def do_delete():
                        node_type_manager.delete_prompt(node_type, existing_filename)
                        if on_delete:
                            on_delete()
                        dialog.close()
                        ui.notify('Prompt deleted', type='warning')
                    
                    ui.button(icon='delete', color='red', on_click=do_delete).props('flat').tooltip('Delete Prompt')
                else:
                    ui.label('')  # Spacer
                
                # Save and Cancel buttons
                with ui.row().classes('gap-2'):
                    ui.button('Cancel', on_click=dialog.close).props('flat color=grey')
                    
                    def do_save():
                        # Validate name
                        name = field_state['name'].strip()
                        if not name:
                            ui.notify('Prompt name is required', type='negative')
                            return
                        
                        # Get latest body value from the component
                        body = body_editor['get_value']()
                        
                        # Save the prompt
                        try:
                            node_type_manager.save_prompt(
                                type_name=node_type,
                                name=name,
                                description=field_state['description'],
                                icon=field_state['icon'],
                                produces_type=field_state['produces_type'],
                                body=body,
                                existing_filename=existing_filename
                            )
                            
                            if on_save:
                                on_save()
                            dialog.close()
                            ui.notify('Prompt saved successfully', type='positive')
                        except Exception as e:
                            ui.notify(f'Failed to save: {e}', type='negative')
                    
                    ui.button('Save', icon='save', color='green', on_click=do_save)
    
    return dialog
