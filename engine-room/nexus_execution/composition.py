"""Execution composition — dependency-injection wiring for the Execution Engine.

Mirrors :func:`nexus_runtime.composition.build_runtime`: it **reuses** the Phase 2
infrastructure substrate (the event emitter is the infrastructure context itself; the
metrics sink is its observability) rather than inventing anything. The infrastructure is
not modified. Every dependency is overridable and there is no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_execution.engine import ExecutionEngine
from nexus_execution.observability import ExecutionObservability
from nexus_infra import InfrastructureContext
from nexus_runtime.events import TimestampSource


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """The wired execution layer (immutable wiring, stateful engine)."""

    infrastructure: InfrastructureContext
    engine: ExecutionEngine


def build_execution(
    infrastructure: InfrastructureContext,
    *,
    timestamps: TimestampSource | None = None,
) -> ExecutionContext:
    """Wire an execution context over an infrastructure context; all parts overridable."""
    engine = ExecutionEngine(
        infrastructure,
        observability=ExecutionObservability(infrastructure.observability),
        timestamps=timestamps,
    )
    return ExecutionContext(infrastructure=infrastructure, engine=engine)
