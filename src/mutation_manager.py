"""
Mutation ledger manager for PRISM.

Provides utilities to create mutation files in a `mutations/` directory and apply
those mutations against per-user JSON files stored in a `data/` directory.

Mutation file format (JSON):
{
  "timestamp": "2026-01-14T12:00:00Z",
  "author": "Alex",
  "node_id": "uuid_of_node",
  "action": "UPDATE_LABEL",  # or "DELETE_NODE"
  "payload": "New Label Name"
}

This module exposes:
- create_mutation(mutations_dir, author, node_id, action, payload, timestamp=None) -> Path
- list_mutation_files(mutations_dir) -> List[Path]
- read_mutation(path) -> dict
- apply_mutations(mutations_dir, data_dir) -> List[str]  # applied mutation ids (filenames)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_mutation(
    mutations_dir: Path,
    author: str,
    node_id: str,
    action: str,
    payload: Any,
    timestamp: Optional[str] = None,
) -> Path:
    """
    Create a mutation JSON file under mutations_dir and return its path.

    The filename is deterministic-ish: {timestamp}_{author}_{action}_{shortnode}_{uuid}.json
    The mutation ID used by the rest of the system is the filename (without path).
    """
    ensure_dir(mutations_dir)
    ts = timestamp or _now_iso()
    short_node = str(node_id)[:8]
    uid = uuid.uuid4().hex[:8]
    # sanitize author and action for filename
    safe_author = "".join(c for c in author if c.isalnum() or c in ("-", "_")).lower()
    safe_action = "".join(c for c in action if c.isalnum() or c in ("-", "_")).upper()
    fname = f"{ts}_{safe_author}_{safe_action}_{short_node}_{uid}.json"
    # replace characters not allowed in filenames (colon etc.)
    fname = fname.replace(":", "-")
    path = mutations_dir / fname
    payload_obj = {
        "timestamp": ts,
        "author": author,
        "node_id": node_id,
        "action": action,
        "payload": payload,
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload_obj, fh, indent=2, sort_keys=True)
    return path


def list_mutation_files(mutations_dir: Path) -> List[Path]:
    """
    Return list of mutation file paths in lexicographical order (oldest first,
    if filenames include timestamps).
    """
    if not mutations_dir.exists():
        return []
    files = [p for p in mutations_dir.iterdir() if p.is_file() and p.suffix == ".json"]
    return sorted(files, key=lambda p: p.name)


def read_mutation(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json_file(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)


def apply_mutations(mutations_dir: Path, data_dir: Path) -> List[str]:
    """
    Apply all mutation files in mutations_dir to all user JSON files in data_dir.

    For each mutation file (file name is the mutation id), we will:
      - Load the mutation.
      - For each user file in data_dir (all .json files):
          - If mutation id already present in user_file['applied_mutations'], skip for that user.
          - Otherwise apply the mutation to that user's nodes as relevant:
              - UPDATE_LABEL: find nodes with matching id and set 'label' = payload
              - DELETE_NODE: remove nodes with matching id
          - Append mutation id to user_file['applied_mutations']
          - Write the user file back

    Returns list of mutation ids that were processed (filenames).
    """
    applied_mutation_ids: List[str] = []
    mutation_files = list_mutation_files(mutations_dir)
    if not mutation_files:
        return applied_mutation_ids

    # Gather data files
    if not data_dir.exists():
        # nothing to apply to, but still return mutation ids?
        # We'll still return an empty list (nothing applied).
        return applied_mutation_ids

    user_files = [p for p in data_dir.iterdir() if p.is_file() and p.suffix == ".json"]
    # If no user files, nothing to do
    if not user_files:
        return applied_mutation_ids

    for mpath in mutation_files:
        mutation_id = mpath.name
        mutation = read_mutation(mpath)
        # sanitize action
        action = (mutation.get("action") or "").upper()
        node_id = mutation.get("node_id")
        payload = mutation.get("payload")
        # Apply to each user file
        any_applied = False
        for ufile in user_files:
            try:
                user_obj = _load_json_file(ufile)
            except Exception:
                # skip malformed files
                continue
            if "applied_mutations" not in user_obj:
                user_obj["applied_mutations"] = []
            # Skip if already applied for this user
            if mutation_id in user_obj.get("applied_mutations", []):
                # still ensure file stays consistent (no change)
                continue
            nodes = user_obj.get("nodes", [])
            if action == "UPDATE_LABEL":
                changed = False
                for node in nodes:
                    if node.get("id") == node_id:
                        node["label"] = payload
                        changed = True
                # Always mark mutation as applied for the user so it won't be retried
                user_obj["applied_mutations"].append(mutation_id)
                _write_json_file(ufile, user_obj)
                any_applied = any_applied or changed or True  # mark as applied for this user
            elif action == "DELETE_NODE":
                orig_len = len(nodes)
                nodes = [n for n in nodes if n.get("id") != node_id]
                user_obj["nodes"] = nodes
                user_obj["applied_mutations"].append(mutation_id)
                _write_json_file(ufile, user_obj)
                any_applied = any_applied or (len(nodes) != orig_len) or True
            else:
                # Unknown action: still record as applied to avoid infinite retries
                user_obj["applied_mutations"].append(mutation_id)
                _write_json_file(ufile, user_obj)
                any_applied = True
        if any_applied:
            applied_mutation_ids.append(mutation_id)
    return applied_mutation_ids
