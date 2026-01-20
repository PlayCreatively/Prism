"""
Custom Fields Module

Provides UI rendering for node type custom fields.
Each field type (text, tag, user) has its own renderer module.
"""

from .renderer import render_custom_fields

__all__ = ['render_custom_fields']
