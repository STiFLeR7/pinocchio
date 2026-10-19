"""Integration proofs — Planning → Orchestration composes end to end (Phase 5).

The Orchestrator consumes Planning's *outputs* (an Execution Graph + an Execution
Strategy) by value/reference; it never imports Planning. These tests plan a Goal
with the real Planning service, feed the resulting graph + strategy into a fresh
orchestration environment, and assert the two phases compose:

* a bound Execution Session names the same goal / plan / graph / strategy;
* the root work item is READY with a harness request *and* a runtime request;
* a ``requires_approval`` work item surfaces as an approval gate;
* the graph's node ids are honored unchanged.

A second test proves the *same* infrastructure substrate can host both phases at
once (one event log, shared persistence): plan then orchestrate over a single
``build_infrastructure()``, and confirm both artifacts persisted and both
``planning.*`` and ``orchestration.*`` events landed in the one log.

A final test pins the one-way dependency: the orchestrator module source must not
import ``nexus_planning`` in any form.
"""

from __future__ import annotations

import inspect

from nexus_core.contracts.enums import CapabilityCategory
from nexus_core.domain import Capability
from nexus_infra import build_infrastructure
from nexus_orchestration import (
    InMemoryHarnessRegistry,
    build_orchestration,
)
from nexus_orchestration.vocabulary import QueueItemState
from nexus_planning import (
    InMemoryCapabilityRegistry,
    PlanningRequest,
    PlanningResult,
    build_planning,
)
from tests.unit.nexus_orchestration.helpers import harness, make_request, orchestration_env
from tests.unit.nexus_planning.helpers import (
    PlanningEnv,
    item,
    make_capability,
    make_goal,
    planning_env,
)

# --------------------------------------------------------------------------- #
# Shared, deterministic planning input.                                        #
# --------------------------------------------------------------------------- #

CAPABILITY = "analysis.design"


def _capability() -> Capability:
    return make_capability(CAPABILITY, category=CapabilityCategory.ANALYSIS)


def _planning_request() -> PlanningRequest:
    """Root ``design`` (capability), then ``build`` (which requires approval)."""
    return PlanningRequest(
        work_items=(
            item("design", capability_requirements=(CAPABILITY,)),
            item("build", depends_on=("design",), requires_approval=True),
        ),
    )


def _plan() -> tuple[PlanningResult, PlanningEnv]:
    """Plan the goal and return ``(plan_result, env)`` from a fresh planning env."""
    env = planning_env(_capability())
    plan_result = env.planning.service.plan(make_goal(), _planning_request())
    return plan_result, env


# --------------------------------------------------------------------------- #
# 1. Planning's graph + strategy orchestrate end to end.                       #
# --------------------------------------------------------------------------- #


def test_orchestration_session_binds_planning_identities() -> None:
    plan_result, _ = _plan()
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)

    result = orchestration_env().orchestration.service.orchestrate(request)
    session = result.session

    # The session names the exact same artifacts Planning produced.
    assert session.goal_ref == plan_result.execution_graph.parent_goal
    assert session.plan_ref == plan_result.execution_graph.parent_plan
    assert session.execution_graph_ref.identifier == plan_result.execution_graph.identity
    assert session.execution_strategy_ref.identifier == plan_result.execution_strategy.identity
    assert session.coordination == plan_result.execution_strategy.coordination
    assert session.node_count == len(plan_result.execution_graph.nodes)


def test_root_work_item_is_ready_with_harness_and_runtime_request() -> None:
    plan_result, _ = _plan()
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)

    # Harness advertising the root's capability so candidates are populated.
    env = orchestration_env(harness("harness-design", capabilities=(CAPABILITY,)))
    result = env.orchestration.service.orchestrate(request)

    # The root (no dependencies, no approval) is READY.
    assert "node-design" in result.queue_state.ready

    harness_nodes = {req.node for req in result.harness_requests}
    runtime_nodes = {req.node for req in result.runtime_requests}
    assert "node-design" in harness_nodes
    assert "node-design" in runtime_nodes


def test_requires_approval_item_surfaces_as_approval_gate() -> None:
    plan_result, _ = _plan()
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)

    result = orchestration_env().orchestration.service.orchestrate(request)

    gate_nodes = {gate.node for gate in result.approval_state.gates}
    assert "node-build" in gate_nodes


def test_graph_node_ids_are_honored_by_orchestration() -> None:
    plan_result, _ = _plan()
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)

    result = orchestration_env().orchestration.service.orchestrate(request)

    graph_node_ids = {node.identifier for node in plan_result.execution_graph.nodes}
    queue_node_ids = {item.node for item in result.queue_state.items}

    assert queue_node_ids == graph_node_ids
    assert graph_node_ids == {"node-design", "node-build"}
    # ``build`` depends on ``design`` and is gated, so it is not yet ready.
    build_item = next(i for i in result.queue_state.items if i.node == "node-build")
    assert build_item.state is not QueueItemState.READY


# --------------------------------------------------------------------------- #
# 2. One infrastructure substrate hosts both Planning and Orchestration.       #
# --------------------------------------------------------------------------- #


def test_shared_infrastructure_hosts_both_phases() -> None:
    infra = build_infrastructure()

    capability_registry = InMemoryCapabilityRegistry()
    capability_registry.register(_capability())
    planning = build_planning(infra, capability_registry=capability_registry)

    harness_registry = InMemoryHarnessRegistry()
    orchestration = build_orchestration(infra, harness_registry=harness_registry)

    plan_result = planning.service.plan(make_goal(), _planning_request())
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)
    orch_result = orchestration.service.orchestrate(request)

    # Both phases persisted through the shared substrate.
    assert infra.plans.get(plan_result.plan.identity) is not None
    assert orchestration.repositories.sessions.get(orch_result.session.identity) is not None

    # The single event log carries both planning.* and orchestration.* events.
    producers = {event.producer for event in infra.event_store.read_all()}
    assert "planning" in producers
    assert "orchestration" in producers

    types = {event.type for event in infra.event_store.read_all()}
    assert any(event_type.startswith("planning.") for event_type in types)
    assert any(event_type.startswith("orchestration.") for event_type in types)


def test_shared_infrastructure_orchestration_consumes_planning_graph() -> None:
    infra = build_infrastructure()

    capability_registry = InMemoryCapabilityRegistry()
    capability_registry.register(_capability())
    planning = build_planning(infra, capability_registry=capability_registry)
    orchestration = build_orchestration(infra, harness_registry=InMemoryHarnessRegistry())

    plan_result = planning.service.plan(make_goal(), _planning_request())
    request = make_request(plan_result.execution_graph, plan_result.execution_strategy)
    orch_result = orchestration.service.orchestrate(request)

    # The orchestration session references the very graph the plan persisted.
    assert (
        orch_result.session.execution_graph_ref.identifier == plan_result.execution_graph.identity
    )
    assert (
        planning.repositories.execution_graphs.get(plan_result.execution_graph.identity) is not None
    )


# --------------------------------------------------------------------------- #
# 3. One-way dependency: orchestration never imports planning.                 #
# --------------------------------------------------------------------------- #


def test_orchestrator_does_not_import_planning() -> None:
    module = __import__("nexus_orchestration.orchestrator", fromlist=["x"])
    source = inspect.getsource(module)

    assert "import nexus_planning" not in source
    assert "from nexus_planning" not in source
