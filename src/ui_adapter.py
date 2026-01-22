"""
UI Adaptation Layer for PRISM.

Provides context-aware UI components that adapt based on:
- Storage backend type (Git vs Supabase)
- Authentication state
- Read-only vs full access mode
- Real-time sync status
"""

import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from nicegui import ui

logger = logging.getLogger(__name__)


@dataclass
class UIContext:
    """
    Context object containing all information needed to adapt the UI.
    
    This is passed to UI components to control what features are available.
    """
    # Backend info
    backend_type: str = "git"  # 'git' or 'supabase'
    supports_realtime: bool = False
    is_read_only: bool = False
    
    # Auth info
    is_authenticated: bool = False
    current_user: Optional[Dict[str, Any]] = None
    
    # Project info
    project_name: str = ""
    is_public: bool = False
    
    # Sync state
    is_connected: bool = True
    has_unpushed_changes: bool = False
    
    @property
    def is_git_backend(self) -> bool:
        return self.backend_type == "git"
    
    @property
    def is_supabase_backend(self) -> bool:
        return self.backend_type == "supabase"
    
    @property
    def show_sync_buttons(self) -> bool:
        """Show sync buttons only for git backend."""
        return self.is_git_backend and not self.is_read_only
    
    @property
    def show_user_dropdown(self) -> bool:
        """Show user dropdown for git backend (local user selection)."""
        return self.is_git_backend and not self.is_read_only
    
    @property
    def show_login_button(self) -> bool:
        """Show login button for Supabase backend when not authenticated."""
        return self.is_supabase_backend and not self.is_authenticated
    
    @property
    def show_user_menu(self) -> bool:
        """Show user menu for Supabase backend when authenticated."""
        return self.is_supabase_backend and self.is_authenticated
    
    @property
    def show_realtime_indicator(self) -> bool:
        """Show real-time indicator for Supabase backend."""
        return self.is_supabase_backend and self.supports_realtime
    
    @property
    def can_edit(self) -> bool:
        """Check if editing is allowed."""
        return not self.is_read_only
    
    @property
    def username(self) -> str:
        """Get current username for display."""
        if self.current_user:
            return self.current_user.get('username') or self.current_user.get('email', 'User')
        return 'Guest'


def create_ui_context(
    data_manager=None,
    project_name: str = "",
    active_user: str = ""
) -> UIContext:
    """
    Create a UIContext from the current state.
    
    Args:
        data_manager: DataManager instance
        project_name: Name of the current project
        active_user: Active user for git backend
        
    Returns:
        UIContext with all relevant state
    """
    from src.auth.middleware import get_current_user, is_authenticated
    
    ctx = UIContext(project_name=project_name)
    
    if data_manager:
        ctx.backend_type = data_manager.backend_type
        ctx.supports_realtime = data_manager.supports_realtime
        ctx.is_read_only = data_manager.is_read_only
        ctx.has_unpushed_changes = data_manager.has_unpushed_changes()
    
    # Auth state
    ctx.is_authenticated = is_authenticated()
    ctx.current_user = get_current_user()
    
    # For git backend, use the active user
    if ctx.is_git_backend and active_user:
        ctx.current_user = {"username": active_user}
        ctx.is_authenticated = True
    
    return ctx


