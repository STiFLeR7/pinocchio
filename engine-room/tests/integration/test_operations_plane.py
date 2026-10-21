"""P15/B — the Constitutional Operations Plane gives operators a durable, read-only view of the platform.

End-to-end proof that Operations observes the whole platform from the one shared log — active sessions,
approval queue, runtime/replay/restart inventories, health, and diagnostics — reflecting an approval pause
and its resolution, and recording a durable health snapshot, while controlling nothing.
"""

from __future__ import annotations

from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_operations import build_operations


def _platform(infra):
    ctx = build_human_interaction(infra)
    ops = build_operations(ctx.spine.coordinator, ctx.approval, ctx.infrastructure)
    return ctx, ops


def test_operations_sees_the_pause_then_the_resolution() -> None:
    ctx, ops = _platform(build_infrastructure())
    request = reference_operator_request(run="r1", gated=("review",))
    ctx.facade.submit(request)

    # Paused: one active session, one gate queued, the run resumable, health carrying the pending approval.
    assert ops.service.restart_inventory().resumable == ("pipe-op-arch-r1",)
    assert ops.service.approval_queue().depth == 1
    paused_health = ops.health.summary()
    assert (
        paused_health.pending_approvals == 1 and dict(paused_health.pipeline_states)["paused"] == 1
    )

    ctx.facade.approve(request, "node-review", decided_by="alice")

    # Resolved: queue drained, nothing resumable, health healthy with the approval counted complete.
    assert (
        ops.service.approval_queue().depth == 0 and ops.service.restart_inventory().resumable == ()
    )
    resolved = ops.health.summary()
    assert resolved.is_healthy and resolved.completed_approvals == 1
    assert dict(resolved.pipeline_states).get("completed") == 1
    assert ops.diagnostics.diagnostics().consistent


def test_operations_snapshot_is_durable_and_diagnostics_survive_replay(tmp_path) -> None:
    db = str(tmp_path / "ops.db")
    ctx, ops = _platform(build_durable_infrastructure(db))
    ctx.facade.submit(reference_operator_request(run="r1"))
    ops.health.record_snapshot()

    # A fresh operations plane over the reopened file reconstructs the snapshot and identical diagnostics.
    reopened = build_human_interaction(build_durable_infrastructure(db))
    ops2 = build_operations(reopened.spine.coordinator, reopened.approval, reopened.infrastructure)
    snapshots = ops2.health.snapshots()
    assert len(snapshots) == 1 and snapshots[0].summary.active_sessions == 1
    assert ops2.diagnostics.diagnostics().consistent
    assert ops2.service.replay_inventory().sessions == ("pipe-op-arch-r1",)
