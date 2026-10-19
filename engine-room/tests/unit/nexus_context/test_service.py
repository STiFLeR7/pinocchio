"""Unit tests for :class:`nexus_context.service.ContextEngineeringService`.

These drive the full pipeline through a deterministic, fully-wired environment
(:func:`context_env`, backed by a :class:`FixedTimestampSource`). They pin the happy
path (a persisted package and an immutable :class:`ContextResult`), the exact ordered
five-event success emission with its deterministic identifiers, the default-collector
guarantee that ``goal_context`` is always present, the failure path
(``context_engineering.failed`` with no success events) for both a terminal Goal and a
malformed request, correlation-identifier selection, and custom-collector flow-through.
Real objects via the shared helpers; no mocks.
"""

from __future__ import annotations

import pytest

from nexus_context import ids
from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.collectors import StaticContextCollector
from nexus_context.events import (
    CONTEXT_COLLECTED,
    CONTEXT_COLLECTION_STARTED,
    CONTEXT_ENGINEERING_COMPLETED,
    CONTEXT_ENGINEERING_FAILED,
    CONTEXT_PACKAGE_CREATED,
    CONTEXT_VALIDATED,
)
from nexus_context.requests import ContextResult
from nexus_context.validators import GoalNotContextualizableError, InvalidContextError
from nexus_core.contracts.base import Correlation
from nexus_core.contracts.status import GoalStatus
from tests.unit.nexus_context.helpers import context_env, fragment, make_goal, request

_SUCCESS_ORDER = [
    CONTEXT_COLLECTION_STARTED,
    CONTEXT_COLLECTED,
    CONTEXT_VALIDATED,
    CONTEXT_PACKAGE_CREATED,
    CONTEXT_ENGINEERING_COMPLETED,
]


def _types(env: object) -> list[str]:
    """Emitted event types, in global append order."""
    return [e.type for e in env.infrastructure.event_store.read_all()]  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# happy path                                                                #
# --------------------------------------------------------------------------- #


def test_engineer_returns_context_result() -> None:
    env = context_env()
    result = env.context.service.engineer(make_goal(), request())
    assert isinstance(result, ContextResult)
    assert result.package is not None


def test_engineer_persists_package() -> None:
    env = context_env()
    result = env.context.service.engineer(make_goal(), request())
    stored = env.context.repositories.context_packages.get(result.package.identity)
    assert stored is not None
    assert stored.identity == result.package.identity


def test_result_is_immutable() -> None:
    from pydantic import ValidationError

    env = context_env()
    result = env.context.service.engineer(make_goal(), request())
    with pytest.raises(ValidationError):
        result.items = ()  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# event emission                                                            #
# --------------------------------------------------------------------------- #


def test_engineer_emits_exactly_five_events_in_order() -> None:
    env = context_env()
    env.context.service.engineer(make_goal(), request())
    assert _types(env) == _SUCCESS_ORDER
    assert env.infrastructure.event_store.global_length() == 5


def test_event_identifiers_are_deterministic() -> None:
    env = context_env()
    goal = make_goal()
    req = request()
    env.context.service.engineer(goal, req)

    context_identity = ids.context_id(goal.identity, req.package_version)
    identifiers = [e.identifier for e in env.infrastructure.event_store.read_all()]
    assert identifiers == [
        ids.event_id(context_identity, "started", 0),
        ids.event_id(context_identity, "collected", 1),
        ids.event_id(context_identity, "validated", 2),
        ids.event_id(context_identity, "package", 3),
        ids.event_id(context_identity, "completed", 4),
    ]
    # The literal format (evt-<context-id>-<kind>-0000) is part of the contract.
    assert identifiers[0] == f"evt-{context_identity}-started-0000"
    assert identifiers[4] == f"evt-{context_identity}-completed-0004"


def test_engineering_is_deterministic_across_runs() -> None:
    goal = make_goal()
    req = request(fragment("alpha"))

    first = context_env().context.service.engineer(goal, req)
    second = context_env().context.service.engineer(goal, req)

    assert first.package.identity == second.package.identity
    assert first.package == second.package


# --------------------------------------------------------------------------- #
# default collectors                                                        #
# --------------------------------------------------------------------------- #


