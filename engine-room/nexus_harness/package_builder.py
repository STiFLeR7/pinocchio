"""Step 7 — Execution Package Builder (compile one immutable, runtime-ready package).

Assembles everything a runtime needs to perform one ready Work Package — and nothing
more — into a single immutable Execution Package: the embedded Work Package (runtimes
receive Work Packages, INV-09), the immutable Context View, the resolved Skill
references, the Capability requirements, the Policy bundle, the input Artifact
references, the governing Execution Strategy, descriptive metadata, and the
correlation lineage. The package is the compilation output the Runtime Manager
consumes next; building it executes nothing.

There is no frozen core contract for an Execution Package; it is a Harness output, so
the value object is defined here in the harness layer.
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.work_package import WorkPackage
from nexus_harness import ids
from nexus_harness.artifact_resolver import ResolvedArtifacts
from nexus_harness.capability_resolver import ResolvedCapabilities
from nexus_harness.context_resolver import ContextView
from nexus_harness.policy_resolver import PolicyBundle
from nexus_harness.skill_resolver import ResolvedSkills
from nexus_harness.validator import ValidatedRequest
from nexus_harness.vocabulary import (
    HARNESS_REQUEST_TARGET_TYPE,
    PackageStatus,
)


class ExecutionPackage(ValueObject):
    """One immutable, runtime-ready compilation unit (a Harness output)."""

    identity: str
    harness_request_ref: Reference
    session_ref: Reference
    node: str
    work_package: WorkPackage
    context_view: ContextView
    skill_refs: tuple[Reference, ...] = ()
    capability_requirements: tuple[Reference, ...] = ()
    policy_bundle: PolicyBundle
    artifact_refs: tuple[Reference, ...] = ()
    execution_strategy: ExecutionStrategy | None = None
    coordination: CoordinationModel
    metadata: Struct = Field(default_factory=dict)
    correlation: Correlation
    status: PackageStatus | None = None


class ExecutionPackageBuilder:
    """Compiles the resolved parts into one immutable Execution Package (deterministic)."""

    def build(
        self,
        validated: ValidatedRequest,
        *,
        skills: ResolvedSkills,
        capabilities: ResolvedCapabilities,
        policies: PolicyBundle,
        context: ContextView,
        artifacts: ResolvedArtifacts,
        correlation_identifier: str,
    ) -> ExecutionPackage:
        """Assemble the Execution Package for one validated Harness Request."""
        request = validated.request
        skill_refs = tuple(skill.reference for skill in skills.skills)
        capability_refs = tuple(capability.reference for capability in capabilities.capabilities)
        artifact_refs = tuple(artifact.reference for artifact in artifacts.artifacts)
        return ExecutionPackage(
            identity=ids.execution_package_id(request.identity),
            harness_request_ref=Reference(
                target_type=HARNESS_REQUEST_TARGET_TYPE, identifier=request.identity
            ),
            session_ref=request.session_ref,
            node=request.node,
            work_package=validated.work_package,
            context_view=context,
            skill_refs=skill_refs,
            capability_requirements=capability_refs,
            policy_bundle=policies,
            artifact_refs=artifact_refs,
            execution_strategy=validated.strategy,
            coordination=request.coordination,
            metadata={
                "node": request.node,
                "session": request.session_ref.identifier,
                "work_package": request.work_package_ref.identifier,
                "context": context.identity,
                "skill_count": len(skill_refs),
                "capability_count": len(capability_refs),
                "policy_count": len(policies.policies),
                "artifact_count": len(artifact_refs),
            },
            correlation=Correlation(correlation_identifier=correlation_identifier),
            status=PackageStatus.COMPILED,
        )
