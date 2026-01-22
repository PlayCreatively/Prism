"""
Authentication Pages for PRISM.

NiceGUI pages for login, registration, and logout.
"""

import logging
from typing import Optional

from nicegui import ui, app

from src.auth.session import get_session_manager

logger = logging.getLogger(__name__)


def create_login_page():
    """
    Create the login page route.
    
    Call this function during app setup to register the /login route.
    """
    
    @ui.page('/login')
    def login_page():
        """Login page with email/password form."""
        
        # Check if already logged in
        session_manager = get_session_manager()
        if session_manager.get_current_user():
            redirect = app.storage.user.get("redirect_after_login", "/")
            app.storage.user.pop("redirect_after_login", None)
            ui.navigate.to(redirect)
            return
        
        # Page styling
        ui.add_head_html('''
            <style>
                .login-container {
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                }
                .login-card {
                    width: 100%;
                    max-width: 400px;
                    padding: 2rem;
                }
            </style>
        ''')
        
        with ui.column().classes('login-container w-full'):
            with ui.card().classes('login-card'):
                # Header
                ui.label('Welcome to PRISM').classes('text-2xl font-bold text-center w-full mb-2')
                ui.label('Sign in to continue').classes('text-gray-400 text-center w-full mb-6')
                
                # Form
                email_input = ui.input('Email').props('outlined').classes('w-full')
                password_input = ui.input('Password', password=True, password_toggle_button=True)\
                    .props('outlined').classes('w-full')
                
                error_label = ui.label('').classes('text-red-500 text-sm hidden')
                
                async def do_login():
                    email = email_input.value.strip()
                    password = password_input.value
                    
                    if not email or not password:
                        error_label.text = 'Please enter email and password'
                        error_label.classes(remove='hidden')
                        return
                    
                    # Show loading
                    login_button.props('loading')
                    
                    result = session_manager.login(email, password)
                    
                    login_button.props(remove='loading')
                    
                    if result['success']:
                        ui.notify('Login successful!', color='positive')
                        redirect = app.storage.user.get("redirect_after_login", "/")
                        app.storage.user.pop("redirect_after_login", None)
                        ui.navigate.to(redirect)
                    else:
                        error_label.text = result.get('error', 'Login failed')
                        error_label.classes(remove='hidden')
                
                login_button = ui.button('Sign In', on_click=do_login)\
                    .classes('w-full mt-4').props('color=primary')
                
                # Enter key to submit
                password_input.on('keydown.enter', do_login)
                
                # Register link
                ui.separator().classes('my-4')
                
                with ui.row().classes('w-full justify-center'):
                    ui.label("Don't have an account?").classes('text-gray-400')
                    ui.link('Register', '/register').classes('text-blue-400')


