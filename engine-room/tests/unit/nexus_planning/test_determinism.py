"""Determinism proofs for Nexus Planning — the core Phase 3 guarantee.

The headline invariant of Phase 3 is that planning is a *pure, reproducible*
function of its inputs: "identical Goals produce identical Plans given identical
inputs." There is no clock, counter, or randomness in identifier derivation, and
the only captured-as-data value (the event timestamp) is injected so it can be
pinned. These tests prove that guarantee end to end:

* the same Goal + Request planned in two independent environments yields equal
  domain objects *and* equal event streams;
* re-planning the same Goal + Request in the same environment is idempotent at
  the event-store level (deterministic event identifiers dedupe);
* different Goals never collide on plan or work-package identity;
* the deterministic identifier helpers produce their documented shapes;
* correlation derivation follows the documented precedence;
* ``plan_version`` flows into every derived identifier shape.
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation
from nexus_core.contracts.enums import (
    Domain,
    InterpretationConfidence,
    Priority,
)
from nexus_core.domain import Goal, Scope
from nexus_planning import PlanningRequest, ids
from tests.unit.nexus_planning.helpers import (
    item,
    make_capability,
    planning_env,
)

# --------------------------------------------------------------------------- #
# Shared deterministic fixtures (plain builders, no pytest fixtures needed).   #
# --------------------------------------------------------------------------- #


def _request() -> PlanningRequest:
    """A non-trivial but fully deterministic planning request.

    Two items with a dependency edge and a capability requirement so the graph,
    strategy, work packages, and capability set are all exercised.
    """
    return PlanningRequest(
        work_items=(
            item("design", capability_requirements=("analysis.design",)),
            item("build", depends_on=("design",)),
        ),
    )


def _capability():
    return make_capability("analysis.design")


# --------------------------------------------------------------------------- #
# 1. Two independent environments produce equal results.                      #
# --------------------------------------------------------------------------- #


def test_two_independent_envs_produce_equal_plan() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    env1 = planning_env(_capability())
    env2 = planning_env(_capability())

    result1 = env1.planning.service.plan(goal, request)
    result2 = env2.planning.service.plan(goal, request)

    assert result1.plan == result2.plan


def test_two_independent_envs_produce_equal_work_packages() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    result1 = planning_env(_capability()).planning.service.plan(goal, request)
    result2 = planning_env(_capability()).planning.service.plan(goal, request)

    assert result1.work_packages == result2.work_packages
    assert isinstance(result1.work_packages, tuple)


def test_two_independent_envs_produce_equal_execution_graph() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    result1 = planning_env(_capability()).planning.service.plan(goal, request)
    result2 = planning_env(_capability()).planning.service.plan(goal, request)

    assert result1.execution_graph == result2.execution_graph


def test_two_independent_envs_produce_equal_execution_strategy() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    result1 = planning_env(_capability()).planning.service.plan(goal, request)
    result2 = planning_env(_capability()).planning.service.plan(goal, request)

    assert result1.execution_strategy == result2.execution_strategy


def test_two_independent_envs_produce_equal_capabilities() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    result1 = planning_env(_capability()).planning.service.plan(goal, request)
    result2 = planning_env(_capability()).planning.service.plan(goal, request)

    assert result1.capabilities == result2.capabilities


def test_whole_planning_result_is_equal_across_envs() -> None:
    """Frozen pydantic models compare by value: the entire result is equal."""
    goal = _make_goal("goal-1")
    request = _request()

    result1 = planning_env(_capability()).planning.service.plan(goal, request)
    result2 = planning_env(_capability()).planning.service.plan(goal, request)

    assert result1 == result2


# --------------------------------------------------------------------------- #
# 2. Emitted event streams are identical across independent runs.             #
# --------------------------------------------------------------------------- #


def test_event_streams_are_identical_across_envs() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    env1 = planning_env(_capability())
    env2 = planning_env(_capability())

    env1.planning.service.plan(goal, request)
    env2.planning.service.plan(goal, request)

    events1 = list(env1.infrastructure.event_store.read_all())
    events2 = list(env2.infrastructure.event_store.read_all())

    assert events1 == events2


def test_event_stream_identifiers_are_deterministic() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    env1 = planning_env(_capability())
    env2 = planning_env(_capability())

    env1.planning.service.plan(goal, request)
    env2.planning.service.plan(goal, request)

    ids1 = [e.identifier for e in env1.infrastructure.event_store.read_all()]
    ids2 = [e.identifier for e in env2.infrastructure.event_store.read_all()]

    assert ids1 == ids2
    # Sanity: identifiers are unique within a single deterministic run.
    assert len(ids1) == len(set(ids1))


def test_event_timestamps_are_pinned_by_fixed_source() -> None:
    """The FixedTimestampSource keeps the one captured-as-data value reproducible."""
    goal = _make_goal("goal-1")
    request = _request()

    env = planning_env(_capability())
    env.planning.service.plan(goal, request)

    timestamps = {e.timestamp for e in env.infrastructure.event_store.read_all()}
    assert timestamps == {"1970-01-01T00:00:00+00:00"}


# --------------------------------------------------------------------------- #
# 3. Re-planning the same Goal + Request in the same env is idempotent.        #
# --------------------------------------------------------------------------- #


def test_replanning_same_env_is_idempotent_at_store_level() -> None:
    """A second identical plan() emits byte-identical events.

    Because every emitted event has a deterministic identifier *and* identical
    content, the append-only store treats the second emission as a duplicate
    (INV-16 idempotent append) and is a no-op. The global log length therefore
    does not double.
    """
    goal = _make_goal("goal-1")
    request = _request()

    env = planning_env(_capability())

    env.planning.service.plan(goal, request)
    length_after_first = env.infrastructure.event_store.global_length()
    assert length_after_first > 0

    env.planning.service.plan(goal, request)
    length_after_second = env.infrastructure.event_store.global_length()

    assert length_after_second == length_after_first


def test_replanning_same_env_leaves_event_stream_unchanged() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    env = planning_env(_capability())

    env.planning.service.plan(goal, request)
    events_after_first = list(env.infrastructure.event_store.read_all())

    env.planning.service.plan(goal, request)
    events_after_second = list(env.infrastructure.event_store.read_all())

    assert events_after_second == events_after_first


def test_replanning_same_env_returns_equal_result() -> None:
    goal = _make_goal("goal-1")
    request = _request()

    env = planning_env(_capability())

    first = env.planning.service.plan(goal, request)
    second = env.planning.service.plan(goal, request)

    assert first == second


# --------------------------------------------------------------------------- #
# 4. Different Goals never collide on plan / work-package identity.            #
# --------------------------------------------------------------------------- #


def test_different_goals_produce_different_plan_identities() -> None:
    request = _request()

    result_a = planning_env(_capability()).planning.service.plan(_make_goal("a"), request)
    result_b = planning_env(_capability()).planning.service.plan(_make_goal("b"), request)

    assert result_a.plan.identity != result_b.plan.identity
    assert result_a.plan.identity == "plan-a-v1"
    assert result_b.plan.identity == "plan-b-v1"


def test_different_goals_produce_disjoint_work_package_identities() -> None:
    request = _request()

    result_a = planning_env(_capability()).planning.service.plan(_make_goal("a"), request)
    result_b = planning_env(_capability()).planning.service.plan(_make_goal("b"), request)

    wp_ids_a = {wp.identifier for wp in result_a.work_packages}
    wp_ids_b = {wp.identifier for wp in result_b.work_packages}

    assert wp_ids_a.isdisjoint(wp_ids_b)
    assert wp_ids_a == {"wp-a-design", "wp-a-build"}
    assert wp_ids_b == {"wp-b-design", "wp-b-build"}


def test_different_goals_produce_different_graph_and_strategy_identities() -> None:
    request = _request()

    result_a = planning_env(_capability()).planning.service.plan(_make_goal("a"), request)
    result_b = planning_env(_capability()).planning.service.plan(_make_goal("b"), request)

    assert result_a.execution_graph.identity != result_b.execution_graph.identity
    assert result_a.execution_strategy.identity != result_b.execution_strategy.identity


# --------------------------------------------------------------------------- #
# 5. Deterministic identifier SHAPES (helpers tested directly).               #
# --------------------------------------------------------------------------- #


def test_plan_id_shape() -> None:
    assert ids.plan_id("goal-1") == "plan-goal-1-v1"
    assert ids.plan_id("goal-1", "2") == "plan-goal-1-v2"


def test_work_package_id_shape() -> None:
    assert ids.work_package_id("goal-1", "build") == "wp-goal-1-build"


def test_graph_id_shape() -> None:
    assert ids.graph_id("goal-1") == "graph-goal-1-v1"
    assert ids.graph_id("goal-1", "2") == "graph-goal-1-v2"


def test_strategy_id_shape() -> None:
    assert ids.strategy_id("goal-1") == "strategy-goal-1-v1"
    assert ids.strategy_id("goal-1", "2") == "strategy-goal-1-v2"


def test_node_id_shape() -> None:
    assert ids.node_id("build") == "node-build"


def test_edge_id_shape() -> None:
    assert ids.edge_id("node-a", "node-b", "dependency") == "edge-node-a->node-b:dependency"


def test_event_id_shape_zero_pads_sequence() -> None:
    assert ids.event_id("plan-goal-1-v1", "wp", 0) == "evt-plan-goal-1-v1-wp-0000"
    assert ids.event_id("plan-goal-1-v1", "plan", 12) == "evt-plan-goal-1-v1-plan-0012"


def test_correlation_id_shape() -> None:
    assert ids.correlation_id("goal-1") == "cor-goal-1"


def test_id_helpers_are_pure_functions() -> None:
    """Calling a helper twice with identical input yields identical output."""
    assert ids.plan_id("g") == ids.plan_id("g")
    assert ids.event_id("p", "k", 3) == ids.event_id("p", "k", 3)


# --------------------------------------------------------------------------- #
# 6. Correlation derivation precedence.                                        #
# --------------------------------------------------------------------------- #


def test_request_correlation_wins_over_goal_and_default() -> None:
    """request.correlation_identifier takes precedence over everything else."""
    goal = _make_goal("goal-1", correlation=Correlation(correlation_identifier="cor-from-goal"))
    request = PlanningRequest(
        work_items=(item("only"),),
        correlation_identifier="cor-from-request",
    )

    env = planning_env()
    env.planning.service.plan(goal, request)

    correlations = {e.correlation_identifier for e in env.infrastructure.event_store.read_all()}
    assert correlations == {"cor-from-request"}


def test_goal_correlation_used_when_request_has_none() -> None:
    """With no request correlation, the Goal's correlation is used."""
    goal = _make_goal("goal-1", correlation=Correlation(correlation_identifier="cor-from-goal"))
    request = PlanningRequest(work_items=(item("only"),))

    env = planning_env()
    env.planning.service.plan(goal, request)

    correlations = {e.correlation_identifier for e in env.infrastructure.event_store.read_all()}
    assert correlations == {"cor-from-goal"}


