"""Deterministic graph walker + dependency resolver — Orchestration's coordinators, driven per wave.

The walker never re-implements coordination: it drives the incumbent Orchestration builders
(:class:`~nexus_orchestration.DependencyTracker`, :class:`~nexus_orchestration.ExecutionQueueBuilder`,
:class:`~nexus_orchestration.HarnessRequestBuilder`, :class:`~nexus_orchestration.RuntimeRequestBuilder`
— all pure, event-free) to resolve, for a given completed/blocked/approval progress, the next wave of
ready nodes and their runtime assignments (candidates only — INV-37, Orchestration assigns, allocation
returns candidates). It emits nothing and invents no coordination the Strategy/graph does not already
imply (INV-05); it is a pure function of the graph + progress, so identical progress yields an
identical wave. Re-running the full event-emitting ``OrchestrationService`` per wave would re-announce
the one-shot ``orchestration.execution_session_created`` fact and collide (INV-13); driving its pure
coordinators is the collision-free reuse.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration import (
    ApprovalState,
    DependencyTracker,
    ExecutionQueueBuilder,
    ExecutionSession,
    HarnessRequestBuilder,
    InMemoryHarnessRegistry,
    RuntimeRequest,
    RuntimeRequestBuilder,
)

_CHECKPOINT_PREFIX = "ckpt-"


@dataclass(frozen=True, slots=True)
class Wave:
    """One deterministic traversal wave: the nodes ready to dispatch now, plus what is not yet ready."""

    ready: tuple[str, ...]
    waiting: tuple[str, ...]  # dependencies satisfied but gated on an unreceived approval
    blocked: tuple[str, ...]  # dependencies unmet (a predecessor is pending/failed/rejected)
    runtime_requests: dict[str, RuntimeRequest]  # node -> its Orchestration runtime assignment


class GraphWalker:
    """Resolves the next wave from the graph + progress by driving Orchestration's pure coordinators."""

    def __init__(self, harness_registry: InMemoryHarnessRegistry) -> None:
        self._dependencies = DependencyTracker()
        self._queue = ExecutionQueueBuilder()
        self._harness = HarnessRequestBuilder()
        self._runtime = RuntimeRequestBuilder(harness_registry)

    def next_wave(
        self,
        graph: ExecutionGraph,
        strategy: ExecutionStrategy,
        session: ExecutionSession,
        approvals: ApprovalState,
        *,
        completed: tuple[str, ...],
        blocked_sources: tuple[str, ...],
        correlation: str,
    ) -> Wave:
        """Compute the ready wave (and its runtime assignments) for the current progress — no events."""
        dependencies = self._dependencies.track(
            graph, session.identity, completed=completed, blocked_sources=blocked_sources
        )
        queue = self._queue.build(
            graph, dependencies, approvals, session.identity, completed=completed
        )
        harness_requests = self._harness.build(
            session, graph, queue, correlation_identifier=correlation
        )
        runtime_requests = self._runtime.build(
            session, strategy, harness_requests, correlation_identifier=correlation
        )
        return Wave(
            ready=queue.ready,
            waiting=queue.waiting,
            blocked=queue.blocked,
            runtime_requests={request.node: request for request in runtime_requests},
        )


def checkpoint_nodes(graph: ExecutionGraph) -> frozenset[str]:
    """The node ids that carry a checkpoint (recovery resume points — INV-18)."""
    nodes: set[str] = set()
    for ref in graph.checkpoints:
        identifier = ref.identifier
        nodes.add(
            identifier[len(_CHECKPOINT_PREFIX) :]
            if identifier.startswith(_CHECKPOINT_PREFIX)
            else identifier
        )
    return frozenset(nodes)
