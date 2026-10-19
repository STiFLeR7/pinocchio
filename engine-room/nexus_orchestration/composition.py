"""Orchestration composition — dependency-injection wiring (no global state).

Assembles the orchestration layer over a Phase 2 :class:`InfrastructureContext`. It
**reuses** the infrastructure substrate rather than inventing persistence: the
session, dependency-state, queue-state, approval-state, harness-request, and
runtime-request repositories are all instances of the same Phase 2
``InMemoryRepository`` generic, and the event emitter is the infrastructure context
itself (``emit`` = append-to-log then publish). The infrastructure is not modified.

The Harness Registry is injected (a deterministic in-memory reference ships by
default); the Runtime Request Builder depends only on the frozen Protocol. Every
dependency is overridable and there is no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.registries.interfaces import HarnessRegistry
from nexus_infra import InfrastructureContext, InMemoryRepository
from nexus_orchestration.approvals import ApprovalState
from nexus_orchestration.dependency_tracker import DependencyState
from nexus_orchestration.events import TimestampSource
from nexus_orchestration.execution_session import ExecutionSession
from nexus_orchestration.harness_requests import HarnessRequest
from nexus_orchestration.orchestrator import OrchestrationRepositories, OrchestrationService
from nexus_orchestration.queue import QueueState
from nexus_orchestration.registry import InMemoryHarnessRegistry
from nexus_orchestration.runtime_requests import RuntimeRequest


@dataclass(frozen=True, slots=True)
class OrchestrationContext:
    """The wired orchestration layer (immutable wiring, stateful components)."""

    infrastructure: InfrastructureContext
    repositories: OrchestrationRepositories
    harness_registry: HarnessRegistry
    service: OrchestrationService


def build_orchestration(
    infrastructure: InfrastructureContext,
    *,
    harness_registry: HarnessRegistry | None = None,
    timestamps: TimestampSource | None = None,
) -> OrchestrationContext:
    """Wire an orchestration context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    registry: HarnessRegistry = harness_registry or InMemoryHarnessRegistry()
    repositories = OrchestrationRepositories(
        sessions=InMemoryRepository[ExecutionSession](
            "execution_session", lambda s: s.identity, obs
        ),
        dependency_states=InMemoryRepository[DependencyState](
            "dependency_state", lambda d: d.identity, obs
        ),
        queue_states=InMemoryRepository[QueueState]("queue_state", lambda q: q.identity, obs),
        approval_states=InMemoryRepository[ApprovalState](
            "approval_state", lambda a: a.identity, obs
        ),
        harness_requests=InMemoryRepository[HarnessRequest](
            "harness_request", lambda h: h.identity, obs
        ),
        runtime_requests=InMemoryRepository[RuntimeRequest](
            "runtime_request", lambda r: r.identity, obs
        ),
    )
    service = OrchestrationService(
        repositories,
        infrastructure,
        harness_registry=registry,
        timestamps=timestamps,
    )
    return OrchestrationContext(
        infrastructure=infrastructure,
        repositories=repositories,
        harness_registry=registry,
        service=service,
    )
