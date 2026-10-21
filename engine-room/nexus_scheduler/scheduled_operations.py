"""Scheduled platform operations (P16/C) — deterministic platform tasks, not engineering Goals.

The Scheduler can fire *platform* activities on a schedule (a health snapshot, a diagnostics sweep, a
runtime-inventory refresh, a replay verification). These are not Goals and do not enter the Constitutional
Pipeline — they invoke the read-only Operations Plane (which observes; it controls nothing). The result is
a short summary the Scheduler records; any durable fact (e.g. an ``operations.snapshot``) is owned by
Operations, not the Scheduler.
"""

from __future__ import annotations

from nexus_operations import OperationsContext

HEALTH_SNAPSHOT = "health_snapshot"
DIAGNOSTICS_SWEEP = "diagnostics_sweep"
RUNTIME_REFRESH = "runtime_refresh"
REPLAY_VERIFICATION = "replay_verification"

SUPPORTED_OPERATIONS: tuple[str, ...] = (
    HEALTH_SNAPSHOT,
    DIAGNOSTICS_SWEEP,
    RUNTIME_REFRESH,
    REPLAY_VERIFICATION,
)


class ScheduledOperations:
    """Runs a named platform operation via the Operations Plane and returns a short summary."""

    def __init__(self, operations: OperationsContext) -> None:
        self._ops = operations

    def run(self, operation: str) -> str:
        """Execute the named platform operation read-only; return a deterministic result summary."""
        if operation == HEALTH_SNAPSHOT:
            snapshot = self._ops.health.record_snapshot()
            return f"health={snapshot.summary.liveness} sessions={snapshot.summary.active_sessions}"
        if operation == DIAGNOSTICS_SWEEP:
            diagnostics = self._ops.diagnostics.diagnostics()
            return f"events={diagnostics.total_events} consistent={diagnostics.consistent}"
        if operation == RUNTIME_REFRESH:
            runtimes = self._ops.service.runtime_inventory()
            return f"runtimes={len(runtimes.runtimes)} utilization={runtimes.utilization}"
        if operation == REPLAY_VERIFICATION:
            replay = self._ops.service.replay_inventory()
            return f"sessions={len(replay.sessions)} events={replay.total_events}"
        return f"unknown operation '{operation}'"
