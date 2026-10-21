"""The Harness Service — compiles Harness Requests into runtime-ready packages.

Receives a deterministic :class:`CompilationRequest` (the ready-node Harness Requests
an Orchestration cycle produced), drives the compilation pipeline for each — validate
→ resolve Skills → resolve Capabilities → resolve Policies → resolve Context → resolve
Artifacts → build Execution Package → build Execution Manifest — persists the
Execution Packages and Manifests through Phase 2 repositories, emits harness events to
the log, and returns an immutable :class:`CompilationResult`.

It compiles only. It never invokes AI, edits repositories it reads from, runs a shell
command, allocates a runtime, executes a Work Package, performs recovery, or validates
an outcome (doc 11 *Architectural Boundaries*). A failure emits a ``harness.failed``
event and raises. The Runtime Manager — the next phase — executes the packages.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Struct
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import Repository
from nexus_harness import events, ids
from nexus_harness.artifact_resolver import ArtifactResolver
from nexus_harness.capability_resolver import CapabilityResolver
from nexus_harness.context_resolver import ContextResolver
from nexus_harness.events import SystemTimestampSource, TimestampSource
from nexus_harness.manifest_builder import ExecutionManifest, ExecutionManifestBuilder
from nexus_harness.package_builder import ExecutionPackage, ExecutionPackageBuilder
from nexus_harness.policy_resolver import PolicyResolver
from nexus_harness.requests import CompilationRequest, CompilationResult
from nexus_harness.skill_resolver import SkillResolver
from nexus_harness.sources import HarnessSources
from nexus_harness.validator import HarnessValidator
from nexus_harness.validators import HarnessError, validate_outputs
from nexus_orchestration.harness_requests import HarnessRequest


@dataclass(frozen=True, slots=True)
class HarnessRepositories:
    """The repositories the Harness persists through (Phase 2 mechanism, reused)."""

    execution_packages: Repository[ExecutionPackage]
    execution_manifests: Repository[ExecutionManifest]


class HarnessService:
    """Compiles one batch of Harness Requests into persisted, emitted packages + manifests."""

    def __init__(
        self,
        sources: HarnessSources,
        repositories: HarnessRepositories,
        emitter: EventEmitter,
        *,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._repos = repositories
        self._emitter = emitter
        self._timestamps = timestamps or SystemTimestampSource()
        self._validator = HarnessValidator(sources)
        self._skills = SkillResolver(sources.skills)
        self._capabilities = CapabilityResolver(sources.capabilities)
        self._policies = PolicyResolver(sources.policies)
        self._context = ContextResolver()
        self._artifacts = ArtifactResolver(sources)
        self._package = ExecutionPackageBuilder()
        self._manifest = ExecutionManifestBuilder()

    def compile(self, request: CompilationRequest) -> CompilationResult:
        """Compile, persist, and announce a batch of Execution Packages and Manifests."""
        scope = self._scope(request)
        correlation = self._correlation(request)
        try:
            result, sequence = self._compile(request, scope, correlation)
            validate_outputs(
                len(result.packages), len(result.manifests), len(request.harness_requests)
            )
        except HarnessError as exc:
            self._emit_failed(scope, correlation, exc)
            raise
        self._persist(result)
        self._emit_completed(scope, correlation, result, sequence)
        return result

    # -- pipeline ------------------------------------------------------------ #

    def _compile(
        self, request: CompilationRequest, scope: str, correlation: str
    ) -> tuple[CompilationResult, int]:
        sequence = 0
        packages: list[ExecutionPackage] = []
        manifests: list[ExecutionManifest] = []
        for harness_request in request.harness_requests:
            package, manifest, sequence = self._compile_one(
                harness_request, scope, correlation, sequence
            )
            packages.append(package)
            manifests.append(manifest)
        result = CompilationResult(packages=tuple(packages), manifests=tuple(manifests))
        return result, sequence

    def _compile_one(
        self, harness_request: HarnessRequest, scope: str, correlation: str, sequence: int
    ) -> tuple[ExecutionPackage, ExecutionManifest, int]:
        node = harness_request.node
        validated = self._validator.validate(harness_request)
        sequence = self._emit(
            scope,
            events.HARNESS_REQUEST_VALIDATED,
            "validated",
            sequence,
            correlation,
            {"node": node},
        )
        skills = self._skills.resolve(harness_request)
        sequence = self._emit(
            scope,
            events.SKILLS_RESOLVED,
            "skills",
            sequence,
            correlation,
            {"node": node, "skills": [s.identity for s in skills.skills]},
        )
        capabilities = self._capabilities.resolve(harness_request, skills)
        sequence = self._emit(
            scope,
            events.CAPABILITIES_RESOLVED,
            "capabilities",
            sequence,
            correlation,
            {"node": node, "capabilities": [c.identifier for c in capabilities.capabilities]},
        )
        policies = self._policies.resolve(harness_request, validated.strategy)
        sequence = self._emit(
            scope,
            events.POLICIES_RESOLVED,
            "policies",
            sequence,
            correlation,
            {"node": node, "policies": [p.identity for p in policies.policies]},
        )
        context = self._context.resolve(validated.context_package)
        sequence = self._emit(
            scope,
            events.CONTEXT_RESOLVED,
            "context",
            sequence,
            correlation,
            {"node": node, "context": context.identity},
        )
        artifacts = self._artifacts.resolve(harness_request.identity, validated.work_package)
        sequence = self._emit(
            scope,
            events.ARTIFACTS_RESOLVED,
            "artifacts",
            sequence,
            correlation,
            {"node": node, "artifacts": [a.identity for a in artifacts.artifacts]},
        )
        package = self._package.build(
            validated,
            skills=skills,
            capabilities=capabilities,
            policies=policies,
            context=context,
            artifacts=artifacts,
            correlation_identifier=correlation,
        )
        sequence = self._emit(
            scope,
            events.EXECUTION_PACKAGE_CREATED,
            "package",
            sequence,
            correlation,
            {"node": node, "package": package.identity},
        )
        manifest = self._manifest.build(package)
        sequence = self._emit(
            scope,
            events.EXECUTION_MANIFEST_CREATED,
            "manifest",
            sequence,
            correlation,
            {"node": node, "manifest": manifest.identity},
        )
        return package, manifest, sequence

    # -- persistence --------------------------------------------------------- #

    def _persist(self, result: CompilationResult) -> None:
        for package in result.packages:
            self._repos.execution_packages.add(package)
        for manifest in result.manifests:
            self._repos.execution_manifests.add(manifest)

    # -- events -------------------------------------------------------------- #

    def _emit_completed(
        self, scope: str, correlation: str, result: CompilationResult, sequence: int
    ) -> None:
        self._emit(
            scope,
            events.HARNESS_COMPLETED,
            "completed",
            sequence,
            correlation,
            {
                "packages": [package.identity for package in result.packages],
                "manifests": [manifest.identity for manifest in result.manifests],
                "package_count": len(result.packages),
            },
        )

    def _emit_failed(self, scope: str, correlation: str, exc: HarnessError) -> None:
        self._emit(
            scope,
            events.HARNESS_FAILED,
            "failed",
            0,
            correlation,
            {"error": str(exc), "reason": type(exc).__name__},
        )

    def _emit(
        self,
        scope: str,
        event_type: str,
        kind: str,
        sequence: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        self._emitter.emit(
            events.build_event(
                ids.event_id(scope, kind, sequence),
                event_type,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )
        return sequence + 1

    # -- derivations --------------------------------------------------------- #

    def _scope(self, request: CompilationRequest) -> str:
        if request.session_ref is not None:
            return request.session_ref.identifier
        if request.harness_requests:
            return request.harness_requests[0].session_ref.identifier
        return "harness"

    def _correlation(self, request: CompilationRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if request.harness_requests:
            first = request.harness_requests[0]
            if first.correlation is not None:
                return first.correlation.correlation_identifier
            return ids.correlation_id(first.session_ref.identifier)
        return ids.correlation_id("harness")
