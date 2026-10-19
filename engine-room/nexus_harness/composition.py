"""Harness composition — dependency-injection wiring (no global state).

Assembles the harness layer over a Phase 2 :class:`InfrastructureContext`. It
**reuses** the infrastructure substrate rather than inventing persistence: the
Execution Package and Execution Manifest repositories are instances of the same Phase
2 ``InMemoryRepository`` generic, and the event emitter is the infrastructure context
itself (``emit`` = append-to-log then publish). The infrastructure is not modified.

The resolution sources are injected. A default :class:`HarnessSources` ships with
deterministic in-memory reference registries (Skill / Capability / Policy) and Phase 2
repositories for Work Packages, Context Packages, and Execution Strategies, while the
Artifact source reuses the infrastructure's own Artifact repository. Every dependency
is overridable and there is no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.work_package import WorkPackage
from nexus_harness.events import TimestampSource
from nexus_harness.harness import HarnessRepositories, HarnessService
from nexus_harness.manifest_builder import ExecutionManifest
from nexus_harness.package_builder import ExecutionPackage
from nexus_harness.sources import (
    HarnessSources,
    InMemoryCapabilityRegistry,
    InMemoryPolicyRegistry,
    InMemorySkillRegistry,
)
from nexus_infra import InfrastructureContext, InMemoryRepository


@dataclass(frozen=True, slots=True)
class HarnessContext:
    """The wired harness layer (immutable wiring, stateful components)."""

    infrastructure: InfrastructureContext
    sources: HarnessSources
    repositories: HarnessRepositories
    service: HarnessService


def build_harness(
    infrastructure: InfrastructureContext,
    *,
    sources: HarnessSources | None = None,
    timestamps: TimestampSource | None = None,
) -> HarnessContext:
    """Wire a harness context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved_sources = sources or HarnessSources(
        skills=InMemorySkillRegistry(),
        capabilities=InMemoryCapabilityRegistry(),
        policies=InMemoryPolicyRegistry(),
        work_packages=InMemoryRepository[WorkPackage]("work_package", lambda w: w.identifier, obs),
        context_packages=InMemoryRepository[ContextPackage](
            "context_package", lambda c: c.identity, obs
        ),
        strategies=InMemoryRepository[ExecutionStrategy](
            "execution_strategy", lambda s: s.identity, obs
        ),
        artifacts=infrastructure.artifacts,
    )
    repositories = HarnessRepositories(
        execution_packages=InMemoryRepository[ExecutionPackage](
            "execution_package", lambda p: p.identity, obs
        ),
        execution_manifests=InMemoryRepository[ExecutionManifest](
            "execution_manifest", lambda m: m.identity, obs
        ),
    )
    service = HarnessService(resolved_sources, repositories, infrastructure, timestamps=timestamps)
    return HarnessContext(
        infrastructure=infrastructure,
        sources=resolved_sources,
        repositories=repositories,
        service=service,
    )
