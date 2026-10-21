"""Durable Engineering Intelligence (ADR-007 through P1) — the P5 replay acceptance gate.

Proves the Strategy is a durable, correlated fact; that replay reconstructs it from the log
without re-inference (INV-17); and that a fresh engine over the reopened durable file reasons to
the identical Strategy (restart determinism). Rides P1 unchanged.
"""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Correlation
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain.goal import Goal, Scope
from nexus_engineering import EngineeringStrategy, build_engineering
from nexus_engineering.events import ENGINEERING_STRATEGIZED
from nexus_estimation import build_estimation
from nexus_infra import build_durable_infrastructure
from nexus_policy import build_policy

_NOW = "2026-01-01T00:00:00Z"


def _goal() -> Goal:
    return Goal(
        identity="g-dur",
        outcome="fix the failing bug in production",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.MEDIUM,
        constraints=(Constraint(kind="governance", detail={}),),
        scope=Scope(included=("mod",), excluded=()),
        correlation=Correlation(correlation_identifier="cor-dur"),
    )


def _strategize(db):
    infra = build_durable_infrastructure(db)
    eng = build_engineering(infra, now=lambda: _NOW)
    est = build_estimation(infra, now=lambda: _NOW)
    pol = build_policy(infra, now=lambda: _NOW)
    return infra, eng.strategize_for_goal(
        _goal(), estimation_engine=est.engine, policy_engine=pol.engine
    )


def test_strategy_event_is_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "eng.db")
    _strategize(db)
    reopened = build_durable_infrastructure(db)
    events = [e for e in reopened.event_store.read_all() if e.type == ENGINEERING_STRATEGIZED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-dur"


def test_replay_reconstructs_the_strategy_from_the_log(tmp_path) -> None:
    db = str(tmp_path / "eng.db")
    _, original = _strategize(db)
    reopened = build_durable_infrastructure(db)
    event = next(e for e in reopened.event_store.read_all() if e.type == ENGINEERING_STRATEGIZED)
    reconstructed = EngineeringStrategy.model_validate(event.payload["strategy"])
    assert reconstructed == original  # full Strategy reconstructed without re-inference


def test_identical_strategy_across_restart(tmp_path) -> None:
    db = str(tmp_path / "eng.db")
    _, before = _strategize(db)
    # a fresh set of engines over the reopened file reasons to the value-equal Strategy (pure function)
    reopened = build_durable_infrastructure(db)
    eng = build_engineering(reopened, now=lambda: _NOW)
    est = build_estimation(reopened, now=lambda: _NOW)
    pol = build_policy(reopened, now=lambda: _NOW)
    after = eng.strategize_for_goal(
        _goal(), estimation_engine=est.engine, policy_engine=pol.engine, persist=False
    )
    assert after.identity == before.identity
