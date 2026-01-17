"""
Manual editing system for PRISM graph.

This package provides Ctrl+Click editing capabilities:
- EditController: State management and hit detection
- EditActions: Graph mutation execution
- EditOverlay: HTML/JS preview rendering
- edit_handlers: Event handlers for app.py integration

Usage:
    from src.edit import EditController, EditActions, EditOverlay
    from src.edit.handlers import setup_edit_handlers
"""

from src.edit.constants import (
    EDGE_MIDDLE_TOLERANCE,
    EDGE_HOVER_TOLERANCE,
    CONNECTION_RADIUS,
    NODE_CLICK_RADIUS,
    CHART_WIDTH,
    CHART_HEIGHT,
)
from src.edit.controller import EditController, EditState
from src.edit.actions import EditActions
from src.edit.overlay import EditOverlay
from src.edit.handlers import setup_edit_handlers

__all__ = [
    'EditController',
    'EditState',
    'EditActions',
    'EditOverlay',
    'setup_edit_handlers',
    'EDGE_MIDDLE_TOLERANCE',
    'EDGE_HOVER_TOLERANCE', 
    'CONNECTION_RADIUS',
    'NODE_CLICK_RADIUS',
    'CHART_WIDTH',
    'CHART_HEIGHT',
]
