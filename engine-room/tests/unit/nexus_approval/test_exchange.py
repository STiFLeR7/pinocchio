"""P15/A unit — the Approval Exchange coordinates the approval lifecycle (records + resumes only).

The exchange publishes a request for each Actuation-waiting gate, records the operator's decision as
durable ``approval.*`` audit, resumes the pipeline on approval, and reconstructs the identical approval
history from the log — evaluating no policy, executing nothing itself.
"""

from __future__ import annotations

from nexus_approval import ApprovalLifecycle, build_approval_exchange
from nexus_approval.events import APPROVAL_PRODUCER
from nexus_infra import build_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def _exchange():
    infra = build_infrastructure()
    spine = build_constitutional_pipeline(infra)
    return infra, spine.coordinator, build_approval_exchange(spine.coordinator, infra)


def _pause_on_review():
    """Drive a gated run to its approval boundary; return (infra, pipeline, exchange, request, session_id)."""
    infra, pipeline, exchange = _exchange()
    request = spine_reference_request(run="r1", gated=("review",))
    run = pipeline.run(request)
    exchange.publish(request.pipeline_session_id, run.execution_state.waiting_nodes)
    return infra, pipeline, exchange, request, request.pipeline_session_id


def test_publish_surfaces_the_actuation_approval_boundary() -> None:
    _, _, exchange, _, session_id = _pause_on_review()
    pending = exchange.pending(session_id)
    assert [request.node for request in pending] == ["node-review"]
    assert pending[0].state is ApprovalLifecycle.PENDING
    assert pending[
        0
    ].taxonomy  # the taxonomy the ExecutionStrategy required (Policy's call, not ours)


def test_publish_is_idempotent() -> None:
    _, pipeline, exchange, request, session_id = _pause_on_review()
    before = len(pipeline.history())
    exchange.publish(session_id, ("node-review",))  # already published → no new facts
    assert len(pipeline.history()) == before


def test_approve_records_and_resumes_to_completion() -> None:
    _, pipeline, exchange, request, session_id = _pause_on_review()
    decision = exchange.approve(request, "node-review", decided_by="alice", reason="looks good")
    assert decision.state is ApprovalLifecycle.APPROVED and decision.resumed
    assert decision.pipeline_status == "completed"
    session = exchange.session(session_id)
    assert session.granted_gates == ("node-review",)
    assert session.request("node-review").decided_by == "alice"


def test_deny_records_and_does_not_resume() -> None:
    _, pipeline, exchange, request, session_id = _pause_on_review()
    decision = exchange.deny(session_id, "node-review", decided_by="bob", reason="not now")
    assert decision.state is ApprovalLifecycle.DENIED and not decision.resumed
    assert exchange.session(session_id).denied_gates == ("node-review",)
    assert not exchange.pending(session_id)  # left the pending queue


def test_expire_and_sweep_transition_pending_to_expired() -> None:
    _, _, exchange, request, session_id = _pause_on_review()
    exchange.expire(session_id, "node-review")
    request_state = exchange.session(session_id).request("node-review")
    assert request_state.state is ApprovalLifecycle.EXPIRED
    # sweep is deadline-driven (ISO-8601 is order-preserving); a fresh session with a past deadline expires.
    infra2, pipeline2, exchange2 = _exchange()
    req2 = spine_reference_request(run="r2", gated=("review",))
    run2 = pipeline2.run(req2)
    exchange2.publish(
        req2.pipeline_session_id,
        run2.execution_state.waiting_nodes,
        expires_at="2000-01-01T00:00:00+00:00",
    )
    swept = exchange2.sweep_expired(req2.pipeline_session_id, now="2030-01-01T00:00:00+00:00")
    assert swept == ("node-review",)
    assert not exchange2.pending(req2.pipeline_session_id)


def test_explanation_names_the_gate_and_state() -> None:
    _, _, exchange, _, session_id = _pause_on_review()
    explanation = exchange.explanation(session_id, "node-review")
    assert explanation.taxonomy and explanation.state is ApprovalLifecycle.PENDING
    assert "node-review" in explanation.detail
    missing = exchange.explanation(session_id, "node-absent")
    assert "no approval" in missing.detail


def test_approval_history_is_deterministic_and_single_producer() -> None:
    def once() -> list[tuple[str, str, object]]:
        infra, pipeline, exchange = _exchange()
        request = spine_reference_request(run="r1", gated=("review",))
        run = pipeline.run(request)
        exchange.publish(request.pipeline_session_id, run.execution_state.waiting_nodes)
        exchange.approve(request, "node-review", decided_by="alice", reason="ok")
        approval = [
            (event.identifier, event.type, event.payload)
            for event in pipeline.history()
            if event.producer == APPROVAL_PRODUCER
        ]
        assert approval  # the exchange recorded its facts
        assert all(
            event.producer == APPROVAL_PRODUCER
            for event in pipeline.history()
            if event.type.startswith("approval.")
        )  # one owner (INV-02)
        return approval

    assert once() == once()  # byte-identical approval stream across runs
