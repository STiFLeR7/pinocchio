"""Step 5 — Harness Request Builder (transform ready work into requests).

Turns every *ready* node (dependencies satisfied, approval granted/none) into one
immutable Harness Request — the runtime-independent description of work handed to a
harness later. Required Skills and required Capabilities are separated onto distinct
reference channels (capability references carry ``target_type == "capability"``).

It does **not** invoke a harness, select a provider, or execute anything — it
produces requests and stops (the next phase introduces the Harness layer).
"""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Correlation, Reference, ValueObject
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_graph import ExecutionGraph, GraphNode
from nexus_orchestration import ids
from nexus_orchestration.execution_session import ExecutionSession
from nexus_orchestration.queue import QueueState
from nexus_orchestration.vocabulary import CAPABILITY_TARGET_TYPE, SESSION_TARGET_TYPE


class HarnessRequest(ValueObject):
    """An immutable, runtime-independent request to perform one ready Work Package."""

    identity: str
    session_ref: Reference
    node: str
    work_package_ref: Reference
    execution_strategy_ref: Reference | None
    context_ref: Reference | None
    coordination: CoordinationModel
    required_skill_refs: tuple[Reference, ...] = ()
    required_capability_refs: tuple[Reference, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    correlation: Correlation | None = None


class HarnessRequestBuilder:
    """Builds one immutable Harness Request per ready node (deterministic, in queue order)."""

    def build(
        self,
        session: ExecutionSession,
        graph: ExecutionGraph,
        queue_state: QueueState,
        *,
        correlation_identifier: str,
    ) -> tuple[HarnessRequest, ...]:
        """Produce a Harness Request for every node the queue reports as ready."""
        nodes = {node.identifier: node for node in graph.nodes}
        correlation = Correlation(correlation_identifier=correlation_identifier)
        return tuple(
            self._build(session, nodes[node], correlation=correlation)
            for node in queue_state.ready
            if node in nodes
        )

    def _build(
        self, session: ExecutionSession, node: GraphNode, *, correlation: Correlation
    ) -> HarnessRequest:
        skills = tuple(
            ref for ref in node.required_skill_refs if ref.target_type != CAPABILITY_TARGET_TYPE
        )
        capabilities = tuple(
            ref for ref in node.required_skill_refs if ref.target_type == CAPABILITY_TARGET_TYPE
        )
        return HarnessRequest(
            identity=ids.harness_request_id(session.identity, node.identifier),
            session_ref=Reference(target_type=SESSION_TARGET_TYPE, identifier=session.identity),
            node=node.identifier,
            work_package_ref=node.work_package_ref,
            execution_strategy_ref=node.execution_strategy_ref,
            context_ref=node.required_context_ref or session.context_ref,
            coordination=session.coordination,
            required_skill_refs=skills,
            required_capability_refs=capabilities,
            constraints=node.constraints,
            correlation=correlation,
        )
