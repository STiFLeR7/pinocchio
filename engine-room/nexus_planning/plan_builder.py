"""Step 2 — Plan construction (ADR-003 §3.3, INV-03/08/10).

Assembles the immutable :class:`Plan`: the strategic approach, milestones,
priority ordering, dependency summary, references to the Work Packages it owns,
and a reference to its sibling Execution Graph. The Plan is an *approach*, never a
procedure and never an execution; it points to the topology and the executable
units without containing their stateful machinery.
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation, Reference, Struct
from nexus_core.domain.goal import Goal
from nexus_core.domain.plan import Milestone, Plan
from nexus_core.domain.work_package import WorkPackage
from nexus_planning import ids
from nexus_planning.requests import PlanningRequest
from nexus_planning.work_package_generator import (
    GOAL_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
)

EXECUTION_GRAPH_TARGET_TYPE = "execution_graph"

_DEFAULT_MILESTONE = Milestone(
    identifier="planning-complete",
    meaning="The Plan is ready for orchestration.",
    completion_condition="All Work Packages generated and the Execution Graph constructed.",
)


class PlanBuilder:
    """Builds the immutable Plan for a planning request (deterministic)."""

    def build(
        self,
        goal: Goal,
        request: PlanningRequest,
        *,
        work_packages: tuple[WorkPackage, ...],
        graph_identity: str,
        correlation_identifier: str,
        operational_risks: tuple[Struct, ...] = (),
    ) -> Plan:
        """Assemble the Plan from the Goal, request, generated packages, and graph."""
        priorities: dict[str, str] = {
            item.key: (item.priority or goal.priority).value for item in request.work_items
        }
        milestones = request.milestones or (_DEFAULT_MILESTONE,)
        return Plan(
            identity=ids.plan_id(goal.identity, request.plan_version),
            parent_goal=Reference(target_type=GOAL_TARGET_TYPE, identifier=goal.identity),
            version=request.plan_version,
            approach_summary=request.approach_summary,
            milestones=milestones,
            priorities=priorities,
            dependency_summary=request.dependency_summary,
            work_package_refs=tuple(
                Reference(target_type=WORK_PACKAGE_TARGET_TYPE, identifier=wp.identifier)
                for wp in work_packages
            ),
            execution_graph_ref=Reference(
                target_type=EXECUTION_GRAPH_TARGET_TYPE, identifier=graph_identity
            ),
            rationale=request.rationale,
            assumptions=request.assumptions,
            operational_risks=request.operational_risks + operational_risks,
            complexity_estimates={
                "work_package_count": len(work_packages),
                "dependency_count": sum(len(item.depends_on) for item in request.work_items),
            },
            correlation=Correlation(correlation_identifier=correlation_identifier),
        )
