"""Recorded Shadow Adjudication routing (``nexus_integration.coordinator``, ADR-008 §3.2/§3.5).

Proves flag-routed authority across disabled/shadow/canary/enabled, that the constitutional
owner is not invoked when disabled, that both decisions are recorded when active, and that a
shadow run produces no non-``migration.*`` events (side-effect isolation, §3.5).
"""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_integration import (
    Authority,
    CanaryCohort,
    DecisionIdentity,
    DeterminismClass,
    FlagState,
    build_integration,
)

_NOW = "2026-01-01T00:00:00Z"


def _ctx():
    return build_integration(build_infrastructure(), now=lambda: _NOW)


def _id(owner: str, i: int, *, cohort_key: str | None = None) -> DecisionIdentity:
    return DecisionIdentity(
        owner=owner, decision_id=f"d{i}", correlation_identifier=f"cor-{i}", cohort_key=cohort_key
    )


def test_disabled_uses_legacy_and_never_invokes_constitutional() -> None:
    ctx = _ctx()
    invoked = []
    result = ctx.coordinator.adjudicate(
        _id("policy_engine", 1),
        legacy=lambda: "allow",
        shadow=lambda: invoked.append(1) or "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert result.authority is Authority.LEGACY
    assert result.authoritative_value == "allow"
    assert invoked == []  # constitutional owner inactive when disabled
    assert result.diff is None


def test_shadow_keeps_legacy_authoritative_and_records_diff() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    result = ctx.coordinator.adjudicate(
        _id("policy_engine", 2),
        legacy=lambda: "allow",
        shadow=lambda: "allow",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert result.authority is Authority.LEGACY  # v1 still authoritative in shadow
    assert result.diff is not None
    assert result.diff.verdict.value == "match"


def test_enabled_makes_constitutional_authoritative_and_still_records_legacy() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    result = ctx.coordinator.adjudicate(
        _id("policy_engine", 3),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert result.authority is Authority.CONSTITUTIONAL
    assert result.authoritative_value == "deny"
    assert result.legacy_value == "allow"  # legacy shadowed as a safety net


def test_canary_routes_by_stable_cohort() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.CANARY)
    everybody = CanaryCohort(100)
    nobody = CanaryCohort(0)
    inside = ctx.coordinator.adjudicate(
        _id("policy_engine", 4, cohort_key="user-1"),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
        cohort=everybody,
    )
    outside = ctx.coordinator.adjudicate(
        _id("policy_engine", 5, cohort_key="user-1"),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
        cohort=nobody,
    )
    assert inside.authority is Authority.CONSTITUTIONAL
    assert outside.authority is Authority.LEGACY


def test_canary_without_cohort_is_safe_legacy() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.CANARY)
    result = ctx.coordinator.adjudicate(
        _id("policy_engine", 6),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert result.authority is Authority.LEGACY  # empty default cohort → nobody


def test_shadow_run_emits_only_migration_events() -> None:
    # Side-effect isolation (ADR-008 §3.5): the only events under the correlation are migration.*.
    infra = build_infrastructure()
    ctx = build_integration(infra, now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    ctx.coordinator.adjudicate(
        _id("policy_engine", 7),
        legacy=lambda: "allow",
        shadow=lambda: "allow",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    under_correlation = [
        e for e in infra.event_store.read_all() if e.correlation_identifier == "cor-7"
    ]
    assert under_correlation, "expected recorded decision events"
    assert all(e.type.startswith("migration.") for e in under_correlation)
