"""Knowledge lineage — deterministic reconstruction of derivation edges from ``knowledge.*`` facts."""

from __future__ import annotations

from nexus_history.lineage import build_lineage
from tests.unit.nexus_history.fixtures import ev


def test_lineage_counts_and_edges() -> None:
    events = (
        ev("k1", "knowledge.candidate_received", "op-1", {}, producer="knowledge"),
        ev(
            "k2",
            "knowledge.candidate_accepted",
            "op-1",
            {"candidate": "cand-1", "subject_key": "sk-1"},
            producer="knowledge",
        ),
        ev("k3", "knowledge.item_created", "op-1", {"subject_key": "sk-1"}, producer="knowledge"),
        ev(
            "k4",
            "knowledge.item_superseded",
            "op-1",
            {"supersedes": "sk-0", "subject_key": "sk-1"},
            producer="knowledge",
        ),
        ev("r1", "runtime.started", "op-1", {}),  # non-knowledge fact ignored
    )
    lineage = build_lineage(events)
    assert lineage.candidates_received == 1 and lineage.accepted == 1
    assert lineage.items_created == 1 and lineage.items_evolved == 1
    assert ("cand-1", "sk-1") in lineage.edges
    assert ("sk-0", "sk-1") in lineage.edges


def test_lineage_is_deterministic_and_sorted() -> None:
    events = (
        ev(
            "k2",
            "knowledge.candidate_accepted",
            "op-1",
            {"candidate": "z", "subject_key": "b"},
            producer="knowledge",
        ),
        ev(
            "k1",
            "knowledge.candidate_accepted",
            "op-1",
            {"candidate": "a", "subject_key": "a"},
            producer="knowledge",
        ),
    )
    assert build_lineage(events).edges == (("a", "a"), ("z", "b"))
