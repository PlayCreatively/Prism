import json
from pathlib import Path

import pytest

from src.data_manager import DataManager


def test_load_new_user_creates_file_and_schema(tmp_path):
    data_dir = tmp_path / "data"
    manager = DataManager(str(data_dir))

    user_id = "alex"
    data = manager.load_user(user_id)

    # Schema checks
    assert isinstance(data, dict)
    assert data["user_id"] == user_id
    assert isinstance(data["applied_mutations"], list)
    assert isinstance(data["nodes"], list)
    assert data["applied_mutations"] == []
    assert data["nodes"] == []

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

    # Add a mutation and a node
    data["applied_mutations"].append("hash_1")
    node = {
        "id": "uuid-1234",
        "label": "Test Node",
        "parent_id": "root",
        "status": "accepted",
        "metadata": "Some notes"
    }
    data["nodes"].append(node)

    manager.save_user(data)

    # Reload using a new manager instance to ensure persistence to disk
    manager2 = DataManager(str(data_dir))
    reloaded = manager2.load_user(user_id)

    assert reloaded["user_id"] == user_id
    assert "hash_1" in reloaded["applied_mutations"]
    assert any(n.get("id") == "uuid-1234" for n in reloaded["nodes"])


def test_load_existing_file_with_missing_keys_is_normalized(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "alison.json"

    # Create a file that lacks some keys or has wrong types
    bad_content = {
        "user_id": "alison",
        "applied_mutations": "not-a-list",  # wrong type
        # nodes missing
    }
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(bad_content, f)

    manager = DataManager(str(data_dir))
    data = manager.load_user("alison")

    assert data["user_id"] == "alison"
    assert isinstance(data["applied_mutations"], list)
    assert isinstance(data["nodes"], list)
    # After normalization the file on disk should also be corrected
    with file_path.open("r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk == data
