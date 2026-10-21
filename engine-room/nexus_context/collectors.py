"""Step 1 — Context Collectors (provider interfaces, dependency-injected).

A :class:`ContextCollector` surfaces raw context fragments from one source class.
Phase 4 defines the **interface** and ships only deterministic, I/O-free reference
collectors — there is no Git, no filesystem scanning, no network, and no AI here.
Real collectors (repository, Drive, calendar, knowledge base, …) implement the same
Protocol in later phases and are injected; nothing about the pipeline changes.

Shipped reference collectors:

- :class:`GoalContextCollector` — derives ``goal_context`` / ``domain_context``
  fragments purely from the Goal, so a package is never empty even with no seed data.
- :class:`RequestFragmentCollector` — surfaces the operator-/environment-supplied
  fragments carried on the :class:`~nexus_context.requests.ContextRequest`.
- :class:`StaticContextCollector` — returns a fixed fragment set (the explicit DI
  seam used in tests and explicit wiring).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.requests import ContextRequest, RawContextFragment
from nexus_core.domain.goal import Goal


@runtime_checkable
class ContextCollector(Protocol):
    """Surfaces raw context fragments from one source class (no execution, no I/O contract)."""

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]: ...


class GoalContextCollector:
    """Derives goal/domain context fragments deterministically from the Goal itself."""

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        goal_payload: dict[str, object] = {"outcome": goal.outcome}
        if goal.success_definition is not None:
            goal_payload["success_definition"] = goal.success_definition
        if goal.rationale is not None:
            goal_payload["rationale"] = goal.rationale
        if goal.scope.included:
            goal_payload["included"] = list(goal.scope.included)
        if goal.scope.excluded:
            goal_payload["excluded"] = list(goal.scope.excluded)
        return (
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.GOAL,
                key="objective",
                payload=goal_payload,
            ),
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.DOMAIN,
                key="domain",
                payload={"domain": goal.domain.value, "priority": goal.priority.value},
            ),
        )


class RequestFragmentCollector:
    """Surfaces the explicit fragments carried on the request (operator/environment seed)."""

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        return request.fragments


class StaticContextCollector:
    """Reference collector returning a fixed fragment set (the explicit DI seam)."""

    def __init__(self, *fragments: RawContextFragment) -> None:
        self._fragments = fragments

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        return self._fragments
