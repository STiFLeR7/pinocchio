"""Unit tests for the repository adapters (:mod:`nexus_infra.repositories`).

Covers the storage-seam contract: identity-keyed add/get/list/remove, ``count``
and ``contains``, immutable replace-by-identity with version bumps, optimistic
concurrency via ``add_expecting``/``version_of``, and the logical ``name`` of each
concrete repository. Plain pytest functions, no I/O.
"""

from __future__ import annotations

import pytest

from nexus_infra import (
    ArtifactRepository,
    ConcurrencyConflictError,
    GoalRepository,
    KnowledgeRepository,
    PlanRepository,
    PolicyRepository,
)
from tests.unit.nexus_infra.factories import (
    make_artifact,
    make_goal,
    make_knowledge,
    make_plan,
    make_policy,
)

# --------------------------------------------------------------------------- #
# GoalRepository — core CRUD contract
# --------------------------------------------------------------------------- #


def test_add_then_get_returns_the_object() -> None:
    repo = GoalRepository()
    goal = make_goal("goal-1")

    repo.add(goal)

    assert repo.get("goal-1") is goal


def test_get_unknown_identity_returns_none() -> None:
    repo = GoalRepository()

    assert repo.get("missing") is None


def test_list_all_returns_objects_in_insertion_order() -> None:
    repo = GoalRepository()
    g1 = make_goal("goal-1")
    g2 = make_goal("goal-2")
    g3 = make_goal("goal-3")

    repo.add(g1)
    repo.add(g2)
    repo.add(g3)

    assert repo.list_all() == (g1, g2, g3)


def test_count_reflects_number_of_distinct_identities() -> None:
    repo = GoalRepository()
    assert repo.count == 0

    repo.add(make_goal("goal-1"))
    repo.add(make_goal("goal-2"))

    assert repo.count == 2


def test_contains_is_true_only_for_stored_identities() -> None:
    repo = GoalRepository()
    repo.add(make_goal("goal-1"))

    assert repo.contains("goal-1") is True
    assert repo.contains("goal-2") is False


def test_remove_deletes_the_object() -> None:
    repo = GoalRepository()
    repo.add(make_goal("goal-1"))

    repo.remove("goal-1")

    assert repo.get("goal-1") is None
    assert repo.contains("goal-1") is False
    assert repo.count == 0


def test_remove_unknown_identity_is_a_no_op() -> None:
    repo = GoalRepository()
    repo.add(make_goal("goal-1"))

    repo.remove("does-not-exist")

    assert repo.count == 1
    assert repo.contains("goal-1") is True


def test_remove_resets_version_for_that_identity() -> None:
    repo = GoalRepository()
    repo.add(make_goal("goal-1"))
    assert repo.version_of("goal-1") == 1

    repo.remove("goal-1")

    assert repo.version_of("goal-1") == 0


# --------------------------------------------------------------------------- #
# immutable replace-by-identity
# --------------------------------------------------------------------------- #


def test_add_with_same_identity_replaces_in_place_and_bumps_version() -> None:
    repo = GoalRepository()
    original = make_goal("g1", outcome="original outcome")
    repo.add(original)
    assert repo.version_of("g1") == 1

    replacement = original.model_copy(update={"outcome": "new outcome"})
    repo.add(replacement)

    current = repo.get("g1")
    assert current is replacement
    assert current is not None
    assert current.outcome == "new outcome"
    assert repo.count == 1
    assert repo.version_of("g1") == 2


# --------------------------------------------------------------------------- #
# optimistic concurrency
# --------------------------------------------------------------------------- #


def test_version_of_is_zero_for_unknown_identity() -> None:
    repo = GoalRepository()

    assert repo.version_of("x") == 0


def test_add_expecting_succeeds_on_matching_version_chain() -> None:
    repo = GoalRepository()
    obj = make_goal("x", outcome="v1")

    assert repo.version_of("x") == 0

    repo.add_expecting(obj, 0)
    assert repo.version_of("x") == 1

    updated = obj.model_copy(update={"outcome": "v2"})
    repo.add_expecting(updated, 1)
    assert repo.version_of("x") == 2
    assert repo.get("x") is updated


def test_add_expecting_with_stale_version_raises_concurrency_conflict() -> None:
    repo = GoalRepository()
    obj = make_goal("x")
    repo.add_expecting(obj, 0)

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        repo.add_expecting(obj, 0)

    error = excinfo.value
    assert error.expected == 0
    assert error.actual == 1
    # The failed write must not have advanced the version or replaced state.
    assert repo.version_of("x") == 1


# --------------------------------------------------------------------------- #
# concrete repository identities + smoke tests
# --------------------------------------------------------------------------- #


def test_each_repository_reports_its_logical_name() -> None:
    assert GoalRepository().name == "goal"
    assert PlanRepository().name == "plan"
    assert ArtifactRepository().name == "artifact"
    assert PolicyRepository().name == "policy"
    assert KnowledgeRepository().name == "knowledge"


def test_plan_repository_round_trips() -> None:
    repo = PlanRepository()
    plan = make_plan("plan-1")

    repo.add(plan)

    assert repo.get("plan-1") is plan
    assert repo.contains("plan-1") is True
    assert repo.list_all() == (plan,)


def test_artifact_repository_round_trips() -> None:
    repo = ArtifactRepository()
    artifact = make_artifact("artifact-1")

    repo.add(artifact)

    assert repo.get("artifact-1") is artifact
    assert repo.count == 1


def test_policy_repository_round_trips() -> None:
    repo = PolicyRepository()
    policy = make_policy("policy-1")

    repo.add(policy)

    assert repo.get("policy-1") is policy
    assert repo.version_of("policy-1") == 1


def test_knowledge_repository_round_trips() -> None:
    repo = KnowledgeRepository()
    knowledge = make_knowledge("knowledge-1")

    repo.add(knowledge)

    assert repo.get("knowledge-1") is knowledge
    repo.remove("knowledge-1")
    assert repo.get("knowledge-1") is None
