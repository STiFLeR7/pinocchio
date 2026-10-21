"""P15/A — the Constitutional Approval Exchange completes the governance loop around gated execution.

End-to-end proof that Actuation's approval pause, the operator's decision, and the resumed pipeline form
one durable, replayable, restartable exchange — surfaced through the Human Interaction façade (which never
bypasses the exchange) — and that replay reconstructs the identical approval history and a restart resumes
an in-flight approval wait without replaying completed constitutional stages.
"""

from __future__ import annotations

from nexus_approval import ApprovalLifecycle, build_approval_exchange, reconstruct_approval_session
from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def test_pause_grant_resume_through_the_operator_surface() -> None:
    ctx = build_human_interaction(build_infrastructure())
    request = reference_operator_request(run="r1", gated=("review",))

    paused = ctx.facade.submit(request)
    assert paused.status == "paused" and paused.awaiting_approval
    assert [p.node for p in paused.pending_approvals] == ["node-review"]
    # The operator inspects why, then authorizes — the exchange records it and resumes execution.
    assert (
        ctx.facade.approval_explanation("op-arch-r1", "node-review").state
        is ApprovalLifecycle.PENDING
    )
    decision = ctx.facade.approve(request, "node-review", decided_by="alice", reason="approved")
    assert decision.state is ApprovalLifecycle.APPROVED and decision.pipeline_status == "completed"
    assert ctx.facade.status("op-arch-r1").is_complete
    assert not ctx.facade.pending_approvals("op-arch-r1")
    assert [h.state for h in ctx.facade.approval_history("op-arch-r1")] == [
        ApprovalLifecycle.APPROVED
    ]


def test_deny_blocks_the_gated_work() -> None:
    ctx = build_human_interaction(build_infrastructure())
    request = reference_operator_request(run="r1", gated=("review",))
    ctx.facade.submit(request)

    decision = ctx.facade.deny(request, "node-review", decided_by="bob", reason="not approved")
    assert decision.state is ApprovalLifecycle.DENIED and not decision.resumed
    # The gate is denied and the session stays paused — the gated node never executed.
    assert not ctx.facade.status("op-arch-r1").is_complete
    graph = ctx.facade.execution_graph("op-arch-r1")
    assert "node-review" in graph.nodes  # planned, but never driven


def test_expiry_is_a_durable_terminal_transition() -> None:
    infra = build_infrastructure()
    spine = build_constitutional_pipeline(infra)
    exchange = build_approval_exchange(spine.coordinator, infra)
    request = spine_reference_request(run="r1", gated=("review",))
    run = spine.coordinator.run(request)
    exchange.publish(request.pipeline_session_id, run.execution_state.waiting_nodes)

    exchange.expire(request.pipeline_session_id, "node-review")
    session = exchange.session(request.pipeline_session_id)
    assert session.request("node-review").state is ApprovalLifecycle.EXPIRED
    assert not exchange.pending(request.pipeline_session_id)


def test_replay_reconstructs_identical_approval_history(tmp_path) -> None:
    db = str(tmp_path / "approval.db")
    ctx = build_human_interaction(build_durable_infrastructure(db))
    request = reference_operator_request(run="r1", gated=("review",))
    ctx.facade.submit(request)
    ctx.facade.approve(request, "node-review", decided_by="alice", reason="approved")

    # A fresh reader over the reopened file reconstructs the identical approval lifecycle.
    reopened = build_durable_infrastructure(db)
    replayed = reconstruct_approval_session(
        tuple(reopened.event_store.read_all()), "pipe-op-arch-r1"
    )
    assert replayed.granted_gates == ("node-review",)
    request_state = replayed.request("node-review")
    assert request_state.state is ApprovalLifecycle.APPROVED
    assert request_state.decided_by == "alice" and request_state.reason == "approved"


def test_restart_resumes_an_in_flight_approval_wait(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    request = reference_operator_request(run="r1", gated=("review",))

    # Process 1: submit drives the pipeline to the approval boundary and pauses (durably).
    first = build_human_interaction(build_durable_infrastructure(db))
    paused = first.facade.submit(request)
    assert paused.status == "paused" and paused.awaiting_approval

    # Process 2: a fresh surface over the reopened file still sees the pending wait, then approves.
    second = build_human_interaction(build_durable_infrastructure(db))
    assert [p.node for p in second.facade.pending_approvals("op-arch-r1")] == ["node-review"]
    resumed = second.facade.approve(request, "node-review", decided_by="alice", reason="approved")
    assert resumed.state is ApprovalLifecycle.APPROVED and resumed.pipeline_status == "completed"
    assert second.facade.status("op-arch-r1").is_complete