def test_default_collectors_always_yield_goal_context() -> None:
    env = context_env()
    # An entirely empty request still produces goal_context via default collectors.
    result = env.context.service.engineer(make_goal(), request())
    assert result.package.context_categories.goal_context != {}
    categories = {item.category for item in result.items}
    assert ContextCategory.GOAL in categories


# --------------------------------------------------------------------------- #
# failure path                                                              #
# --------------------------------------------------------------------------- #


def test_terminal_goal_raises_and_emits_only_failed() -> None:
    env = context_env()
    goal = make_goal(status=GoalStatus.ACHIEVED)
    with pytest.raises(GoalNotContextualizableError):
        env.context.service.engineer(goal, request())

    assert _types(env) == [CONTEXT_ENGINEERING_FAILED]
    assert all(t not in _SUCCESS_ORDER for t in _types(env))


def test_terminal_goal_persists_no_package() -> None:
    env = context_env()
    goal = make_goal("goal-term", status=GoalStatus.ABANDONED)
    with pytest.raises(GoalNotContextualizableError):
        env.context.service.engineer(goal, request())
    assert env.context.repositories.context_packages.list_all() == ()


def test_malformed_request_raises_and_emits_only_failed() -> None:
    env = context_env()
    # Duplicate fragment => InvalidContextError before any success event.
    dup_a = fragment("shared", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE)
    dup_b = fragment("shared", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE)
    with pytest.raises(InvalidContextError):
        env.context.service.engineer(make_goal(), request(dup_a, dup_b))

    assert _types(env) == [CONTEXT_ENGINEERING_FAILED]


def test_failed_event_carries_reason() -> None:
    env = context_env()
    goal = make_goal(status=GoalStatus.ACHIEVED)
    with pytest.raises(GoalNotContextualizableError):
        env.context.service.engineer(goal, request())
    failed = next(iter(env.infrastructure.event_store.read_all()))
    assert failed.type == CONTEXT_ENGINEERING_FAILED
    assert failed.payload["reason"] == "GoalNotContextualizableError"
    assert failed.payload["goal"] == goal.identity


# --------------------------------------------------------------------------- #
# correlation                                                               #
# --------------------------------------------------------------------------- #


def test_request_correlation_is_used_when_set() -> None:
    env = context_env()
    req = request(correlation_identifier="cor-explicit")
    env.context.service.engineer(make_goal(), req)
    correlations = {e.correlation_identifier for e in env.infrastructure.event_store.read_all()}
    assert correlations == {"cor-explicit"}


def test_correlation_falls_back_to_derived_when_unset() -> None:
    env = context_env()
    goal = make_goal("goal-corr")
    # No request correlation and (helper) no goal correlation => derived from goal.
    env.context.service.engineer(goal, request())
    correlations = {e.correlation_identifier for e in env.infrastructure.event_store.read_all()}
    assert correlations == {ids.correlation_id(goal.identity)}


def test_failed_event_uses_correlation() -> None:
    env = context_env()
    goal = make_goal(status=GoalStatus.ACHIEVED)
    req = request(correlation_identifier="cor-explicit")
    with pytest.raises(GoalNotContextualizableError):
        env.context.service.engineer(goal, req)
    failed = next(iter(env.infrastructure.event_store.read_all()))
    assert failed.correlation_identifier == "cor-explicit"


# --------------------------------------------------------------------------- #
# custom collectors                                                         #
# --------------------------------------------------------------------------- #


def test_custom_collectors_flow_through_to_package() -> None:
    custom = fragment(
        "ws-key",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"detail": "from-static"},
    )
    env = context_env(collectors=(StaticContextCollector(custom),))
    result = env.context.service.engineer(make_goal(), request())

    keys = {item.key for item in result.items}
    assert keys == {"ws-key"}
    assert result.package.context_categories.workspace_context.get("ws-key") is not None
    # The static collector replaces the defaults entirely => no goal_context here.
    assert result.package.context_categories.goal_context == {}


def test_correlation_falls_back_to_goal_correlation() -> None:
    # No request correlation, but the Goal carries one: the Goal's lineage is used.
    goal = make_goal().model_copy(
        update={"correlation": Correlation(correlation_identifier="cor-from-goal")}
    )
    env = context_env()
    result = env.context.service.engineer(goal, request())

    assert result.package.correlation.correlation_identifier == "cor-from-goal"
    assert all(
        event.correlation_identifier == "cor-from-goal"
        for event in env.infrastructure.event_store.read_all()
    )
