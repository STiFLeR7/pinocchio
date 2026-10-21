"""Orchestration inputs and outputs — the deterministic request/result models.

The Orchestrator coordinates an Execution Graph + Execution Strategy (the artifacts
Planning produced for a Goal) into a deterministic execution structure. The
*request* is an immutable value: the graph and strategy plus optional orchestration
progress (nodes already completed, paused, or with out-of-band approval decisions).
With all progress fields empty, the result is determined solely by the five bound
artifacts — identical inputs always yield an identical orchestration.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration.approvals import ApprovalState
from nexus_orchestration.dependency_tracker import DependencyState
from nexus_orchestration.execution_session import ExecutionSession
from nexus_orchestration.harness_requests import HarnessRequest
from nexus_orchestration.queue import QueueState
from nexus_orchestration.runtime_requests import RuntimeRequest


class OrchestrationRequest(ValueObject):
    """The complete, immutable input to one orchestration cycle."""

    execution_graph: ExecutionGraph
    execution_strategy: ExecutionStrategy
    context_ref: Reference | None = None
    """Binds the Context Package; if absent it is derived from the graph nodes."""
    completed_nodes: tuple[str, ...] = ()
    """Node identifiers already complete (orchestration progress / resume)."""
    paused_nodes: tuple[str, ...] = ()
    """Node identifiers explicitly paused (their downstream becomes blocked)."""
    approved_gates: tuple[str, ...] = ()
    """Gated node identifiers granted out-of-band (human/multi-stage/deferred)."""
    rejected_gates: tuple[str, ...] = ()
    """Gated node identifiers rejected out-of-band (the node and its downstream block)."""
    correlation_identifier: str | None = None
    session_version: str = "1"


class OrchestrationResult(ValueObject):
    """The complete output of an orchestration cycle — immutable, ready for the Harness layer."""

    session: ExecutionSession
    dependency_state: DependencyState
    queue_state: QueueState
    approval_state: ApprovalState
    harness_requests: tuple[HarnessRequest, ...]
    runtime_requests: tuple[RuntimeRequest, ...]
