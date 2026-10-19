"""Shared fixtures for the P11 execution-actuation suite — real upstream ExecutionPlans.

Every ExecutionPlan is produced by the incumbent P10 grounded planner (so the tests drive a genuine
frozen Plan + Execution Graph + Strategy + Work Packages), and every runtime is the deterministic
``StubClaudeInvoker`` behind the real ``ClaudeRuntimeAdapter`` (the adapter is *injected* — the driver
imports no provider). Fixed timestamps + clock-free ids throughout, so replay/restart reproduce exactly.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_execution.actuation import (
    ActuationInputs,
    ExecutionActuationContext,
    build_execution_actuation,
)
from nexus_execution.actuation.traversal import GraphWalker
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_orchestration import (
    ApprovalCoordinator,
    ApprovalState,
    ExecutionSession,
    ExecutionSessionBuilder,
    InMemoryHarnessRegistry,
)
from nexus_planning import FixedTimestampSource, WorkItemSpec
from nexus_planning.grounded import ExecutionPlan, PlanningInputs, build_grounded_planning
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from tests.unit.nexus_engineering.fixtures import make_goal, strategy_for

_CONTEXT_REF = Reference(target_type="context_package", identifier="ctx-actuation")


def item(key: str, **overrides: object) -> WorkItemSpec:
    """A work item that requires ``code_generation`` (the capability the stub adapter advertises)."""
    overrides.setdefault("capability_requirements", ("code_generation",))
    objective = overrides.pop("objective", f"do {key}")
    return WorkItemSpec(key=key, objective=objective, **overrides)  # type: ignore[arg-type]


def make_plan(work_items: tuple[WorkItemSpec, ...], *, goal_identity: str = "g1") -> ExecutionPlan:
    """A real, deterministic ExecutionPlan from the incumbent P10 producer (throwaway infra)."""
    infra = build_infrastructure()  # throwaway — the plan is an immutable input
    goal = make_goal(identity=goal_identity)
    inputs = PlanningInputs(
        goal=goal,
        engineering_strategy=strategy_for(goal, persist=False),
        context_package=None,
        work_items=work_items,
    )
    return build_grounded_planning(infra, timestamps=FixedTimestampSource()).planner.plan(inputs)


def to_inputs(plan: ExecutionPlan, *, granted_gates: tuple[str, ...] = ()) -> ActuationInputs:
    """Lower a P10 ExecutionPlan into the actuation input bundle (by value)."""
    return ActuationInputs(
        plan=plan.plan,
        execution_graph=plan.execution_graph,
        execution_strategy=plan.execution_strategy,
        work_packages=plan.work_packages,
        context_references=plan.context_references,
        granted_gates=granted_gates,
    )


def make_inputs(
    work_items: tuple[WorkItemSpec, ...] = (), *, granted_gates: tuple[str, ...] = ()
) -> ActuationInputs:
    """Build actuation inputs for a work-item decomposition (defaults to a single atomic item)."""
    if not work_items:
        work_items = (item("a"),)
    return to_inputs(make_plan(work_items), granted_gates=granted_gates)


def adapter(*, fail: bool = False) -> ClaudeRuntimeAdapter:
    """The injected runtime adapter (deterministic stub; ``fail`` maps a provider failure)."""
    return ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=fail))


def wired(
    infrastructure: InfrastructureContext | None = None, *, fail: bool = False
) -> tuple[InfrastructureContext, ExecutionActuationContext]:
    """A fresh infra plus a wired execution-actuation context with a fixed clock."""
    infra = infrastructure or build_infrastructure()
    ctx = build_execution_actuation(
        infra, adapter=adapter(fail=fail), timestamps=FixedTimestampSource()
    )
    return infra, ctx


def walker_context(
    plan: ExecutionPlan,
) -> tuple[GraphWalker, ExecutionSession, ApprovalState, str]:
    """A GraphWalker + bound ExecutionSession + approval state for driving ``next_wave`` directly."""
    graph, strategy = plan.execution_graph, plan.execution_strategy
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=_CONTEXT_REF,
        correlation_identifier="cor-actuation",
        version=graph.version,
    )
    approvals = ApprovalCoordinator().coordinate(graph, strategy, session.identity)
    return GraphWalker(InMemoryHarnessRegistry()), session, approvals, "cor-actuation"


def execution_event_types(infra: InfrastructureContext) -> list[str]:
    """The ordered ``execution.*`` event types on the log."""
    return [e.type for e in infra.event_store.read_all() if e.type.startswith("execution.")]