def create_register_page():
    """
    Create the registration page route.
    
    Call this function during app setup to register the /register route.
    """
    
    @ui.page('/register')
    def register_page():
        """Registration page with email/password/username form."""
        
        session_manager = get_session_manager()
        
        # Check if already logged in
        if session_manager.get_current_user():
            ui.navigate.to('/')
            return
        
        # Page styling
        ui.add_head_html('''
            <style>
                .register-container {
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                }
                .register-card {
                    width: 100%;
                    max-width: 400px;
                    padding: 2rem;
                }
            </style>
        ''')
        
        with ui.column().classes('register-container w-full'):
            with ui.card().classes('register-card'):
                # Header
                ui.label('Create Account').classes('text-2xl font-bold text-center w-full mb-2')
                ui.label('Join PRISM to collaborate').classes('text-gray-400 text-center w-full mb-6')
                
                # Form
                username_input = ui.input('Username').props('outlined').classes('w-full')
                email_input = ui.input('Email').props('outlined').classes('w-full')
                password_input = ui.input('Password', password=True, password_toggle_button=True)\
                    .props('outlined').classes('w-full')
                confirm_password_input = ui.input('Confirm Password', password=True, password_toggle_button=True)\
                    .props('outlined').classes('w-full')
                
                error_label = ui.label('').classes('text-red-500 text-sm hidden')
                
                async def do_register():
                    username = username_input.value.strip()
                    email = email_input.value.strip()
                    password = password_input.value
                    confirm = confirm_password_input.value
                    
                    # Validation
                    if not username:
                        error_label.text = 'Please enter a username'
                        error_label.classes(remove='hidden')
                        return
                    
                    if len(username) < 3:
                        error_label.text = 'Username must be at least 3 characters'
                        error_label.classes(remove='hidden')
                        return
                    
                    if not email:
                        error_label.text = 'Please enter an email'
                        error_label.classes(remove='hidden')
                        return
                    
                    if not password:
                        error_label.text = 'Please enter a password'
                        error_label.classes(remove='hidden')
                        return
                    
                    if len(password) < 6:
                        error_label.text = 'Password must be at least 6 characters'
                        error_label.classes(remove='hidden')
                        return
                    
                    if password != confirm:
                        error_label.text = 'Passwords do not match'
                        error_label.classes(remove='hidden')
                        return
                    
                    # Show loading
                    register_button.props('loading')
                    
                    result = session_manager.register(email, password, username)
                    
                    register_button.props(remove='loading')
                    
                    if result['success']:
                        ui.notify('Account created! Check your email to confirm before logging in.', color='positive')
                        ui.navigate.to('/')
                    else:
                        error_label.text = result.get('error', 'Registration failed')
                        error_label.classes(remove='hidden')
                
                register_button = ui.button('Create Account', on_click=do_register)\
                    .classes('w-full mt-4').props('color=primary')
                
                # Enter key to submit
                confirm_password_input.on('keydown.enter', do_register)
                
                # Login link
                ui.separator().classes('my-4')
                
                with ui.row().classes('w-full justify-center'):
                    ui.label('Already have an account?').classes('text-gray-400')
                    ui.link('Sign In', '/login').classes('text-blue-400')


def create_logout_handler():
    """
    Create the logout route.
    
    Call this function during app setup to register the /logout route.
    """
    
    @ui.page('/logout')
    def logout_page():
        """Logout and redirect to home."""
        session_manager = get_session_manager()
        session_manager.logout()
        ui.notify('Logged out successfully', color='info')
        ui.navigate.to('/')


def render_user_menu(container=None):
    """
    Render a user menu in the header.
    
    Shows login button if not authenticated, or user dropdown if authenticated.
    
    Args:
        container: Optional UI container to render into
    """
    from src.auth.middleware import get_current_user
    
    user = get_current_user()
    
    parent = container or ui
    
    if user:
        # Authenticated user menu
        with parent:
            with ui.button(icon='account_circle').props('flat round'):
                with ui.menu():
                    with ui.column().classes('p-2 min-w-48'):
                        ui.label(user.get('display_name') or user.get('username')).classes('font-bold')
                        ui.label(user.get('email', '')).classes('text-sm text-gray-400')
                    
                    ui.separator()
                    
                    ui.menu_item('Settings', lambda: ui.navigate.to('/settings'))
                    ui.menu_item('Logout', lambda: ui.navigate.to('/logout'))
    else:
        # Not authenticated - show login button
        with parent:
            ui.button('Sign In', on_click=lambda: ui.navigate.to('/login'))\
                .props('flat')


def render_login_prompt():
    """
    Render a login prompt for public/read-only views.
    
    Call this when showing a public project to encourage login.
    """
    with ui.card().classes('w-full max-w-md mx-auto my-4 p-4'):
        with ui.row().classes('items-center gap-4'):
            ui.icon('lock_open').classes('text-4xl text-blue-400')
            with ui.column():
                ui.label('Want to contribute?').classes('font-bold')
                ui.label('Sign in or create an account to edit this project.').classes('text-sm text-gray-400')
        
        with ui.row().classes('mt-4 gap-2'):
            ui.button('Sign In', on_click=lambda: ui.navigate.to('/login')).props('color=primary')
            ui.button('Register', on_click=lambda: ui.navigate.to('/register')).props('outline')
