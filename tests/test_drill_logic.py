import pytest
from src.drill_engine import DrillEngine


def test_initial_node_is_ignored_and_in_backlog():
    engine = DrillEngine(users=["alex", "sasha", "alison"])
    engine.add_node("n1", "Serious Games")

    assert engine.get_node_state("n1") == "ignored"
    assert "n1" in engine.get_backlog()


def test_majority_acceptance_transitions_out_of_backlog():
    engine = DrillEngine(users=["alex", "sasha", "alison"])
    engine.add_node("n1", "Serious Games")

    engine.vote("alex", "n1", "accepted")
    engine.vote("sasha", "n1", "accepted")

    assert engine.get_node_state("n1") == "accepted"
    assert "n1" not in engine.get_backlog()


def test_flip_to_ignored_when_no_majority():
    engine = DrillEngine(users=["alex", "sasha", "alison"])
    engine.add_node("n1", "Serious Games")

    # initial: pending/pending/pending -> ignored
    engine.vote("alex", "n1", "accepted")
    engine.vote("sasha", "n1", "accepted")
    assert engine.get_node_state("n1") == "accepted"

    # Sasha flips to rejected -> now: accepted, rejected, pending -> no majority -> ignored
    engine.vote("sasha", "n1", "rejected")
    assert engine.get_node_state("n1") == "ignored"
    assert "n1" in engine.get_backlog()


def test_majority_rejection():
    engine = DrillEngine(users=["alex", "sasha", "alison"])
    engine.add_node("n1", "Serious Games")

    engine.vote("alex", "n1", "accepted")
    engine.vote("sasha", "n1", "rejected")
    engine.vote("alison", "n1", "rejected")

    assert engine.get_node_state("n1") == "rejected"
    assert "n1" not in engine.get_backlog()


def test_adding_new_user_initializes_pending_votes():
    engine = DrillEngine(users=["alex", "sasha"])
    engine.add_node("n1", "Idea")

    # add a new user via ensure_user or voting - should initialize to pending
    engine.ensure_user("alison")
    votes = engine.get_node_votes("n1")
    assert votes["alison"] == "pending"

    # change vote for new user works as expected
    engine.vote("alison", "n1", "accepted")
    assert engine.get_node_votes("n1")["alison"] == "accepted"
