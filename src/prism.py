"""
Minimal PRISM core utilities.

This module provides a tiny, dependency-using scaffold so the app can import
and verify that nicegui, networkx, and graphviz are available.
"""

from typing import Tuple

import networkx as nx
from graphviz import Digraph


def initialize_graph() -> Tuple[nx.DiGraph, Digraph]:
    """
    Create a very small example directed graph with NetworkX and a Graphviz
    Digraph representation. Returned objects are:
      - NetworkX DiGraph (for future algorithmic use)
      - graphviz.Digraph (for visualization via nicegui.ui.graphviz)
    """
    G = nx.DiGraph()
    # Minimal example nodes with labels
    G.add_node("root", label="Root")
    G.add_node("serious_games", label="Serious Games")
    G.add_node("ai_agent", label="AI Agent")

    # Simple relationships
    G.add_edge("root", "serious_games")
    G.add_edge("root", "ai_agent")

    # Build a Graphviz DOT representation
    dot = Digraph(name="prism_graph", comment="PRISM Sample Graph")
    for node_id, data in G.nodes(data=True):
        label = data.get("label", node_id)
        dot.node(node_id, label=label)

    for u, v in G.edges():
        dot.edge(u, v)

    return G, dot


def get_status() -> str:
    """
    Return a short status string used by the app at startup.
    """
    return "PRISM System Online"
