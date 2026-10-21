"""Policy composition wiring (``nexus_policy.composition``).

``build_policy`` reuses the infrastructure substrate unchanged, seeds the v1-migrated
governance defaults, and produces an engine whose decisions land in the infrastructure
event store. It never modifies the infrastructure.
"""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_policy import DecisionRequest, build_policy
from nexus_policy.events import POLICY_EVALUATED, POLICY_REGISTERED


def test_build_policy_seeds_the_v1_defaults() -> None:
    ctx = build_policy(build_infrastructure(), now=lambda: "t")
    identities = {p.identity for p in ctx.registry.enabled()}
    assert "policy.execution.allow-baseline" in identities
    assert "policy.execution.deny-unapproved-runtime" in identities


def test_build_policy_without_seed_is_empty() -> None:
    ctx = build_policy(build_infrastructure(), seed=False, now=lambda: "t")
    assert ctx.registry.enabled() == ()
    # A governed request against an empty registry fails closed (INV-30).
    e = ctx.engine.evaluate(DecisionRequest(action_class="execution", correlation_identifier="c"))
    assert e.default_applied is True


def test_registrations_and_decisions_are_persisted_to_the_shared_log() -> None:
    infra = build_infrastructure()
    ctx = build_policy(infra, now=lambda: "t")
    ctx.engine.evaluate(
        DecisionRequest(
            action_class="execution",
            correlation_identifier="cor",
            attributes={"runtime": "claude", "command": "ls", "runtime_policy": "approved"},
        )
    )
    types = [e.type for e in infra.event_store.read_all()]
    assert types.count(POLICY_REGISTERED) == 4  # the four seed policies
    assert types.count(POLICY_EVALUATED) == 1


def test_policies_persist_through_the_infrastructure_repository() -> None:
    infra = build_infrastructure()
    build_policy(infra, now=lambda: "t")
    # The shared PolicyRepository read-model holds the seed policies (projection, not authority).
    assert infra.policies.get("policy.execution.allow-baseline") is not None


def test_build_policy_over_a_restarted_log_does_not_reseed_or_crash_under_a_real_clock() -> None:
    """A second build_policy(seed=True) call over the same infra, at a genuinely different
    timestamp (a real restart, not the fixed clock every other test uses across two calls),
    must rebuild from the existing log rather than re-emit the same seed policies — a real,
    reproduced crash this test guards against (DuplicateEventError: same identifier, different
    timestamp)."""
    infra = build_infrastructure()
    build_policy(infra, now=lambda: "2026-01-01T00:00:00+00:00")

    second = build_policy(infra, now=lambda: "2026-01-01T00:05:00+00:00")  # must not raise

    identities = {p.identity for p in second.registry.enabled()}
    assert "policy.execution.allow-baseline" in identities
    types = [e.type for e in infra.event_store.read_all()]
    assert types.count(POLICY_REGISTERED) == 4  # not re-emitted a second time


def test_build_policy_seed_still_applies_over_a_log_with_unrelated_existing_policies() -> None:
    """``seed=True`` must still register the v1 defaults when the log already has *some* policy
    history that isn't the product of a prior identical seed call (e.g. a caller that registers
    a custom policy directly before ever calling build_policy) — the rebuild-from-log step must
    not silently substitute for seeding."""
    infra = build_infrastructure()
    build_policy(infra, seed=False, now=lambda: "t").registry.register(
        _custom_policy("policy.custom.example")
    )

    ctx = build_policy(infra, now=lambda: "t")

    identities = {p.identity for p in ctx.registry.enabled()}
    assert "policy.custom.example" in identities  # the pre-existing registration survived
    assert "policy.execution.allow-baseline" in identities  # and the v1 defaults were still seeded


def _custom_policy(identity: str):  # type: ignore[no-untyped-def]
    from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
    from nexus_core.contracts.status import PolicyStatus
    from nexus_core.domain.policy import Policy

    return Policy(
        identity=identity,
        version="1",
        purpose="test",
        conditions={"attr": "action_class", "op": "eq", "value": "custom"},
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner="test",
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
    )
