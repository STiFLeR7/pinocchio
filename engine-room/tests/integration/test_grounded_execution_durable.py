"""Durable execution actuation (P11) — replay + restart acceptance gate.

Proves the traversal is durable and correlated, that replaying the ``execution.*`` stream reconstructs
the ExecutionState exactly (the state is embedded in ``execution.completed``), and that a restart over a
reopened durable log resumes from recorded progress — without replanning — to a byte-identical state.
Rides P1/ADR-007 unchanged through the incumbent Runtime + Execution engines (INV-13/14/18).

The ExecutionPlan is built on a throwaway in-memory infra — it is an immutable input — so the durable
actuation db carries only the ``execution.*`` / ``runtime.*`` traversal facts.
"""

from __future__ import annotations

from nexus_execution.actuation import (
    EXECUTION_COMPLETED,
    ActuationControl,
    ActuationStatus,
    build_execution_actuation,
    reconstruct_execution_state,
)
from nexus_infra import build_durable_infrastructure
from nexus_planning import FixedTimestampSource
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from tests.unit.nexus_execution.actuation.fixtures import item, make_plan, to_inputs

_DIAMOND = (
    item("a"),
    item("b", depends_on=("a",)),
    item("c", depends_on=("a",)),
    item("d", depends_on=("b", "c")),
)


def _durable(db: str):
    infra = build_durable_infrastructure(db)
    ctx = build_execution_actuation(
        infra,
        adapter=ClaudeRuntimeAdapter(invoker=StubClaudeInvoker()),
        timestamps=FixedTimestampSource(),
    )
    return infra, ctx


def _inputs():
    return to_inputs(make_plan(_DIAMOND))  # built once; immutable


def test_execution_is_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "e.db")
    _infra, ctx = _durable(db)
    state = ctx.actuator.actuate(_inputs())

    reopened = build_durable_infrastructure(db)
    events = [e for e in reopened.event_store.read_all() if e.type == EXECUTION_COMPLETED]
    assert len(events) == 1
    assert events[0].correlation_identifier == state.correlation_identifier


def test_replay_reconstructs_state_from_the_log(tmp_path) -> None:
    db = str(tmp_path / "e.db")
    _infra, ctx = _durable(db)
    original = ctx.actuator.actuate(_inputs())

    reopened = build_durable_infrastructure(db)
    reconstructed = reconstruct_execution_state(
        reopened.event_store.read_all(), session_identity=original.identity
    )
    assert reconstructed == original  # reconstructed from the log, no re-execution


def test_restart_resumes_without_replanning_to_an_identical_state(tmp_path) -> None:
    db = str(tmp_path / "e.db")
    inputs = _inputs()

    _infra_before, ctx_before = _durable(db)
    partial = ctx_before.actuator.actuate(inputs, control=ActuationControl(stop_after=1))
    assert partial.status is ActuationStatus.PAUSED
    assert partial.completed_nodes == ("node-a",)  # interrupted after the entry node

    _infra_after, ctx_after = _durable(db)  # fresh engines over the reopened file
    resumed = ctx_after.actuator.actuate(inputs)  # same plan — never rebuilt
    assert resumed.status is ActuationStatus.COMPLETED
    assert resumed.completed_nodes == ("node-a", "node-b", "node-c", "node-d")

    # A restart-resumed run reaches the same state as one uninterrupted run.
    _clean_infra, ctx_clean = _durable(str(tmp_path / "clean.db"))
    assert resumed == ctx_clean.actuator.actuate(inputs)
