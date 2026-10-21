"""Operations-Plane composition — wire the read-only operations surface over the shared platform.

Additive DI wiring only: it builds the Operations service, Diagnostics service, and Health inspector over
an existing :class:`~nexus_workflows.spine.ConstitutionalPipeline` + :class:`~nexus_approval.ApprovalExchange`
and the *same* infrastructure + clock. It introduces no engine, modifies no owner, and controls nothing —
every service is a read-only projection of the one durable log (the health inspector's snapshot is the
single additive instrumentation fact).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_approval import ApprovalExchange
from nexus_infra import InfrastructureContext
from nexus_operations.diagnostics import DiagnosticsService
from nexus_operations.health import HealthInspector
from nexus_operations.observability import OperationsObservability
from nexus_operations.service import OperationsService
from nexus_workflows.spine import ConstitutionalPipeline


@dataclass(frozen=True, slots=True)
class OperationsContext:
    """The wired operations plane (immutable wiring; stateless read-only services + inspector)."""

    service: OperationsService
    diagnostics: DiagnosticsService
    health: HealthInspector


def build_operations(
    pipeline: ConstitutionalPipeline,
    approval: ApprovalExchange,
    infrastructure: InfrastructureContext,
    *,
    now: Callable[[], str] | None = None,
) -> OperationsContext:
    """Wire the read-only Operations Plane over the constitutional pipeline + Approval Exchange."""
    service = OperationsService(pipeline, approval)
    diagnostics = DiagnosticsService(pipeline)
    health = HealthInspector(
        pipeline,
        approval,
        service,
        diagnostics,
        infrastructure,
        now=now,
        observability=OperationsObservability(infrastructure.observability),
    )
    return OperationsContext(service=service, diagnostics=diagnostics, health=health)
