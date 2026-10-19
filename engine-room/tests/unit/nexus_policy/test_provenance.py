"""Policy provenance events (WP-P2.2, INV-39/INV-17).

Every ``evaluate()`` produces exactly one correlated decision event; the payload records
the decision, matched policy, and attributes; replaying the ``policy.evaluated`` stream
reconstructs the full authorization history without re-inference.
"""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_policy import DecisionRequest, build_policy
from nexus_policy.events import POLICY_EVALUATED


def _exec(correlation: str, **attrs) -> DecisionRequest:
    return DecisionRequest(
        action_class="execution", correlation_identifier=correlation, attributes=attrs
    )


def _ctx():
    return build_policy(build_infrastructure(), now=lambda: "2026-01-01T00:00:00Z")


def test_exactly_one_decision_event_per_evaluate() -> None:
    ctx = _ctx()
    before = _count_decisions(ctx)
    ctx.engine.evaluate(_exec("cor-1", runtime="claude", command="ls", runtime_policy="approved"))
    assert _count_decisions(ctx) == before + 1


def test_decision_event_is_correlated_and_carries_the_verdict() -> None:
    ctx = _ctx()
    ctx.engine.evaluate(_exec("cor-42", runtime="evil", command="ls", runtime_policy="approved"))
    decision = _decisions(ctx)[-1]
    assert decision.correlation_identifier == "cor-42"  # INV-39
    assert decision.payload["decision"] == "deny"
    assert (
        decision.payload["matched_policy"]["identity"] == "policy.execution.deny-unapproved-runtime"
    )
    assert decision.payload["attributes"]["runtime"] == "evil"


def test_replay_reconstructs_authorization_history() -> None:
    ctx = _ctx()
    ctx.engine.evaluate(_exec("op-a", runtime="claude", command="ls", runtime_policy="approved"))
    ctx.engine.evaluate(_exec("op-b", runtime="evil", command="ls", runtime_policy="approved"))
    ctx.engine.evaluate(
        _exec("op-c", runtime="claude", command="sudo x", runtime_policy="approved")
    )
    history = [(d.correlation_identifier, d.payload["decision"]) for d in _decisions(ctx)]
    assert history == [("op-a", "allow"), ("op-b", "deny"), ("op-c", "deny")]


def test_identical_evaluation_is_idempotent_in_the_log() -> None:
    ctx = _ctx()
    req = _exec("op-x", runtime="claude", command="ls", runtime_policy="approved")
    ctx.engine.evaluate(req)
    n = _count_decisions(ctx)
    ctx.engine.evaluate(req)  # same request, same decision → same content-addressed id (INV-16)
    assert _count_decisions(ctx) == n


def _decisions(ctx):
    return [e for e in ctx.infrastructure.event_store.read_all() if e.type == POLICY_EVALUATED]


def _count_decisions(ctx) -> int:
    return len(_decisions(ctx))
