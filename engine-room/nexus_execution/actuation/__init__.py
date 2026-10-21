"""``nexus_execution.actuation`` — Execution Actuation: the deterministic execution-graph traversal driver.

Planning produces *what* should happen (the P10 ExecutionPlan); Execution Actuation deterministically
drives that plan through Orchestration and Runtime while preserving governance, replay, and
observability. It owns execution *traversal* — not planning, reasoning, or runtime implementation::

    ExecutionPlan (Plan + Execution Graph + Strategy + Work Packages)
        → GraphWalker (Orchestration coordinators, per wave)   # what is ready now
        → RuntimeDispatcher (Runtime Manager → Execution Engine)   # perform through the Runtime abstraction
        → execution.* events + immutable ExecutionState (a projection of the log)

Additive to the incumbent ``nexus_execution`` subsystem: it reuses the Orchestration coordinators, the
Runtime Manager, and the Execution Engine unchanged, and consumes the frozen plan bundle by value.
Distinct from the roadmap's ``nexus_actuation`` "Act" capability (external side effects via the
Harness) — this is the execution-graph *traversal* driver.
"""

from __future__ import annotations

from nexus_execution.actuation.actuator import ExecutionActuator, reconstruct_execution_state
from nexus_execution.actuation.composition import (
    ExecutionActuationContext,
    build_execution_actuation,
)
from nexus_execution.actuation.dispatch import DispatchOutcome, RuntimeDispatcher
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
from nexus_execution.actuation.traversal import GraphWalker, Wave, checkpoint_nodes

__all__ = [
    "EXECUTION_APPROVAL_RECEIVED",
    "EXECUTION_APPROVAL_WAITING",
    "EXECUTION_CHECKPOINT_COMPLETED",
    "EXECUTION_CHECKPOINT_ENTERED",
    "EXECUTION_COMPLETED",
    "EXECUTION_NODE_COMPLETED",
    "EXECUTION_NODE_FAILED",
    "EXECUTION_NODE_STARTED",
    "EXECUTION_STARTED",
    "ActuationControl",
    "ActuationInputs",
    "ActuationObservability",
    "ActuationStatus",
    "DispatchOutcome",
    "ExecutionActuationContext",
    "ExecutionActuator",
    "ExecutionState",
    "GraphWalker",
    "NodeState",
    "NodeStatus",
    "RuntimeDispatcher",
    "Wave",
    "build_execution_actuation",
    "checkpoint_nodes",
    "reconstruct_execution_state",
]
