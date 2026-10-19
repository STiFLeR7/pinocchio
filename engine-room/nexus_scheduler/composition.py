"""Scheduler composition — wire the Scheduler + autonomy coordinator over the shared platform.

Additive DI wiring only: it registers the overridable ``autonomous_execution`` allow-baseline on the
pipeline's *own* Policy registry (so autonomy is governed by the one Policy configuration), wires the
Autonomous Execution Coordinator over the Constitutional Pipeline + Approval Exchange + Policy engine, and
builds the Scheduler over the *same* infrastructure + clock. It introduces no engine, modifies no owner,
and adds no competing coordinator — the pipeline stays the sole execution driver.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_approval import ApprovalExchange
from nexus_operations import OperationsContext
from nexus_policy import autonomous_execution_baseline
from nexus_scheduler.autonomy import AutonomousExecutionCoordinator
from nexus_scheduler.dispatcher import Dispatcher
from nexus_scheduler.observability import SchedulerObservability
from nexus_scheduler.scheduled_operations import ScheduledOperations
from nexus_scheduler.scheduler import Scheduler
from nexus_workflows.spine import SpinePipelineContext


@dataclass(frozen=True, slots=True)
class SchedulerContext:
    """The wired scheduling surface (immutable wiring; stateful scheduler + coordinator)."""

    scheduler: Scheduler
    autonomy: AutonomousExecutionCoordinator
    dispatcher: Dispatcher


def build_scheduler(
    spine: SpinePipelineContext,
    approval: ApprovalExchange,
    operations: OperationsContext,
    *,
    now: Callable[[], str] | None = None,
) -> SchedulerContext:
    """Wire the Scheduler + Policy-mediated autonomy over the constitutional pipeline (durable-capable)."""
    spine.policy.registry.register(
        autonomous_execution_baseline()
    )  # governed on, overridable by a deny
    autonomy = AutonomousExecutionCoordinator(spine.coordinator, approval, spine.policy.engine)
    dispatcher = Dispatcher(autonomy, ScheduledOperations(operations))
    scheduler = Scheduler(
        dispatcher,
        spine.infrastructure,
        now=now,
        observability=SchedulerObservability(spine.infrastructure.observability),
    )
    return SchedulerContext(scheduler=scheduler, autonomy=autonomy, dispatcher=dispatcher)
