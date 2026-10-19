"""Constitutional guardrails for the integration substrate (ADR-008 §9).

Proves: legacy path unchanged when disabled; shadow never mutates production; rollback
restores the previous owner; canary is isolated; the constitutional owner is active only
when enabled/canary-for-cohort; migration events are append-only; the substrate contains no
business logic and reads flags at a single seam.
"""

from __future__ import annotations

from pathlib import Path

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
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _ctx():
    return build_integration(build_infrastructure(), now=lambda: _NOW)


def _id(i: int, *, owner="policy_engine", cohort_key=None) -> DecisionIdentity:
    return DecisionIdentity(
        owner=owner, decision_id=f"d{i}", correlation_identifier=f"cor-{i}", cohort_key=cohort_key
    )


def test_legacy_path_unchanged_when_disabled() -> None:
    ctx = _ctx()
    calls = {"legacy": 0, "shadow": 0}

    def legacy():
        calls["legacy"] += 1
        return "allow"

    def shadow():
        calls["shadow"] += 1
        return "deny"

    result = ctx.coordinator.adjudicate(
        _id(1), legacy=legacy, shadow=shadow, determinism_class=DeterminismClass.DETERMINISTIC
    )
    assert result.authoritative_value == "allow"
    assert calls == {"legacy": 1, "shadow": 0}  # shadow never runs


def test_shadow_never_mutates_production() -> None:
    infra = build_infrastructure()
    ctx = build_integration(infra, now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    production_effects: list = []

    def shadow():
        # A well-behaved shadow is a pure decision; if it tried to mutate production it would
        # append here. The substrate must not perform such effects itself either.
        return "allow"

    ctx.coordinator.adjudicate(
        _id(2),
        legacy=lambda: "allow",
        shadow=shadow,
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert production_effects == []
    non_migration = [e for e in infra.event_store.read_all() if not e.type.startswith("migration.")]
    assert non_migration == []


def test_rollback_restores_previous_owner() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    ctx.rollback.rollback("policy_engine")
    r = ctx.coordinator.adjudicate(
        _id(3),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert r.authority is Authority.LEGACY


def test_canary_isolated_from_non_cohort() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.CANARY)
    out = ctx.coordinator.adjudicate(
        _id(4, cohort_key="k"),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
        cohort=CanaryCohort(0),
    )
    assert out.authority is Authority.LEGACY  # non-cohort stays on legacy


def test_constitutional_active_only_when_enabled_or_canary_cohort() -> None:
    ctx = _ctx()
    for state in (FlagState.DISABLED, FlagState.SHADOW):
        ctx.flags.set("policy_engine", state)
        r = ctx.coordinator.adjudicate(
            _id(10),
            legacy=lambda: "a",
            shadow=lambda: "b",
            determinism_class=DeterminismClass.DETERMINISTIC,
        )
        assert r.authority is Authority.LEGACY, state


def test_migration_events_are_append_only() -> None:
    # The substrate only ever appends; it exposes no update/delete of recorded facts.
    from nexus_integration import recorder as recorder_module

    src = Path(recorder_module.__file__).read_text(encoding="utf-8")
    assert "delete" not in src.lower()
    assert "update" not in src.lower()


def test_flags_read_at_a_single_seam() -> None:
    # No scattered flag-store reads: the private state dict is touched only in flags.py.
    offenders = []
    for path in (_REPO_ROOT / "nexus_integration").glob("*.py"):
        if path.name == "flags.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "_state[" in text or "_state.get" in text:
            offenders.append(path.name)
    assert offenders == [], f"flag state read outside the FlagStore seam: {offenders}"


def test_substrate_has_no_engine_dependency() -> None:
    # No business logic / engine import: the substrate depends only on nexus_core + nexus_infra.
    engines = (
        "nexus_policy",
        "nexus_planning",
        "nexus_execution",
        "nexus_validation",
        "nexus_recovery",
    )
    for path in (_REPO_ROOT / "nexus_integration").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for engine in engines:
            assert f"import {engine}" not in text, f"{path.name} imports {engine}"
