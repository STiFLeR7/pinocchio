"""Retrieval scoping — deterministic selection by correlation / runtime / operator, own-event exclusion."""

from __future__ import annotations

from nexus_history import HistoryQuery
from nexus_history.retrieval import filter_events
from tests.unit.nexus_history.fixtures import ev, seed_episode, wired


def _events(infra):
    return tuple(infra.event_store.read_all())


def test_correlation_scope_selects_one_stream() -> None:
    infra, _ = wired()
    seed_episode(infra, "op-1")
    seed_episode(infra, "op-2")
    scoped = filter_events(_events(infra), HistoryQuery(correlation_identifier="op-1"))
    assert scoped and all(e.correlation_identifier == "op-1" for e in scoped)


def test_runtime_scope_filters_by_recorded_fact() -> None:
    infra, _ = wired()
    seed_episode(infra, "op-1", runtime="claude")
    seed_episode(infra, "op-2", runtime="gemini")
    claude = filter_events(_events(infra), HistoryQuery(runtime="claude"))
    assert claude and all(e.payload.get("runtime") == "claude" for e in claude)


def test_history_own_events_are_never_retrieved() -> None:
    infra, _ = wired()
    seed_episode(infra, "op-1")
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
    scoped = filter_events(_events(infra), HistoryQuery())
    assert all(not e.type.startswith("execution_history.") for e in scoped)
