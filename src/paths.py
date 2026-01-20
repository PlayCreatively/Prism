"""
Path utilities for PRISM.

Handles path resolution for both development mode and frozen (PyInstaller) executables.
- In development: paths are relative to the project root
- When frozen: paths are relative to the executable location

External data (db/, node_types/, config.json) lives NEXT TO the executable, not bundled inside.
"""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """
    Get the application directory.
    
    - In development: the project root (parent of src/)
    - When frozen: the directory containing the executable
    
    This is where external data folders (db/, prompts/) should be located.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use executable's directory
        return Path(sys.executable).parent
    else:
        # Development mode - use the project root (parent of src/)
        return Path(__file__).parent.parent


def get_db_dir() -> Path:
    """Get the database directory (db/) containing all projects."""
    return get_app_dir() / "db"


def get_config_path() -> Path:
    """Get the path to the config file (stores API key, etc.)."""
    return get_app_dir() / "config.json"


def ensure_db_dir() -> Path:
    """
    Ensure the db directory exists, creating it if necessary.
    Returns the path to the db directory.
    """
    db_dir = get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir
