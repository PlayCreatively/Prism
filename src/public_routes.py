"""
Public Routes for PRISM.

Provides read-only access to public projects via /public/{slug} URLs.
Unauthenticated users can view but not edit.
"""

import logging
from typing import Optional, Dict, Any

from nicegui import ui, app

logger = logging.getLogger(__name__)


def create_public_routes():
    """
    Create public access routes.
    
    Call this function during app setup to register public routes.
    """
    
    @ui.page('/public/{project_slug}')
    async def public_project_page(project_slug: str):
        """
        Public read-only view of a project.
        
        Displays the graph visualization without editing capabilities.
        Shows login prompt for users who want to contribute.
        """
        from src.storage.factory import get_project_config, create_backend
        from src.project_manager import get_project_path, project_exists, list_projects
        from src.auth.middleware import get_current_user
        from src.auth.pages import render_login_prompt
        
        # Find the project
        project_name = None
        project_path = None
        
        # Check if slug matches a project name
        projects = list_projects()
        for proj in projects:
            if proj.lower().replace(' ', '-') == project_slug.lower():
                project_name = proj
                project_path = str(get_project_path(proj))
                break
        
        if not project_name:
            # Check by exact name
            if project_exists(project_slug):
                project_name = project_slug
                project_path = str(get_project_path(project_slug))
        
        if not project_name:
            with ui.column().classes('items-center justify-center min-h-screen'):
                ui.icon('error_outline').classes('text-6xl text-red-400')
                ui.label('Project Not Found').classes('text-2xl font-bold mt-4')
                ui.label(f'The project "{project_slug}" does not exist or is not public.').classes('text-gray-400')
                ui.button('Go Home', on_click=lambda: ui.navigate.to('/')).classes('mt-4')
            return
        
        # Check if project is public
        config = get_project_config(project_path)
        
        # For git projects, they're "public" locally by default
        # For Supabase projects, check the is_public flag
        is_public = True
        if config.get('storage_backend') == 'supabase':
            is_public = config.get('is_public', False)
        
        if not is_public:
            # Check if user is logged in and has access
            user = get_current_user()
            if not user:
                with ui.column().classes('items-center justify-center min-h-screen'):
                    ui.icon('lock').classes('text-6xl text-yellow-400')
                    ui.label('Private Project').classes('text-2xl font-bold mt-4')
                    ui.label('This project is private. Please sign in to access.').classes('text-gray-400')
                    ui.button('Sign In', on_click=lambda: ui.navigate.to(f'/login?redirect=/public/{project_slug}')).classes('mt-4')
                return
        
        # Create read-only backend
        try:
            backend = create_backend(project_path, read_only=True)
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            ui.label(f'Error loading project: {e}').classes('text-red-400')
            return
        
        # Render public view
        await render_public_project_view(project_name, backend)


async def render_public_project_view(project_name: str, backend):
    """
    Render the public read-only view of a project.
    
    Args:
        project_name: Name of the project
        backend: StorageBackend instance (read-only)
    """
    from src.auth.middleware import get_current_user, is_authenticated
    from src.auth.pages import render_login_prompt
    from src.data_manager import DataManager
    
    # Create data manager with read-only backend
    dm = DataManager(backend=backend)
    
    # Get graph data
    graph_data = dm.get_graph()
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])
    
    # Page header
    with ui.header().classes('bg-slate-800 px-4 py-2'):
        with ui.row().classes('items-center gap-4 w-full'):
            # Logo/title
            ui.label('PRISM').classes('text-xl font-bold')
            ui.separator().props('vertical').classes('h-6')
            ui.label(project_name).classes('text-lg')
            
            # Public badge
            with ui.badge('Public', color='blue').classes('ml-2'):
                ui.tooltip('Anyone can view this project')
            
            ui.space()
            
            # User menu / login button
            user = get_current_user()
            if user:
                with ui.button(icon='account_circle').props('flat round'):
                    with ui.menu():
                        ui.label(user.get('username', 'User')).classes('font-bold px-4 py-2')
                        ui.separator()
                        ui.menu_item('Go to Dashboard', lambda: ui.navigate.to('/'))
                        ui.menu_item('Logout', lambda: ui.navigate.to('/logout'))
            else:
                ui.button('Sign In to Contribute', on_click=lambda: ui.navigate.to('/login'))\
                    .props('outline color=white')
    
    # Main content
    with ui.column().classes('w-full h-full p-4'):
        # Info banner for non-authenticated users
        if not is_authenticated():
            render_login_prompt()
        
        # Graph visualization
        with ui.card().classes('w-full flex-1'):
            ui.label('Project Graph').classes('text-lg font-bold mb-4')
            
            if not nodes:
                ui.label('This project has no nodes yet.').classes('text-gray-400')
            else:
                # Render ECharts graph
                render_public_graph(nodes, edges)
        
        # Node details panel (when a node is selected)
        with ui.card().classes('w-full mt-4') as details_panel:
            details_panel.set_visibility(False)
            ui.label('Select a node to view details').classes('text-gray-400')


