"""
Markdown Textarea Component

A multiline text field that:
- Auto-sizes height to display all text
- Shows rendered markdown when not editing
- Shows editable textarea when editing (on click)
"""

from nicegui import ui
from typing import Callable, Optional
import uuid


def render_markdown_textarea(
    value: str = '',
    editable: bool = True,
    min_rows: int = 2,
    max_rows: int = 20,
    classes: str = '',
    label: Optional[str] = None,
    placeholder: str = 'Enter text...',
    on_change: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Render a markdown textarea that shows rendered markdown when not editing.
    
    Args:
        value: Initial text value
        label: Optional label above the field
        placeholder: Placeholder text when empty
        on_change: Callback when value changes (receives new value)
        editable: Whether the field can be edited
        min_rows: Minimum height in rows
        max_rows: Maximum height in rows (for auto-sizing)
        classes: Additional CSS classes for the container
    
    Returns:
        Dict with 'get_value' function to retrieve current value
    """
    current_value = {'text': value or ''}
    
    container = ui.column().classes(f'w-full gap-0 {classes}')
    
    with container:
        if label:
            ui.label(label).classes('text-xs text-gray-400 mb-1')
        
        # Markdown preview (shown when not editing)
        display_text = value if value and value.strip() else f'*{placeholder}*'
        preview_classes = (
            'w-full bg-slate-800/50 rounded p-3 text-sm text-gray-200 '
            '[&_h1]:text-lg [&_h1]:font-bold [&_h1]:mb-2 '
            '[&_h2]:text-base [&_h2]:font-semibold [&_h2]:mb-1 '
            '[&_h3]:text-sm [&_h3]:font-medium '
            '[&_p]:mb-2 [&_ul]:ml-4 [&_ol]:ml-4 '
            '[&_code]:bg-slate-700 [&_code]:px-1 [&_code]:rounded '
        )
        if editable:
            preview_classes += 'cursor-pointer hover:bg-slate-700/50 transition-colors '
        
        preview = ui.markdown(display_text).classes(preview_classes)
        
        # Textarea editor - use rows-based sizing instead of autogrow
        textarea_id = f"markdown-textarea-{uuid.uuid4()}"
        editor = ui.textarea(value=value).classes('w-full')
        # Assign a unique id to the textarea element
        editor.props(f'outlined input-class="text-sm" id={textarea_id}')
        editor.set_visibility(False)
        
        if editable:
            def show_editor():
                preview.set_visibility(False)
                editor.set_visibility(True)
                # After visibility change, manually resize textarea using JS
                ui.run_javascript(f'''
                    requestAnimationFrame(() => {{
                        // Try direct id first
                        let textarea = document.getElementById('{textarea_id}');
                        const wrapper = document.getElementById('c{editor.id}');
                        if (!textarea) {{
                            // Find visible textarea candidates
                            const all = Array.from(document.querySelectorAll('textarea'));
                            const candidates = all.filter(t => t.offsetParent !== null);
                            if (candidates.length === 0) {{
                                console.warn('No visible textareas found on page');
                            }} else if (candidates.length === 1) {{
                                textarea = candidates[0];
                            }} else if (wrapper) {{
                                // Prefer textarea that intersects the wrapper bounding rect
                                const wrect = wrapper.getBoundingClientRect();
                                let found = null;
                                for (const t of candidates) {{
                                    const r = t.getBoundingClientRect();
                                    const intersect = !(r.right < wrect.left || r.left > wrect.right || r.bottom < wrect.top || r.top > wrect.bottom);
                                    if (intersect) {{ found = t; break; }}
                                }}
                                if (!found) {{
                                    // pick nearest by center distance
                                    const wcx = (wrect.left + wrect.right) / 2;
                                    const wcy = (wrect.top + wrect.bottom) / 2;
                                    let best = null; let bestDist = Infinity;
                                    for (const t of candidates) {{
                                        const r = t.getBoundingClientRect();
                                        const tcx = (r.left + r.right) / 2;
                                        const tcy = (r.top + r.bottom) / 2;
                                        const dx = tcx - wcx; const dy = tcy - wcy;
                                        const dist = Math.hypot(dx, dy);
                                        if (dist < bestDist) {{ bestDist = dist; best = t; }}
                                    }}
                                    found = best;
                                }}
                                textarea = found;
                            }} else {{
                                textarea = candidates[0];
                            }}
                        }}
                        if (!textarea) {{
                            console.warn('Textarea not found for id {textarea_id} after candidate search');
                            return;
                        }}
                        // Mark it for future reference
                        textarea.dataset.mdTextareaId = '{textarea_id}';
                        // Resize and focus
                        textarea.style.boxSizing = "border-box";
                        textarea.style.overflow = "hidden";
                        textarea.style.width = "100%";
                        textarea.style.minHeight = "0";
                        textarea.style.maxHeight = "none";
                        textarea.style.height = "auto";
                        void textarea.offsetHeight; // force reflow
                        textarea.style.height = textarea.scrollHeight + "px";
                        textarea.style.maxHeight = "none";
                        textarea.style.minHeight = "0";
                        textarea.focus();
                    }});
                ''')
            
            def hide_editor():
                editor.set_visibility(False)
                preview.set_visibility(True)
                
                # Update preview
                new_text = editor.value or ''
                current_value['text'] = new_text
                preview.set_content(new_text if new_text.strip() else f'*{placeholder}*')
            
            def handle_change(e):
                new_text = e.value or ''
                current_value['text'] = new_text
                if on_change:
                    on_change(new_text)
                # Also resize on content change
                ui.run_javascript(f'''
                    requestAnimationFrame(() => {{
                        console.log('JS injected for markdown textarea (change), textarea_id: {textarea_id}');
                        // Prefer previously marked textarea
                        let textarea = document.querySelector('[data-md-textarea-id="{textarea_id}"]');
                        if (!textarea) textarea = document.getElementById('{textarea_id}');
                        if (!textarea) {{
                            // fallback: find visible candidates and pick nearest to wrapper
                            const all = Array.from(document.querySelectorAll('textarea'));
                            const candidates = all.filter(t => t.offsetParent !== null);
                            if (candidates.length === 1) textarea = candidates[0];
                            else if (candidates.length > 1) {{
                                const wrapper = document.getElementById('c{editor.id}');
                                if (wrapper) {{
                                    const wrect = wrapper.getBoundingClientRect();
                                    let best = null; let bestDist = Infinity;
                                    for (const t of candidates) {{
                                        const r = t.getBoundingClientRect();
                                        const tcx = (r.left + r.right) / 2;
                                        const tcy = (r.top + r.bottom) / 2;
                                        const wcx = (wrect.left + wrect.right) / 2;
                                        const wcy = (wrect.top + wrect.bottom) / 2;
                                        const dist = Math.hypot(tcx - wcx, tcy - wcy);
                                        if (dist < bestDist) {{ bestDist = dist; best = t; }}
                                    }}
                                    textarea = best;
                                }} else textarea = candidates[0];
                            }}
                        }}
                        if (!textarea) {{
                            console.warn('Textarea not found for change handler, id {textarea_id}');
                            return;
                        // Resize
                        textarea.style.boxSizing = "border-box";
                        textarea.style.overflow = "hidden";
                        textarea.style.width = "100%";
                        textarea.style.minHeight = "0";
                        textarea.style.maxHeight = "none";
                        textarea.style.height = "auto";
                        void textarea.offsetHeight;
                        textarea.style.height = textarea.scrollHeight + "px";
                        textarea.style.maxHeight = "none";
                        textarea.style.minHeight = "0";
                        console.log('Resized textarea (change):', textarea, textarea.scrollHeight);
                    }});
                ''')
            
            preview.on('click', show_editor)
            editor.on('blur', hide_editor)
            editor.on_value_change(handle_change)
    
    return {
        'get_value': lambda: current_value['text'],
        'container': container,
        'preview': preview,
        'editor': editor
    }
