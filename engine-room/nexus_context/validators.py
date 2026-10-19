"""Context Engineering validation — fail-fast on malformed input, surface conflicts.

Two distinct responsibilities, deliberately kept apart:

- **Fail-fast guards** (:func:`validate_goal`, :func:`validate_request`,
  :func:`validate_outputs`) reject *malformed* input or output by raising a
  :class:`ContextError`; the service turns that into a
  ``context_engineering.failed`` event. Nothing is auto-corrected.
- **Conflict surfacing** (:func:`compute_validation_status`) never raises. Missing,
  duplicate, contradictory, or stale context is *reported* in the package's
  ``validation_status`` so Planning can see it — it is identified, never silently
  resolved (doc 03 *Context Validation*).
"""

from __future__ import annotations

from collections import Counter

from nexus_context.categories import ConflictKind, ContextCategory, FreshnessState
from nexus_context.requests import Conflict, ContextItem, ContextRequest
from nexus_core.contracts.base import Struct
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.goal import Goal

# A Goal in a terminal lifecycle state cannot have context (re)assembled for it.
_TERMINAL_GOAL_STATES = frozenset({GoalStatus.ACHIEVED, GoalStatus.ABANDONED})


class ContextError(Exception):
    """Base for every context-engineering failure."""


class GoalNotContextualizableError(ContextError):
    """The Goal cannot have context assembled (terminal state or malformed)."""


class InvalidContextError(ContextError):
    """The supplied context input is malformed (empty key or duplicate fragment)."""


class ContextValidationError(ContextError):
    """A produced Context Package is internally inconsistent (dangling reference)."""


def validate_goal(goal: Goal) -> None:
    """The Goal must be present, have an outcome, and not be in a terminal state."""
    if not goal.outcome.strip():
        raise GoalNotContextualizableError(f"goal {goal.identity!r} has no outcome")
    if goal.status is not None and goal.status in _TERMINAL_GOAL_STATES:
        raise GoalNotContextualizableError(
            f"goal {goal.identity!r} is in terminal state {goal.status.value!r}"
        )


def validate_request(request: ContextRequest) -> None:
    """Fragments must have non-empty keys and be unique within a ``(source, category)``."""
    if not request.package_version.strip():
        raise InvalidContextError("context request has an empty package version")
    seen: set[tuple[str, str, str]] = set()
    for fragment in request.fragments:
        if not fragment.key.strip():
            raise InvalidContextError("a context fragment has an empty key")
        signature = (fragment.source.value, fragment.category.value, fragment.key)
        if signature in seen:
            raise InvalidContextError(
                f"duplicate fragment {fragment.key!r} from source {fragment.source.value!r}"
                f" in category {fragment.category.value!r}"
            )
        seen.add(signature)
    for dependency in request.declared_dependencies:
        if not dependency.strip():
            raise InvalidContextError("a declared dependency is empty")
    policy = request.freshness_policy
    if policy.default_max_age_seconds is not None and policy.default_max_age_seconds < 0:
        raise InvalidContextError("freshness default_max_age_seconds must be non-negative")


def compute_validation_status(
    items: tuple[ContextItem, ...], conflicts: tuple[Conflict, ...]
) -> Struct:
    """Summarize completeness, consistency, and freshness — surfacing, never raising."""
    by_kind: Counter[str] = Counter(conflict.kind.value for conflict in conflicts)
    categories_present = sorted({item.category.value for item in items})
    has_goal_context = ContextCategory.GOAL.value in categories_present
    has_missing_dependency = by_kind.get(ConflictKind.MISSING_DEPENDENCY.value, 0) > 0
    has_contradiction = by_kind.get(ConflictKind.CONTRADICTION.value, 0) > 0
    has_expired = any(item.freshness is FreshnessState.EXPIRED for item in items)
    complete = has_goal_context and not has_missing_dependency
    consistent = not has_contradiction
    fresh = not has_expired
    return {
        "item_count": len(items),
        "category_count": len(categories_present),
        "categories_present": categories_present,
        "conflict_count": len(conflicts),
        "conflicts_by_kind": dict(sorted(by_kind.items())),
        "complete": complete,
        "consistent": consistent,
        "fresh": fresh,
        "fit_for_planning": complete and consistent and fresh,
    }


def validate_outputs(package: ContextPackage, goal: Goal) -> None:
    """Cross-check that the produced Context Package agrees with its Goal."""
    if not package.identity.strip():
        raise ContextValidationError("context package has an empty identity")
    if package.goal_ref.target_type != "goal":
        raise ContextValidationError(
            f"context package goal_ref targets {package.goal_ref.target_type!r}, not 'goal'"
        )
    if package.goal_ref.identifier != goal.identity:
        raise ContextValidationError(
            "context package goal_ref does not match the goal it was built from"
        )
