"""``nexus_operations`` — the Constitutional Operations Plane (P15).

The sole constitutional owner of platform **observation** for operators: a read-only surface over the one
shared durable log. It projects active sessions, pipeline/execution status, the approval queue, and
runtime/replay/restart inventories; runs deterministic diagnostics; and derives a platform health summary
(recording it, optionally, as a durable ``operations.snapshot``). It **observes** — it never controls
execution, never mutates an engine, and produces no Supervision ``Observation`` domain object (INV-11).

Dependency direction is one-way: ``nexus_operations → {nexus_workflows.spine, nexus_approval, nexus_core,
nexus_infra}``; it imports no engine, introduces no contract/ADR/invariant, and modifies no owner.
"""

from __future__ import annotations

from nexus_operations.composition import OperationsContext, build_operations
from nexus_operations.diagnostics import DiagnosticsService
from nexus_operations.events import OPERATIONS_PRODUCER, OPERATIONS_SNAPSHOT
from nexus_operations.health import HealthInspector
from nexus_operations.model import (
    ApprovalQueueView,
    Diagnostics,
    ExecutionStatusView,
    HealthSummary,
    OperationsSnapshot,
    ReplayInventory,
    RestartInventory,
    RuntimeInventory,
    SessionSummary,
)
from nexus_operations.service import OperationsService

__version__ = "2.5.0"

__all__ = [
    "OPERATIONS_PRODUCER",
    "OPERATIONS_SNAPSHOT",
    "ApprovalQueueView",
    "Diagnostics",
    "DiagnosticsService",
    "ExecutionStatusView",
    "HealthInspector",
    "HealthSummary",
    "OperationsContext",
    "OperationsService",
    "OperationsSnapshot",
    "ReplayInventory",
    "RestartInventory",
    "RuntimeInventory",
    "SessionSummary",
    "build_operations",
]