def test_default_correlation_derived_from_goal_identity() -> None:
    """With neither request nor goal correlation, the default ids helper is used."""
    goal = _make_goal("goal-1")
    request = PlanningRequest(work_items=(item("only"),))

    env = planning_env()
    env.planning.service.plan(goal, request)

    correlations = {e.correlation_identifier for e in env.infrastructure.event_store.read_all()}
    assert correlations == {ids.correlation_id("goal-1")}
    assert correlations == {"cor-goal-1"}


# --------------------------------------------------------------------------- #
# 7. plan_version flows into every derived identifier shape.                   #
# --------------------------------------------------------------------------- #


def test_plan_version_flows_into_all_identities() -> None:
    goal = _make_goal("goal-1")
    request = PlanningRequest(
        plan_version="2",
        work_items=(item("only"),),
    )

    result = planning_env().planning.service.plan(goal, request)

    assert result.plan.identity == "plan-goal-1-v2"
    assert result.execution_graph.identity == "graph-goal-1-v2"
    assert result.execution_strategy.identity == "strategy-goal-1-v2"


def test_plan_version_yields_distinct_identities_from_default_version() -> None:
    goal = _make_goal("goal-1")
    v1_request = PlanningRequest(work_items=(item("only"),))
    v2_request = PlanningRequest(plan_version="2", work_items=(item("only"),))

    v1 = planning_env().planning.service.plan(goal, v1_request)
    v2 = planning_env().planning.service.plan(goal, v2_request)

    assert v1.plan.identity != v2.plan.identity
    assert v1.execution_graph.identity != v2.execution_graph.identity
    assert v1.execution_strategy.identity != v2.execution_strategy.identity


# --------------------------------------------------------------------------- #
# Local Goal builder (make_goal in helpers does not accept a Correlation, so   #
# we construct the Goal directly where a correlation is needed and reuse it    #
# everywhere for consistency).                                                 #
# --------------------------------------------------------------------------- #


def _make_goal(identity: str, *, correlation: Correlation | None = None) -> Goal:
    return Goal(
        identity=identity,
        outcome="Ship the feature",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("x",), excluded=()),
        correlation=correlation,
        status=None,
    )
