import json
from pathlib import Path

import pytest

from src.data_manager import DataManager


def test_load_new_user_creates_file_and_schema(tmp_path):
    data_dir = tmp_path / "data"
    manager = DataManager(str(data_dir))

    user_id = "alex"
    data = manager.load_user(user_id)

    # Schema checks - current schema uses nodes as a dict (UUID -> state)
    assert isinstance(data, dict)
    assert data["user_id"] == user_id
    assert isinstance(data["nodes"], dict)
    assert data["nodes"] == {}

    # File created
    file_path = data_dir / f"{user_id}.json"
    assert file_path.exists()

    # File content is valid JSON and matches the returned data
    with file_path.open("r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert file_data == data


def test_save_user_and_reload(tmp_path):
    data_dir = tmp_path / "data"
    manager = DataManager(str(data_dir))

    user_id = "sasha"
    data = manager.load_user(user_id)

    # Add a node vote (current schema: UUID -> {interested, metadata})
    data["nodes"]["uuid-1234"] = {
        "interested": True,
        "metadata": "Some notes"
    }

    manager.save_user(data)

    # Reload using a new manager instance to ensure persistence to disk
    manager2 = DataManager(str(data_dir))
    reloaded = manager2.load_user(user_id)

    assert reloaded["user_id"] == user_id
    assert "uuid-1234" in reloaded["nodes"]
    assert reloaded["nodes"]["uuid-1234"]["interested"] == True


def test_load_existing_file_with_missing_keys_is_normalized(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "alison.json"

    # Create a file that lacks some keys or has wrong types
    bad_content = {
        "user_id": "alison",
        "nodes": []  # wrong type - should be dict, not list
    }
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(bad_content, f)

    manager = DataManager(str(data_dir))
    data = manager.load_user("alison")

    assert data["user_id"] == "alison"
    # The current implementation converts list to empty dict
    assert isinstance(data["nodes"], dict)


def test_add_node_creates_individual_file(tmp_path):
    """Test that adding a node creates an individual file in db/nodes/."""
    data_dir = tmp_path / "data"
    manager = DataManager(str(data_dir))
    
    # Add a node
    node = manager.add_node("Test Idea", parent_id=None, users=[], description="A test node")
    
    # Check that node file was created
    nodes_dir = data_dir.parent / "nodes"
    node_file = nodes_dir / f"{node['id']}.json"
    assert node_file.exists()
    
    # Verify content
    with node_file.open("r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert file_data["id"] == node["id"]
    assert file_data["label"] == "Test Idea"
    assert file_data["parent_id"] is None
    assert file_data["description"] == "A test node"


def test_load_global_reads_from_nodes_directory(tmp_path):
    """Test that _load_global reads nodes from individual files."""
    data_dir = tmp_path / "data"
    nodes_dir = data_dir.parent / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    
    # Create node files manually
    node1 = {"id": "node-1", "label": "Node One", "parent_id": None, "description": ""}
    node2 = {"id": "node-2", "label": "Node Two", "parent_id": "node-1", "description": ""}
    
    with (nodes_dir / "node-1.json").open("w", encoding="utf-8") as f:
        json.dump(node1, f)
    with (nodes_dir / "node-2.json").open("w", encoding="utf-8") as f:
        json.dump(node2, f)
    
    manager = DataManager(str(data_dir))
    global_data = manager._load_global()
    
    assert "node-1" in global_data["nodes"]
    assert "node-2" in global_data["nodes"]
    assert global_data["nodes"]["node-1"]["label"] == "Node One"
    assert global_data["nodes"]["node-2"]["parent_id"] == "node-1"


def test_concurrent_node_creation_no_conflict(tmp_path):
    """Test that two nodes can be created without file conflicts."""
    data_dir = tmp_path / "data"
    manager = DataManager(str(data_dir))
    
    # Simulate concurrent creation by adding nodes rapidly
    node1 = manager.add_node("Idea A", parent_id=None)
    node2 = manager.add_node("Idea B", parent_id=None)
    node3 = manager.add_node("Idea C", parent_id=node1["id"])
    
    # All nodes should exist as separate files
    nodes_dir = data_dir.parent / "nodes"
    assert (nodes_dir / f"{node1['id']}.json").exists()
    assert (nodes_dir / f"{node2['id']}.json").exists()
    assert (nodes_dir / f"{node3['id']}.json").exists()
    
    # Verify graph integrity
    graph = manager.get_graph()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node1["id"] in node_ids
    assert node2["id"] in node_ids
    assert node3["id"] in node_ids