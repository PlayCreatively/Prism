# src/prism_core.py
# Minimal core utilities for the PRISM app.

from typing import Dict


def get_startup_status() -> Dict[str, str]:
    """
    Return a small dictionary representing startup status.
    Kept minimal to ensure compatibility with Python 3.9+.
    """
    return {
        "status": "online",
        "message": "PRISM System Online",
        "version": __import__("pkgutil").get_data("src", "__init__.py").decode().split("__version__ = ")[1].splitlines()[0].strip("\"' ")  # conservative version read
    }
