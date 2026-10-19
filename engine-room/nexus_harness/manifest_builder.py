"""Step 8 — Execution Manifest Builder (generate a deterministic, descriptive manifest).

Folds one Execution Package into a flat Execution Manifest: a *descriptive* statement
of what the package requires — its required capabilities, skills, artifacts, context,
execution metadata, and capability-based runtime requirements. The manifest is the
declarative companion a scheduler/Runtime Manager reads; it is never executable and
names no runtime (the runtime requirements come from the Strategy's capability-based
``runtime_policy``, ADR-002 / INV-37).

There is no frozen core contract for an Execution Manifest; it is a Harness output,
so the value object is defined here in the harness layer.
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_harness import ids
from nexus_harness.package_builder import ExecutionPackage
from nexus_harness.vocabulary import (
    EXECUTION_PACKAGE_TARGET_TYPE,
    ManifestStatus,
)


class ExecutionManifest(ValueObject):
    """A flat, descriptive manifest of one Execution Package's requirements."""

    identity: str
    package_ref: Reference
    node: str
    required_capabilities: tuple[Reference, ...] = ()
    required_skills: tuple[Reference, ...] = ()
    required_artifacts: tuple[Reference, ...] = ()
    required_context: Reference
    execution_metadata: Struct = Field(default_factory=dict)
    runtime_requirements: Struct = Field(default_factory=dict)
    correlation: Correlation
    status: ManifestStatus | None = None


class ExecutionManifestBuilder:
    """Generates a deterministic, descriptive manifest from an Execution Package."""

    def build(self, package: ExecutionPackage) -> ExecutionManifest:
        """Describe the package's requirements; derive nothing executable."""
        runtime_requirements = (
            dict(package.execution_strategy.runtime_policy)
            if package.execution_strategy is not None
            else {}
        )
        return ExecutionManifest(
            identity=ids.execution_manifest_id(package.identity),
            package_ref=Reference(
                target_type=EXECUTION_PACKAGE_TARGET_TYPE, identifier=package.identity
            ),
            node=package.node,
            required_capabilities=package.capability_requirements,
            required_skills=package.skill_refs,
            required_artifacts=package.artifact_refs,
            required_context=package.context_view.reference,
            execution_metadata={
                "node": package.node,
                "coordination": package.coordination.value,
                "work_package": package.work_package.identifier,
                "approval_taxonomy": package.policy_bundle.approval_taxonomy,
                "policy_count": len(package.policy_bundle.policies),
            },
            runtime_requirements=runtime_requirements,
            correlation=package.correlation,
            status=ManifestStatus.CREATED,
        )
