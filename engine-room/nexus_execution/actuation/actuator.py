"""The Execution Actuator — deterministically drives the frozen Plan through its Execution Graph.

:class:`ExecutionActuator` owns execution *traversal* and nothing else. Given the frozen Plan bundle it
walks the Execution Graph wave by wave: it asks the incumbent Orchestration coordinators (via
:class:`~nexus_execution.actuation.traversal.GraphWalker`) which nodes are ready for the current
progress, dispatches each ready node through the existing Runtime abstraction (via
:class:`~nexus_execution.actuation.dispatch.RuntimeDispatcher` → Runtime Manager → Execution Engine),
records each transition as a durable ``execution.*`` event, advances checkpoints and honors approval
boundaries, and projects one immutable :class:`~nexus_execution.actuation.model.ExecutionState`.

It never reasons, estimates, assembles context, modifies the plan, evaluates policy, executes
provider-specific logic, validates outputs, recovers failures, reflects, or learns — those remain their
owners' (INV-03/05/11/20/21/22/23/28). On failure it records the fact and lets the branch halt (no
retry — Recovery's call); at an ungranted approval gate it pauses (Orchestration/Governance decides).

Replay & restart ride the log (ADR-001; INV-13/14/18): the full ExecutionState is embedded in
``execution.completed`` so replay reconstructs it exactly, and a fresh actuator over the same log
reconstructs the completed nodes and continues — never rebuilding the plan, never re-emitting a
completed node's events (idempotent — INV-16).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_core.domain.execution_graph import ExecutionGraph, GraphNode
from nexus_core.domain.work_package import WorkPackage
from nexus_execution.actuation.dispatch import RuntimeDispatcher
from nexus_execution.actuation.model import (
    EXECUTION_APPROVAL_RECEIVED,
    EXECUTION_APPROVAL_WAITING,
    EXECUTION_CHECKPOINT_COMPLETED,
    EXECUTION_CHECKPOINT_ENTERED,
    EXECUTION_COMPLETED,
    EXECUTION_NODE_COMPLETED,
    EXECUTION_NODE_FAILED,
    EXECUTION_NODE_STARTED,
    EXECUTION_STARTED,
    ActuationControl,
    ActuationInputs,
    ActuationStatus,
    ExecutionState,
    NodeState,
    NodeStatus,
)
from nexus_execution.actuation.observability import ActuationObservability
from nexus_execution.actuation.traversal import GraphWalker, checkpoint_nodes
from nexus_infra import InfrastructureContext, content_hash
from nexus_orchestration import (
    ApprovalCoordinator,
    ApprovalState,
    ApprovalStatus,
    ExecutionSession,
    ExecutionSessionBuilder,
    InMemoryHarnessRegistry,
    RuntimeRequest,
)
from nexus_runtime.events import SystemTimestampSource, TimestampSource, build_event

_CONTEXT_TARGET_TYPE = "context_package"


class ExecutionActuator:
    """Drives one Plan's Execution Graph to a terminal execution state, deterministically."""

    def __init__(
        self,
        dispatcher: RuntimeDispatcher,
        harness_registry: InMemoryHarnessRegistry,
        infrastructure: InfrastructureContext,
        *,
        timestamps: TimestampSource | None = None,
        observability: ActuationObservability | None = None,
    ) -> None:
        self._dispatch = dispatcher
        self._walker = GraphWalker(harness_registry)
        self._sessions = ExecutionSessionBuilder()
        self._approvals = ApprovalCoordinator()
        self._infra = infrastructure
        self._timestamps = timestamps or SystemTimestampSource()
        self._obs = observability or ActuationObservability()

    # -- public entry point -------------------------------------------------- #

    def actuate(
        self, inputs: ActuationInputs, *, control: ActuationControl | None = None
    ) -> ExecutionState:
        """Drive (or resume) the traversal; return the immutable ExecutionState."""
        control = control or ActuationControl()
        graph = inputs.execution_graph
        strategy = inputs.execution_strategy
        correlation = self._correlation(inputs)
        session = self._build_session(inputs, correlation)
        approvals = self._approvals.coordinate(
            graph,
            strategy,
            session.identity,
            approved=inputs.granted_gates,
            rejected=(),
            human_required=inputs.human_required_gates,
        )

        run = self._seed(
            session.identity
        )  # restart: reconstruct prior progress from the log (INV-18)
        self._dispatch.register_runtime(
            len(graph.nodes)
        )  # populate the Manager registry (idempotent)
        self._begin(session, graph, run)
        self._walk(inputs, session, approvals, run, control)
        state = self._project(inputs, session, approvals, run, control)

        self._obs.completed(completed=len(state.completed_nodes), waves=run.waves)
        if state.status is ActuationStatus.COMPLETED:
            self._emit_completed(session, correlation, state)
        return state

    # -- the traversal loop -------------------------------------------------- #

    def _walk(
        self,
        inputs: ActuationInputs,
        session: ExecutionSession,
        approvals: ApprovalState,
        run: _Run,
        control: ActuationControl,
    ) -> None:
        graph = inputs.execution_graph
        strategy = inputs.execution_strategy
        correlation = session.correlation.correlation_identifier
        node_by_id = {node.identifier: node for node in graph.nodes}
        wp_by_id = {wp.identifier: wp for wp in inputs.work_packages}
        checkpoints = checkpoint_nodes(graph)
        gate_status = {gate.node: gate.status for gate in approvals.gates}

        while not self._should_stop(control, run):
            wave = self._walker.next_wave(
                graph,
                strategy,
                session,
                approvals,
                completed=tuple(sorted(run.completed)),
                blocked_sources=tuple(sorted(run.failed | set(approvals.rejected))),
                correlation=correlation,
            )
            self._announce_waiting(session, wave.waiting, run)
            ready = tuple(node for node in wave.ready if node not in run.node_states)
            if not ready:
                break
            run.waves += 1
            self._obs.wave(ready=len(ready))
            for node_id in ready:
                if self._should_stop(control, run):
                    return
                self._drive_node(
                    node_by_id[node_id],
                    wp_by_id,
                    wave.runtime_requests.get(node_id),
                    session,
                    gate_status,
                    checkpoints,
                    run,
                )

    def _drive_node(
        self,
        node: GraphNode,
        wp_by_id: dict[str, WorkPackage],
        runtime_request: RuntimeRequest | None,
        session: ExecutionSession,
        gate_status: dict[str, ApprovalStatus],
        checkpoints: frozenset[str],
        run: _Run,
    ) -> None:
        node_id = node.identifier
        work_package = wp_by_id[node.work_package_ref.identifier]
        correlation = session.correlation.correlation_identifier
        run.current_node = node_id

        if (
            gate_status.get(node_id) is ApprovalStatus.GRANTED
            and node_id not in run.approval_received
        ):
            run.approval_received.append(node_id)
            self._emit(
                session.identity,
                f"approval-{node_id}-received",
                EXECUTION_APPROVAL_RECEIVED,
                correlation,
                {"node": node_id},
            )

        self._emit(
            session.identity,
            f"node-{node_id}-started",
            EXECUTION_NODE_STARTED,
            correlation,
            {"node": node_id, "work_package": work_package.identifier},
        )
        is_checkpoint = node_id in checkpoints
        if is_checkpoint:
            self._emit(
                session.identity,
                f"ckpt-{node_id}-entered",
                EXECUTION_CHECKPOINT_ENTERED,
                correlation,
                {"node": node_id},
            )

        outcome = self._dispatch.dispatch(
            node,
            work_package,
            runtime_request,
            session_identity=session.identity,
            correlation=correlation,
        )
        run.dispatched += 1

        status = NodeStatus.COMPLETED if outcome.succeeded else NodeStatus.FAILED
        state = NodeState(
            node=node_id,
            status=status,
            work_package_ref=node.work_package_ref,
            runtime_ref=outcome.runtime_ref,
            outcome=outcome.outcome,
            artifact_refs=outcome.artifact_refs,
            error_detail=outcome.error_detail,
        )
        run.node_states[node_id] = state
        if outcome.succeeded:
            run.completed.append(node_id)
            self._obs.node_completed()
            self._emit(
                session.identity,
                f"node-{node_id}-completed",
                EXECUTION_NODE_COMPLETED,
                correlation,
                _node_payload(state),
            )
            if is_checkpoint:
                run.checkpoints.append(node_id)
                self._obs.checkpoint()
                self._emit(
                    session.identity,
                    f"ckpt-{node_id}-completed",
                    EXECUTION_CHECKPOINT_COMPLETED,
                    correlation,
                    {"node": node_id},
                )
        else:
            run.failed.add(node_id)
            self._obs.node_failed()
            self._emit(
                session.identity,
                f"node-{node_id}-failed",
                EXECUTION_NODE_FAILED,
                correlation,
                _node_payload(state),
            )

    def _announce_waiting(
        self, session: ExecutionSession, waiting: tuple[str, ...], run: _Run
    ) -> None:
        correlation = session.correlation.correlation_identifier
        for node_id in waiting:
            if node_id in run.approval_waiting:
                continue
            run.approval_waiting.append(node_id)
            self._obs.approval_waiting()
            self._emit(
                session.identity,
                f"approval-{node_id}-waiting",
                EXECUTION_APPROVAL_WAITING,
                correlation,
                {"node": node_id},
            )

    @staticmethod
    def _should_stop(control: ActuationControl, run: _Run) -> bool:
        """Graceful stop: explicit cancellation or the shutdown budget for this run is spent."""
        return control.cancelled or (
            control.stop_after is not None and run.dispatched >= control.stop_after
        )

    # -- projection ---------------------------------------------------------- #

    def _project(
        self,
        inputs: ActuationInputs,
        session: ExecutionSession,
        approvals: ApprovalState,
        run: _Run,
        control: ActuationControl,
    ) -> ExecutionState:
        graph = inputs.execution_graph
        node_ids = [node.identifier for node in graph.nodes]
        final = self._walker.next_wave(
            graph,
            inputs.execution_strategy,
            session,
            approvals,
            completed=tuple(sorted(run.completed)),
            blocked_sources=tuple(sorted(run.failed | set(approvals.rejected))),
            correlation=session.correlation.correlation_identifier,
        )
        waiting_now, blocked_now = set(final.waiting), set(final.blocked)
        ready_now = set(final.ready) - set(run.node_states)  # a driven (failed) node is not "ready"

        nodes: list[NodeState] = []
        for node in graph.nodes:
            recorded = run.node_states.get(node.identifier)
            if recorded is not None:
                nodes.append(recorded)
                continue
            if node.identifier in waiting_now:
                node_status = NodeStatus.WAITING
            elif node.identifier in blocked_now:
                node_status = NodeStatus.BLOCKED
            else:  # ready-but-undriven (paused) or genuinely pending
                node_status = NodeStatus.PENDING
            nodes.append(
                NodeState(
                    node=node.identifier, status=node_status, work_package_ref=node.work_package_ref
                )
            )
        nodes.sort(key=lambda state: state.node)

        by_status: dict[NodeStatus, list[str]] = {member: [] for member in NodeStatus}
        for state in nodes:
            by_status[state.status].append(state.node)

        status = self._aggregate_status(len(run.completed), len(node_ids), ready_now)
        runtime_assignments = tuple(
            sorted(
                (state.node, state.runtime_ref.identifier)
                for state in nodes
                if state.runtime_ref is not None
            )
        )
        artifacts: list[Reference] = []
        for state in nodes:
            artifacts.extend(state.artifact_refs)

        return ExecutionState(
            identity=session.identity,
            plan_ref=session.plan_ref,
            graph_ref=session.execution_graph_ref,
            goal_ref=session.goal_ref,
            status=status,
            current_node=run.current_node,
            nodes=tuple(nodes),
            completed_nodes=tuple(sorted(by_status[NodeStatus.COMPLETED])),
            pending_nodes=tuple(sorted(by_status[NodeStatus.PENDING])),
            running_nodes=tuple(sorted(by_status[NodeStatus.RUNNING])),
            blocked_nodes=tuple(
                sorted(by_status[NodeStatus.BLOCKED] + by_status[NodeStatus.FAILED])
            ),
            waiting_nodes=tuple(sorted(by_status[NodeStatus.WAITING])),
            checkpoint_state=tuple(run.checkpoints),
            approval_waiting=tuple(run.approval_waiting),
            approval_received=tuple(run.approval_received),
            lineage=tuple(run.completed),
            runtime_assignments=runtime_assignments,
            artifact_references=tuple(artifacts),
            correlation_identifier=session.correlation.correlation_identifier,
        )

    @staticmethod
    def _aggregate_status(completed: int, total: int, ready_now: set[str]) -> ActuationStatus:
        if completed == total:
            return ActuationStatus.COMPLETED
        if ready_now:
            return (
                ActuationStatus.PAUSED
            )  # ready work remained undriven → stopped early (cancel/shutdown)
        return (
            ActuationStatus.BLOCKED
        )  # nothing ready and not all done → a failure/gate halted a branch

    # -- restart seeding (reconstruct prior progress from the log) ----------- #

    def _seed(self, session_identity: str) -> _Run:
        run = _Run()
        prefix = f"evt-{session_identity}-"
        for event in self._infra.event_store.read_all():
            if not event.identifier.startswith(prefix) or not event.type.startswith("execution."):
                continue
            self._apply(run, event)
        return run

    @staticmethod
    def _apply(run: _Run, event: Event) -> None:
        if event.type == EXECUTION_STARTED:
            run.started_present = True
        elif event.type == EXECUTION_NODE_COMPLETED:
            state = _node_state_from_payload(event.payload, NodeStatus.COMPLETED)
            run.node_states[state.node] = state
            run.completed.append(state.node)
        elif event.type == EXECUTION_NODE_FAILED:
            state = _node_state_from_payload(event.payload, NodeStatus.FAILED)
            run.node_states[state.node] = state
            run.failed.add(state.node)
        elif event.type == EXECUTION_CHECKPOINT_COMPLETED:
            run.checkpoints.append(str(event.payload["node"]))
        elif event.type == EXECUTION_APPROVAL_WAITING:
            run.approval_waiting.append(str(event.payload["node"]))
        elif event.type == EXECUTION_APPROVAL_RECEIVED:
            run.approval_received.append(str(event.payload["node"]))

    # -- events -------------------------------------------------------------- #

    def _begin(self, session: ExecutionSession, graph: ExecutionGraph, run: _Run) -> None:
        if (
            run.started_present
        ):  # restart — the session start is already on the log (idempotent, INV-16)
            return
        self._obs.started(nodes=len(graph.nodes))
        self._emit(
            session.identity,
            "execution-started",
            EXECUTION_STARTED,
            session.correlation.correlation_identifier,
            {
                "session": session.identity,
                "plan": session.plan_ref.identifier,
                "graph": session.execution_graph_ref.identifier,
                "goal": session.goal_ref.identifier,
                "node_count": len(graph.nodes),
            },
        )

    def _emit_completed(
        self, session: ExecutionSession, correlation: str, state: ExecutionState
    ) -> None:
        payload: Struct = {
            "session": session.identity,
            "status": state.status.value,
            "completed": list(state.completed_nodes),
            "execution_state": dict(state.model_dump(mode="json")),
        }
        identifier = f"evt-{session.identity}-execution-completed-{content_hash(payload)[:16]}"
        self._infra.emit(
            build_event(
                identifier, EXECUTION_COMPLETED, correlation, payload, self._timestamps.now()
            )
        )

    def _emit(
        self, scope: str, kind_suffix: str, event_type: str, correlation: str, payload: Struct
    ) -> None:
        identifier = f"evt-{scope}-{kind_suffix}"
        self._infra.emit(
            build_event(identifier, event_type, correlation, payload, self._timestamps.now())
        )

    # -- helpers ------------------------------------------------------------- #

    def _build_session(self, inputs: ActuationInputs, correlation: str) -> ExecutionSession:
        graph = inputs.execution_graph
        context_ref = (
            inputs.context_references[0]
            if inputs.context_references
            else Reference(
                target_type=_CONTEXT_TARGET_TYPE,
                identifier=f"context-{graph.parent_goal.identifier}",
            )
        )
        return self._sessions.build(
            graph,
            inputs.execution_strategy,
            context_ref=context_ref,
            correlation_identifier=correlation,
            version=graph.version,
        )

    @staticmethod
    def _correlation(inputs: ActuationInputs) -> str:
        graph = inputs.execution_graph
        if graph.correlation is not None:
            return graph.correlation.correlation_identifier
        if inputs.execution_strategy.correlation is not None:
            return inputs.execution_strategy.correlation.correlation_identifier
        return f"cor-{graph.parent_goal.identifier}"