class AdaptiveHeader:
    """
    Renders an adaptive header that changes based on UI context.
    """
    
    def __init__(
        self,
        ctx: UIContext,
        users: List[str] = None,
        active_user: str = "",
        on_user_change: Callable[[str], None] = None,
        on_sync: Callable[[], None] = None,
        on_push: Callable[[], None] = None
    ):
        """
        Initialize adaptive header.
        
        Args:
            ctx: UIContext for adaptation
            users: List of users (git backend)
            active_user: Currently active user (git backend)
            on_user_change: Callback when user changes (git backend)
            on_sync: Callback for sync/pull action (git backend)
            on_push: Callback for push action (git backend)
        """
        self.ctx = ctx
        self.users = users or []
        self.active_user = active_user
        self.on_user_change = on_user_change
        self.on_sync = on_sync
        self.on_push = on_push
    
    def render(self):
        """Render the header."""
        with ui.header().classes('bg-slate-800 px-4 py-2'):
            with ui.row().classes('items-center gap-4 w-full'):
                # Logo
                ui.label('PRISM').classes('text-xl font-bold')
                
                # Project name
                if self.ctx.project_name:
                    ui.separator().props('vertical').classes('h-6')
                    ui.label(self.ctx.project_name).classes('text-lg')
                
                # Public badge
                if self.ctx.is_public:
                    ui.badge('Public', color='blue').classes('ml-2')
                
                # Read-only badge
                if self.ctx.is_read_only:
                    ui.badge('Read Only', color='orange').classes('ml-2')
                
                ui.space()
                
                # Real-time indicator (Supabase)
                if self.ctx.show_realtime_indicator:
                    self._render_realtime_indicator()
                
                # Sync buttons (Git)
                if self.ctx.show_sync_buttons:
                    self._render_sync_buttons()
                
                # User selection (Git)
                if self.ctx.show_user_dropdown:
                    self._render_user_dropdown()
                
                # Login button (Supabase, not authenticated)
                if self.ctx.show_login_button:
                    self._render_login_button()
                
                # User menu (Supabase, authenticated)
                if self.ctx.show_user_menu:
                    self._render_user_menu()
    
    def _render_realtime_indicator(self):
        """Render real-time connection indicator."""
        color = 'bg-green-500' if self.ctx.is_connected else 'bg-red-500'
        tooltip = 'Real-time sync active' if self.ctx.is_connected else 'Disconnected'
        
        with ui.row().classes('items-center gap-2'):
            ui.element('div').classes(f'{color} w-2 h-2 rounded-full')
            ui.label('Live').classes('text-sm text-gray-400')
        ui.tooltip(tooltip)
    
    def _render_sync_buttons(self):
        """Render git sync buttons."""
        with ui.row().classes('gap-2'):
            # Pull button
            pull_btn = ui.button(icon='sync', on_click=self.on_sync)\
                .props('flat round')\
                .tooltip('Pull latest changes')
            
            # Push button
            push_btn = ui.button(icon='cloud_upload', on_click=self.on_push)\
                .props('flat round')
            
            if self.ctx.has_unpushed_changes:
                push_btn.classes('text-yellow-400')
                push_btn.tooltip('Push changes (unsaved)')
            else:
                push_btn.tooltip('Push changes')
    
    def _render_user_dropdown(self):
        """Render user selection dropdown for git backend."""
        if not self.users:
            return
        
        with ui.row().classes('items-center gap-2'):
            ui.icon('person').classes('text-gray-400')
            
            select = ui.select(
                options=self.users,
                value=self.active_user,
                on_change=lambda e: self.on_user_change(e.value) if self.on_user_change else None
            ).classes('min-w-32')
    
    def _render_login_button(self):
        """Render login button for unauthenticated Supabase users."""
        ui.button('Sign In', on_click=lambda: ui.navigate.to('/login'))\
            .props('outline color=white')
    
    def _render_user_menu(self):
        """Render user menu for authenticated Supabase users."""
        user = self.ctx.current_user
        
        with ui.button(icon='account_circle').props('flat round'):
            with ui.menu():
                with ui.column().classes('p-2 min-w-48'):
                    ui.label(user.get('display_name') or user.get('username', 'User'))\
                        .classes('font-bold')
                    ui.label(user.get('email', '')).classes('text-sm text-gray-400')
                
                ui.separator()
                ui.menu_item('Settings', lambda: ui.navigate.to('/settings'))
                ui.menu_item('Logout', lambda: ui.navigate.to('/logout'))


