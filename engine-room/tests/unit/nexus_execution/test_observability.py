"""Unit tests for nexus_execution.observability — derived counters over the Phase 2 sink."""

from __future__ import annotations

from nexus_execution.observability import ExecutionObservability
from nexus_infra import InMemoryObservability


def test_all_counters_increment_the_sink() -> None:
    sink = InMemoryObservability()
    obs = ExecutionObservability(sink)
    obs.started()
    obs.output(10)
    obs.progress()
    obs.artifact()
    obs.timed_out()
    obs.completed()
    obs.cancelled()
    obs.failed()
    obs.destroyed()
    counters = sink.counters
    assert counters["execution.started"] == 1
    assert counters["execution.output"] == 1
    assert counters["execution.completed"] == 1
    assert counters["execution.destroyed"] == 1


def test_defaults_to_null_sink() -> None:
    # No sink provided → the null sink; calling counters must not raise.
    obs = ExecutionObservability()
    obs.started()
    obs.destroyed()
