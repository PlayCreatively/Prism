# Minimal core utilities for the scaffolded PRISM app.
# Uses networkx to create a simple directed graph that demonstrates imports/functions.

import networkx as nx
from typing import Any


def build_sample_graph() -> nx.DiGraph:
    """
    Build a tiny example directed graph to validate networkx usage.
    Returns:
        nx.DiGraph: A graph with a root and two child nodes.
    """
    G = nx.DiGraph()
    # Add nodes with some minimal metadata
    G.add_node("root", label="root", status="accepted", interested_users=[])
    G.add_node("serious_games", label="Serious Games", status="pending", interested_users=["Alex"])
    G.add_node("ai_agents", label="AI Agents", status="pending", interested_users=["Sasha", "Alison"])

    # Add edges
    G.add_edge("root", "serious_games", relation="child")
    G.add_edge("root", "ai_agents", relation="child")

    return G
