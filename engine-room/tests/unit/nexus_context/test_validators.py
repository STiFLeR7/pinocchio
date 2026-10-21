"""Unit tests for :mod:`nexus_context.validators`.

Two responsibilities are exercised separately. The fail-fast guards
(:func:`validate_goal`, :func:`validate_request`, :func:`validate_outputs`) reject
malformed input/output by raising a :class:`ContextError` subclass — every negative
case is pinned with ``pytest.raises``. The conflict-surfacing summary
(:func:`compute_validation_status`) never raises; it reports completeness,
consistency, and freshness, and these tests pin each flag and the
``fit_for_planning`` conjunction. Real objects are built through the shared helpers;
no mocks.
"""

from __future__ import annotations

import pytest

from nexus_context.builder import ContextPackageBuilder
from nexus_context.categories import (
    ConflictKind,
    ContextCategory,
    ContextSource,
    FreshnessState,
)
from nexus_context.composition import default_collectors
from nexus_context.conflict_detector import ConflictDetector
from nexus_context.freshness import FreshnessValidator
from nexus_context.normalizer import Normalizer
from nexus_context.requests import (
    Conflict,
    ContextItem,
    ContextRequest,
    FreshnessPolicy,
    RawContextFragment,
)
from nexus_context.validators import (
    ContextValidationError,
    GoalNotContextualizableError,
    InvalidContextError,
    compute_validation_status,
    validate_goal,
    validate_outputs,
    validate_request,
)
from nexus_core.contracts.base import Reference
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.goal import Goal
from tests.unit.nexus_context.helpers import fragment, make_goal, request

# --------------------------------------------------------------------------- #
# small builders                                                              #
# --------------------------------------------------------------------------- #


def _items(*fragments: RawContextFragment) -> tuple[ContextItem, ...]:
    """Normalize fragments into the canonical item set the validators consume."""
    return Normalizer().normalize(fragments)


def _collect(goal: Goal, req: ContextRequest) -> tuple[RawContextFragment, ...]:
    """Run the default collectors so the goal_context fragment is always present."""
    gathered: list[RawContextFragment] = []
    for collector in default_collectors():
        gathered.extend(collector.collect(goal, req))
    return tuple(gathered)


def _build_package(goal: Goal) -> ContextPackage:
    """Build a real Context Package for ``goal`` via the production pipeline."""
    req = request()
    items = Normalizer().normalize(_collect(goal, req))
    conflicts = ConflictDetector().detect(items, req)
    status = compute_validation_status(items, conflicts)
    return ContextPackageBuilder().build(
        goal,
        items,
        conflicts,
        req,
        status,
        correlation_identifier="cor-test",
    )


# --------------------------------------------------------------------------- #
# validate_goal                                                              #
# --------------------------------------------------------------------------- #


def test_validate_goal_passes_for_normal_goal() -> None:
    validate_goal(make_goal())  # does not raise


def test_validate_goal_passes_for_none_status() -> None:
    validate_goal(make_goal(status=None))  # does not raise


def test_validate_goal_passes_for_non_terminal_status() -> None:
    validate_goal(make_goal(status=GoalStatus.PLANNING))  # does not raise


def test_validate_goal_rejects_blank_outcome() -> None:
    with pytest.raises(GoalNotContextualizableError):
        validate_goal(make_goal(outcome=""))


def test_validate_goal_rejects_whitespace_outcome() -> None:
    with pytest.raises(GoalNotContextualizableError):
        validate_goal(make_goal(outcome="   \t  "))


def test_validate_goal_rejects_achieved_status() -> None:
    with pytest.raises(GoalNotContextualizableError):
        validate_goal(make_goal(status=GoalStatus.ACHIEVED))


def test_validate_goal_rejects_abandoned_status() -> None:
    with pytest.raises(GoalNotContextualizableError):
        validate_goal(make_goal(status=GoalStatus.ABANDONED))


