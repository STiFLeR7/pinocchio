"""The grounded planner — assembles the ExecutionPlan from the three inputs via the incumbent producer.

:class:`GroundedPlanner` runs P10's flow: build a :class:`~nexus_planning.requests.PlanningRequest`
from the Goal + ContextPackage (context reference + operative constraints) + the declared work
decomposition, run the **incumbent** :class:`~nexus_planning.planner.PlanningService` (which binds the
EngineeringStrategy, builds the frozen Plan / Work Packages / Execution Graph / Execution Strategy,
validates acyclicity, persists, and emits its ``plan.*`` facts), compute the deterministic coordination
view, and assemble one immutable :class:`~nexus_planning.grounded.model.ExecutionPlan`.

It adds one ``planning.execution_plan_assembled`` fact whose payload embeds the full ExecutionPlan, so
replaying the ``planning.*`` stream reconstructs the plan without re-planning (INV-17). Assembly is a
pure function of the inputs; the only captured-as-data value is the injected event timestamp.

Planning consumes the EngineeringStrategy and ContextPackage **by value**. It never reasons, estimates,
evaluates policy, grounds, or assembles context — and imports no such engine (guardrail-proven).
"""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Reference, Struct
from nexus_core.domain.goal import Goal
from nexus_core.events.interfaces import EventEmitter
from nexus_infra import NullObservability, Observability, content_hash
from nexus_planning import ids
from nexus_planning.events import (
    SystemTimestampSource,
    TimestampSource,
    build_event,
)
from nexus_planning.grounded.coordination import analyze_coordination
from nexus_planning.grounded.model import ExecutionPlan, PlanningInputs
from nexus_planning.planner import PlanningService
from nexus_planning.requests import PlanningRequest, WorkItemSpec

PLANNING_EXECUTION_PLAN_ASSEMBLED = "planning.execution_plan_assembled"


class GroundedPlanningObservability:
    """Grounded-planning counters over the P1 sink (derived convenience, never authoritative)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def assembled(self, *, work_packages: int, parallel_groups: int) -> None:
        self._obs.increment("planning.execution_plan_assembled")
        self._obs.observe("planning.work_package_count", float(work_packages))
        self._obs.observe("planning.parallel_group_count", float(parallel_groups))


class GroundedPlanner:
    """Assembles the ExecutionPlan deterministically by driving the incumbent Planning producer."""

    def __init__(
        self,
        service: PlanningService,
        emitter: EventEmitter,
        *,
        timestamps: TimestampSource | None = None,
        observability: GroundedPlanningObservability | None = None,
    ) -> None:
        self._service = service
        self._emitter = emitter
        self._timestamps = timestamps or SystemTimestampSource()
        self._obs = observability or GroundedPlanningObservability()

    def plan(self, inputs: PlanningInputs) -> ExecutionPlan:
        """Produce, record, and return the one immutable ExecutionPlan for ``inputs.goal``."""
        goal = inputs.goal
        correlation = self._correlation(goal)
        request = self._build_request(inputs, correlation)

        result = self._service.plan(goal, request, engineering_strategy=inputs.engineering_strategy)
        coordination = analyze_coordination(result.execution_graph, result.execution_strategy)

        execution_plan = ExecutionPlan(
            identity=result.plan.identity,
            goal_ref=Reference(target_type="goal", identifier=goal.identity),
            plan=result.plan,
            work_packages=result.work_packages,
            execution_graph=result.execution_graph,
            execution_strategy=result.execution_strategy,
            capabilities=result.capabilities,
            coordination=coordination,
            context_references=self._context_references(inputs),
            correlation_identifier=correlation,
        )

        self._obs.assembled(
            work_packages=len(execution_plan.work_packages),
            parallel_groups=len(coordination.parallel_groups),
        )
        self._emit_assembled(goal, correlation, execution_plan)
        return execution_plan

    # -- request construction ------------------------------------------------ #

    def _build_request(self, inputs: PlanningInputs, correlation: str) -> PlanningRequest:
        """Derive the PlanningRequest from the Goal + ContextPackage + declared decomposition."""
        context = inputs.context_package
        context_ref = (
            Reference(target_type="context_package", identifier=context.identity)
            if context is not None
            else None
        )
        constraints = tuple(context.constraints) if context is not None else ()

        if inputs.work_items:
            # Explicit caller decomposition is authoritative, even when Intent also recorded
            # a declared sequence from request text.
            items = tuple(
                item.model_copy(update={"constraints": item.constraints + constraints})
                for item in inputs.work_items
            )
        elif inputs.operator_steps:
            template = inputs.operator_step_template
            default_capabilities = (
                template.capability_requirements
                if template is not None and template.capability_requirements
                else tuple(inputs.engineering_strategy.skill_requirements.selection)
                if inputs.engineering_strategy is not None
                else ()
            )
            default_skills = template.skill_refs if template is not None else ()
            items = tuple(
                item.model_copy(
                    update={
                        "constraints": item.constraints + constraints,
                        "capability_requirements": item.capability_requirements
                        or default_capabilities,
                        "skill_refs": item.skill_refs or default_skills,
                    }
                )
                for item in (WorkItemSpec.model_validate(step) for step in inputs.operator_steps)
            )
        else:
            items = (self._default_item(inputs, constraints),)

        return PlanningRequest(
            work_items=items,
            assumptions=inputs.assumptions
            + (
                ()
                if inputs.work_items or inputs.operator_steps
                else (
                    "No task sequence was explicitly declared; represented the requested outcome as one atomic work item.",
                )
            ),
            context_ref=context_ref,
            correlation_identifier=correlation,
        )

    @staticmethod
    def _default_item(inputs: PlanningInputs, constraints: tuple[Constraint, ...]) -> WorkItemSpec:
        """The atomic single-package decomposition: one objective → one work item (no invention)."""
        strategy = inputs.engineering_strategy
        capabilities = tuple(strategy.skill_requirements.selection) if strategy is not None else ()
        return WorkItemSpec(
            key="main",
            objective=inputs.goal.outcome,
            capability_requirements=capabilities,
            constraints=constraints,
        )

    @staticmethod
    def _context_references(inputs: PlanningInputs) -> tuple[Reference, ...]:
        context = inputs.context_package
        if context is None:
            return ()
        return (
            Reference(target_type="context_package", identifier=context.identity),
            *((inputs.repository_profile_ref,) if inputs.repository_profile_ref else ()),
            *context.supporting_artifacts,
        )

    # -- events -------------------------------------------------------------- #

    def _emit_assembled(self, goal: Goal, correlation: str, execution_plan: ExecutionPlan) -> None:
        payload: Struct = {
            "plan": execution_plan.plan.identity,
            "goal": goal.identity,
            "work_packages": len(execution_plan.work_packages),
            "coordination_model": execution_plan.coordination.coordination_model,
            "execution_plan": dict(execution_plan.model_dump(mode="json")),
        }
        identifier = (
            f"evt-{execution_plan.plan.identity}-execution-plan-{content_hash(payload)[:16]}"
        )
        self._emitter.emit(
            build_event(
                identifier,
                PLANNING_EXECUTION_PLAN_ASSEMBLED,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )

    @staticmethod
    def _correlation(goal: Goal) -> str:
        if goal.correlation is not None:
            return goal.correlation.correlation_identifier
        return ids.correlation_id(goal.identity)
