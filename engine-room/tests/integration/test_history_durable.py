"""Durable Execution History (ADR-007 through P1) — the P8 acceptance gate.

Proves durable persistence, replay reconstruction of the historical view from the log (no
re-projection), restart determinism, and the two grounding integrations: Repository Intelligence
consumes history through its seam (it reconstructs nothing), and Engineering Intelligence consumes
historical facts (it never queries the log). Rides P1 unchanged.
"""

from __future__ import annotations

from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain.goal import Goal, Scope
from nexus_engineering import build_engineering
from nexus_estimation import build_estimation
from nexus_history import (
    EXECUTION_HISTORY_PROJECTED,
    ExecutionHistoryProfile,
    HistoryQuery,
    build_history,
)
from nexus_infra import build_durable_infrastructure
from nexus_policy import build_policy
from nexus_repository import build_repository
from tests.unit.nexus_history.fixtures import seed_episode

_NOW = "2026-01-01T00:00:00Z"


def _seeded(db: str):
    infra = build_durable_infrastructure(db)
    seed_episode(infra, "op-1")
    return infra


def test_history_event_is_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "h.db")
    infra = _seeded(db)
    build_history(infra, now=lambda: _NOW).engine.profile(
        HistoryQuery(correlation_identifier="op-1")
    )

    reopened = build_durable_infrastructure(db)
    events = [e for e in reopened.event_store.read_all() if e.type == EXECUTION_HISTORY_PROJECTED]
    assert len(events) == 1 and events[0].correlation_identifier == "op-1"


def test_replay_reconstructs_view_without_reprojecting(tmp_path) -> None:
    db = str(tmp_path / "h.db")
    infra = _seeded(db)
    original = build_history(infra, now=lambda: _NOW).engine.profile(
        HistoryQuery(correlation_identifier="op-1")
    )
    reopened = build_durable_infrastructure(db)
    event = next(
        e for e in reopened.event_store.read_all() if e.type == EXECUTION_HISTORY_PROJECTED
    )
    reconstructed = ExecutionHistoryProfile.model_validate(event.payload["profile"])
    assert reconstructed == original  # reconstructed from the log, no re-projection


def test_restart_reconstruction_is_identical(tmp_path) -> None:
    db = str(tmp_path / "h.db")
    _seeded(db)
    before = build_history(build_durable_infrastructure(db), now=lambda: _NOW).engine.profile(
        persist=False
    )
    after = build_history(build_durable_infrastructure(db), now=lambda: _NOW).engine.profile(
        persist=False
    )
    assert before.identity == after.identity


def test_repository_intelligence_consumes_history_through_its_seam(tmp_path) -> None:
    db = str(tmp_path / "h.db")
    infra = _seeded(db)
    hist = build_history(infra, now=lambda: _NOW).engine.profile(persist=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text('[project]\nname="s"\n', encoding="utf-8")
    ri = build_repository(infra, now=lambda: _NOW)
    grounded = ri.engine.profile(
        str(repo_root), repository_history=hist.repository_seam(), persist=False
    )
    assert grounded.execution_history.available
    assert grounded.execution_history.prior_executions == hist.execution_count == 1
    # the seam is kept out of identity — same tree yields the same identity regardless of history.
    ungrounded = ri.engine.profile(str(repo_root), persist=False)
    assert grounded.identity == ungrounded.identity


def test_engineering_intelligence_consumes_historical_facts(tmp_path) -> None:
    db = str(tmp_path / "h.db")
    infra = _seeded(db)
    hist = build_history(infra, now=lambda: _NOW).engine.profile(persist=False)

    eng = build_engineering(infra, now=lambda: _NOW)
    est = build_estimation(infra, now=lambda: _NOW)
    pol = build_policy(infra, now=lambda: _NOW)
    goal = Goal(
        identity="g",
        outcome="ship the release",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.MEDIUM,
        constraints=(),
        scope=Scope(),
    )
    grounded = eng.strategize_for_goal(
        goal,
        estimation_engine=est.engine,
        policy_engine=pol.engine,
        execution_history_profile=hist,
        persist=False,
    )
    ungrounded = eng.strategize_for_goal(
        goal, estimation_engine=est.engine, policy_engine=pol.engine, persist=False
    )
    # EI consumed historical facts as grounding — the decision reflects it deterministically.
    assert grounded.identity != ungrounded.identity
