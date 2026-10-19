"""Step 1 — the Planning Service (orchestrates the planning pipeline).

Receives a Goal and a deterministic :class:`PlanningRequest`, drives the pipeline
(decompose → resolve capabilities → assign strategy → generate packages → build
graph → build plan → validate), persists the results through Phase 2 repositories,
emits planning events to the log, and returns an immutable
:class:`PlanningResult`.

It coordinates only. It never executes work, allocates a runtime, invokes a
harness, validates execution, or performs recovery (INV-03). A failure emits a
``planning.failed`` event and raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Struct
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.goal import Goal
from nexus_core.domain.plan import Plan
from nexus_core.domain.work_package import WorkPackage
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import Repository
from nexus_engineering.model import EngineeringStrategy
from nexus_planning import events, ids
from nexus_planning.capability_resolver import CapabilityResolver
from nexus_planning.decomposition import DecompositionStrategy, ExplicitDecompositionStrategy
from nexus_planning.events import SystemTimestampSource, TimestampSource
from nexus_planning.execution_graph_builder import ExecutionGraphBuilder
from nexus_planning.plan_builder import PlanBuilder
from nexus_planning.requests import PlanningRequest, PlanningResult
from nexus_planning.strategy_assigner import StrategyAssigner
from nexus_planning.strategy_binding import bind_strategy
from nexus_planning.validators import (
    PlanningError,
    validate_acyclic,
    validate_goal,
    validate_outputs,
    validate_request,
)
from nexus_planning.work_package_generator import WorkPackageGenerator


@dataclass(frozen=True, slots=True)
class PlanningRepositories:
    """The repositories Planning persists through (Phase 2 mechanism, reused)."""

    plans: Repository[Plan]
    work_packages: Repository[WorkPackage]
    execution_graphs: Repository[ExecutionGraph]
    execution_strategies: Repository[ExecutionStrategy]


class PlanningService:
    """Coordinates one planning cycle from Goal to persisted, emitted Plan."""

    def __init__(
        self,
        repositories: PlanningRepositories,
        capability_resolver: CapabilityResolver,
        emitter: EventEmitter,
        *,
        decomposition: DecompositionStrategy | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._repos = repositories
        self._resolver = capability_resolver
        self._emitter = emitter
        self._decomposition = decomposition or ExplicitDecompositionStrategy()
        self._timestamps = timestamps or SystemTimestampSource()
        self._work_packages = WorkPackageGenerator()
        self._strategies = StrategyAssigner()
        self._graphs = ExecutionGraphBuilder()
        self._plans = PlanBuilder()

    def plan(
        self,
        goal: Goal,
        request: PlanningRequest,
        *,
        engineering_strategy: EngineeringStrategy | None = None,
    ) -> PlanningResult:
        """Produce, persist, and announce a complete execution plan for ``goal``.

        When an :class:`EngineeringStrategy` is supplied (P6), Planning **consumes** its engineering
        postures (execution style, approval, recovery, validation, runtime capabilities) via
        :func:`bind_strategy` instead of deriving them — Planning decomposes within EI's decision.
        Absent a Strategy, the existing operator-authored derivation applies unchanged.
        """
        if engineering_strategy is not None:
            request = bind_strategy(request, engineering_strategy)
        correlation = self._correlation(goal, request)
        try:
            validate_goal(goal)
            effective = self._decomposition.decompose(goal, request)
            validate_request(effective)
            result = self._assemble(goal, effective, correlation)
        except PlanningError as exc:
            self._emit_failed(goal, request, correlation, exc)
            raise
        self._persist(result)
        self._emit_success(goal, result, correlation)
        return result

    # -- pipeline ------------------------------------------------------------ #

    def _assemble(self, goal: Goal, request: PlanningRequest, correlation: str) -> PlanningResult:
        plan_identity = ids.plan_id(goal.identity, request.plan_version)
        capabilities = self._resolver.resolve(request)
        strategy = self._strategies.assign(goal, request, correlation_identifier=correlation)
        work_packages = self._work_packages.generate(
            goal,
            request,
            plan_identity=plan_identity,
            strategy_identity=strategy.identity,
            correlation_identifier=correlation,
        )
        graph = self._graphs.build(
            goal,
            request,
            plan_identity=plan_identity,
            strategy_identity=strategy.identity,
            coordination=strategy.coordination,
            correlation_identifier=correlation,
        )
        validate_acyclic(graph)
        risks: tuple[Struct, ...] = tuple(
            {"kind": "missing_capability", "capability": capability}
            for capability in capabilities.missing
        )
        plan = self._plans.build(
            goal,
            request,
            work_packages=work_packages,
            graph_identity=graph.identity,
            correlation_identifier=correlation,
            operational_risks=risks,
        )
        validate_outputs(
            plan.execution_graph_ref.identifier,
            graph,
            work_packages,
            tuple(ref.identifier for ref in plan.work_package_refs),
        )
        return PlanningResult(
            plan=plan,
            work_packages=work_packages,
            execution_graph=graph,
            execution_strategy=strategy,
            capabilities=capabilities,
        )

    # -- persistence --------------------------------------------------------- #

    def _persist(self, result: PlanningResult) -> None:
        self._repos.execution_strategies.add(result.execution_strategy)
        for work_package in result.work_packages:
            self._repos.work_packages.add(work_package)
        self._repos.execution_graphs.add(result.execution_graph)
        self._repos.plans.add(result.plan)

    # -- events -------------------------------------------------------------- #

    def _emit_success(self, goal: Goal, result: PlanningResult, correlation: str) -> None:
        plan = result.plan
        sequence = 0
        for work_package in result.work_packages:
            self._emit(
                plan.identity,
                events.WORK_PACKAGE_CREATED,
                "wp",
                sequence,
                correlation,
                {"work_package": work_package.identifier, "plan": plan.identity},
            )
            sequence += 1
        self._emit(
            plan.identity,
            events.EXECUTION_GRAPH_CREATED,
            "graph",
            sequence,
            correlation,
            {
                "graph": result.execution_graph.identity,
                "nodes": len(result.execution_graph.nodes),
                "edges": len(result.execution_graph.edges),
            },
        )
        sequence += 1
        self._emit(
            plan.identity,
            events.PLAN_CREATED,
            "plan",
            sequence,
            correlation,
            {
                "plan": plan.identity,
                "goal": goal.identity,
                "coordination": result.execution_strategy.coordination.value,
                "work_packages": [wp.identifier for wp in result.work_packages],
            },
        )
        sequence += 1
        self._emit(
            plan.identity,
            events.PLANNING_COMPLETED,
            "completed",
            sequence,
            correlation,
            {
                "plan": plan.identity,
                "work_package_count": len(result.work_packages),
                "capabilities_required": list(result.capabilities.required),
                "capabilities_missing": list(result.capabilities.missing),
            },
        )

    def _emit_failed(
        self, goal: Goal, request: PlanningRequest, correlation: str, exc: PlanningError
    ) -> None:
        plan_identity = ids.plan_id(goal.identity, request.plan_version)
        self._emit(
            plan_identity,
            events.PLANNING_FAILED,
            "failed",
            0,
            correlation,
            {"goal": goal.identity, "error": str(exc), "reason": type(exc).__name__},
        )

    def _emit(
        self,
        plan_identity: str,
        event_type: str,
        kind: str,
        sequence: int,
        correlation: str,
        payload: Struct,
    ) -> None:
        self._emitter.emit(
            events.build_event(
                ids.event_id(plan_identity, kind, sequence),
                event_type,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )

    def _correlation(self, goal: Goal, request: PlanningRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if goal.correlation is not None:
            return goal.correlation.correlation_identifier
        return ids.correlation_id(goal.identity)
