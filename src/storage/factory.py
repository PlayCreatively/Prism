"""
Backend Factory for PRISM.

Creates the appropriate storage backend based on project configuration.
Handles loading project config and instantiating GitBackend or SupabaseBackend.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING

from src.storage.git_backend import GitBackend

if TYPE_CHECKING:
    from src.storage.supabase_backend import SupabaseBackend
    from src.storage.protocol import StorageBackend

logger = logging.getLogger(__name__)

# Default backend type
DEFAULT_BACKEND = "git"

# Config filename
CONFIG_FILENAME = "config.json"


def get_project_config(project_path: Union[str, Path]) -> dict:
    """
    Load project configuration from config.json.
    
    Args:
        project_path: Path to the project folder
        
    Returns:
        Dict with project config, or default config if file doesn't exist
    """
    project_path = Path(project_path)
    config_path = project_path / CONFIG_FILENAME
    
    default_config = {
        "storage_backend": DEFAULT_BACKEND
    }
    
    if not config_path.exists():
        return default_config
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Ensure storage_backend is set
            if "storage_backend" not in config:
                config["storage_backend"] = DEFAULT_BACKEND
            return config
    except Exception as e:
        logger.warning(f"Failed to load config from {config_path}: {e}")
        return default_config


def save_project_config(project_path: Union[str, Path], config: dict) -> None:
    """
    Save project configuration to config.json.
    
    Args:
        project_path: Path to the project folder
        config: Configuration dict to save
    """
    project_path = Path(project_path)
    config_path = project_path / CONFIG_FILENAME
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_backend_type(project_path: Union[str, Path]) -> str:
    """
    Get the storage backend type for a project.
    
    Args:
        project_path: Path to the project folder
        
    Returns:
        'git' or 'supabase'
    """
    config = get_project_config(project_path)
    # Support both 'backend' and 'storage_backend' keys
    return config.get("backend", config.get("storage_backend", DEFAULT_BACKEND))


def create_backend(
    project_path: Union[str, Path],
    git_manager=None,
    supabase_client=None,
    auth_provider=None,
    force_backend: Optional[str] = None,
    read_only: bool = False
) -> "StorageBackend":
    """
    Create a storage backend instance for a project.
    
    Args:
        project_path: Path to the project folder
        git_manager: Optional GitManager instance for git sync
        supabase_client: Optional Supabase client for cloud storage
        auth_provider: Optional auth provider for Supabase
        force_backend: Override the configured backend type
        read_only: If True, create a read-only backend (for public access)
        
    Returns:
        StorageBackend instance (GitBackend or SupabaseBackend)
    """
    project_path = Path(project_path)
    
    # Determine backend type
    if force_backend:
        backend_type = force_backend
    else:
        backend_type = get_backend_type(project_path)
    
    if backend_type == "supabase":
        return _create_supabase_backend(
            project_path=project_path,
            supabase_client=supabase_client,
            auth_provider=auth_provider,
            read_only=read_only
        )
    else:
        # Default to git backend
        return GitBackend(
            project_path=str(project_path),
            git_manager=git_manager
        )


def _create_supabase_backend(
    project_path: Path,
    supabase_client=None,
    auth_provider=None,
    read_only: bool = False
) -> "SupabaseBackend":
    """
    Create a Supabase backend instance.
    
    Args:
        project_path: Path to the project folder (for config)
        supabase_client: Supabase client instance
        auth_provider: Auth provider for user authentication
        read_only: If True, create a read-only backend
        
    Returns:
        SupabaseBackend instance
    """
    import os
    
    # Import here to avoid circular imports and allow optional dependency
    try:
        from src.storage.supabase_backend import SupabaseBackend
    except ImportError:
        raise ImportError(
            "SupabaseBackend requires supabase-py. "
            "Install with: pip install supabase"
        )
    
    config = get_project_config(project_path)
    
    # Get Supabase-specific config
    # project_id is the UUID from Supabase, project_slug is the human-readable identifier
    project_id = config.get("supabase_project_id")
    
    # Generate project slug from folder name
    project_name = project_path.name
    project_slug = project_name.lower().replace(' ', '-').replace('_', '-')
    
    # If we have a UUID in config, use it; otherwise backend will look up by slug
    if not project_id:
        logger.info(f"No supabase_project_id in config, will look up by slug: {project_slug}")
        project_id = project_slug  # Backend will resolve this to UUID via slug lookup
    
    # Get Supabase URL and key from config or environment
    supabase_url = config.get("supabase_url") or os.environ.get("SUPABASE_URL")
    supabase_key = config.get("supabase_key") or os.environ.get("SUPABASE_KEY")
    
    return SupabaseBackend(
        project_id=project_id,
        project_slug=project_slug,
        client=supabase_client,
        auth_provider=auth_provider,
        read_only=read_only,
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )


def create_git_project_config(
    project_path: Union[str, Path],
    remote_url: Optional[str] = None
) -> dict:
    """
    Create a git backend configuration for a new project.
    
    Args:
        project_path: Path to the project folder
        remote_url: Optional git remote URL
        
    Returns:
        The created config dict
    """
    config = {
        "storage_backend": "git"
    }
    if remote_url:
        config["git_remote_url"] = remote_url
    
    save_project_config(project_path, config)
    return config


def create_supabase_project_config(
    project_path: Union[str, Path],
    supabase_project_id: str,
    supabase_url: Optional[str] = None,
    supabase_anon_key: Optional[str] = None,
    is_public: bool = False
) -> dict:
    """
    Create a Supabase backend configuration for a new project.
    
    Args:
        project_path: Path to the project folder
        supabase_project_id: UUID of the project in Supabase
        supabase_url: Supabase project URL (optional, can use env)
        supabase_anon_key: Supabase anon key (optional, can use env)
        is_public: Whether the project is publicly accessible
        
    Returns:
        The created config dict
    """
    config = {
        "storage_backend": "supabase",
        "supabase_project_id": supabase_project_id,
        "is_public": is_public
    }
    
    if supabase_url:
        config["supabase_project_url"] = supabase_url
    if supabase_anon_key:
        config["supabase_anon_key"] = supabase_anon_key
    
    save_project_config(project_path, config)
    return config


def is_supabase_available() -> bool:
    """Check if Supabase support is available (package installed)."""
    try:
        import supabase
        return True
    except ImportError:
        return False