@dataclass
class _Run:
    """Mutable per-actuation accumulators (seeded from the log on restart)."""

    node_states: dict[str, NodeState] = field(default_factory=dict)
    completed: list[str] = field(default_factory=list)  # lineage — completion order
    failed: set[str] = field(default_factory=set)
    checkpoints: list[str] = field(default_factory=list)
    approval_waiting: list[str] = field(default_factory=list)
    approval_received: list[str] = field(default_factory=list)
    current_node: str | None = None
    dispatched: int = 0
    waves: int = 0
    started_present: bool = False


def reconstruct_execution_state(
    events: Iterable[Event], *, session_identity: str
) -> ExecutionState | None:
    """Reconstruct the final ExecutionState from the log alone — the ``execution.completed`` fact.

    Replay is exact because the full state is embedded in the completed event (ADR-001; INV-13/14).
    Returns ``None`` when the traversal has not completed (a partial/interrupted run).
    """
    target = f"evt-{session_identity}-execution-completed-"
    for event in events:
        if event.type == EXECUTION_COMPLETED and event.identifier.startswith(target):
            return ExecutionState.model_validate(event.payload["execution_state"])
    return None


# -- payload (de)serialization for node facts ------------------------------------- #


def _dump_ref(ref: Reference) -> Struct:
    return {"target_type": ref.target_type, "identifier": ref.identifier}


def _load_ref(raw: object) -> Reference:
    assert isinstance(raw, dict)  # a serialized {target_type, identifier} pair
    return Reference(target_type=str(raw["target_type"]), identifier=str(raw["identifier"]))


def _node_payload(state: NodeState) -> Struct:
    return {
        "node": state.node,
        "work_package": _dump_ref(state.work_package_ref),
        "runtime": _dump_ref(state.runtime_ref) if state.runtime_ref is not None else None,
        "outcome": state.outcome,
        "artifacts": [_dump_ref(ref) for ref in state.artifact_refs],
        "error_detail": state.error_detail,
    }


def _node_state_from_payload(payload: Struct, status: NodeStatus) -> NodeState:
    runtime = payload.get("runtime")
    return NodeState(
        node=str(payload["node"]),
        status=status,
        work_package_ref=_load_ref(payload["work_package"]),
        runtime_ref=_load_ref(runtime) if runtime is not None else None,
        outcome=payload.get("outcome"),
        artifact_refs=tuple(_load_ref(ref) for ref in payload.get("artifacts", ())),
        error_detail=payload.get("error_detail"),
    )
