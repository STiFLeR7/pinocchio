"""Runtime dispatch — drive one ready node through the Runtime abstraction to an ExecutionResult.

The dispatcher never touches a provider (INV — Runtime independence): it projects a node's Orchestration
runtime assignment into a ``nexus_core``-only :class:`~nexus_runtime.RuntimeIntake` (the sanctioned
integration-boundary projection — copies references only, invents nothing, lowers no requirement), asks
the incumbent :class:`~nexus_runtime.runtime_manager.RuntimeManager` to prepare a Ready session
(selection/allocation stays Orchestration+Runtime's — INV-37), and hands that session to the incumbent
:class:`~nexus_execution.engine.ExecutionEngine`, which performs the Work Package through the injected
:class:`~nexus_execution.adapter.RuntimeAdapter`. It adds no execution behavior; it wires the existing
Runtime + Execution engines.

The projection duplicates ~15 lines of ``nexus_workflows.project_intake`` deliberately: importing
``nexus_workflows`` (which imports ``nexus_execution``) would create a cycle. It copies references only.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_graph import GraphNode
from nexus_core.domain.work_package import WorkPackage
from nexus_execution.adapter import RuntimeAdapter
from nexus_execution.engine import ExecutionEngine
from nexus_orchestration import RuntimeRequest
from nexus_runtime import PreparationRequest, RuntimeIntake
from nexus_runtime.runtime_manager import RuntimeManager

_SESSION_TARGET_TYPE = "execution_session"


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """The immutable result of dispatching one node through Runtime + Execution."""

    node: str
    outcome: str  # "completed" | "failed" | "cancelled" (the runtime terminal outcome)
    runtime_ref: Reference | None
    artifact_refs: tuple[Reference, ...]
    error_detail: str | None

    @property
    def succeeded(self) -> bool:
        """Whether the runtime performed the node to normal completion."""
        return self.outcome == "completed"


class RuntimeDispatcher:
    """Prepares a Ready session for a node and performs it through the existing Runtime abstraction."""

    def __init__(
        self, manager: RuntimeManager, engine: ExecutionEngine, adapter: RuntimeAdapter
    ) -> None:
        self._manager = manager
        self._engine = engine
        self._adapter = adapter

    def register_runtime(self, capacity: int) -> None:
        """Register the injected runtime with the Manager, sized to hold ``capacity`` nodes.

        Called every run (the Manager's registry is in-memory, so a restart over a reopened durable
        log must re-register). Capacity is a deterministic function of the graph, and the
        ``runtime.registered`` fact does not encode it, so the re-emitted event is identical and
        idempotent (INV-16). Selection/allocation stays the Manager's (INV-37).
        """
        descriptor = self._adapter.descriptor()
        descriptor = descriptor.model_copy(
            update={"metadata": {**(descriptor.metadata or {}), "capacity": capacity}}
        )
        self._manager.register_runtime(descriptor)

    def dispatch(
        self,
        node: GraphNode,
        work_package: WorkPackage,
        runtime_request: RuntimeRequest | None,
        *,
        session_identity: str,
        correlation: str,
    ) -> DispatchOutcome:
        """Prepare → perform one node; never calls the provider directly (the engine drives it)."""
        intake = _project_intake(
            node,
            work_package,
            runtime_request,
            session_identity=session_identity,
            correlation=correlation,
        )
        prepared = self._manager.prepare(
            PreparationRequest(
                intakes=(intake,), session_ref=None, correlation_identifier=correlation
            )
        )
        if not prepared.sessions:
            return DispatchOutcome(
                node=node.identifier,
                outcome="failed",
                runtime_ref=None,
                artifact_refs=(),
                error_detail="runtime manager prepared no session (no candidate runtime)",
            )
        result = self._engine.execute(prepared.sessions[0], self._adapter, work_package)
        return DispatchOutcome(
            node=node.identifier,
            outcome=result.outcome.value,
            runtime_ref=result.runtime_ref,
            artifact_refs=result.artifact_refs,
            error_detail=result.error_detail,
        )


def _project_intake(
    node: GraphNode,
    work_package: WorkPackage,
    runtime_request: RuntimeRequest | None,
    *,
    session_identity: str,
    correlation: str,
    attempt: int = 1,
) -> RuntimeIntake:
    """Project a node's Orchestration assignment into the Runtime Manager's intake (the seam).

    ``package_identity`` includes ``session_identity`` (the goal-scoped Execution Session id) because
    ``node.identifier`` alone is only unique *within one plan* (RC2) — two goals whose plans both produce
    a work item with the same key would otherwise mint the same Runtime Session id and collide on every
    downstream ``runtime.*``/``validation.*`` event scope.
    """
    candidates = runtime_request.candidate_harness_refs if runtime_request else ()
    policy = runtime_request.runtime_policy if runtime_request else {}
    coordination = runtime_request.coordination if runtime_request else CoordinationModel.SEQUENTIAL
    capabilities = runtime_request.required_capability_refs if runtime_request else ()
    session_ref = (
        runtime_request.session_ref
        if runtime_request
        else Reference(target_type=_SESSION_TARGET_TYPE, identifier=session_identity)
    )
    return RuntimeIntake(
        package_identity=f"actuation-pkg-{session_identity}-{node.identifier}",
        node=node.identifier,
        session_ref=session_ref,
        work_package=work_package,
        required_capability_refs=tuple(capabilities),
        candidate_harness_refs=tuple(candidates),
        runtime_policy=policy,
        coordination=coordination,
        context_view_ref=node.required_context_ref,
        manifest_ref=None,
        execution_strategy_ref=node.execution_strategy_ref,
        attempt=attempt,
        correlation=Correlation(correlation_identifier=correlation),
    )
