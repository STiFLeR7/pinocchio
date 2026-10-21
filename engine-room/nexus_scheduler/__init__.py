"""``nexus_scheduler`` — the Constitutional Scheduler & governed autonomy (P16).

The sole constitutional owner of execution **timing**. It determines *when* a Goal (or a platform
operation) enters the platform — deterministic one-time / delayed / immediate / interval / cron-like
schedules, durable and replayable, driven by an injected clock (never a wall clock). A due Goal is
dispatched through the Policy-mediated Autonomous Execution Coordinator (``Manual`` / ``Governed`` /
``Fully Automatic``) into the Constitutional Pipeline — the single execution coordinator; approvals stay
with the Approval Exchange and governance with Policy. Platform operations are dispatched through the
read-only Operations Plane. It records durable ``scheduler.*`` facts (producer ``scheduler``); replay
reconstructs the scheduling history exactly and a restart resumes without duplicate dispatch (INV-13/14/18).

Dependency direction is one-way: ``nexus_scheduler → {nexus_workflows.spine, nexus_approval,
nexus_operations, nexus_policy, nexus_core, nexus_infra}``. It reasons/plans/executes/validates/recovers
nothing, evaluates no policy (it delegates to the Policy engine), and modifies no owner.
"""

from __future__ import annotations

from nexus_scheduler.autonomy import AutonomousExecutionCoordinator
from nexus_scheduler.composition import SchedulerContext, build_scheduler
from nexus_scheduler.dispatcher import Dispatcher
from nexus_scheduler.events import (
    SCHEDULER_DISPATCH_DENIED,
    SCHEDULER_DISPATCH_REQUESTED,
    SCHEDULER_DISPATCHED,
    SCHEDULER_OPERATION_RAN,
    SCHEDULER_PRODUCER,
    SCHEDULER_REGISTERED,
)
from nexus_scheduler.model import (
    AutonomyMode,
    DispatchOutcome,
    Schedule,
    ScheduleKind,
    SchedulerHealth,
    ScheduleStatus,
    ScheduleTrigger,
)
from nexus_scheduler.registry import reconstruct_schedule, reconstruct_schedules
from nexus_scheduler.scheduled_operations import (
    DIAGNOSTICS_SWEEP,
    HEALTH_SNAPSHOT,
    REPLAY_VERIFICATION,
    RUNTIME_REFRESH,
    ScheduledOperations,
)
from nexus_scheduler.scheduler import Scheduler

__version__ = "2.5.0"

__all__ = [
    "DIAGNOSTICS_SWEEP",
    "HEALTH_SNAPSHOT",
    "REPLAY_VERIFICATION",
    "RUNTIME_REFRESH",
    "SCHEDULER_DISPATCHED",
    "SCHEDULER_DISPATCH_DENIED",
    "SCHEDULER_DISPATCH_REQUESTED",
    "SCHEDULER_OPERATION_RAN",
    "SCHEDULER_PRODUCER",
    "SCHEDULER_REGISTERED",
    "AutonomousExecutionCoordinator",
    "AutonomyMode",
    "DispatchOutcome",
    "Dispatcher",
    "Schedule",
    "ScheduleKind",
    "ScheduleStatus",
    "ScheduleTrigger",
    "ScheduledOperations",
    "Scheduler",
    "SchedulerContext",
    "SchedulerHealth",
    "build_scheduler",
    "reconstruct_schedule",
    "reconstruct_schedules",
]
