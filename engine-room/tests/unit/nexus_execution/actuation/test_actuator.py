"""The Execution Actuator — traversal, events, state projection, failure/pause, checkpoints, approvals."""

from __future__ import annotations

from dataclasses import replace

from nexus_execution.actuation import (
    EXECUTION_COMPLETED,
    ActuationControl,
    ActuationStatus,
    NodeStatus,
    reconstruct_execution_state,
)
from tests.unit.nexus_execution.actuation.fixtures import (
    execution_event_types,
    item,
    make_inputs,
    make_plan,
    to_inputs,
    wired,
)

_DIAMOND = (
    item("a"),
    item("b", depends_on=("a",)),
    item("c", depends_on=("a",)),
    item("d", depends_on=("b", "c")),
)


def test_full_traversal_completes_every_node_in_dependency_order() -> None:
    infra, ctx = wired()
    state = ctx.actuator.actuate(make_inputs(_DIAMOND))
    assert state.status is ActuationStatus.COMPLETED
    assert state.completed_nodes == ("node-a", "node-b", "node-c", "node-d")
    assert state.lineage == ("node-a", "node-b", "node-c", "node-d")  # a before b/c before d
    assert state.pending_nodes == () and state.blocked_nodes == () and state.waiting_nodes == ()


def test_traversal_emits_the_execution_event_stream() -> None:
    infra, ctx = wired()
    ctx.actuator.actuate(make_inputs((item("a"), item("b", depends_on=("a",)))))
    types = execution_event_types(infra)
    assert types[0] == "execution.started"
    assert types[-1] == "execution.completed"
    assert types.count("execution.node_started") == 2
    assert types.count("execution.node_completed") == 2


def test_runtime_assignments_and_artifacts_are_recorded() -> None:
    _infra, ctx = wired()
    state = ctx.actuator.actuate(make_inputs((item("a"),)))
    assert state.runtime_assignments == (
        ("node-a", "claude-code"),
    )  # Orchestration assigned; we drove
    assert state.artifact_references  # evidence candidates surfaced by reference (never embedded)


def test_completed_event_embeds_the_full_state_for_replay() -> None:
    infra, ctx = wired()
    state = ctx.actuator.actuate(make_inputs(_DIAMOND))
    events = [e for e in infra.event_store.read_all() if e.type == EXECUTION_COMPLETED]
    assert len(events) == 1
    reconstructed = reconstruct_execution_state(
        infra.event_store.read_all(), session_identity=state.identity
    )
    assert reconstructed == state  # replay reconstructs the state exactly, from the log alone


def test_a_node_failure_halts_the_branch_without_retry() -> None:
    # The stub fails every node; a's failure blocks its dependents. Actuation records, never recovers.
    infra, ctx = wired(fail=True)
    state = ctx.actuator.actuate(make_inputs(_DIAMOND))
    assert state.status is ActuationStatus.BLOCKED
    node_a = next(n for n in state.nodes if n.node == "node-a")
    assert node_a.status is NodeStatus.FAILED
    assert set(state.blocked_nodes) == {"node-a", "node-b", "node-c", "node-d"}
    types = execution_event_types(infra)
    assert "execution.node_failed" in types
    assert "execution.completed" not in types  # no completion is declared on a halted graph


def test_checkpoint_boundaries_emit_enter_and_complete() -> None:
    infra, ctx = wired()
    state = ctx.actuator.actuate(make_inputs((item("a", is_checkpoint=True),)))
    assert state.checkpoint_state == ("node-a",)
    types = execution_event_types(infra)
    assert "execution.checkpoint_entered" in types
    assert "execution.checkpoint_completed" in types


def test_an_ungranted_approval_gate_pauses_the_node() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",), requires_approval=True)))
    infra, ctx = wired()
    state = ctx.actuator.actuate(to_inputs(plan))  # gate not granted
    assert "node-b" in state.waiting_nodes
    assert "node-b" not in state.completed_nodes
    assert "execution.approval_waiting" in execution_event_types(infra)
    assert "execution.completed" not in execution_event_types(infra)


def test_a_granted_approval_gate_lets_the_node_proceed() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",), requires_approval=True)))
    infra, ctx = wired()
    state = ctx.actuator.actuate(to_inputs(plan, granted_gates=("node-b",)))
    assert state.status is ActuationStatus.COMPLETED
    assert state.approval_received == ("node-b",)
    assert "execution.approval_received" in execution_event_types(infra)


def test_action_write_gate_waits_even_when_strategy_is_automatic() -> None:
    plan = make_plan((item("write", requires_approval=True),))
    infra, ctx = wired()
    inputs = replace(to_inputs(plan), human_required_gates=("node-write",))

    state = ctx.actuator.actuate(inputs)

    assert "node-write" in state.waiting_nodes
    assert "node-write" not in state.completed_nodes
    assert not any(
        event.type == "runtime.started" and event.payload.get("work_package") == "wp-g1-write"
        for event in infra.event_store.read_all()
    )


def test_explicitly_human_approved_action_gate_proceeds_under_automatic_strategy() -> None:
    plan = make_plan((item("write", requires_approval=True),))
    infra, ctx = wired()
    inputs = replace(
        to_inputs(plan, granted_gates=("node-write",)),
        human_required_gates=("node-write",),
    )

    state = ctx.actuator.actuate(inputs)

    assert state.status is ActuationStatus.COMPLETED
    assert state.approval_received == ("node-write",)


def test_graceful_shutdown_pauses_with_ready_work_remaining() -> None:
    infra, ctx = wired()
    state = ctx.actuator.actuate(make_inputs(_DIAMOND), control=ActuationControl(stop_after=1))
    assert state.status is ActuationStatus.PAUSED
    assert state.completed_nodes == ("node-a",)
    assert "execution.completed" not in execution_event_types(infra)  # not complete → not declared


def test_traversal_is_deterministic() -> None:
    inputs = make_inputs(_DIAMOND)
    _infra_a, ctx_a = wired()
    _infra_b, ctx_b = wired()
    assert ctx_a.actuator.actuate(inputs) == ctx_b.actuator.actuate(inputs)
