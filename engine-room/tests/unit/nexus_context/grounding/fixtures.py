"""Shared fixtures for the P9 grounding suite — genuine upstream artifacts, deterministically.

Builds real RepositoryProfile (P7), ExecutionHistoryProfile (P8), EngineeringStrategy (P5),
and Knowledge via the actual subsystem engines, so the grounding tests exercise true integration
rather than hand-mocked shapes. The sample repository (from the P7 fixtures) carries an ADR,
a contract (``thing``), an invariant file, and ``pkg_a`` / ``pkg_b`` modules/packages — the goal
keywords select some and (explainably) omit others.
"""

from __future__ import annotations

from nexus_context import FixedTimestampSource
from nexus_context.grounding import (
    GroundingInputs,
    build_grounded_context_engineering,
)
from nexus_core.contracts.base import Constraint, Correlation
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain.goal import Goal, Scope
from nexus_history import HistoryQuery, build_history
from nexus_infra import build_infrastructure
from nexus_repository import build_repository
from tests.unit.nexus_engineering.fixtures import make_knowledge, strategy_for
from tests.unit.nexus_history.fixtures import seed_episode
from tests.unit.nexus_repository.fixtures import make_repo

_NOW = "2026-01-01T00:00:00Z"
_FIXED = "1970-01-01T00:00:00+00:00"

_OUTCOME = "refactor the pkg_a module and update the thing contract for persistence"


def make_goal(
    identity: str = "g-ground", outcome: str = _OUTCOME, correlation: str = "cor-ground"
) -> Goal:
    return Goal(
        identity=identity,
        outcome=outcome,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(Constraint(kind="governance", detail={"note": "scoped"}),),
        scope=Scope(included=("pkg_a",), excluded=()),
        correlation=Correlation(correlation_identifier=correlation),
    )


def make_repo_profile(tmp_path):
    infra = build_infrastructure()
    root = make_repo(tmp_path)
    return build_repository(infra, now=lambda: _NOW).engine.profile(root, persist=False)


def make_history_profile():
    infra = build_infrastructure()
    seed_episode(infra, "pkg-a-fix")  # keyword-related prior execution (selected)
    seed_episode(infra, "billing-run")  # unrelated prior execution (omitted, explained)
    return build_history(infra, now=lambda: _NOW).engine.profile(HistoryQuery(), persist=False)


def make_strategy(goal: Goal | None = None):
    return strategy_for(goal or make_goal(), persist=False)


def make_inputs(
    tmp_path,
    *,
    repo: bool = True,
    history: bool = True,
    strategy: bool = True,
    knowledge: bool = True,
    goal: Goal | None = None,
) -> GroundingInputs:
    goal = goal or make_goal()
    return GroundingInputs(
        goal=goal,
        repository_profile=make_repo_profile(tmp_path) if repo else None,
        history_profile=make_history_profile() if history else None,
        engineering_strategy=make_strategy(goal) if strategy else None,
        knowledge=(make_knowledge("k1"), make_knowledge("k2")) if knowledge else (),
    )


def wired_grounded(timestamp: str = _FIXED):
    """A fresh infra plus a grounded Context Engineering context with a fixed clock."""
    infra = build_infrastructure()
    ctx = build_grounded_context_engineering(infra, timestamps=FixedTimestampSource(timestamp))
    return infra, ctx
