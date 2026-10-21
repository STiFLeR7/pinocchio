"""Orchestration vocabularies — the closed, orchestration-local enumerations.

The Orchestrator coordinates; these name the coordination states it computes. They
are intentionally orchestration-local (there is no frozen core contract for an
Execution Session, Harness Request, or Runtime Request — those are Orchestration
*outputs*, doc 07 *Outputs*). Target-type constants are the canonical ``Reference``
``target_type`` strings the layer emits, kept here as one source of truth so they
never drift from the strings Planning already uses.
"""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    """Lifecycle of one orchestration instance (doc 07 *State Model*, pre-execution subset)."""

    CREATED = "created"
    COORDINATING = "coordinating"
    READY = "ready"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class DependencyOutcome(StrEnum):
    """Per-node dependency-readiness verdict (doc 07 *Dependency Coordination*)."""

    SATISFIED = "satisfied"
    PENDING = "pending"
    BLOCKED = "blocked"


class QueueItemState(StrEnum):
    """Deterministic execution-queue state for a node (doc 07; pre-execution subset)."""

    READY = "ready"
    WAITING = "waiting"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"


class ApprovalStatus(StrEnum):
    """Approval-gate decision state (ADR-004 taxonomy is the *kind*; this is the *state*)."""

    REQUESTED = "requested"
    GRANTED = "granted"
    REJECTED = "rejected"


# --- canonical Reference target_type strings (must match Planning's) ---------- #
GOAL_TARGET_TYPE = "goal"
PLAN_TARGET_TYPE = "plan"
CONTEXT_TARGET_TYPE = "context_package"
STRATEGY_TARGET_TYPE = "execution_strategy"
GRAPH_TARGET_TYPE = "execution_graph"
WORK_PACKAGE_TARGET_TYPE = "work_package"
CAPABILITY_TARGET_TYPE = "capability"
CHECKPOINT_TARGET_TYPE = "checkpoint"
SESSION_TARGET_TYPE = "execution_session"
HARNESS_TARGET_TYPE = "harness"
HARNESS_REQUEST_TARGET_TYPE = "harness_request"
RUNTIME_REQUEST_TARGET_TYPE = "runtime_request"
