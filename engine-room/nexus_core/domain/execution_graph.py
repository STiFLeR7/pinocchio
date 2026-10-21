"""Execution Graph — the authoritative operational topology of a Plan.

Contract: ``contracts/execution_graph.md``. Produced by Planning; state owned by
Orchestration/Recovery. Binding: ADR-003 (§3.3 sibling artifact referenced by the
Plan by id), ADR-001 (state is a projection of the event log). Invariants: INV-10
(dependencies are edges; the graph is a sibling of the Plan, never nested, and
there is no separate Dependency Graph), INV-13/14/15, INV-18, INV-03.

The graph is **directed and acyclic** except for explicitly declared iterative
loops, and its ``conditions`` must be **deterministic** so replay is reproducible
(ADR-001 §3.6). It describes operational behavior and flow; it never executes.
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import (
    Constraint,
    Correlation,
    DomainObject,
    Reference,
    Struct,
    ValueObject,
)
from nexus_core.contracts.enums import EdgeType
from nexus_core.contracts.status import ExecutionGraphStatus


class GraphNode(ValueObject):
    """An executable unit of topology: a by-id pointer to a Work Package plus coordination metadata.

    A node *references* a Work Package (INV-07) and may reference its Execution
    Strategy, required Skills, required Context, and node-level constraints. Nodes
    never embed or replace Work Packages, and never perform execution.
    """

    identifier: str
    work_package_ref: Reference
    execution_strategy_ref: Reference | None = None
    required_skill_refs: tuple[Reference, ...] = ()
    required_context_ref: Reference | None = None
    constraints: tuple[Constraint, ...] = ()


class GraphEdge(ValueObject):
    """A typed relationship between two nodes — dependencies are Execution edges (INV-10).

    The edge type is drawn from the closed ``EdgeType`` vocabulary. A ``Conditional``
    edge is gated by its bound ``condition``, which must evaluate deterministically.
    """

    identifier: str
    edge_type: EdgeType
    source_node: str
    target_node: str
    condition: str | None = None


class ExecutionGraph(DomainObject):
    """The operational topology for a Plan (contract: execution_graph.md). It never executes."""

    LIFECYCLE_NAME: ClassVar[str] = "execution_graph"

    # --- required ---------------------------------------------------------- #
    identity: str
    """Stable unique id; the Plan references the graph by this id (sibling, never nested — INV-10)."""
    parent_goal: Reference
    """Reference (by id) to the Goal this topology serves."""
    parent_plan: Reference
    """Reference (by id) to the owning Plan; the graph is its stateful sibling artifact."""
    version: str
    """Graph version; topology changes create a new version, never in-place mutation."""
    nodes: tuple[GraphNode, ...]
    """The executable units of topology; each references a Work Package by id."""
    edges: tuple[GraphEdge, ...]
    """The typed relationships between nodes; dependencies are Execution edges (INV-10)."""
    conditions: tuple[Struct, ...]
    """Deterministic predicates gating Conditional edges/branching (no replay non-determinism)."""
    checkpoints: tuple[Reference, ...]
    """References to node-level checkpoints; derived snapshots that enable graph restoration."""
    policies: Struct
    """Graph-level coordination/approval/recovery policy bindings; govern enactment, never duplicate Strategy."""
    metadata: Struct
    """Identifier, Goal, Plan, version, created time, execution state, progress, and node tallies."""

    # --- optional ---------------------------------------------------------- #
    status: ExecutionGraphStatus | None = None
    """Projected aggregate graph state — a projection of the event log (ADR-001); optional until projected."""
    state: Struct | None = None
    """Projected aggregate plus per-node states; a projection of the log, never authoritative."""
    metrics: Struct | None = None
    """Operational metrics for supervision (completion %, critical path, retry/recovery counts, …)."""
    created_time: str | None = None
    """Construction timestamp (also surfaced via metadata)."""
    correlation: Correlation | None = None
    """Correlation / trace identifiers tying the graph to its Plan/Goal lineage."""
    loops: tuple[Struct, ...] = ()
    """Explicit iterative-loop declarations — the only sanctioned exception to acyclicity."""
    recovery_paths: tuple[Struct, ...] = ()
    """Named recovery sub-topologies (expressed via Recovery edges) for auditable recovery flow."""