# --------------------------------------------------------------------------- #
# validate_request                                                          #
# --------------------------------------------------------------------------- #


def test_validate_request_passes_for_valid() -> None:
    validate_request(request(fragment("alpha")))  # does not raise


def test_validate_request_rejects_empty_package_version() -> None:
    with pytest.raises(InvalidContextError):
        validate_request(request(package_version=""))


def test_validate_request_rejects_whitespace_package_version() -> None:
    with pytest.raises(InvalidContextError):
        validate_request(request(package_version="   "))


def test_validate_request_rejects_empty_fragment_key() -> None:
    with pytest.raises(InvalidContextError):
        validate_request(request(fragment("")))


def test_validate_request_rejects_whitespace_fragment_key() -> None:
    with pytest.raises(InvalidContextError):
        validate_request(request(fragment("   ")))


def test_validate_request_rejects_duplicate_fragment() -> None:
    # Two identical fragments share the same (source, category, key) signature.
    dup_a = fragment("shared", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE)
    dup_b = fragment("shared", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE)
    with pytest.raises(InvalidContextError):
        validate_request(request(dup_a, dup_b))


def test_validate_request_rejects_empty_declared_dependency() -> None:
    with pytest.raises(InvalidContextError):
        validate_request(request(declared_dependencies=("   ",)))


def test_validate_request_rejects_negative_freshness_default_max_age() -> None:
    policy = FreshnessPolicy(default_max_age_seconds=-1)
    with pytest.raises(InvalidContextError):
        validate_request(request(freshness_policy=policy))


def test_validate_request_allows_distinct_fragments_same_key_different_source() -> None:
    # Same key but a different source => distinct signature => not a duplicate.
    a = fragment("shared", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE)
    b = fragment("shared", source=ContextSource.RUNTIME, category=ContextCategory.WORKSPACE)
    validate_request(request(a, b))  # does not raise


# --------------------------------------------------------------------------- #
# compute_validation_status                                                 #
# --------------------------------------------------------------------------- #


def _goal_item() -> ContextItem:
    """A normalized goal_context item — its presence makes a status 'complete'."""
    return Normalizer().normalize(
        (fragment("objective", source=ContextSource.OPERATOR, category=ContextCategory.GOAL),)
    )[0]


def test_compute_validation_status_shape() -> None:
    status = compute_validation_status(_items(fragment("alpha")), ())
    for field in (
        "item_count",
        "category_count",
        "categories_present",
        "conflict_count",
        "conflicts_by_kind",
        "complete",
        "consistent",
        "fresh",
        "fit_for_planning",
    ):
        assert field in status


def test_compute_validation_status_fit_when_clean() -> None:
    status = compute_validation_status((_goal_item(),), ())
    assert status["complete"] is True
    assert status["consistent"] is True
    assert status["fresh"] is True
    assert status["fit_for_planning"] is True


def test_compute_validation_status_incomplete_without_goal_context() -> None:
    # An item present, but no goal_context category => not complete.
    status = compute_validation_status(_items(fragment("alpha")), ())
    assert status["complete"] is False
    assert status["fit_for_planning"] is False


def test_compute_validation_status_incomplete_on_missing_dependency() -> None:
    items = (_goal_item(),)
    conflicts = ConflictDetector().detect(items, request(declared_dependencies=("absent",)))
    status = compute_validation_status(items, conflicts)
    assert status["conflicts_by_kind"].get(ConflictKind.MISSING_DEPENDENCY.value) == 1
    assert status["complete"] is False
    assert status["fit_for_planning"] is False


def test_compute_validation_status_inconsistent_on_contradiction() -> None:
    goal_item = _goal_item()
    a = fragment("shared", source=ContextSource.WORKSPACE, payload={"v": 1})
    b = fragment("shared", source=ContextSource.RUNTIME, payload={"v": 2})
    items = (*Normalizer().normalize((a, b)), goal_item)
    conflicts = ConflictDetector().detect(items, request())
    status = compute_validation_status(items, conflicts)
    assert status["conflicts_by_kind"].get(ConflictKind.CONTRADICTION.value) == 1
    assert status["consistent"] is False
    assert status["fit_for_planning"] is False


