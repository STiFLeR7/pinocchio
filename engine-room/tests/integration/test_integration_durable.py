"""Durable migration substrate integration (ADR-007 through P1) — the P3 acceptance gate.

Proves decision recording is durable, replay reconstructs the migration history, replay is
deterministic, flags and rollback replay, restart preserves migration state, and correlation
is preserved end to end. All of this rides P1 unchanged — no substrate-specific durable code.
"""

from __future__ import annotations

from nexus_infra import build_durable_infrastructure
from nexus_integration import (
    DecisionIdentity,
    DeterminismClass,
    FlagState,
    FlagStore,
    build_integration,
)
from nexus_integration.events import (
    MIGRATION_DECISION_DIFF,
    MIGRATION_DECISION_RECORDED,
    MIGRATION_SHADOW_DECISION,
)

_NOW = "2026-01-01T00:00:00Z"


def _adjudicate(ctx, i, *, owner="policy_engine", legacy="allow", shadow="allow"):
    return ctx.coordinator.adjudicate(
        DecisionIdentity(owner=owner, decision_id=f"d{i}", correlation_identifier=f"cor-{i}"),
        legacy=lambda: legacy,
        shadow=lambda: shadow,
        determinism_class=DeterminismClass.DETERMINISTIC,
    )


def test_decision_recording_is_durable(tmp_path) -> None:
    db = str(tmp_path / "mig.db")
    ctx = build_integration(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    _adjudicate(ctx, 1)

    reopened = build_durable_infrastructure(db)
    types = {e.type for e in reopened.event_store.read_all()}
    assert {
        MIGRATION_DECISION_RECORDED,
        MIGRATION_SHADOW_DECISION,
        MIGRATION_DECISION_DIFF,
    } <= types


def test_replay_reconstructs_migration_history(tmp_path) -> None:
    db = str(tmp_path / "mig.db")
    ctx = build_integration(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    _adjudicate(ctx, 1, legacy="allow", shadow="allow")
    _adjudicate(ctx, 2, legacy="allow", shadow="deny")

    reopened = build_durable_infrastructure(db)
    diffs = [
        (e.payload["decision_id"], e.payload["verdict"])
        for e in reopened.event_store.read_all()
        if e.type == MIGRATION_DECISION_DIFF
    ]
    assert diffs == [("d1", "match"), ("d2", "mismatch")]


def test_restart_preserves_flags_and_rollback(tmp_path) -> None:
    db = str(tmp_path / "mig.db")
    ctx = build_integration(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.ENABLED)
    ctx.flags.set("intent_resolution", FlagState.CANARY)
    ctx.rollback.rollback("policy_engine")  # → disabled

    reopened = build_durable_infrastructure(db)
    flags = FlagStore()
    flags.rebuild(reopened.event_store.read_all())
    assert flags.state("policy_engine") is FlagState.DISABLED  # rollback replayed
    assert flags.state("intent_resolution") is FlagState.CANARY


def test_deterministic_replay_of_flag_state(tmp_path) -> None:
    db = str(tmp_path / "mig.db")
    ctx = build_integration(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    ctx.flags.set("policy_engine", FlagState.ENABLED)

    reopened = build_durable_infrastructure(db)
    a, b = FlagStore(), FlagStore()
    a.rebuild(reopened.event_store.read_all())
    b.rebuild(reopened.event_store.read_all())
    assert a.snapshot() == b.snapshot()


def test_correlation_preserved_end_to_end(tmp_path) -> None:
    db = str(tmp_path / "mig.db")
    ctx = build_integration(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    _adjudicate(ctx, 7)

    reopened = build_durable_infrastructure(db)
    decision_stream = [
        e for e in reopened.event_store.read_all() if e.correlation_identifier == "cor-7"
    ]
    assert len(decision_stream) == 3  # record + shadow + diff, all correlated (INV-39)
    assert all(e.correlation_identifier == "cor-7" for e in decision_stream)
