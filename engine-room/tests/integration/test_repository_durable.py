"""Durable Repository Intelligence (ADR-007 through P1) — the P7 acceptance gate.

Proves durable persistence, replay reconstruction of the profile from the log (no rescan), restart
determinism, and that Engineering Intelligence consumes the RepositoryProfile as grounding. Rides P1
unchanged.
"""

from __future__ import annotations

from pathlib import Path

from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain.goal import Goal, Scope
from nexus_engineering import build_engineering
from nexus_estimation import build_estimation
from nexus_infra import build_durable_infrastructure
from nexus_policy import build_policy
from nexus_repository import RepositoryProfile, build_repository
from nexus_repository.events import REPOSITORY_PROFILED

_NOW = "2026-01-01T00:00:00Z"

_PYPROJECT = '[project]\nname = "s"\ndependencies = ["pydantic"]\n[tool.ruff]\nline-length = 88\n'


def _repo(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    return str(root)


def test_profile_event_is_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "r.db")
    root = _repo(tmp_path / "repo")
    ri = build_repository(build_durable_infrastructure(db), now=lambda: _NOW)
    ri.engine.profile(root, correlation_identifier="cor-d")

    reopened = build_durable_infrastructure(db)
    events = [e for e in reopened.event_store.read_all() if e.type == REPOSITORY_PROFILED]
    assert len(events) == 1 and events[0].correlation_identifier == "cor-d"


def test_replay_reconstructs_profile_without_rescanning(tmp_path) -> None:
    db = str(tmp_path / "r.db")
    root = _repo(tmp_path / "repo")
    original = build_repository(build_durable_infrastructure(db), now=lambda: _NOW).engine.profile(
        root, correlation_identifier="cor-d"
    )
    reopened = build_durable_infrastructure(db)
    event = next(e for e in reopened.event_store.read_all() if e.type == REPOSITORY_PROFILED)
    reconstructed = RepositoryProfile.model_validate(event.payload["profile"])
    assert reconstructed == original  # reconstructed from the log, no rescan


def test_restart_reconstruction_is_identical(tmp_path) -> None:
    db = str(tmp_path / "r.db")
    root = _repo(tmp_path / "repo")
    before = build_repository(build_durable_infrastructure(db), now=lambda: _NOW).engine.profile(
        root, correlation_identifier="cor-d", persist=False
    )
    after = build_repository(build_durable_infrastructure(db), now=lambda: _NOW).engine.profile(
        root, correlation_identifier="cor-d", persist=False
    )
    assert before.identity == after.identity


def test_engineering_intelligence_consumes_the_profile(tmp_path) -> None:
    root = _repo(tmp_path / "repo")
    infra = build_durable_infrastructure(str(tmp_path / "r.db"))
    ri = build_repository(infra, now=lambda: _NOW)
    profile = ri.engine.profile(root, correlation_identifier="cor-d")

    eng = build_engineering(infra, now=lambda: _NOW)
    est = build_estimation(infra, now=lambda: _NOW)
    pol = build_policy(infra, now=lambda: _NOW)
    goal = Goal(
        identity="g",
        outcome="fix the auth bug",
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
        repository_profile=profile,
        persist=False,
    )
    ungrounded = eng.strategize_for_goal(
        goal, estimation_engine=est.engine, policy_engine=pol.engine, persist=False
    )
    # EI consumed the profile as grounding — the decision reflects it deterministically.
    assert grounded.identity != ungrounded.identity