def test_compute_validation_status_not_fresh_with_expired_item() -> None:
    # An EXPIRED freshness on any item makes the whole set not fresh.
    expired = _goal_item().model_copy(update={"freshness": FreshnessState.EXPIRED})
    status = compute_validation_status((expired,), ())
    assert status["fresh"] is False
    assert status["fit_for_planning"] is False


def test_compute_validation_status_expired_via_freshness_validator() -> None:
    # Construct a real EXPIRED verdict: age > 2x max_age under a tight policy.
    item = Normalizer().normalize(
        (
            fragment(
                "objective",
                source=ContextSource.OPERATOR,
                category=ContextCategory.GOAL,
                observed_at="1970-01-01T00:00:00+00:00",
            ),
        )
    )
    policy = FreshnessPolicy(
        evaluation_instant="1970-01-01T01:00:00+00:00",
        default_max_age_seconds=10,
    )
    evaluated = FreshnessValidator().evaluate(item, policy)
    assert evaluated[0].freshness is FreshnessState.EXPIRED
    status = compute_validation_status(evaluated, ())
    assert status["fresh"] is False


def test_compute_validation_status_fit_is_conjunction() -> None:
    # fit_for_planning is exactly complete AND consistent AND fresh.
    goal_item = _goal_item()
    a = fragment("shared", source=ContextSource.WORKSPACE, payload={"v": 1})
    b = fragment("shared", source=ContextSource.RUNTIME, payload={"v": 2})
    items = (*Normalizer().normalize((a, b)), goal_item)
    conflicts = ConflictDetector().detect(items, request())
    status = compute_validation_status(items, conflicts)
    expected = status["complete"] and status["consistent"] and status["fresh"]
    assert status["fit_for_planning"] == expected


def test_compute_validation_status_never_raises_on_empty() -> None:
    status = compute_validation_status((), ())
    assert status["item_count"] == 0
    assert status["complete"] is False


# --------------------------------------------------------------------------- #
# validate_outputs                                                          #
# --------------------------------------------------------------------------- #


def test_validate_outputs_passes_for_matching_goal() -> None:
    goal = make_goal("goal-A")
    package = _build_package(goal)
    validate_outputs(package, goal)  # does not raise


def test_validate_outputs_rejects_goal_identifier_mismatch() -> None:
    goal_a = make_goal("goal-A")
    goal_b = make_goal("goal-B")
    package = _build_package(goal_a)
    with pytest.raises(ContextValidationError):
        validate_outputs(package, goal_b)


def test_validate_outputs_rejects_wrong_target_type() -> None:
    goal = make_goal("goal-A")
    package = _build_package(goal)
    broken = package.model_copy(
        update={"goal_ref": Reference(target_type="plan", identifier=goal.identity)}
    )
    with pytest.raises(ContextValidationError):
        validate_outputs(broken, goal)


def test_validate_outputs_rejects_empty_identity() -> None:
    goal = make_goal("goal-A")
    package = _build_package(goal)
    # Bypass field validation to forge an empty identity, then assert the guard fires.
    broken = package.model_construct(**{**package.__dict__, "identity": ""})
    with pytest.raises(ContextValidationError):
        validate_outputs(broken, goal)


def test_conflict_kind_values_are_stable() -> None:
    # Guard against silent renames the status summary keys on.
    assert ConflictKind.MISSING_DEPENDENCY.value == "missing_dependency"
    assert ConflictKind.CONTRADICTION.value == "contradiction"
    assert isinstance(Conflict(kind=ConflictKind.STALE, category=None, key="k"), Conflict)
