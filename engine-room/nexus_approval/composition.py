"""Approval-Exchange composition — wire the exchange over the constitutional pipeline.

Additive DI wiring only: it builds the :class:`ApprovalExchange` over an existing
:class:`~nexus_workflows.spine.ConstitutionalPipeline` and the *same* infrastructure + clock, so the
``approval.*`` decision facts share the one durable log with the constitutional owners. It introduces no
engine, modifies no owner, and adds no competing coordinator — the pipeline stays the sole execution driver.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_approval.exchange import ApprovalExchange
from nexus_approval.observability import ApprovalObservability
from nexus_infra import InfrastructureContext
from nexus_workflows.spine import ConstitutionalPipeline


def build_approval_exchange(
    pipeline: ConstitutionalPipeline,
    infrastructure: InfrastructureContext,
    *,
    now: Callable[[], str] | None = None,
) -> ApprovalExchange:
    """Wire the Approval Exchange over the constitutional pipeline (durable-capable; records + resumes)."""
    return ApprovalExchange(
        pipeline,
        infrastructure,
        now=now,
        observability=ApprovalObservability(infrastructure.observability),
    )
