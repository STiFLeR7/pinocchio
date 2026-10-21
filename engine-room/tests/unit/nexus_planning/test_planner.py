"""End-to-end tests for the Nexus Planning Service.

Covers the full planning cycle: the :class:`PlanningResult` shape, persistence
through the Phase 2 repositories, the deterministic event sequence emitted to the
log, correlation propagation, the failure path (``planning.failed``), and
byte-for-byte deterministic replay.

All builders come from :mod:`tests.unit.nexus_planning.helpers`, which wires a
fresh infrastructure + planning pair with a ``FixedTimestampSource`` so every
emitted event is reproducible.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.status import GoalStatus
from nexus_planning import PlanningError, PlanningRequest
from nexus_planning.requests import CapabilityRequirementSet
from tests.unit.nexus_planning.helpers import (
    item,
    make_capability,
    make_goal,
    planning_env,
)

# -- shared fixtures ------------------------------------------------------- #


def _two_item_request() -> PlanningRequest:
    """A minimal valid request: item ``b`` depends on item ``a``."""
    return PlanningRequest(work_items=(item("a"), item("b", depends_on=("a",))))


# -- PlanningResult shape -------------------------------------------------- #


def test_plan_returns_result_with_deterministic_identities() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    assert result.plan.identity == "plan-goal-1-v1"
    assert result.execution_graph.identity == "graph-goal-1-v1"
    assert result.execution_strategy.identity == "strategy-goal-1-v1"


def test_plan_parent_goal_references_the_goal() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    assert result.plan.parent_goal.identifier == goal.identity


def test_plan_work_packages_match_the_items() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    assert [wp.identifier for wp in result.work_packages] == [
        "wp-goal-1-a",
        "wp-goal-1-b",
    ]
    assert [ref.identifier for ref in result.plan.work_package_refs] == [
        "wp-goal-1-a",
        "wp-goal-1-b",
    ]


def test_plan_execution_graph_ref_matches_the_graph() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    assert result.plan.execution_graph_ref.identifier == result.execution_graph.identity


def test_plan_capabilities_is_a_requirement_set() -> None:
    cap = make_capability("analysis.core")
    env = planning_env(cap)
    goal = make_goal()
    request = PlanningRequest(
        work_items=(
            item("a", capability_requirements=("analysis.core",)),
            item("b", capability_requirements=("missing.cap",), depends_on=("a",)),
        )
    )

    result = env.planning.service.plan(goal, request)

    assert isinstance(result.capabilities, CapabilityRequirementSet)
    assert result.capabilities.required == ("analysis.core", "missing.cap")
    assert result.capabilities.missing == ("missing.cap",)


# -- persistence ----------------------------------------------------------- #


def test_plan_is_persisted_in_the_plans_repository() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    stored = env.planning.repositories.plans.get("plan-goal-1-v1")
    assert stored == result.plan


def test_work_packages_are_persisted() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    for work_package in result.work_packages:
        assert env.planning.repositories.work_packages.get(work_package.identifier) == work_package


def test_execution_graph_is_persisted() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    stored = env.planning.repositories.execution_graphs.get("graph-goal-1-v1")
    assert stored == result.execution_graph


def test_execution_strategy_is_persisted() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    stored = env.planning.repositories.execution_strategies.get("strategy-goal-1-v1")
    assert stored == result.execution_strategy


# -- event emission -------------------------------------------------------- #


def test_event_count_and_order() -> None:
    env = planning_env()
    goal = make_goal()
    request = PlanningRequest(
        work_items=(item("a"), item("b", depends_on=("a",)), item("c", depends_on=("b",)))
    )

    env.planning.service.plan(goal, request)

    events = env.infrastructure.event_store.read_all()
    assert [e.type for e in events] == [
        "work_package.created",
        "work_package.created",
        "work_package.created",
        "execution_graph.created",
        "plan.created",
        "planning.completed",
    ]
    assert len(events) == 3 + 3  # n_work_packages + 3


def test_every_event_has_planning_producer() -> None:
    env = planning_env()
    goal = make_goal()

    env.planning.service.plan(goal, _two_item_request())

    events = env.infrastructure.event_store.read_all()
    assert all(e.producer == "planning" for e in events)


def test_event_identifiers_are_deterministic() -> None:
    env = planning_env()
    goal = make_goal()

    env.planning.service.plan(goal, _two_item_request())

    events = env.infrastructure.event_store.read_all()
    assert [e.identifier for e in events] == [
        "evt-plan-goal-1-v1-wp-0000",
        "evt-plan-goal-1-v1-wp-0001",
        "evt-plan-goal-1-v1-graph-0002",
        "evt-plan-goal-1-v1-plan-0003",
        "evt-plan-goal-1-v1-completed-0004",
    ]


def test_work_package_created_events_carry_identifiers_in_order() -> None:
    env = planning_env()
    goal = make_goal()

    env.planning.service.plan(goal, _two_item_request())

    events = env.infrastructure.event_store.read_all()
    wp_events = [e for e in events if e.type == "work_package.created"]
    assert [e.payload["work_package"] for e in wp_events] == ["wp-goal-1-a", "wp-goal-1-b"]


def test_planning_completed_payload_reports_counts_and_capabilities() -> None:
    cap = make_capability("analysis.core")
    env = planning_env(cap)
    goal = make_goal()
    request = PlanningRequest(
        work_items=(
            item("a", capability_requirements=("analysis.core",)),
            item("b", capability_requirements=("missing.cap",), depends_on=("a",)),
        )
    )

    env.planning.service.plan(goal, request)

    events = env.infrastructure.event_store.read_all()
    completed = next(e for e in events if e.type == "planning.completed")
    assert completed.payload["work_package_count"] == 2
    assert completed.payload["capabilities_required"] == ["analysis.core", "missing.cap"]
    assert completed.payload["capabilities_missing"] == ["missing.cap"]


def test_plan_created_payload_lists_work_packages_and_coordination() -> None:
    env = planning_env()
    goal = make_goal()

    result = env.planning.service.plan(goal, _two_item_request())

    events = env.infrastructure.event_store.read_all()
    created = next(e for e in events if e.type == "plan.created")
    assert created.payload["plan"] == "plan-goal-1-v1"
    assert created.payload["goal"] == goal.identity
    assert created.payload["work_packages"] == ["wp-goal-1-a", "wp-goal-1-b"]
    assert created.payload["coordination"] == result.execution_strategy.coordination.value


# -- correlation ----------------------------------------------------------- #


def test_default_correlation_is_derived_from_goal() -> None:
    env = planning_env()
    goal = make_goal()

    env.planning.service.plan(goal, _two_item_request())

    events = env.infrastructure.event_store.read_all()
    assert {e.correlation_identifier for e in events} == {"cor-goal-1"}


def test_request_correlation_overrides_default() -> None:
    env = planning_env()
    goal = make_goal()
    request = PlanningRequest(
        work_items=(item("a"), item("b", depends_on=("a",))),
        correlation_identifier="custom-cor",
    )

    env.planning.service.plan(goal, request)

    events = env.infrastructure.event_store.read_all()
    assert {e.correlation_identifier for e in events} == {"custom-cor"}


# -- planning failed ------------------------------------------------------- #


def test_empty_request_raises_and_emits_only_planning_failed() -> None:
    env = planning_env()
    goal = make_goal()

    with pytest.raises(PlanningError):
        env.planning.service.plan(goal, PlanningRequest(work_items=()))

    events = env.infrastructure.event_store.read_all()
    assert [e.type for e in events] == ["planning.failed"]
    failed = events[0]
    assert failed.producer == "planning"
    assert failed.payload["goal"] == goal.identity
    assert "error" in failed.payload
    assert failed.payload["reason"] == "InvalidDecompositionError"


def test_no_success_events_on_failure() -> None:
    env = planning_env()
    goal = make_goal()

    with pytest.raises(PlanningError):
        env.planning.service.plan(goal, PlanningRequest(work_items=()))

    events = env.infrastructure.event_store.read_all()
    emitted_types = {e.type for e in events}
    assert "plan.created" not in emitted_types
    assert "planning.completed" not in emitted_types


def test_nothing_is_persisted_on_failure() -> None:
    env = planning_env()
    goal = make_goal()

    with pytest.raises(PlanningError):
        env.planning.service.plan(goal, PlanningRequest(work_items=()))

    assert env.planning.repositories.plans.get("plan-goal-1-v1") is None


def test_terminal_goal_raises_and_emits_planning_failed() -> None:
    env = planning_env()
    goal = make_goal(status=GoalStatus.ACHIEVED)

    with pytest.raises(PlanningError):
        env.planning.service.plan(goal, PlanningRequest(work_items=(item("a"),)))

    events = env.infrastructure.event_store.read_all()
    assert [e.type for e in events] == ["planning.failed"]
    assert events[0].payload["goal"] == goal.identity
    assert events[0].payload["reason"] == "GoalNotPlannableError"


# -- deterministic replay -------------------------------------------------- #


def test_replay_yields_identical_events_and_plan() -> None:
    def run() -> tuple[tuple[object, ...], object]:
        env = planning_env(make_capability("analysis.core"))
        goal = make_goal()
        request = PlanningRequest(
            work_items=(
                item("a", capability_requirements=("analysis.core",)),
                item("b", depends_on=("a",)),
            )
        )
        result = env.planning.service.plan(goal, request)
        return tuple(env.infrastructure.event_store.read_all()), result.plan

    events_one, plan_one = run()
    events_two, plan_two = run()

    assert events_one == events_two
    assert plan_one == plan_two
