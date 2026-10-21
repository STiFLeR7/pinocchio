"""Runtime composition — dependency-injection wiring (no global state).

Assembles the runtime layer over a Phase 2 :class:`InfrastructureContext`. It **reuses**
the infrastructure substrate rather than inventing persistence: the Session and Allocation
repositories are instances of the same Phase 2 ``InMemoryRepository`` generic, the event
emitter is the infrastructure context itself (``emit`` = append-to-log then publish), and
the metrics sink is the infrastructure's observability. The infrastructure is not modified.

The Registry is injected. A default :class:`InMemoryHarnessRegistry` reference ships (no
standalone registry phase exists yet), wrapped by the ``RUNTIME``-category
:class:`RuntimeRegistry` view. Every dependency is overridable and there is no
module-level singleton (doc 00 §4 — RM imports only ``nexus_core`` / ``nexus_infra``).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.registries.interfaces import HarnessRegistry
from nexus_infra import InfrastructureContext
from nexus_runtime.events import TimestampSource
from nexus_runtime.observability import RuntimeObservability
from nexus_runtime.persistence import RuntimeRepositories, build_runtime_repositories
from nexus_runtime.runtime_manager import RuntimeManager
from nexus_runtime.runtime_registry import InMemoryHarnessRegistry, RuntimeRegistry


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """The wired runtime layer (immutable wiring, stateful components)."""

    infrastructure: InfrastructureContext
    harness_registry: HarnessRegistry
    registry: RuntimeRegistry
    repositories: RuntimeRepositories
    manager: RuntimeManager


def build_runtime(
    infrastructure: InfrastructureContext,
    *,
    harness_registry: HarnessRegistry | None = None,
    repositories: RuntimeRepositories | None = None,
    timestamps: TimestampSource | None = None,
) -> RuntimeContext:
    """Wire a runtime context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    backing_registry = harness_registry or InMemoryHarnessRegistry()
    registry = RuntimeRegistry(backing_registry)
    resolved_repositories = repositories or build_runtime_repositories(obs)
    manager = RuntimeManager(
        registry,
        resolved_repositories,
        infrastructure,
        observability=RuntimeObservability(obs),
        timestamps=timestamps,
    )
    return RuntimeContext(
        infrastructure=infrastructure,
        harness_registry=backing_registry,
        registry=registry,
        repositories=resolved_repositories,
        manager=manager,
    )
