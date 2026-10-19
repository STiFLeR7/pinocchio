"""Estimation test fixtures — a minimal immutable Work Package and signal set."""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Reference
from nexus_core.contracts.enums import Priority
from nexus_core.domain.work_package import WorkPackage


def make_work_package(
    identifier: str = "wp-1", *, dependencies: int = 2, skills: int = 3
) -> WorkPackage:
    """A minimal, valid, immutable Work Package for estimation input."""
    return WorkPackage(
        identifier=identifier,
        parent_goal=Reference(target_type="goal", identifier="g-1"),
        parent_plan=Reference(target_type="plan", identifier="p-1"),
        priority=Priority.MEDIUM,
        objective="Implement the feature and add tests for the new module.",
        context=Reference(target_type="context_package", identifier="ctx-1"),
        constraints=(Constraint(kind="deadline", detail={"by": "eod"}),),
        resources=(Reference(target_type="resource", identifier="r-1"),),
        skills=tuple(Reference(target_type="skill", identifier=f"s-{i}") for i in range(skills)),
        inputs=(Reference(target_type="artifact", identifier="in-1"),),
        outputs=({"kind": "source"},),
        evidence={"requires": "tests"},
        completion_criteria={"tests": "pass"},
        dependencies=tuple(
            Reference(target_type="work_package", identifier=f"dep-{i}")
            for i in range(dependencies)
        ),
    )


SAMPLE_SIGNALS = {
    "objective_size": 40.0,
    "skill_count": 3.0,
    "input_count": 2.0,
    "output_count": 1.0,
    "constraint_count": 2.0,
    "dependency_count": 4.0,
    "resource_count": 1.0,
}
