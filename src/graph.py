"""
Minimal graph utilities for PRISM (scaffold).

This module contains simple helpers that will be expanded in the full project.
"""

from typing import Dict, List, Any
import uuid


def make_node(label: str, parent_id: str = "root", status: str = "pending", metadata: str = "") -> Dict[str, Any]:
    """
    Create a minimal node dictionary following the project's node schema.
    ID is a UUID4 string. Labels should be unique across the graph in real usage.
    """
    return {
        "id": str(uuid.uuid4()),
        "label": label,
        "parent_id": parent_id,
        "status": status,
        "metadata": metadata,
    }


def merge_user_nodes(list_of_node_lists: List[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """
    Merge multiple users' node lists into a single dict keyed by node id.
    This is a naive in-memory aggregator used for initial prototyping.
    Later implementations will handle authoritative mutation ledgers and conflicts.
    """
    merged = {}
    for nodes in list_of_node_lists:
        for node in nodes:
            merged[node["id"]] = node
    return merged