class AdaptiveNodePanel:
    """
    Renders an adaptive node detail panel that changes based on context.
    """
    
    def __init__(
        self,
        ctx: UIContext,
        node: Dict[str, Any],
        active_user: str = "",
        on_update: Callable[[str, Any], None] = None,
        on_delete: Callable[[], None] = None,
        on_vote: Callable[[bool], None] = None
    ):
        """
        Initialize adaptive node panel.
        
        Args:
            ctx: UIContext for adaptation
            node: Node data dict
            active_user: Currently active user
            on_update: Callback for node updates
            on_delete: Callback for node deletion
            on_vote: Callback for voting (accept/reject)
        """
        self.ctx = ctx
        self.node = node
        self.active_user = active_user
        self.on_update = on_update
        self.on_delete = on_delete
        self.on_vote = on_vote
        
        # Check encumbrance
        self.external_users = node.get('_external_users', [])
        self.is_encumbered = len(self.external_users) > 0
    
    def render(self):
        """Render the node panel."""
        with ui.card().classes('w-full'):
            # Header with node label
            with ui.row().classes('items-center justify-between w-full'):
                if self.ctx.can_edit and not self.is_encumbered:
                    # Editable label
                    label_input = ui.input(value=self.node.get('label', '')).classes('text-xl font-bold')
                    label_input.on('blur', lambda e: self._update_field('label', e.sender.value))
                else:
                    # Read-only label
                    ui.label(self.node.get('label', 'Untitled')).classes('text-xl font-bold')
                
                # Encumbrance indicator
                if self.is_encumbered:
                    with ui.chip('Shared', icon='group').classes('bg-blue-800'):
                        ui.tooltip(f"Other users: {', '.join([u['user_id'] for u in self.external_users])}")
            
            ui.separator()
            
            # Description
            self._render_description()
            
            # Voting section
            self._render_voting()
            
            # Actions
            self._render_actions()
    
    def _render_description(self):
        """Render description field."""
        description = self.node.get('description', '')
        
        if self.ctx.can_edit:
            if self.is_encumbered:
                # Show warning before edit
                with ui.expansion('Description (click to edit)', icon='edit_note').classes('w-full'):
                    self._show_encumbrance_warning()
                    textarea = ui.textarea(value=description).classes('w-full')
                    textarea.on('blur', lambda e: self._update_field_with_confirm('description', e.sender.value))
            else:
                # Direct edit
                ui.label('Description').classes('text-sm text-gray-400 mt-2')
                textarea = ui.textarea(value=description).classes('w-full')
                textarea.on('blur', lambda e: self._update_field('description', e.sender.value))
        else:
            # Read-only
            if description:
                ui.markdown(description).classes('prose prose-invert max-w-none')
            else:
                ui.label('No description').classes('text-gray-400 italic')
    
    def _render_voting(self):
        """Render voting section."""
        interested = self.node.get('interested_users', [])
        rejected = self.node.get('rejected_users', [])
        
        ui.separator()
        
        with ui.row().classes('gap-4 my-2'):
            # Interested users
            with ui.row().classes('items-center gap-2'):
                ui.icon('thumb_up').classes('text-green-400')
                if interested:
                    ui.label(', '.join(interested))
                else:
                    ui.label('None').classes('text-gray-400')
            
            # Rejected users
            with ui.row().classes('items-center gap-2'):
                ui.icon('thumb_down').classes('text-red-400')
                if rejected:
                    ui.label(', '.join(rejected))
                else:
                    ui.label('None').classes('text-gray-400')
        
        # Vote buttons (if not read-only)
        if self.ctx.can_edit and self.on_vote:
            user_interested = self.active_user in interested
            user_rejected = self.active_user in rejected
            
            with ui.row().classes('gap-2 mt-2'):
                accept_btn = ui.button(
                    'Accept' if not user_interested else 'Accepted ✓',
                    icon='thumb_up',
                    on_click=lambda: self.on_vote(True)
                )
                if user_interested:
                    accept_btn.props('color=positive')
                
                reject_btn = ui.button(
                    'Reject' if not user_rejected else 'Rejected ✗',
                    icon='thumb_down',
                    on_click=lambda: self.on_vote(False)
                )
                if user_rejected:
                    reject_btn.props('color=negative')
    
    def _render_actions(self):
        """Render action buttons."""
        if not self.ctx.can_edit:
            return
        
        ui.separator()
        
        with ui.row().classes('gap-2 mt-2'):
            # Delete button
            if self.is_encumbered:
                # Disabled with tooltip
                btn = ui.button('Delete', icon='delete').props('disable')
                ui.tooltip('Cannot delete: other users have data on this node')
            else:
                ui.button('Delete', icon='delete', on_click=self._confirm_delete)\
                    .props('color=negative')
    
    def _update_field(self, field: str, value: Any):
        """Update a field directly."""
        if self.on_update:
            self.on_update(field, value)
    
    def _update_field_with_confirm(self, field: str, value: Any):
        """Update a field with encumbrance warning."""
        if not self.is_encumbered:
            self._update_field(field, value)
            return
        
        # Show confirmation dialog
        with ui.dialog() as dialog, ui.card():
            ui.label('⚠️ This change will affect other users').classes('text-lg font-bold')
            ui.separator()
            ui.label('The following users have data connected to this node:')
            
            for user_info in self.external_users:
                with ui.row().classes('items-center gap-2'):
                    ui.label(f"• {user_info['user_id']}")
                    if user_info.get('has_vote'):
                        interest = '(interested)' if user_info.get('interested') else '(rejected)'
                        ui.label(interest).classes('text-sm text-gray-400')
                    if user_info.get('has_metadata'):
                        ui.label('(has notes)').classes('text-sm text-gray-400')
            
            ui.separator()
            
            with ui.row().classes('gap-2 justify-end'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button('Proceed Anyway', on_click=lambda: (self._update_field(field, value), dialog.close()))\
                    .props('color=warning')
        
        dialog.open()
    
    def _confirm_delete(self):
        """Confirm and execute delete."""
        with ui.dialog() as dialog, ui.card():
            ui.label('Delete this node?').classes('text-lg font-bold')
            ui.label('This action cannot be undone.')
            
            with ui.row().classes('gap-2 justify-end mt-4'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button('Delete', on_click=lambda: (self.on_delete() if self.on_delete else None, dialog.close()))\
                    .props('color=negative')
        
        dialog.open()
    
    def _show_encumbrance_warning(self):
        """Show a warning about encumbered node."""
        with ui.row().classes('items-center gap-2 p-2 bg-yellow-900/30 rounded'):
            ui.icon('warning').classes('text-yellow-400')
            ui.label('Changes will affect other users').classes('text-sm')


def render_adaptive_header(
    ctx: UIContext,
    users: List[str] = None,
    active_user: str = "",
    on_user_change: Callable[[str], None] = None,
    on_sync: Callable[[], None] = None,
    on_push: Callable[[], None] = None
):
    """
    Convenience function to render an adaptive header.
    """
    header = AdaptiveHeader(
        ctx=ctx,
        users=users,
        active_user=active_user,
        on_user_change=on_user_change,
        on_sync=on_sync,
        on_push=on_push
    )
    header.render()


def render_adaptive_node_panel(
    ctx: UIContext,
    node: Dict[str, Any],
    active_user: str = "",
    on_update: Callable[[str, Any], None] = None,
    on_delete: Callable[[], None] = None,
    on_vote: Callable[[bool], None] = None
):
    """
    Convenience function to render an adaptive node panel.
    """
    panel = AdaptiveNodePanel(
        ctx=ctx,
        node=node,
        active_user=active_user,
        on_update=on_update,
        on_delete=on_delete,
        on_vote=on_vote
    )
    panel.render()
