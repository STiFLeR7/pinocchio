"""Step 4 — Approval Coordinator (orchestration logic only; ADR-004).

Planning *identifies* which nodes require approval (recorded on the Execution Graph
as ``approval`` node constraints and in ``policies['approval_gates']``); the
Orchestrator *enforces* them. Each gated node is assigned the platform's single
approval taxonomy (ADR-004 §3.3) carried on the Execution Strategy
(``approval_policy``) and a deterministic decision state:

- **automatic** → granted immediately;
- **human_review / multi_stage / deferred** → requested (pending) unless the
  request supplies an out-of-band grant;
- an explicit out-of-band rejection → rejected (which blocks the node downstream).

There is no UI and no notification system here — only the orchestration decision.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.contracts.enums import ApprovalTaxonomy
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration import ids
from nexus_orchestration.vocabulary import (
    SESSION_TARGET_TYPE,
    ApprovalStatus,
)

APPROVAL_CONSTRAINT_KIND = "approval"


class ApprovalGate(ValueObject):
    """One node's approval requirement: its taxonomy (the kind) and decision state."""

    node: str
    taxonomy: ApprovalTaxonomy
    status: ApprovalStatus


class ApprovalState(ValueObject):
    """The deterministic approval snapshot for one orchestration instance."""

    identity: str
    session_ref: Reference
    gates: tuple[ApprovalGate, ...]
    requested: tuple[str, ...]
    granted: tuple[str, ...]
    rejected: tuple[str, ...]


class ApprovalCoordinator:
    """Computes the deterministic approval state for a graph (enforces, never notifies)."""

    def coordinate(
        self,
        graph: ExecutionGraph,
        strategy: ExecutionStrategy,
        session_identity: str,
        *,
        approved: tuple[str, ...] = (),
        rejected: tuple[str, ...] = (),
        human_required: tuple[str, ...] = (),
    ) -> ApprovalState:
        """Assign each gated node a taxonomy and a deterministic decision state."""
        taxonomy = strategy.approval_policy
        approved_set = set(approved)
        rejected_set = set(rejected)
        human_required_set = set(human_required)
        gated = self._gated_nodes(graph, human_required_set)

        gates: list[ApprovalGate] = []
        requested: list[str] = []
        granted: list[str] = []
        rejected_nodes: list[str] = []
        for node in gated:
            gate_taxonomy = (
                ApprovalTaxonomy.HUMAN_REVIEW if node in human_required_set else taxonomy
            )
            status = self._decide(
                node, gate_taxonomy, approved_set, rejected_set, human_required_set
            )
            if status is ApprovalStatus.GRANTED:
                granted.append(node)
            elif status is ApprovalStatus.REJECTED:
                rejected_nodes.append(node)
            else:
                requested.append(node)
            gates.append(ApprovalGate(node=node, taxonomy=gate_taxonomy, status=status))

        return ApprovalState(
            identity=ids.approval_state_id(session_identity),
            session_ref=Reference(target_type=SESSION_TARGET_TYPE, identifier=session_identity),
            gates=tuple(gates),
            requested=tuple(requested),
            granted=tuple(granted),
            rejected=tuple(rejected_nodes),
        )

    @staticmethod
    def _decide(
        node: str,
        taxonomy: ApprovalTaxonomy,
        approved: set[str],
        rejected: set[str],
        human_required: set[str],
    ) -> ApprovalStatus:
        if node in rejected:
            return ApprovalStatus.REJECTED
        if node in human_required:
            return ApprovalStatus.GRANTED if node in approved else ApprovalStatus.REQUESTED
        if taxonomy is ApprovalTaxonomy.AUTOMATIC:
            return ApprovalStatus.GRANTED
        if node in approved:
            return ApprovalStatus.GRANTED
        return ApprovalStatus.REQUESTED

    @staticmethod
    def _gated_nodes(graph: ExecutionGraph, human_required: set[str]) -> tuple[str, ...]:
        node_ids = {node.identifier for node in graph.nodes}
        gated: set[str] = set()
        raw = graph.policies.get("approval_gates", ())
        if isinstance(raw, (list, tuple)):
            gated.update(str(item) for item in raw)
        for node in graph.nodes:
            if any(constraint.kind == APPROVAL_CONSTRAINT_KIND for constraint in node.constraints):
                gated.add(node.identifier)
        return tuple(sorted((gated | human_required) & node_ids))
