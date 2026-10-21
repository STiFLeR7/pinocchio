"""The Policy Engine (``nexus_policy.engine``) — decisions, boundaries, determinism.

Proves the allow/deny matrix, fail-closed behaviour (INV-30), the RequireApproval level
(ADR-004 §3.3), ungoverned allow-by-default, explainability (INV-31), determinism, and
INV-29 (decides, performs no action; simulation is side-effect-free).
"""

from __future__ import annotations

from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_policy import (
    DecisionRequest,
    InMemoryPolicyRegistry,
    PolicyEngine,
    v1_seed_policies,
)

_NOW = "2026-01-01T00:00:00Z"


def _seeded_engine(*, emitter=None) -> PolicyEngine:
    reg = InMemoryPolicyRegistry(now=lambda: _NOW)
    for policy in v1_seed_policies():
        reg.register(policy)
    return PolicyEngine(reg, emitter=emitter, now=lambda: _NOW)


def _exec(**attrs) -> DecisionRequest:
    return DecisionRequest(action_class="execution", correlation_identifier="cor", attributes=attrs)


def test_allow_when_all_checks_pass() -> None:
    e = _seeded_engine().evaluate(
        _exec(runtime="claude", command="pytest", runtime_policy="approved")
    )
    assert e.decision is PolicyDecision.ALLOW
    assert e.matched_policy.identity == "policy.execution.allow-baseline"
    assert e.default_applied is False


def test_deny_matrix() -> None:
    engine = _seeded_engine()
    assert (
        engine.evaluate(_exec(runtime="evil", command="ls", runtime_policy="approved")).decision
        is PolicyDecision.DENY
    )
    assert (
        engine.evaluate(
            _exec(runtime="claude", command="sudo x", runtime_policy="approved")
        ).decision
        is PolicyDecision.DENY
    )
    assert (
        engine.evaluate(_exec(runtime="claude", command="ls", runtime_policy="pending")).decision
        is PolicyDecision.DENY
    )


def test_fail_closed_no_matching_policy_denies() -> None:
    # A governed action of an unknown class matches nothing → Default Policy denies (INV-30).
    e = _seeded_engine().evaluate(
        DecisionRequest(action_class="mystery", correlation_identifier="cor")
    )
    assert e.decision is PolicyDecision.DENY
    assert e.default_applied is True
    assert e.matched_policy.identity == "policy.default"


def test_fail_closed_malformed_policy_denies() -> None:
    reg = InMemoryPolicyRegistry(now=lambda: _NOW)
    reg.register(
        Policy(
            identity="broken",
            version="1",
            purpose="malformed conditions",
            conditions={"attr": "x", "op": "no-such-op", "value": 1},
            decision=PolicyDecision.ALLOW,
            priority=0,
            owner="governance",
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.EXECUTION,
        )
    )
    e = PolicyEngine(reg, now=lambda: _NOW).evaluate(_exec(x=1))
    assert e.decision is PolicyDecision.DENY
    assert e.default_applied is True
    assert "fail-closed" in e.reasoning_trace[0]


def test_ungoverned_is_allow_by_default() -> None:
    e = _seeded_engine().evaluate(
        DecisionRequest(action_class="chat", correlation_identifier="cor", governed=False)
    )
    assert e.decision is PolicyDecision.ALLOW
    assert e.matched_policy is None


def test_require_approval_reports_level_but_performs_no_action() -> None:
    reg = InMemoryPolicyRegistry(now=lambda: _NOW)
    reg.register(
        Policy(
            identity="policy.deploy.approval",
            version="1",
            purpose="deploys need review",
            conditions={"attr": "action_class", "op": "eq", "value": "deploy"},
            decision=PolicyDecision.REQUIRE_APPROVAL,
            approval_requirement=ApprovalTaxonomy.MULTI_STAGE,
            priority=0,
            owner="governance",
            status=PolicyStatus.ENABLED,
        )
    )
    e = PolicyEngine(reg, now=lambda: _NOW).evaluate(
        DecisionRequest(action_class="deploy", correlation_identifier="cor")
    )
    assert e.decision is PolicyDecision.REQUIRE_APPROVAL
    assert e.approval_requirement is ApprovalTaxonomy.MULTI_STAGE


def test_require_approval_defaults_to_human_review() -> None:
    reg = InMemoryPolicyRegistry(now=lambda: _NOW)
    reg.register(
        Policy(
            identity="p",
            version="1",
            purpose="approval without explicit level",
            conditions={"attr": "action_class", "op": "eq", "value": "deploy"},
            decision=PolicyDecision.REQUIRE_APPROVAL,
            priority=0,
            owner="governance",
            status=PolicyStatus.ENABLED,
        )
    )
    e = PolicyEngine(reg, now=lambda: _NOW).evaluate(
        DecisionRequest(action_class="deploy", correlation_identifier="cor")
    )
    assert e.approval_requirement is ApprovalTaxonomy.HUMAN_REVIEW  # ADR-004 §3.3


def test_explainability_trace_and_refs() -> None:
    e = _seeded_engine().evaluate(_exec(runtime="evil", command="ls", runtime_policy="approved"))
    assert e.reasoning_trace  # non-empty (INV-31)
    assert any("winner:" in line for line in e.reasoning_trace)
    assert e.matched_policy.identity == "policy.execution.deny-unapproved-runtime"
    assert len(e.applicable_policies) >= 2  # baseline + the deny both applied


def test_determinism_identical_input_identical_output() -> None:
    engine = _seeded_engine()
    req = _exec(runtime="claude", command="ls", runtime_policy="approved")
    assert engine.simulate(req) == engine.simulate(req)


def test_simulate_is_side_effect_free() -> None:
    spy = _SpyEmitter()
    engine = _seeded_engine(emitter=spy)
    engine.simulate(_exec(runtime="claude", command="ls", runtime_policy="approved"))
    assert spy.events == []  # no event emitted (contract §6)


def test_evaluate_emits_exactly_one_decision_event() -> None:
    spy = _SpyEmitter()
    engine = _seeded_engine(emitter=spy)
    engine.evaluate(_exec(runtime="claude", command="ls", runtime_policy="approved"))
    assert len(spy.events) == 1
    assert spy.events[0].type == "policy.evaluated"


class _SpyEmitter:
    def __init__(self) -> None:
        self.events: list = []

    def emit(self, event) -> None:
        self.events.append(event)
