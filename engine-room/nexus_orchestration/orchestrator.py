"""The Orchestration Service — coordinates a Plan into an executable structure.

Receives a deterministic :class:`OrchestrationRequest` (an Execution Graph + an
Execution Strategy, plus optional progress), drives the pipeline (bind session →
coordinate approvals → track dependencies → build queue → build harness requests →
build runtime requests), persists the results through Phase 2 repositories, emits
orchestration events to the log, and returns an immutable
:class:`OrchestrationResult`.

It coordinates only. It never executes work, edits repositories, plans, builds
context, validates outcomes, performs recovery, updates Knowledge, or invokes an
LLM (doc 07 *Architectural Boundaries*). A failure emits an ``orchestration.failed``
event and raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Reference, Struct
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import Repository
from nexus_core.registries.interfaces import HarnessRegistry
from nexus_orchestration import events, ids
from nexus_orchestration.approvals import ApprovalCoordinator, ApprovalState
from nexus_orchestration.dependency_tracker import DependencyState, DependencyTracker
from nexus_orchestration.events import SystemTimestampSource, TimestampSource
from nexus_orchestration.execution_session import ExecutionSession, ExecutionSessionBuilder
from nexus_orchestration.harness_requests import HarnessRequest, HarnessRequestBuilder
from nexus_orchestration.queue import ExecutionQueueBuilder, QueueState
from nexus_orchestration.requests import OrchestrationRequest, OrchestrationResult
from nexus_orchestration.runtime_requests import RuntimeRequest, RuntimeRequestBuilder
from nexus_orchestration.validators import (
    OrchestrationError,
    validate_acyclic,
    validate_outputs,
    validate_request,
)
from nexus_orchestration.vocabulary import (
    CONTEXT_TARGET_TYPE,
    ApprovalStatus,
)


@dataclass(frozen=True, slots=True)
class OrchestrationRepositories:
    """The repositories Orchestration persists through (Phase 2 mechanism, reused)."""

    sessions: Repository[ExecutionSession]
    dependency_states: Repository[DependencyState]
    queue_states: Repository[QueueState]
    approval_states: Repository[ApprovalState]
    harness_requests: Repository[HarnessRequest]
    runtime_requests: Repository[RuntimeRequest]


class OrchestrationService:
    """Coordinates one orchestration cycle from a Plan to a persisted, emitted structure."""

    def __init__(
        self,
        repositories: OrchestrationRepositories,
        emitter: EventEmitter,
        *,
        harness_registry: HarnessRegistry | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._repos = repositories
        self._emitter = emitter
        self._timestamps = timestamps or SystemTimestampSource()
        self._sessions = ExecutionSessionBuilder()
        self._approvals = ApprovalCoordinator()
        self._dependencies = DependencyTracker()
        self._queue = ExecutionQueueBuilder()
        self._harness = HarnessRequestBuilder()
        self._runtime = RuntimeRequestBuilder(harness_registry)

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Coordinate, persist, and announce a complete execution structure."""
        graph = request.execution_graph
        correlation = self._correlation(request)
        session_identity = ids.session_id(graph.parent_goal.identifier, request.session_version)
        try:
            validate_request(request)
            validate_acyclic(graph)
            result = self._assemble(request, correlation)
            validate_outputs(result, graph)
        except OrchestrationError as exc:
            self._emit_failed(session_identity, graph.parent_goal.identifier, correlation, exc)
            raise
        self._persist(result)
        self._emit_success(result, graph.parent_goal.identifier, correlation)
        return result

    # -- pipeline ------------------------------------------------------------ #

    def _assemble(self, request: OrchestrationRequest, correlation: str) -> OrchestrationResult:
        graph = request.execution_graph
        strategy = request.execution_strategy
        context_ref = self._context_ref(request)
        session = self._sessions.build(
            graph,
            strategy,
            context_ref=context_ref,
            correlation_identifier=correlation,
            version=request.session_version,
        )
        approvals = self._approvals.coordinate(
            graph,
            strategy,
            session.identity,
            approved=request.approved_gates,
            rejected=request.rejected_gates,
        )
        blocked_sources = (*request.paused_nodes, *approvals.rejected)
        dependencies = self._dependencies.track(
            graph,
            session.identity,
            completed=request.completed_nodes,
            blocked_sources=blocked_sources,
        )
        queue = self._queue.build(
            graph,
            dependencies,
            approvals,
            session.identity,
            completed=request.completed_nodes,
            paused=request.paused_nodes,
        )
        harness_requests = self._harness.build(
            session, graph, queue, correlation_identifier=correlation
        )
        runtime_requests = self._runtime.build(
            session, strategy, harness_requests, correlation_identifier=correlation
        )
        return OrchestrationResult(
            session=session,
            dependency_state=dependencies,
            queue_state=queue,
            approval_state=approvals,
            harness_requests=harness_requests,
            runtime_requests=runtime_requests,
        )

    def _context_ref(self, request: OrchestrationRequest) -> Reference:
        if request.context_ref is not None:
            return request.context_ref
        for node in request.execution_graph.nodes:
            if node.required_context_ref is not None:
                return node.required_context_ref
        return Reference(
            target_type=CONTEXT_TARGET_TYPE,
            identifier=f"context-{request.execution_graph.parent_goal.identifier}",
        )

    # -- persistence --------------------------------------------------------- #

    def _persist(self, result: OrchestrationResult) -> None:
        self._repos.sessions.add(result.session)
        self._repos.dependency_states.add(result.dependency_state)
        self._repos.queue_states.add(result.queue_state)
        self._repos.approval_states.add(result.approval_state)
        for harness_request in result.harness_requests:
            self._repos.harness_requests.add(harness_request)
        for runtime_request in result.runtime_requests:
            self._repos.runtime_requests.add(runtime_request)

    # -- events -------------------------------------------------------------- #

    def _emit_success(
        self, result: OrchestrationResult, goal_identity: str, correlation: str
    ) -> None:
        session = result.session
        wp_ref = {item.node: item.work_package_ref for item in result.queue_state.items}
        sequence = self._emit(
            session.identity,
            events.EXECUTION_SESSION_CREATED,
            "session",
            0,
            correlation,
            {
                "session": session.identity,
                "goal": goal_identity,
                "coordination": session.coordination.value,
                "node_count": session.node_count,
            },
        )
        for gate in result.approval_state.gates:
            sequence = self._emit(
                session.identity,
                _APPROVAL_EVENTS[gate.status],
                "approval",
                sequence,
                correlation,
                {"node": gate.node, "taxonomy": gate.taxonomy.value},
            )
        for node in result.dependency_state.satisfied:
            sequence = self._emit(
                session.identity,
                events.DEPENDENCY_SATISFIED,
                "dependency",
                sequence,
                correlation,
                {"node": node},
            )
        for node in result.queue_state.ready:
            sequence = self._emit(
                session.identity,
                events.WORK_PACKAGE_READY,
                "ready",
                sequence,
                correlation,
                {"node": node, "work_package": wp_ref[node].identifier},
            )
            sequence = self._emit(
                session.identity,
                events.EXECUTION_QUEUED,
                "queued",
                sequence,
                correlation,
                {"node": node},
            )
        for harness_request in result.harness_requests:
            sequence = self._emit(
                session.identity,
                events.HARNESS_REQUEST_CREATED,
                "harness",
                sequence,
                correlation,
                {
                    "harness_request": harness_request.identity,
                    "node": harness_request.node,
                    "work_package": harness_request.work_package_ref.identifier,
                },
            )
        for runtime_request in result.runtime_requests:
            sequence = self._emit(
                session.identity,
                events.RUNTIME_REQUEST_CREATED,
                "runtime",
                sequence,
                correlation,
                {
                    "runtime_request": runtime_request.identity,
                    "node": runtime_request.node,
                    "candidates": [
                        ref.identifier for ref in runtime_request.candidate_harness_refs
                    ],
                },
            )
        self._emit(
            session.identity,
            events.ORCHESTRATION_COMPLETED,
            "completed",
            sequence,
            correlation,
            {
                "session": session.identity,
                "ready": list(result.queue_state.ready),
                "waiting": list(result.queue_state.waiting),
                "blocked": list(result.queue_state.blocked),
                "harness_requests": len(result.harness_requests),
                "runtime_requests": len(result.runtime_requests),
            },
        )

    def _emit_failed(
        self, session_identity: str, goal_identity: str, correlation: str, exc: OrchestrationError
    ) -> None:
        self._emit(
            session_identity,
            events.ORCHESTRATION_FAILED,
            "failed",
            0,
            correlation,
            {"goal": goal_identity, "error": str(exc), "reason": type(exc).__name__},
        )

    def _emit(
        self,
        session_identity: str,
        event_type: str,
        kind: str,
        sequence: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        self._emitter.emit(
            events.build_event(
                ids.event_id(session_identity, kind, sequence),
                event_type,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )
        return sequence + 1

    def _correlation(self, request: OrchestrationRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if request.execution_strategy.correlation is not None:
            return request.execution_strategy.correlation.correlation_identifier
        if request.execution_graph.correlation is not None:
            return request.execution_graph.correlation.correlation_identifier
        return ids.correlation_id(request.execution_graph.parent_goal.identifier)


_APPROVAL_EVENTS = {
    ApprovalStatus.REQUESTED: events.APPROVAL_REQUESTED,
    ApprovalStatus.GRANTED: events.APPROVAL_GRANTED,
    ApprovalStatus.REJECTED: events.APPROVAL_REJECTED,
}
