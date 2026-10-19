"""Projection behavior — facts-only facets, determinism, and own-event exclusion."""

from __future__ import annotations

from nexus_history import HistoryQuery
from nexus_history.projection import project
from tests.unit.nexus_history.fixtures import ev, seed_episode, wired


def _events(infra):
    return tuple(infra.event_store.read_all())


def test_projection_reconstructs_operational_facets() -> None:
    infra, _ = wired()
    seed_episode(infra, "op-1")
    p = project(_events(infra), HistoryQuery(), "1")

    assert p.available and p.event_count == 12
    assert p.execution_count == 1
    assert p.runtime.starts == 1 and p.runtime.completions == 1
    assert p.runtime.selections == 1  # one orchestration.runtime_request_created
    assert "claude" in p.runtime.runtimes
    assert p.validation.completed == 1 and p.validation.verdicts == (("op-1", "passed"),)
    assert p.recovery.decisions == 1 and p.recovery.outcomes == (("op-1", "retry"),)
    assert p.reflection.reports == 1
    assert p.knowledge_lineage.items_created == 1 and p.knowledge_lineage.accepted == 1
    assert p.knowledge_lineage.edges  # candidate -> subject edge recorded
    assert p.artifacts.count == 2  # runtime.artifact_emitted + validation artifact
    assert p.evidence.count == 1
    assert p.work_packages.created == 1
    assert p.executions[0].validated and p.executions[0].recovered and p.executions[0].reflected


def test_projection_is_deterministic() -> None:
    infra, _ = wired()
    seed_episode(infra, "op-1")
    seed_episode(infra, "op-2")
    events = _events(infra)
    assert project(events, HistoryQuery(), "1") == project(events, HistoryQuery(), "1")


def test_projection_excludes_own_history_events() -> None:
    # A prior execution_history.* fact in the log must not perturb a fresh projection.
    infra, _ = wired()
    seed_episode(infra, "op-1")
    before = project(_events(infra), HistoryQuery(), "1")

    infra.emit(
        ev(
            "hist-1",
            "execution_history.projected",
            "op-1",
            {"profile": {}},
            producer="execution_history",
            source="nexus_history",
        )
    )
    after = project(_events(infra), HistoryQuery(), "1")

    assert before.event_count == after.event_count  # own fact ignored
    assert before.frequency == after.frequency


def test_empty_log_is_facts_only_and_unavailable() -> None:
    infra, _ = wired()
    p = project(_events(infra), HistoryQuery(), "1")
    assert not p.available and p.event_count == 0 and p.execution_count == 0
