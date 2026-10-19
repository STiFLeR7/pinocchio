"""Harness inputs and outputs — the deterministic request/result models.

The Harness compiles a batch of Harness Requests (the ready-node requests an
Orchestration cycle produced) into Execution Packages and Execution Manifests. The
*request* is an immutable value: the Harness Requests plus optional correlation. With
identical Harness Requests and identical resolution sources, the result is identical —
the headline Phase 6 determinism guarantee.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_harness.manifest_builder import ExecutionManifest
from nexus_harness.package_builder import ExecutionPackage
from nexus_orchestration.harness_requests import HarnessRequest


class CompilationRequest(ValueObject):
    """The complete, immutable input to one compilation cycle."""

    harness_requests: tuple[HarnessRequest, ...]
    session_ref: Reference | None = None
    correlation_identifier: str | None = None


class CompilationResult(ValueObject):
    """The complete output of a compilation cycle — packages + manifests, ready for Runtime."""

    packages: tuple[ExecutionPackage, ...] = ()
    manifests: tuple[ExecutionManifest, ...] = ()
