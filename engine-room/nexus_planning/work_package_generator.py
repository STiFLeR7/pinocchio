"""Step 3 — Work Package generation (ADR-003 §3.2, INV-09).

Turns each declared work item into one immutable :class:`WorkPackage` — the
smallest independently executable unit. The generator assigns boundaries,
ownership (parent Goal + Plan), dependencies (by reference), inputs/outputs,
constraints, required capabilities (as references), evidence, and completion
criteria.

It never assigns a runtime, selects a provider, or declares completion (INV-04,
INV-21). Required capabilities are carried as references on ``skills`` (the
runtime-independent requirement channel, INV-33); ``resources`` is left empty
because Planning declares requirements, not availability/selection (INV-37).
Context is carried **by reference** (ADR-003 §7); Planning never builds it.
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.domain.goal import Goal
from nexus_core.domain.work_package import WorkPackage
from nexus_planning import ids
from nexus_planning.capability_resolver import CAPABILITY_TARGET_TYPE
from nexus_planning.requests import PlanningRequest, WorkItemSpec

GOAL_TARGET_TYPE = "goal"
PLAN_TARGET_TYPE = "plan"
WORK_PACKAGE_TARGET_TYPE = "work_package"
CONTEXT_TARGET_TYPE = "context_package"
STRATEGY_TARGET_TYPE = "execution_strategy"


class WorkPackageGenerator:
    """Generates the immutable Work Packages for a planning cycle (deterministic)."""

    def generate(
        self,
        goal: Goal,
        request: PlanningRequest,
        *,
        plan_identity: str,
        strategy_identity: str,
        correlation_identifier: str,
    ) -> tuple[WorkPackage, ...]:
        """One Work Package per declared item, in request order."""
        context_ref = request.context_ref or Reference(
            target_type=CONTEXT_TARGET_TYPE, identifier=f"context-{goal.identity}"
        )
        goal_ref = Reference(target_type=GOAL_TARGET_TYPE, identifier=goal.identity)
        plan_ref = Reference(target_type=PLAN_TARGET_TYPE, identifier=plan_identity)
        strategy_ref = Reference(target_type=STRATEGY_TARGET_TYPE, identifier=strategy_identity)
        correlation = Correlation(correlation_identifier=correlation_identifier)
        return tuple(
            self._build(
                goal,
                item,
                goal_ref=goal_ref,
                plan_ref=plan_ref,
                strategy_ref=strategy_ref,
                context_ref=context_ref,
                correlation=correlation,
            )
            for item in request.work_items
        )

    def _build(
        self,
        goal: Goal,
        item: WorkItemSpec,
        *,
        goal_ref: Reference,
        plan_ref: Reference,
        strategy_ref: Reference,
        context_ref: Reference,
        correlation: Correlation,
    ) -> WorkPackage:
        capability_refs = tuple(
            Reference(target_type=CAPABILITY_TARGET_TYPE, identifier=capability)
            for capability in item.capability_requirements
        )
        dependency_refs = tuple(
            Reference(
                target_type=WORK_PACKAGE_TARGET_TYPE,
                identifier=ids.work_package_id(goal.identity, dependency),
            )
            for dependency in item.depends_on
        )
        return WorkPackage(
            identifier=ids.work_package_id(goal.identity, item.key),
            parent_goal=goal_ref,
            parent_plan=plan_ref,
            priority=item.priority or goal.priority,
            objective=item.objective,
            context=context_ref,
            constraints=item.constraints,
            resources=(),
            skills=item.skill_refs + capability_refs,
            inputs=item.inputs,
            outputs=item.outputs,
            evidence=item.evidence,
            completion_criteria=item.completion_criteria,
            dependencies=dependency_refs,
            execution_strategy_ref=strategy_ref,
            correlation=correlation,
        )
