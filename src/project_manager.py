"""
Project Manager for PRISM.

Handles multi-project support where each project is a folder inside db/
with its own:
- data/ folder (user state files)
- nodes/ folder (node files)
- .git/ folder (separate repository)

Projects are completely isolated from each other.
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Base directory for all projects
PROJECTS_BASE_DIR = Path("db")


def get_projects_dir() -> Path:
    """Get the base directory containing all projects."""
    return PROJECTS_BASE_DIR


def list_projects() -> List[str]:
    """
    List all available projects.
    
    A valid project is a folder inside db/ that contains either:
    - a 'nodes' subfolder, OR
    - a 'data' subfolder
    
    Returns a sorted list of project names (folder names).
    """
    base = get_projects_dir()
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return []
    
    projects = []
    for item in base.iterdir():
        if item.is_dir():
            # Skip hidden folders and special files
            if item.name.startswith('.'):
                continue
            # Check if it's a valid project (has nodes or data subfolder)
            has_nodes = (item / "nodes").exists()
            has_data = (item / "data").exists()
            if has_nodes or has_data:
                projects.append(item.name)
    
    return sorted(projects)


def get_project_path(project_name: str) -> Path:
    """Get the full path to a project folder."""
    return get_projects_dir() / project_name


def project_exists(project_name: str) -> bool:
    """Check if a project exists."""
    return project_name in list_projects()


def get_project_data_dir(project_name: str) -> str:
    """Get the data directory path for a project (for DataManager)."""
    return str(get_project_path(project_name) / "data")


def get_project_git_path(project_name: str) -> str:
    """Get the git repository path for a project (for GitManager)."""
    return str(get_project_path(project_name))


def create_project(
    project_name: str,
    initial_username: str,
    root_node_label: str,
    root_node_description: str = "",
    init_git: bool = True
) -> Dict[str, Any]:
    """
    Create a new project with the required folder structure.
    
    Args:
        project_name: Name of the project (will be the folder name)
        initial_username: First user to create
        root_node_label: Label for the root node
        root_node_description: Optional description for the root node
        init_git: Whether to initialize a git repository
        
    Returns:
        Dict with 'success' (bool), 'message' (str), and optionally 'project_path'
    """
    # Validate project name
    if not project_name or not project_name.strip():
        return {'success': False, 'message': 'Project name cannot be empty'}
    
    project_name = project_name.strip()
    
    # Check for invalid characters in folder name
    invalid_chars = '<>:"/\\|?*'
    if any(c in project_name for c in invalid_chars):
        return {'success': False, 'message': f'Project name cannot contain: {invalid_chars}'}
    
    # Check if project already exists
    project_path = get_project_path(project_name)
    if project_path.exists():
        return {'success': False, 'message': f'Project "{project_name}" already exists'}
    
    # Validate username
    if not initial_username or not initial_username.strip():
        return {'success': False, 'message': 'Username cannot be empty'}
    
    initial_username = initial_username.strip()
    
    # Validate root node label
    if not root_node_label or not root_node_label.strip():
        return {'success': False, 'message': 'Root node label cannot be empty'}
    
    root_node_label = root_node_label.strip()
    
    try:
        # Create project structure
        data_dir = project_path / "data"
        nodes_dir = project_path / "nodes"
        
        data_dir.mkdir(parents=True, exist_ok=True)
        nodes_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize git repository if requested
        if init_git:
            try:
                subprocess.run(
                    ['git', 'init'],
                    cwd=str(project_path),
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Create .gitignore
                gitignore_path = project_path / ".gitignore"
                gitignore_path.write_text("__pycache__/\n*.pyc\n.DS_Store\n", encoding='utf-8')
                
            except subprocess.CalledProcessError as e:
                logger.warning(f"Git init failed for project {project_name}: {e}")
                # Don't fail project creation if git init fails
        
        # Now create the initial user and root node using DataManager
        # We import here to avoid circular imports
        from src.data_manager import DataManager
        
        dm = DataManager(data_dir=str(data_dir))
        
        # Create the root node with the initial user
        root_node = dm.add_node(
            label=root_node_label,
            parent_id=None,
            users=[initial_username],
            interested=True,
            description=root_node_description
        )
        
        logger.info(f"Created project '{project_name}' with user '{initial_username}' and root node '{root_node_label}'")
        
        return {
            'success': True,
            'message': f'Project "{project_name}" created successfully',
            'project_path': str(project_path),
            'root_node_id': root_node.get('id')
        }
        
    except Exception as e:
        logger.error(f"Failed to create project {project_name}: {e}")
        # Try to clean up on failure
        try:
            import shutil
            if project_path.exists():
                shutil.rmtree(project_path)
        except Exception:
            pass
        return {'success': False, 'message': f'Failed to create project: {str(e)}'}


def delete_project(project_name: str) -> Dict[str, Any]:
    """
    Delete a project and all its data.
    
    WARNING: This is destructive and cannot be undone!
    
    Args:
        project_name: Name of the project to delete
        
    Returns:
        Dict with 'success' (bool) and 'message' (str)
    """
    if not project_exists(project_name):
        return {'success': False, 'message': f'Project "{project_name}" does not exist'}
    
    try:
        import shutil
        project_path = get_project_path(project_name)
        shutil.rmtree(project_path)
        logger.info(f"Deleted project '{project_name}'")
        return {'success': True, 'message': f'Project "{project_name}" deleted'}
    except Exception as e:
        logger.error(f"Failed to delete project {project_name}: {e}")
        return {'success': False, 'message': f'Failed to delete project: {str(e)}'}


def get_project_users(project_name: str) -> List[str]:
    """Get list of users in a project."""
    if not project_exists(project_name):
        return []
    
    data_dir = get_project_path(project_name) / "data"
    if not data_dir.exists():
        return []
    
    return sorted([f.stem for f in data_dir.glob("*.json")])


def add_user_to_project(project_name: str, username: str) -> Dict[str, Any]:
    """
    Add a new user to an existing project.
    
    Args:
        project_name: Name of the project
        username: Name of the new user
        
    Returns:
        Dict with 'success' (bool) and 'message' (str)
    """
    if not project_exists(project_name):
        return {'success': False, 'message': f'Project "{project_name}" does not exist'}
    
    if not username or not username.strip():
        return {'success': False, 'message': 'Username cannot be empty'}
    
    username = username.strip()
    
    # Check if user already exists
    existing_users = get_project_users(project_name)
    if username in existing_users:
        return {'success': False, 'message': f'User "{username}" already exists in project'}
    
    try:
        from src.data_manager import DataManager
        data_dir = get_project_data_dir(project_name)
        dm = DataManager(data_dir=data_dir)
        
        # Create user file (load_user creates empty file if not exists)
        dm.load_user(username)
        
        return {'success': True, 'message': f'User "{username}" added to project'}
    except Exception as e:
        return {'success': False, 'message': f'Failed to add user: {str(e)}'}
