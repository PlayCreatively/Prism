import sys
import json
from pathlib import Path

import pytest

# Ensure src is importable
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import mutation_manager as mm  # type: ignore


def _read_json(p: Path):
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_update_and_delete_mutations(tmp_path):
    # Setup directories
    data_dir = tmp_path / "data"
    mutations_dir = tmp_path / "mutations"
    data_dir.mkdir()
    mutations_dir.mkdir()

    # Create two user files: alex.json has node-1, sasha.json has node-2
    alex_file = data_dir / "alex.json"
    sasha_file = data_dir / "sasha.json"

    alex_obj = {
        "user_id": "Alex",
        "applied_mutations": [],
        "nodes": [
            {
                "id": "node-1",
                "label": "Old Label",
                "parent_id": "root",
                "status": "accepted",
                "metadata": "alex notes",
            }
        ],
    }
    sasha_obj = {
        "user_id": "Sasha",
        "applied_mutations": [],
        "nodes": [
            {
                "id": "node-2",
                "label": "Other",
                "parent_id": "root",
                "status": "accepted",
                "metadata": "sasha notes",
            }
        ],
    }

    alex_file.write_text(json.dumps(alex_obj, indent=2))
    sasha_file.write_text(json.dumps(sasha_obj, indent=2))

    # Create an UPDATE_LABEL mutation for node-1
    mpath = mm.create_mutation(
        mutations_dir=mutations_dir,
        author="Alex",
        node_id="node-1",
        action="UPDATE_LABEL",
        payload="New Label",
        timestamp="2026-01-14T12:00:00Z",
    )
    assert mpath.exists()

    # Apply mutations
    applied = mm.apply_mutations(mutations_dir, data_dir)
    assert len(applied) == 1
    mutation_id = applied[0]

    # Verify alex.json updated
    alex_after = _read_json(alex_file)
    assert mutation_id in alex_after["applied_mutations"]
    assert any(n["id"] == "node-1" and n["label"] == "New Label" for n in alex_after["nodes"])

    # Verify sasha.json marked mutation applied even though it didn't have the node
    sasha_after = _read_json(sasha_file)
    assert mutation_id in sasha_after["applied_mutations"]
    assert any(n["id"] == "node-2" for n in sasha_after["nodes"])

    # Create a DELETE_NODE mutation for node-1
    mpath2 = mm.create_mutation(
        mutations_dir=mutations_dir,
        author="Alex",
        node_id="node-1",
        action="DELETE_NODE",
        payload=None,
        timestamp="2026-01-14T12:01:00Z",
    )
    assert mpath2.exists()

    # Apply mutations again
    applied2 = mm.apply_mutations(mutations_dir, data_dir)
    # Should process the new mutation
    assert len(applied2) >= 1
    # Find the second mutation id in returned list
    m2_id = pth_name = [p for p in applied2 if p == mpath2.name][0]

    # Verify node-1 removed from alex.json
    alex_after2 = _read_json(alex_file)
    assert m2_id in alex_after2["applied_mutations"]
    assert not any(n["id"] == "node-1" for n in alex_after2["nodes"])

    # Verify sasha.json also has the mutation id recorded and still has its node
    sasha_after2 = _read_json(sasha_file)
    assert m2_id in sasha_after2["applied_mutations"]
    assert any(n["id"] == "node-2" for n in sasha_after2["nodes"])

    # Re-applying mutations should not duplicate entries in applied_mutations
    applied3 = mm.apply_mutations(mutations_dir, data_dir)
    # No new mutations applied, or at least applied_mutations lists should not grow duplicates
    alex_final = _read_json(alex_file)
    assert alex_final["applied_mutations"].count(mutation_id) == 1
    assert alex_final["applied_mutations"].count(m2_id) == 1
