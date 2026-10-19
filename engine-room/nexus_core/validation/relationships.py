"""Relationship validation — references point at the right kind of object.

Each object declares, per reference field, the ``target_type`` its references
must carry (e.g. ``WorkPackage.parent_goal`` must reference a ``goal``). The
validator walks every reference (including nested ones, e.g. graph node
``work_package_ref``) and flags type mismatches. An optional dangling check
verifies references resolve within a known id set.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel

from nexus_core.validation.errors import ContractViolation, RelationshipViolation
from nexus_core.validation.framework import (
    ValidationIssue,
    ValidationReport,
    Validator,
    iter_references,
    object_name_of,
)

# Expected reference target types, keyed by object name then leaf field name.
# A leaf not listed here carries no expectation (skipped). "dependencies" is
# object-specific (Work Package -> work_package, Capability -> capability,
# Policy -> policy), which is why this map is keyed per object.
EXPECTED_REFERENCE_TYPES: dict[str, dict[str, str]] = {
    "intent": {"resolved_goal_ref": "goal"},
    "context_package": {
        "goal_ref": "goal",
        "resources": "resource",
        "supporting_artifacts": "artifact",
    },
    "plan": {
        "parent_goal": "goal",
        "work_package_refs": "work_package",
        "execution_graph_ref": "execution_graph",
        "supersedes": "plan",
    },
    "work_package": {
        "parent_goal": "goal",
        "parent_plan": "plan",
        "context": "context_package",
        "resources": "resource",
        "skills": "skill",
        "checkpoints": "checkpoint",
        "dependencies": "work_package",
        "execution_strategy_ref": "execution_strategy",
        "evidence_refs": "evidence",
    },
    "execution_graph": {
        "parent_goal": "goal",
        "parent_plan": "plan",
        "checkpoints": "checkpoint",
        "work_package_ref": "work_package",
        "execution_strategy_ref": "execution_strategy",
        "required_context_ref": "context_package",
        "required_skill_refs": "skill",
    },
    "skill": {
        "composition_references": "skill",
        "required_capabilities": "capability",
    },
    "capability": {"dependencies": "capability"},
    "resource": {
        "capability_reference": "capability",
        "relationships": "resource",
        "allocation_holder": "work_package",
    },
    "artifact": {
        "evidence_ref": "evidence",
        "parent_version": "artifact",
    },
    "observation": {
        "derived_from_events": "event",
        "checkpoint_history": "checkpoint",
    },
    "checkpoint": {
        "current_work_package": "work_package",
        "execution_graph_position": "execution_graph",
        "context_references": "context_package",
        "artifacts_produced": "artifact",
        "evidence_collected": "evidence",
        "parent_checkpoint": "checkpoint",
    },
    "policy": {"dependencies": "policy"},
    "knowledge": {
        "relationships": "knowledge",
        "artifact_refs": "artifact",
        "observation_refs": "observation",
        "candidate_ref": "reflection",
        "superseded_by": "knowledge",
    },
    "reflection": {"inputs": "evidence"},
}


def _leaf(path: str) -> str:
    """The reference's leaf field name, stripped of nesting and tuple indices."""
    return path.rsplit(".", 1)[-1].split("[", 1)[0]


class RelationshipValidator(Validator):
    """Validates that references carry the expected ``target_type``."""

    category: ClassVar[str] = "relationship"
    exception: ClassVar[type[ContractViolation]] = RelationshipViolation

    def issues(self, obj: BaseModel) -> Iterator[ValidationIssue]:
        name = object_name_of(obj)
        expected = EXPECTED_REFERENCE_TYPES.get(name, {})
        for path, ref in iter_references(obj):
            want = expected.get(_leaf(path))
            if want is not None and ref.target_type != want:
                yield ValidationIssue(
                    category=self.category,
                    object_name=name,
                    message=(f"{path} references {ref.target_type!r} but must reference {want!r}"),
                    location=path,
                )

    def find_dangling(self, obj: BaseModel, known_identifiers: frozenset[str]) -> ValidationReport:
        """Report references whose identifier is absent from ``known_identifiers``."""
        issues: list[ValidationIssue] = []
        name = object_name_of(obj)
        for path, ref in iter_references(obj):
            if ref.identifier not in known_identifiers:
                issues.append(
                    ValidationIssue(
                        category=self.category,
                        object_name=name,
                        message=f"dangling reference at {path}: {ref.identifier!r} is unknown",
                        location=path,
                    )
                )
        return ValidationReport(issues=tuple(issues))
