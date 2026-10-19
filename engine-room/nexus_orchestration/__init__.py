"""``nexus_orchestration`` — Phase 5 Orchestration Layer for Nexus v2.

The Orchestrator coordinates execution; it never performs it. Given a validated
Plan (its Execution Graph and Execution Strategy), it deterministically decides what
becomes executable, when dependencies are satisfied, when approvals are required,
what is waiting, and what has completed — then produces the runtime-independent
Harness Requests and Runtime Requests the next phase will act on::

    … → Planning → Execution Strategy → Orchestration → (Harness → Runtime)

It never executes work, edits repositories, plans, builds context, validates
outcomes, performs recovery, updates Knowledge, or invokes an LLM (doc 07
*Architectural Boundaries*). Runtime *allocation* is deferred to a later phase; the
Orchestrator produces requirements and candidates only (INV-37).

Determinism is a hard requirement: given identical Goal / Context Package / Plan /
Execution Graph / Strategy, the Orchestrator always produces an identical execution
queue, dependency state, approval state, harness requests, runtime requests, and
event stream. There is no AI and no randomness.

Dependency direction is one-way: ``nexus_orchestration → {nexus_infra,
nexus_core}``. It never imports ``nexus_planning`` or ``nexus_context`` — it
consumes their *outputs* (graph/strategy/context reference) by value/reference.
"""

from __future__ import annotations

from nexus_orchestration.approvals import ApprovalCoordinator, ApprovalGate, ApprovalState
from nexus_orchestration.composition import OrchestrationContext, build_orchestration
from nexus_orchestration.dependency_tracker import (
    DependencyState,
    DependencyTracker,
    NodeDependency,
)
from nexus_orchestration.events import (
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)
from nexus_orchestration.execution_session import ExecutionSession, ExecutionSessionBuilder
from nexus_orchestration.harness_requests import HarnessRequest, HarnessRequestBuilder
from nexus_orchestration.orchestrator import OrchestrationRepositories, OrchestrationService
from nexus_orchestration.queue import ExecutionQueueBuilder, QueueItem, QueueState
from nexus_orchestration.registry import InMemoryHarnessRegistry
from nexus_orchestration.requests import OrchestrationRequest, OrchestrationResult
from nexus_orchestration.runtime_requests import RuntimeRequest, RuntimeRequestBuilder
from nexus_orchestration.validators import (
    CyclicDependencyError,
    InvalidGraphError,
    OrchestrationError,
    SessionBindingError,
    UnknownNodeError,
    validate_acyclic,
    validate_graph,
    validate_outputs,
    validate_request,
)
from nexus_orchestration.vocabulary import (
    ApprovalStatus,
    DependencyOutcome,
    QueueItemState,
    SessionStatus,
)

__version__ = "2.5.0"

__all__ = [
    "ApprovalCoordinator",
    "ApprovalGate",
    "ApprovalState",
    "ApprovalStatus",
    "CyclicDependencyError",
    "DependencyOutcome",
    "DependencyState",
    "DependencyTracker",
    "ExecutionQueueBuilder",
    "ExecutionSession",
    "ExecutionSessionBuilder",
    "FixedTimestampSource",
    "HarnessRequest",
    "HarnessRequestBuilder",
    "InMemoryHarnessRegistry",
    "InvalidGraphError",
    "NodeDependency",
    "OrchestrationContext",
    "OrchestrationError",
    "OrchestrationRepositories",
    "OrchestrationRequest",
    "OrchestrationResult",
    "OrchestrationService",
    "QueueItem",
    "QueueItemState",
    "QueueState",
    "RuntimeRequest",
    "RuntimeRequestBuilder",
    "SessionBindingError",
    "SessionStatus",
    "SystemTimestampSource",
    "TimestampSource",
    "UnknownNodeError",
    "build_orchestration",
    "validate_acyclic",
    "validate_graph",
    "validate_outputs",
    "validate_request",
]