def render_public_graph(nodes: list, edges: list):
    """
    Render the graph visualization for public view.
    
    Uses ECharts with interaction disabled for editing.
    """
    from src.graph_viz import build_echart_options
    
    # Build ECharts options (read-only mode)
    try:
        options = build_echart_options(nodes, edges, read_only=True)
    except Exception:
        # Fallback to basic options
        options = build_basic_echart_options(nodes, edges)
    
    chart = ui.echart(options).classes('w-full h-96')
    
    # Handle node click to show details
    def on_node_click(e):
        if e.args and 'data' in e.args:
            node_data = e.args['data']
            show_node_details_dialog(node_data)
    
    chart.on('click', on_node_click)


def build_basic_echart_options(nodes: list, edges: list) -> dict:
    """
    Build basic ECharts options for the graph.
    
    Fallback when graph_viz module has issues.
    """
    chart_nodes = []
    for node in nodes:
        # Calculate color based on interested users
        interested = node.get('interested_users', [])
        color = '#808080'  # Default gray
        
        if len(interested) == 0:
            color = '#4a5568'  # Dark gray
        elif len(interested) == 1:
            color = '#ef4444'  # Red for single user
        elif len(interested) == 2:
            color = '#eab308'  # Yellow for two users
        else:
            color = '#ffffff'  # White for consensus
        
        chart_nodes.append({
            'id': node['id'],
            'name': node.get('label', 'Untitled'),
            'symbolSize': 30 + len(interested) * 10,
            'itemStyle': {'color': color},
            'label': {'show': True},
            # Store extra data for click handler
            'description': node.get('description', ''),
            'interested_users': interested,
            'rejected_users': node.get('rejected_users', [])
        })
    
    chart_edges = []
    for edge in edges:
        chart_edges.append({
            'source': edge['source'],
            'target': edge['target']
        })
    
    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}'
        },
        'series': [{
            'type': 'graph',
            'layout': 'force',
            'data': chart_nodes,
            'links': chart_edges,
            'roam': True,
            'draggable': False,  # Read-only
            'force': {
                'repulsion': 200,
                'gravity': 0.1
            },
            'emphasis': {
                'focus': 'adjacency'
            }
        }]
    }


def show_node_details_dialog(node_data: dict):
    """
    Show a dialog with node details (read-only).
    """
    with ui.dialog() as dialog, ui.card().classes('min-w-96'):
        with ui.row().classes('items-center justify-between w-full'):
            ui.label(node_data.get('name', 'Node')).classes('text-xl font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round')
        
        ui.separator()
        
        # Description
        description = node_data.get('description', '')
        if description:
            ui.markdown(description).classes('prose prose-invert max-w-none')
        else:
            ui.label('No description').classes('text-gray-400 italic')
        
        ui.separator()
        
        # Interested users
        interested = node_data.get('interested_users', [])
        if interested:
            with ui.row().classes('items-center gap-2'):
                ui.icon('thumb_up').classes('text-green-400')
                ui.label(f'Interested: {", ".join(interested)}')
        
        # Rejected users
        rejected = node_data.get('rejected_users', [])
        if rejected:
            with ui.row().classes('items-center gap-2'):
                ui.icon('thumb_down').classes('text-red-400')
                ui.label(f'Rejected: {", ".join(rejected)}')
        
        # Login prompt
        from src.auth.middleware import is_authenticated
        if not is_authenticated():
            ui.separator()
            with ui.row().classes('items-center gap-2 text-gray-400'):
                ui.icon('info')
                ui.label('Sign in to vote or add notes')
    
    dialog.open()


def get_project_public_url(project_name: str) -> str:
    """
    Get the public URL for a project.
    
    Args:
        project_name: Name of the project
        
    Returns:
        URL slug for public access
    """
    # Convert to URL-friendly slug
    slug = project_name.lower().replace(' ', '-')
    # Remove special characters
    import re
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return f'/public/{slug}'


def create_share_button(project_name: str):
    """
    Create a share button that copies the public URL.
    
    Args:
        project_name: Name of the project
    """
    url = get_project_public_url(project_name)
    
    async def copy_url():
        full_url = f"{ui.context.client.request.base_url.scheme}://{ui.context.client.request.base_url.netloc}{url}"
        await ui.run_javascript(f'navigator.clipboard.writeText("{full_url}")')
        ui.notify('Public URL copied to clipboard!', color='positive')
    
    with ui.button(icon='share').props('flat round'):
        ui.tooltip('Copy public link')
    
    return ui.button('Share', icon='share', on_click=copy_url).props('outline')
