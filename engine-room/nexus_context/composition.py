"""Context Engineering composition — dependency-injection wiring (no global state).

Assembles the context layer over a Phase 2 :class:`InfrastructureContext`. It
**reuses** the infrastructure substrate rather than inventing persistence: the
Context Package repository is an instance of the same Phase 2 ``InMemoryRepository``
generic, and the event emitter is the infrastructure context itself
(``emit`` = append-to-log then publish). The infrastructure layer is not modified.

The default collector set is deterministic and I/O-free (Goal-derived context plus
the request's explicit fragments). Real source collectors are injected here in later
phases; every dependency is overridable and there is no module-level singleton.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nexus_context.collectors import (
    ContextCollector,
    GoalContextCollector,
    RequestFragmentCollector,
)
from nexus_context.events import TimestampSource
from nexus_context.service import ContextEngineeringService, ContextRepositories
from nexus_core.domain.context_package import ContextPackage
from nexus_infra import InfrastructureContext, InMemoryRepository


@dataclass(frozen=True, slots=True)
class ContextEngineeringContext:
    """The wired context-engineering layer (immutable wiring, stateful components)."""

    infrastructure: InfrastructureContext
    repositories: ContextRepositories
    collectors: tuple[ContextCollector, ...]
    service: ContextEngineeringService


def default_collectors() -> tuple[ContextCollector, ...]:
    """The deterministic, I/O-free reference collectors used when none are injected."""
    return (GoalContextCollector(), RequestFragmentCollector())


def build_context_engineering(
    infrastructure: InfrastructureContext,
    *,
    collectors: Iterable[ContextCollector] | None = None,
    timestamps: TimestampSource | None = None,
) -> ContextEngineeringContext:
    """Wire a context-engineering context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    repositories = ContextRepositories(
        context_packages=InMemoryRepository[ContextPackage](
            "context_package", lambda c: c.identity, obs
        ),
    )
    used_collectors = tuple(collectors) if collectors is not None else default_collectors()
    service = ContextEngineeringService(
        repositories,
        used_collectors,
        infrastructure,
        timestamps=timestamps,
    )
    return ContextEngineeringContext(
        infrastructure=infrastructure,
        repositories=repositories,
        collectors=used_collectors,
        service=service,
    )
