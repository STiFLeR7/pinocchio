"""Execution-history composition — dependency-injection wiring for Execution History.

Mirrors ``build_repository`` / ``build_engineering``: it **reuses** the P1 substrate unchanged —
the reader is the infrastructure's authoritative event store (Execution History reads it read-only),
the emitter is the infrastructure context, the repository is a reused ``InMemoryRepository``, and
metrics are the context's observability. Integration is additive DI only; no engine is modified.
Durable persistence is transparent over ``build_durable_infrastructure`` (ADR-007). It imports no
downstream engine and no other grounding subsystem — grounding depends only on the foundation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_history.engine import PROJECTOR_VERSION, ExecutionHistory
from nexus_history.observability import HistoryObservability
from nexus_history.persistence import HistoryRepositories, build_history_repositories
from nexus_infra import InfrastructureContext


@dataclass(frozen=True, slots=True)
class HistoryContext:
    """The wired Execution-History subsystem (immutable wiring, stateful engine + repository)."""

    infrastructure: InfrastructureContext
    repositories: HistoryRepositories
    engine: ExecutionHistory


def build_history(
    infrastructure: InfrastructureContext,
    *,
    repositories: HistoryRepositories | None = None,
    now: Callable[[], str] | None = None,
    projector_version: str = PROJECTOR_VERSION,
) -> HistoryContext:
    """Wire an execution-history context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_history_repositories(obs)
    engine = ExecutionHistory(
        reader=infrastructure.event_store,
        emitter=infrastructure,
        repositories=resolved,
        observability=HistoryObservability(obs),
        now=now,
        projector_version=projector_version,
    )
    return HistoryContext(infrastructure=infrastructure, repositories=resolved, engine=engine)
