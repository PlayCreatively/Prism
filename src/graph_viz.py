"""
Graph visualizer that produces an ECharts-compatible configuration for rendering
a directed graph where node colors are computed from interested users.

This implementation uses NetworkX to manage the graph structure, but the output
is a plain dict representing ECharts option/config which can be used with NiceGUI.

The color system dynamically assigns colors based on visible users:
- Each visible user gets an equal slice of the HSL color wheel
- When all visible users are interested, the color approaches white
"""

from typing import List, Dict, Any
import networkx as nx
from src.utils import color_from_users, get_visible_users


class GraphVisualizer:
    """
    Build an ECharts configuration (dict) for a graph visualization based on nodes
    and edges. Node colors are computed from the interested_users list for each node
    using the dynamic HSL-based color system.

    Expected node input format (list of dicts):
      {
        "id": "<unique id>",
        "label": "<display label>",
        "interested_users": ["User1", "User2"]   # any subset of visible users
      }

    Expected edge input format (list of dicts):
      {
        "source": "<node id>",
        "target": "<node id>"
      }

    The returned dict follows an ECharts option pattern with a single 'graph' series:
      {
        "series": [
          {
            "type": "graph",
            "layout": "force",
            "roam": True,
            "data": [...],
            "links": [...],
            ...
          }
        ]
      }
    """

    def __init__(self):
        # placeholder for networkx graph instance
        self.G = nx.DiGraph()

    @staticmethod
    def _normalize_user(u: str) -> str:
        return (u or "").strip()

    @classmethod
    def color_for_users(cls, users: List[str], visible_users: List[str] = None) -> str:
        """
        Compute hex color string for a list of users using the dynamic color system.
        Returns color as lowercase hex string like '#ff00aa'.
        """
        return color_from_users(users, visible_users=visible_users)

    @staticmethod
    def _is_white_color(hex_color: str) -> bool:
        """
        Determine if a hex color represents white (#ffffff or #fff).
        Comparison is case-insensitive.
        """
        if not hex_color:
            return False
        c = hex_color.lower()
        if c == "#ffffff" or c == "#fff":
            return True
        return False

    def generate_echarts(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Given node and edge definitions, construct the ECharts option dict.
        """
        # Clear and rebuild graph
        self.G = nx.DiGraph()
        # Map node id to computed color for reference
        color_map = {}

        # Add nodes to NetworkX graph and prepare ECharts data entries
        for nd in nodes:
            node_id = nd.get("id")
            label = nd.get("label", "")
            interested = nd.get("interested_users", [])
            color = self.color_for_users(interested)
            color_map[node_id] = color
            # store attributes in networkx graph
            self.G.add_node(node_id, label=label, interested_users=interested, color=color)

        # Add edges
        for e in edges or []:
            src = e.get("source")
            tgt = e.get("target")
            # Only add edges if both nodes exist
            if src in self.G.nodes and tgt in self.G.nodes:
                self.G.add_edge(src, tgt)

        # Build ECharts 'data' array
        data = []
        for n, attrs in self.G.nodes(data=True):
            data.append({
                "id": n,
                "name": attrs.get("label", n),
                "symbolSize": 28,
                "itemStyle": {"color": attrs.get("color")},
                "label": {"show": True, "formatter": attrs.get("label", n)},
                # Keep interested_users for debugging / potential UI use
                "interested_users": attrs.get("interested_users", []),
            })

        # Build ECharts 'links' array, applying special styling when both endpoints are white (full consensus)
        links = []
        for src, tgt in self.G.edges():
            src_color = color_map.get(src, "#000000")
            tgt_color = color_map.get(tgt, "#000000")
            is_consensus_path = self._is_white_color(src_color) and self._is_white_color(tgt_color)

            if is_consensus_path:
                line_style = {
                    "color": "#ffd700",      # gold line for consensus path
                    "width": 6,
                    "opacity": 1.0,
                    # Use shadow to emulate a glow
                    "shadowColor": "#ffd700",
                    "shadowBlur": 12,
                }
            else:
                line_style = {
                    "color": "#bdbdbd",   # neutral gray
                    "width": 1,
                    "opacity": 0.9,
                }

            links.append({
                "source": src,
                "target": tgt,
                "lineStyle": line_style,
            })

        # Compose final ECharts option dict
        option = {
            "series": [
                {
                    "type": "graph",
                    "layout": "force",
                    "roam": True,
                    "data": data,
                    "links": links,
                    "force": {"repulsion": 200, "edgeLength": [50, 150]},
                    "emphasis": {"focus": "adjacency"},
                }
            ]
        }
        return option
