"""P15/B unit — the Operations service projects the platform read-only from the shared log.

Every method is a deterministic projection (active sessions, execution status, approval queue, runtime /
replay / restart inventories, event lookup); it drives nothing and mutates nothing.
"""

from __future__ import annotations

from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_workflows.spine import PIPELINE_PRODUCER


def _paused_platform():
    ctx = build_human_interaction(build_infrastructure())
    request = reference_operator_request(run="r1", gated=("review",))
    ctx.facade.submit(request)
    ops = build_operations(ctx.spine.coordinator, ctx.approval, ctx.infrastructure)
    return ctx, ops, request, request.identity


def test_active_sessions_report_pause_and_pending_approvals() -> None:
    _, ops, _, _ = _paused_platform()
    sessions = ops.service.active_sessions()
    assert len(sessions) == 1
    summary = sessions[0]
    assert summary.session_id == "pipe-op-arch-r1"
    assert summary.is_paused and summary.pending_approvals == 1
    assert ops.service.session_lookup("pipe-op-arch-r1") == summary
    assert ops.service.session_lookup("pipe-absent") is None


def test_execution_lookup_exposes_the_waiting_gate() -> None:
    _, ops, _, _ = _paused_platform()
    view = ops.service.execution_lookup("pipe-op-arch-r1")
    assert not view.actuation_complete
    assert view.waiting_gates == ("node-review",)
    assert view.pipeline_status == "paused"


def test_queue_and_inventories_project_the_paused_run() -> None:
    _, ops, _, _ = _paused_platform()
    queue = ops.service.approval_queue()
    assert queue.depth == 1 and queue.pending[0][:2] == ("pipe-op-arch-r1", "node-review")

    runtime = ops.service.runtime_inventory()  # node-draft ran while node-review waits
    assert runtime.utilization >= 1 and runtime.runtimes

    replay = ops.service.replay_inventory()
    assert "pipe-op-arch-r1" in replay.sessions and replay.total_events > 0

    restart = ops.service.restart_inventory()
    assert restart.resumable == ("pipe-op-arch-r1",) and restart.pending_approvals == 1


def test_event_and_runtime_lookup_filter_the_log() -> None:
    _, ops, _, _ = _paused_platform()
    assert ops.service.event_lookup(producer=PIPELINE_PRODUCER)
    assert all(
        event.identifier.startswith("evt-pipe-op-arch-r1-")
        or event.payload.get("session") == "pipe-op-arch-r1"
        for event in ops.service.event_lookup(session="pipe-op-arch-r1")
    )
    assignments = ops.service.runtime_lookup("pipe-op-arch-r1")
    assert any(node == "node-draft" for node, _ in assignments)


def test_approving_drains_the_queue_and_restart_inventory() -> None:
    ctx, ops, request, identity = _paused_platform()
    ctx.facade.approve(request, "node-review", decided_by="alice")
    assert ops.service.approval_queue().depth == 0
    assert ops.service.restart_inventory().resumable == ()
    assert ops.service.execution_lookup("pipe-op-arch-r1").actuation_complete
