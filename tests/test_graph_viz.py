import pytest
from src.graph_viz import GraphVisualizer

def find_link(links, src, tgt):
    for l in links:
        if l.get("source") == src and l.get("target") == tgt:
            return l
    return None

def test_color_mapping_and_edges():
    """
    Verify that node colors follow the RGB additive model and that edges connecting
    two white (full-consensus) nodes are highlighted (thicker + glow).
    """
    nodes = [
        {"id": "n_red", "label": "Red Node", "interested_users": ["Alex"]},
        {"id": "n_green", "label": "Green Node", "interested_users": ["Sasha"]},
        {"id": "n_blue", "label": "Blue Node", "interested_users": ["Alison"]},
        {"id": "n_yellow", "label": "Yellow Node", "interested_users": ["Alex", "Sasha"]},
        {"id": "n_magenta", "label": "Magenta Node", "interested_users": ["Alex", "Alison"]},
        {"id": "n_cyan", "label": "Cyan Node", "interested_users": ["Sasha", "Alison"]},
        {"id": "n_white_a", "label": "White A", "interested_users": ["Alex", "Sasha", "Alison"]},
        {"id": "n_white_b", "label": "White B", "interested_users": ["Alex", "Sasha", "Alison"]},
    ]

    edges = [
        {"source": "n_red", "target": "n_green"},
        {"source": "n_white_a", "target": "n_white_b"},  # consensus path, should be highlighted
        {"source": "n_blue", "target": "n_magenta"},
    ]

    viz = GraphVisualizer()
    echarts_opt = viz.generate_echarts(nodes, edges)

    # basic structure
    assert isinstance(echarts_opt, dict)
    assert "series" in echarts_opt and isinstance(echarts_opt["series"], list)
    series = echarts_opt["series"][0]
    assert "data" in series and "links" in series

    data = series["data"]
    links = series["links"]

    # Build a map from id -> itemStyle color
    color_map = {d["id"]: d["itemStyle"]["color"] for d in data}

    expected = {
        "n_red": "#ff0000",
        "n_green": "#00ff00",
        "n_blue": "#0000ff",
        "n_yellow": "#ffff00",
        "n_magenta": "#ff00ff",
        "n_cyan": "#00ffff",
        "n_white_a": "#ffffff",
        "n_white_b": "#ffffff",
    }

    # verify colors exactly match expected hex codes
    assert color_map == expected

    # verify consensus edge is highlighted (thicker than default)
    consensus_link = find_link(links, "n_white_a", "n_white_b")
    assert consensus_link is not None, "consensus link missing"
    ls = consensus_link.get("lineStyle", {})
    assert ls.get("width", 0) >= 4, "consensus path should have larger width"
    # glow emulation uses shadowBlur in our implementation
    assert ls.get("shadowBlur", 0) >= 10

    # verify a normal edge has a thin gray style
    normal_link = find_link(links, "n_red", "n_green")
    assert normal_link is not None
    normal_ls = normal_link.get("lineStyle", {})
    assert normal_ls.get("width", 0) == 1
    assert normal_ls.get("color") == "#bdbdbd"
