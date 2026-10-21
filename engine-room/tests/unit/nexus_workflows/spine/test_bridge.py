"""P13 unit — the Execution Actuation → Validation seam (F-3).

Proves the additive ExecutionState→ExecutionResult projection is *faithful*: it recovers each node's
execution-session scope from the log so Validation's independent artifact corroboration (INV-20)
resolves exactly as it does for the incumbent per-session loop — PASSED, not PARTIAL — and it never
touches the actuator's contract.
"""

from __future__ import annotations

from nexus_execution.signals import TerminalOutcome
from nexus_infra import InfrastructureContext
from nexus_planning import FixedTimestampSource
from nexus_runtime.vocabulary import RuntimeLifecycleState
from nexus_validation import build_validation
from nexus_workflows.spine.bridge import execution_results
from tests.unit.nexus_execution.actuation.fixtures import item, make_plan, to_inputs, wired


def _actuated(
    *,
    fail: bool = False,
    goal_identity: str = "g1",
    infrastructure: InfrastructureContext | None = None,
):
    plan = make_plan((item("a"), item("b", depends_on=("a",))), goal_identity=goal_identity)
    infra, ctx = wired(infrastructure, fail=fail)
    state = ctx.actuator.actuate(to_inputs(plan))
    return infra, plan, state


def test_projects_one_execution_result_per_executed_node() -> None:
    infra, _plan, state = _actuated()
    results = execution_results(state, infra.event_store.read_all())
    assert len(results) == len(state.completed_nodes) == 2
    assert all(r.outcome is TerminalOutcome.COMPLETED for r in results)
    # The engine's teardown always reaches Destroyed, so the projection is deterministic.
    assert all(r.final_state is RuntimeLifecycleState.DESTROYED for r in results)
    # Each result addresses a distinct work package (one per node).
    assert len({r.work_package_ref.identifier for r in results}) == 2


def test_recovered_scope_lets_validation_corroborate_to_passed() -> None:
    infra, plan, state = _actuated()
    events = infra.event_store.read_all()
    results = execution_results(state, events)
    validation = build_validation(infra, timestamps=FixedTimestampSource()).engine
    wp_by_ref = {wp.identifier: wp for wp in plan.work_packages}
    reports = [
        validation.validate(r, wp_by_ref[r.work_package_ref.identifier], events=events)
        for r in results
    ]
    # PASSED (not PARTIAL) proves the recovered session_ref matched the runtime.artifact_emitted scope.
    assert all(rep.decision.value == "passed" for rep in reports)


def test_failed_node_projects_a_failed_result() -> None:
    infra, _plan, state = _actuated(fail=True)
    results = execution_results(state, infra.event_store.read_all())
    assert results and all(r.outcome is TerminalOutcome.FAILED for r in results)


def test_two_goals_sharing_a_node_key_do_not_cross_contaminate_scopes() -> None:
    """RC2: two goals whose plans both produce nodes "a"/"b" must not resolve each other's scope.

    ``events`` passed to ``execution_results`` is the *entire* durable log (every goal ever run in
    this process, per ``coordinator._stage_validation``) — the reproduced RC1 collision.
    """
    infra, _plan_a, state_a = _actuated(goal_identity="g1")
    _infra2, _plan_b, state_b = _actuated(goal_identity="g2", infrastructure=infra)

    events = infra.event_store.read_all()
    results_a = execution_results(state_a, events)
    results_b = execution_results(state_b, events)

    scopes_a = {r.session_ref.identifier for r in results_a}
    scopes_b = {r.session_ref.identifier for r in results_b}
    assert len(scopes_a) == len(scopes_b) == 2
    assert scopes_a.isdisjoint(scopes_b)
