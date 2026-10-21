"""Durable Policy Engine integration (ADR-007 through P1) — the P2 acceptance gate.

Proves the engine works transparently over the durable substrate: decision events are
durable and correlated, the registry rebuilds from the durable log after a restart, and
the same request yields the same verdict across restart (replay-after-restart
determinism, INV-17). No policy-specific durable code exists — it rides P1.
"""

from __future__ import annotations

from nexus_infra import build_durable_infrastructure
from nexus_policy import (
    DecisionRequest,
    InMemoryPolicyRegistry,
    PolicyEngine,
    build_policy,
)
from nexus_policy.events import POLICY_EVALUATED

_NOW = "2026-01-01T00:00:00Z"


def _exec(correlation: str, **attrs) -> DecisionRequest:
    return DecisionRequest(
        action_class="execution", correlation_identifier=correlation, attributes=attrs
    )


def test_decision_events_are_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "policy.db")
    ctx = build_policy(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.engine.evaluate(_exec("cor-1", runtime="claude", command="ls", runtime_policy="approved"))

    reopened = build_durable_infrastructure(db)
    decisions = [e for e in reopened.event_store.read_all() if e.type == POLICY_EVALUATED]
    assert len(decisions) == 1
    assert decisions[0].correlation_identifier == "cor-1"
    assert decisions[0].payload["decision"] == "allow"


def test_registry_rebuilds_from_durable_log_after_restart(tmp_path) -> None:
    db = str(tmp_path / "policy.db")
    build_policy(build_durable_infrastructure(db), now=lambda: _NOW)  # seeds + logs registrations

    reopened = build_durable_infrastructure(db)
    rebuilt = InMemoryPolicyRegistry()
    rebuilt.rebuild(reopened.event_store.read_all())
    assert {p.identity for p in rebuilt.enabled()} == {
        "policy.execution.allow-baseline",
        "policy.execution.deny-unapproved-runtime",
        "policy.execution.deny-blacklisted-command",
        "policy.execution.deny-unapproved-runtime-policy",
    }


def test_same_verdict_across_restart(tmp_path) -> None:
    db = str(tmp_path / "policy.db")
    ctx = build_policy(build_durable_infrastructure(db), now=lambda: _NOW)
    req = _exec("cor-x", runtime="evil", command="ls", runtime_policy="approved")
    before = ctx.engine.evaluate(req)

    reopened = build_durable_infrastructure(db)
    rebuilt = InMemoryPolicyRegistry()
    rebuilt.rebuild(reopened.event_store.read_all())
    after = PolicyEngine(rebuilt, now=lambda: _NOW).simulate(req)

    assert before.decision == after.decision
    assert before.matched_policy == after.matched_policy


def test_full_authorization_history_replays_after_restart(tmp_path) -> None:
    db = str(tmp_path / "policy.db")
    ctx = build_policy(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.engine.evaluate(_exec("op-a", runtime="claude", command="ls", runtime_policy="approved"))
    ctx.engine.evaluate(_exec("op-b", runtime="evil", command="ls", runtime_policy="approved"))

    reopened = build_durable_infrastructure(db)
    history = [
        (e.correlation_identifier, e.payload["decision"])
        for e in reopened.event_store.read_all()
        if e.type == POLICY_EVALUATED
    ]
    assert history == [("op-a", "allow"), ("op-b", "deny")]
