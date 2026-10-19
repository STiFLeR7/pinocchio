"""Durable repository parity tests (:class:`nexus_infra.durable.DurableRepository`).

Mirrors ``test_repositories.py`` against the SQLite-backed adapters. Per ADR-007 a
durable read reconstructs a value-equal object (state is a projection), so
assertions use ``==`` where the in-memory suite used identity (``is``). Version
bumps, insertion order, optimistic concurrency, and remove behave identically.
"""

from __future__ import annotations

import pytest

from nexus_infra import (
    ConcurrencyConflictError,
    DurableArtifactRepository,
    DurableGoalRepository,
    DurableKnowledgeRepository,
    DurablePlanRepository,
    DurablePolicyRepository,
    connect,
)
from tests.unit.nexus_infra.factories import (
    make_artifact,
    make_goal,
    make_knowledge,
    make_plan,
    make_policy,
)


@pytest.fixture
def repo(tmp_path) -> DurableGoalRepository:
    return DurableGoalRepository(connect(str(tmp_path / "repo.db")))


# -- core CRUD --------------------------------------------------------------- #


def test_add_then_get_returns_equal_object(repo: DurableGoalRepository) -> None:
    goal = make_goal("goal-1")
    repo.add(goal)
    assert repo.get("goal-1") == goal


def test_get_unknown_identity_returns_none(repo: DurableGoalRepository) -> None:
    assert repo.get("missing") is None


def test_list_all_returns_objects_in_insertion_order(repo: DurableGoalRepository) -> None:
    g1, g2, g3 = make_goal("goal-1"), make_goal("goal-2"), make_goal("goal-3")
    repo.add(g1)
    repo.add(g2)
    repo.add(g3)
    assert repo.list_all() == (g1, g2, g3)


def test_count_and_contains(repo: DurableGoalRepository) -> None:
    assert repo.count == 0
    repo.add(make_goal("goal-1"))
    repo.add(make_goal("goal-2"))
    assert repo.count == 2
    assert repo.contains("goal-1") is True
    assert repo.contains("goal-3") is False


def test_remove_deletes_and_resets_version(repo: DurableGoalRepository) -> None:
    repo.add(make_goal("goal-1"))
    assert repo.version_of("goal-1") == 1
    repo.remove("goal-1")
    assert repo.get("goal-1") is None
    assert repo.count == 0
    assert repo.version_of("goal-1") == 0


def test_remove_unknown_identity_is_a_no_op(repo: DurableGoalRepository) -> None:
    repo.add(make_goal("goal-1"))
    repo.remove("does-not-exist")
    assert repo.count == 1


# -- replace-by-identity keeps position, bumps version ----------------------- #


def test_replace_keeps_position_and_bumps_version(repo: DurableGoalRepository) -> None:
    repo.add(make_goal("g1", outcome="original"))
    repo.add(make_goal("g2"))
    assert repo.version_of("g1") == 1

    replacement = make_goal("g1", outcome="new outcome")
    repo.add(replacement)

    current = repo.get("g1")
    assert current == replacement
    assert current is not None
    assert current.outcome == "new outcome"
    assert repo.count == 2
    assert repo.version_of("g1") == 2
    # Insertion position preserved on replace (g1 still first).
    assert tuple(g.identity for g in repo.list_all()) == ("g1", "g2")


# -- optimistic concurrency -------------------------------------------------- #


def test_version_of_is_zero_for_unknown(repo: DurableGoalRepository) -> None:
    assert repo.version_of("x") == 0


def test_add_expecting_chain_and_conflict(repo: DurableGoalRepository) -> None:
    obj = make_goal("x", outcome="v1")
    repo.add_expecting(obj, 0)
    assert repo.version_of("x") == 1
    repo.add_expecting(make_goal("x", outcome="v2"), 1)
    assert repo.version_of("x") == 2

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        repo.add_expecting(obj, 0)
    err = excinfo.value
    assert (err.expected, err.actual) == (0, 2)
    # Failed write did not advance version or replace state.
    assert repo.version_of("x") == 2
    assert repo.get("x").outcome == "v2"


# -- every concrete repository round-trips ----------------------------------- #


def test_all_concrete_repositories_round_trip(tmp_path) -> None:
    conn = connect(str(tmp_path / "all.db"))
    assert DurableGoalRepository(conn).name == "goal"
    assert DurablePlanRepository(conn).name == "plan"
    assert DurableArtifactRepository(conn).name == "artifact"
    assert DurablePolicyRepository(conn).name == "policy"
    assert DurableKnowledgeRepository(conn).name == "knowledge"

    plan_repo = DurablePlanRepository(conn)
    plan = make_plan("plan-1")
    plan_repo.add(plan)
    assert plan_repo.get("plan-1") == plan

    art_repo = DurableArtifactRepository(conn)
    art_repo.add(make_artifact("artifact-1"))
    assert art_repo.get("artifact-1") == make_artifact("artifact-1")

    pol_repo = DurablePolicyRepository(conn)
    pol_repo.add(make_policy("policy-1"))
    assert pol_repo.version_of("policy-1") == 1

    know_repo = DurableKnowledgeRepository(conn)
    know_repo.add(make_knowledge("knowledge-1"))
    assert know_repo.get("knowledge-1") == make_knowledge("knowledge-1")
