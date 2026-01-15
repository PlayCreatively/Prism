"""
Drill Engine - Backlog & Tri-State voting logic

This module implements a small in-memory engine to manage "drill down" items
and tri-state voting across multiple users. Each node holds per-user votes
(one of "accepted", "rejected", "pending"). The aggregated node state is:

- "accepted" : when at least 2 users have voted "accepted"
- "rejected" : when at least 2 users have voted "rejected"
- "ignored"  : otherwise (no majority)

Backlog is defined as the list of nodes whose aggregated state is "ignored".
"""

from typing import Dict, List, Optional


VALID_USER_STATUS = {"accepted", "rejected", "pending"}


class DrillEngine:
    """
    Simple drill engine to manage nodes and per-user tri-state votes.

    Usage:
        engine = DrillEngine(users=["alex", "sasha", "alison"])
        engine.add_node("n1", "Some Idea")
        engine.vote("alex", "n1", "accepted")
        state = engine.get_node_state("n1")  # "ignored", "accepted", or "rejected"
        backlog = engine.get_backlog()
    """

    def __init__(self, users: Optional[List[str]] = None):
        # normalized user list (lowercased)
        self.users = [u.lower() for u in (users or [])]
        # nodes: id -> {"label": str, "votes": {user: status}}
        self.nodes: Dict[str, Dict] = {}

    def add_node(self, node_id: str, label: str) -> None:
        """
        Add a node to the engine. If node exists, label is updated.
        Initializes votes for all known users to "pending".
        """
        node_id = str(node_id)
        label = str(label)
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "label": label,
                "votes": {user: "pending" for user in self.users},
            }
        else:
            # keep existing votes, update label
            self.nodes[node_id]["label"] = label

    def ensure_user(self, user: str) -> None:
        """
        Ensure a user is known to engine. Adds user to users list and initializes
        their vote to "pending" for all existing nodes.
        """
        user = user.lower()
        if user in self.users:
            return
        self.users.append(user)
        for node in self.nodes.values():
            node["votes"][user] = "pending"

    def vote(self, user: str, node_id: str, status: str) -> None:
        """
        Cast (or change) a user's vote on a node. Status must be one of:
        "accepted", "rejected", "pending".

        Raises:
            KeyError if node_id does not exist.
            ValueError if status is invalid.
        """
        status = status.lower()
        if status not in VALID_USER_STATUS:
            raise ValueError(f"Invalid status '{status}'. Valid: {VALID_USER_STATUS}")
        node_id = str(node_id)
        user = user.lower()

        if node_id not in self.nodes:
            raise KeyError(f"Unknown node id: {node_id}")

        if user not in self.users:
            # Automatically add new users (this matches per-user JSON files approach)
            self.ensure_user(user)

        self.nodes[node_id]["votes"][user] = status

    def get_node_votes(self, node_id: str) -> Dict[str, str]:
        """
        Returns a copy of per-user votes for the node.
        """
        node_id = str(node_id)
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node id: {node_id}")
        # return a shallow copy
        return dict(self.nodes[node_id]["votes"])

    def get_node_state(self, node_id: str) -> str:
        """
        Compute aggregated node state using majority rules:
        - "accepted" if >= 2 accepted votes
        - "rejected" if >= 2 rejected votes
        - otherwise "ignored"
        """
        votes = self.get_node_votes(node_id)
        accepted = sum(1 for s in votes.values() if s == "accepted")
        rejected = sum(1 for s in votes.values() if s == "rejected")

        if accepted >= 2:
            return "accepted"
        if rejected >= 2:
            return "rejected"
        return "ignored"

    def get_backlog(self) -> List[str]:
        """
        Return list of node ids whose aggregated state is "ignored".
        """
        return [nid for nid in self.nodes if self.get_node_state(nid) == "ignored"]

    def list_nodes(self) -> List[Dict]:
        """
        Return a list of node summaries: {"id","label","state","votes"}
        """
        out = []
        for nid, data in self.nodes.items():
            out.append(
                {
                    "id": nid,
                    "label": data["label"],
                    "state": self.get_node_state(nid),
                    "votes": dict(data["votes"]),
                }
            )
        return out
