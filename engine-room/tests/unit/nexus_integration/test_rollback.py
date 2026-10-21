"""Per-owner rollback (``nexus_integration.coordinator.RollbackCoordinator``, ADR-008 §3.6).

Rollback is per-owner (never global), atomic (one flag write), immediate, deterministic,
observable, and durable/replayable — returning authority to the retained legacy path.
"""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_integration import (
    Authority,
    DecisionIdentity,
    DeterminismClass,
    FlagState,
    build_integration,
)

_NOW = "2026-01-01T00:00:00Z"


def _ctx():
    return build_integration(build_infrastructure(), now=lambda: _NOW)


def _adjudicate(ctx, owner, i):
    return ctx.coordinator.adjudicate(
        DecisionIdentity(owner=owner, decision_id=f"d{i}", correlation_identifier=f"cor-{i}"),
        legacy=lambda: "allow",
        shadow=lambda: "deny",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )


def test_rollback_restores_legacy_authority() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    assert _adjudicate(ctx, "policy_engine", 1).authority is Authority.CONSTITUTIONAL

    ctx.rollback.rollback("policy_engine")
    assert ctx.flags.state("policy_engine") is FlagState.DISABLED
    assert _adjudicate(ctx, "policy_engine", 2).authority is Authority.LEGACY


def test_rollback_is_owner_scoped_never_global() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    ctx.flags.set("intent_resolution", FlagState.ENABLED)

    ctx.rollback.rollback("policy_engine")
    assert ctx.flags.state("policy_engine") is FlagState.DISABLED
    assert ctx.flags.state("intent_resolution") is FlagState.ENABLED  # untouched


def test_rollback_to_earlier_state() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    ctx.rollback.rollback_to("policy_engine", FlagState.SHADOW)
    assert ctx.flags.state("policy_engine") is FlagState.SHADOW


def test_rollback_preserves_decision_history() -> None:
    ctx = _ctx()
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    _adjudicate(ctx, "policy_engine", 1)
    before = len(list(ctx.infrastructure.event_store.read_all()))
    ctx.rollback.rollback("policy_engine")  # only appends a flag_set; never deletes (INV-13)
    after = list(ctx.infrastructure.event_store.read_all())
    assert len(after) == before + 1
    assert any(e.type == "migration.decision_diff" for e in after)  # history intact
