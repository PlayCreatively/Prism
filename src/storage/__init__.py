"""
Storage backend abstraction for PRISM.

Supports multiple storage backends:
- GitBackend: Local file storage with git sync (default)
- SupabaseBackend: Cloud PostgreSQL with real-time sync
"""

from src.storage.protocol import StorageBackend
from src.storage.git_backend import GitBackend
from src.storage.factory import create_backend, get_backend_type

__all__ = [
    'StorageBackend',
    'GitBackend', 
    'create_backend',
    'get_backend_type',
]
