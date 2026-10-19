"""The Harness -> Runtime projection -- the one sanctioned integration seam.

Runtime is deliberately isolated from the upstream layers: it imports only ``{nexus_core,
nexus_infra}`` and consumes a ``nexus_core``-only :class:`RuntimeIntake`, never an
``ExecutionPackage`` / ``RuntimeRequest`` / ``ExecutionManifest`` (which live in Harness /
Orchestration). ``nexus_runtime/requests.py`` states the intake is "assembled at the integration
boundary (which may import the upstream layers)" -- and this integration package *is* that boundary.

:func:`project_intake` performs that assembly by value: it maps a compiled Harness
:class:`ExecutionPackage` (paired with its Orchestration :class:`RuntimeRequest` and Harness
:class:`ExecutionManifest` by node) into the :class:`RuntimeIntake` the Runtime Manager prepares.
It copies references only (INV-27); it invents nothing and lowers no requirement.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_harness import ExecutionManifest, ExecutionPackage
from nexus_orchestration import RuntimeRequest
from nexus_runtime import RuntimeIntake

_MANIFEST_TARGET_TYPE = "execution_manifest"


def project_intake(
    package: ExecutionPackage,
    runtime_request: RuntimeRequest | None,
    manifest: ExecutionManifest | None,
    *,
    attempt: int = 1,
) -> RuntimeIntake:
    """Project a compiled Harness package into the Runtime Manager's intake (the seam)."""
    candidates = runtime_request.candidate_harness_refs if runtime_request else ()
    policy = runtime_request.runtime_policy if runtime_request else {}
    manifest_ref = (
        Reference(target_type=_MANIFEST_TARGET_TYPE, identifier=manifest.identity)
        if manifest
        else None
    )
    return RuntimeIntake(
        package_identity=package.identity,
        node=package.node,
        session_ref=package.session_ref,
        work_package=package.work_package,
        required_capability_refs=tuple(package.capability_requirements),
        candidate_harness_refs=tuple(candidates),
        runtime_policy=policy,
        coordination=package.coordination,
        context_view_ref=package.context_view.reference,
        manifest_ref=manifest_ref,
        execution_strategy_ref=None,
        attempt=attempt,
        correlation=package.correlation,
    )
