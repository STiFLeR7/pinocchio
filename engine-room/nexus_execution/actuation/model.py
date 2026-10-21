"""Execution-actuation value models — the immutable ExecutionState projection and driver inputs.

Execution Actuation drives the frozen Plan through its Execution Graph. Its output is one immutable
:class:`ExecutionState`: a deterministic **projection** of the ``execution.*`` event log (INV-13/14) —
never a new frozen domain object (INV-07). :class:`NodeState` is the per-node projection;
:class:`ActuationInputs` is the read-only bundle the driver consumes — the frozen ``Plan`` + its sibling
``ExecutionGraph`` + governing ``ExecutionStrategy`` + owned ``WorkPackage`` set, all by value (the P10
``ExecutionPlan``'s constituents). The ``execution.*`` event-type constants are the traversal's durable
facts; the namespace is additive (no incumbent emits under it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.plan import Plan
from nexus_core.domain.work_package import WorkPackage

# -- execution.* event types (the durable traversal facts; additive namespace) ------------------- #
EXECUTION_STARTED = "execution.started"
EXECUTION_NODE_STARTED = "execution.node_started"
EXECUTION_NODE_COMPLETED = "execution.node_completed"
EXECUTION_NODE_FAILED = "execution.node_failed"
EXECUTION_CHECKPOINT_ENTERED = "execution.checkpoint_entered"
EXECUTION_CHECKPOINT_COMPLETED = "execution.checkpoint_completed"
EXECUTION_APPROVAL_WAITING = "execution.approval_waiting"
EXECUTION_APPROVAL_RECEIVED = "execution.approval_received"
EXECUTION_COMPLETED = "execution.completed"


class NodeStatus(StrEnum):
    """The projected lifecycle state of a single graph node (a projection, not a frozen schema)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING = "waiting"  # gated on an approval that has not been received


class ActuationStatus(StrEnum):
    """The projected aggregate state of one execution-actuation run."""

    RUNNING = "running"
    COMPLETED = "completed"  # every reachable node completed
    BLOCKED = (
        "blocked"  # no ready nodes remain but not all completed (a failure/gate halted a branch)
    )
    PAUSED = "paused"  # gracefully stopped (cancellation / shutdown) before completion — resumable


class NodeState(ValueObject):
    """The per-node projection: its status plus the runtime assignment and evidence it produced."""

    node: str
    status: NodeStatus
    work_package_ref: Reference
    runtime_ref: Reference | None = None
    outcome: str | None = None
    artifact_refs: tuple[Reference, ...] = ()
    error_detail: str | None = None


class ExecutionState(ValueObject):
    """The one immutable execution-actuation artifact — a deterministic projection of the log.

    Bundles the frozen references it drives (Plan / Execution Graph / Goal) with the node-partitioned
    traversal state (completed / pending / running / blocked / waiting), the checkpoint and approval
    state, the completion lineage, the runtime assignments, and the produced artifact references. It is
    a ``ValueObject`` (INV-07 — no second Plan/Execution-State domain schema), rebuildable from the
    ``execution.*`` events (INV-13/14) and embedded whole in ``execution.completed`` for exact replay.
    """

    identity: str  # the Execution Session identity
    plan_ref: Reference
    graph_ref: Reference
    goal_ref: Reference
    status: ActuationStatus
    current_node: str | None
    nodes: tuple[NodeState, ...]
    completed_nodes: tuple[str, ...]
    pending_nodes: tuple[str, ...]
    running_nodes: tuple[str, ...]
    blocked_nodes: tuple[str, ...]
    waiting_nodes: tuple[str, ...]
    checkpoint_state: tuple[str, ...]
    approval_waiting: tuple[str, ...]
    approval_received: tuple[str, ...]
    lineage: tuple[str, ...]
    runtime_assignments: tuple[tuple[str, str], ...]
    artifact_references: tuple[Reference, ...]
    correlation_identifier: str = ""


@dataclass(frozen=True, slots=True)
class ActuationInputs:
    """The immutable inputs the driver consumes — the frozen plan bundle, all by value.

    ``plan`` + ``execution_graph`` + ``execution_strategy`` + ``work_packages`` are the P10
    ``ExecutionPlan``'s constituents (Planning produced *what* should happen; Actuation drives it).
    ``granted_gates`` are the approval gates already received out-of-band — a node whose gate is not
    granted pauses at the approval boundary (Orchestration/Governance owns the decision, not Actuation).
    """

    plan: Plan
    execution_graph: ExecutionGraph
    execution_strategy: ExecutionStrategy
    work_packages: tuple[WorkPackage, ...]
    context_references: tuple[Reference, ...] = ()
    granted_gates: tuple[str, ...] = field(default_factory=tuple)
    human_required_gates: tuple[str, ...] = field(default_factory=tuple)


class ActuationControl:
    """Cooperative cancellation + graceful-shutdown bound for a traversal run (checked between nodes).

    ``stop_after`` bounds how many nodes this run drives before it stops gracefully (leaving the rest
    for a later run to resume from the log — INV-18); ``cancel()`` requests an immediate graceful stop.
    Neither loses recorded progress: durable ``execution.*`` events for completed nodes are already on
    the log, so a restart continues without replanning.
    """

    def __init__(self, *, stop_after: int | None = None) -> None:
        self.stop_after = stop_after
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Whether an explicit cancellation has been requested."""
        return self._cancelled

    def cancel(self) -> None:
        """Request a graceful stop after the current node."""
        self._cancelled = True
