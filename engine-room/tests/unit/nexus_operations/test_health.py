"""P15/B unit — the Health inspector + Diagnostics derive a deterministic operational view.

Health composes the read-only projections into a summary and records durable snapshots; diagnostics
counts the log and verifies structural consistency. Both are pure functions of the shared log.
"""

from __future__ import annotations

from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_operations.events import OPERATIONS_PRODUCER, OPERATIONS_SNAPSHOT


def _ops(*, gated: tuple[str, ...] = ()):
    ctx = build_human_interaction(build_infrastructure())
    request = reference_operator_request(run="r1", gated=gated)
    ctx.facade.submit(request)
    return ctx, build_operations(ctx.spine.coordinator, ctx.approval, ctx.infrastructure), request


def test_health_summary_of_a_completed_run_is_healthy() -> None:
    _, ops, _ = _ops()
    summary = ops.health.summary()
    assert summary.is_healthy and summary.liveness == "healthy"
    assert summary.active_sessions == 1 and summary.pending_approvals == 0
    assert summary.runtime_utilization >= 2  # both nodes ran
    assert dict(summary.pipeline_states).get("completed") == 1


def test_health_summary_reflects_a_pending_approval() -> None:
    ctx, ops, request = _ops(gated=("review",))
    summary = ops.health.summary()
    assert summary.pending_approvals == 1 and summary.queue_depth == 1
    assert dict(summary.pipeline_states).get("paused") == 1
    ctx.facade.approve(request, "node-review", decided_by="alice")
    after = ops.health.summary()
    assert after.pending_approvals == 0 and after.completed_approvals == 1


def test_snapshot_is_recorded_and_reconstructed() -> None:
    ctx, ops, _ = _ops()
    snapshot = ops.health.record_snapshot()
    assert snapshot.summary.is_healthy
    reloaded = ops.health.snapshots()
    assert len(reloaded) == 1 and reloaded[0].summary.active_sessions == 1
    recorded = [
        event for event in ctx.spine.coordinator.history() if event.type == OPERATIONS_SNAPSHOT
    ]
    assert recorded and all(event.producer == OPERATIONS_PRODUCER for event in recorded)


def test_diagnostics_are_consistent_and_count_the_log() -> None:
    _, ops, _ = _ops()
    diagnostics = ops.diagnostics.diagnostics()
    assert diagnostics.consistent and not diagnostics.issues
    assert diagnostics.total_events > 0
    producers = dict(diagnostics.by_producer)
    assert producers.get("pipeline", 0) > 0  # the pipeline recorded its stage facts
