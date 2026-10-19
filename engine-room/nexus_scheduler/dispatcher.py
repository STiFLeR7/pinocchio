"""The Dispatcher (P16) — routes a due occurrence to its executor (Goal → autonomy; operation → Ops).

The Dispatcher owns no timing and no policy: it is the thin router the Scheduler calls once an occurrence
is due. A Goal occurrence goes to the Autonomous Execution Coordinator (Policy-mediated); a platform
operation goes to Scheduled Operations. It returns a :class:`DispatchOutcome`; the Scheduler records it.
"""

from __future__ import annotations

from nexus_scheduler.autonomy import AutonomousExecutionCoordinator
from nexus_scheduler.model import AutonomyMode, DispatchOutcome
from nexus_scheduler.scheduled_operations import ScheduledOperations
from nexus_workflows.spine import SpineRequest


class Dispatcher:
    """Routes a due occurrence to the autonomy coordinator (Goal) or scheduled operations (platform task)."""

    def __init__(
        self, autonomy: AutonomousExecutionCoordinator, scheduled_operations: ScheduledOperations
    ) -> None:
        self._autonomy = autonomy
        self._scheduled_operations = scheduled_operations

    def dispatch_goal(
        self,
        request: SpineRequest,
        *,
        autonomy: AutonomyMode,
        occurrence: int,
        occurrence_at: str,
        correlation: str,
        schedule_id: str,
    ) -> DispatchOutcome:
        """Dispatch a due Goal through the Policy-mediated autonomy coordinator."""
        return self._autonomy.dispatch(
            request,
            autonomy=autonomy,
            occurrence=occurrence,
            occurrence_at=occurrence_at,
            correlation=correlation,
            schedule_id=schedule_id,
        )

    def dispatch_operation(
        self, operation: str, *, occurrence: int, occurrence_at: str, schedule_id: str
    ) -> DispatchOutcome:
        """Dispatch a due platform operation through the read-only Operations Plane."""
        summary = self._scheduled_operations.run(operation)
        return DispatchOutcome(
            schedule_id=schedule_id,
            occurrence=occurrence,
            occurrence_at=occurrence_at,
            autonomy=AutonomyMode.GOVERNED,
            executed=True,
            policy_allowed=True,
            policy_decision="not_applicable",
            operation=operation,
            note=summary,
        )
