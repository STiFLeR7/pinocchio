"""``nexus_approval`` — the Constitutional Approval Exchange (P15).

The sole constitutional owner of approval **coordination**. Execution Actuation already pauses at an
approval boundary (a gated node left WAITING); the Approval Exchange completes the governance loop —
publishing the approval request, awaiting the operator decision, recording it as immutable audit (durable
``approval.*`` facts, producer ``approval_exchange``), and, on approval, resuming execution by re-driving
the Constitutional Pipeline with the now-granted gate. It owns the deterministic lifecycle
``Requested → Pending → Approved | Denied | Expired`` and nothing else: it never evaluates policy (INV-28),
executes (INV-23), plans, reasons, validates, or recovers.

Dependency direction is one-way: ``nexus_approval → {nexus_workflows.spine, nexus_core, nexus_infra}``; it
imports no engine, introduces no contract/ADR/invariant, and modifies no owner. Replay reconstructs the
identical approval history and a restart resumes an in-flight approval wait (INV-13/14/18).
"""

from __future__ import annotations

from nexus_approval.composition import build_approval_exchange
from nexus_approval.events import (
    APPROVAL_APPROVED,
    APPROVAL_DENIED,
    APPROVAL_EXPIRED,
    APPROVAL_PENDING,
    APPROVAL_PRODUCER,
    APPROVAL_REQUESTED,
)
from nexus_approval.exchange import ApprovalExchange
from nexus_approval.model import (
    ApprovalDecision,
    ApprovalExplanation,
    ApprovalLifecycle,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalSession,
)
from nexus_approval.session import reconstruct_approval_session

__version__ = "2.5.0"

__all__ = [
    "APPROVAL_APPROVED",
    "APPROVAL_DENIED",
    "APPROVAL_EXPIRED",
    "APPROVAL_PENDING",
    "APPROVAL_PRODUCER",
    "APPROVAL_REQUESTED",
    "ApprovalDecision",
    "ApprovalExchange",
    "ApprovalExplanation",
    "ApprovalLifecycle",
    "ApprovalOutcome",
    "ApprovalRequest",
    "ApprovalSession",
    "build_approval_exchange",
    "reconstruct_approval_session",
]
