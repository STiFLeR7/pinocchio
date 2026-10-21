"""Durable grounded planning (P10) — replay + restart acceptance gate.

Proves the ExecutionPlan fact is durable and correlated, that replaying the ``planning.*`` stream
reconstructs the ExecutionPlan without re-planning, and that restart reconstructs an identical plan.
Rides P1/ADR-007 unchanged through the incumbent Planning producer.

Upstream artifacts (EngineeringStrategy, ContextPackage) are built on throwaway in-memory infras — they
are inputs, immutable and deterministic — so the durable planning db carries only ``planning.*`` events.
"""

from __future__ import annotations

from nexus_infra import build_durable_infrastructure
from nexus_planning import FixedTimestampSource
from nexus_planning.grounded import ExecutionPlan, build_grounded_planning
from nexus_planning.grounded.assembler import PLANNING_EXECUTION_PLAN_ASSEMBLED
from tests.unit.nexus_planning.grounded.fixtures import item, make_inputs


def _grounded(db: str):
    infra = build_durable_infrastructure(db)
    return infra, build_grounded_planning(infra, timestamps=FixedTimestampSource())


def _durable_inputs():
    return make_inputs(work_items=(item("a"), item("b", depends_on=("a",))))


def test_execution_plan_fact_is_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "p.db")
    _, ctx = _grounded(db)
    ep = ctx.planner.plan(_durable_inputs())

    reopened = build_durable_infrastructure(db)
    events = [
        e for e in reopened.event_store.read_all() if e.type == PLANNING_EXECUTION_PLAN_ASSEMBLED
    ]
    assert len(events) == 1
    assert events[0].correlation_identifier == ep.correlation_identifier


def test_replay_reconstructs_plan_without_replanning(tmp_path) -> None:
    db = str(tmp_path / "p.db")
    _, ctx = _grounded(db)
    original = ctx.planner.plan(_durable_inputs())

    reopened = build_durable_infrastructure(db)
    event = next(
        e for e in reopened.event_store.read_all() if e.type == PLANNING_EXECUTION_PLAN_ASSEMBLED
    )
    reconstructed = ExecutionPlan.model_validate(event.payload["execution_plan"])
    assert reconstructed == original  # reconstructed from the log, no re-planning


def test_restart_reconstruction_is_identical(tmp_path) -> None:
    db = str(tmp_path / "p.db")
    inputs = _durable_inputs()  # built once; immutable

    _, ctx_before = _grounded(db)
    before = ctx_before.planner.plan(inputs)

    _, ctx_after = _grounded(db)  # fresh engines over the reopened file
    after = ctx_after.planner.plan(inputs)

    assert before == after
