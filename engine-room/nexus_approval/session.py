"""Approval-session reconstruction — rebuild the approval history from the ``approval.*`` log.

The approval session is a projection (INV-13/14): its state is a pure function of the durable
``approval.*`` facts, so a reopened log reconstructs the identical approval history and a restart resumes
an in-flight approval wait. Reconstruction is deterministic — the last lifecycle fact per gate wins.
"""

from __future__ import annotations

from nexus_approval import events as aevents
from nexus_approval.model import ApprovalLifecycle, ApprovalRequest, ApprovalSession
from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event

_SESSION_TARGET_TYPE = "pipeline_session"


class _Trace:
    """Per-node lifecycle accumulator threaded across the ``approval.*`` stream."""

    __slots__ = (
        "decided_at",
        "decided_by",
        "expires_at",
        "reason",
        "requested_at",
        "state",
        "taxonomy",
    )

    def __init__(self) -> None:
        self.state = ApprovalLifecycle.REQUESTED
        self.taxonomy = ""
        self.requested_at = ""
        self.decided_at: str | None = None
        self.decided_by: str | None = None
        self.reason: str | None = None
        self.expires_at: str | None = None


def reconstruct_approval_session(events: tuple[Event, ...], session_id: str) -> ApprovalSession:
    """Rebuild one session's approval history from the ``approval.*`` stream (the log is truth)."""
    traces: dict[str, _Trace] = {}
    order: list[str] = []
    for event in events:
        if event.producer != aevents.APPROVAL_PRODUCER:
            continue
        if str(event.payload.get("session", "")) != session_id:
            continue
        node = str(event.payload.get("node", ""))
        trace = traces.get(node)
        if trace is None:
            trace = traces[node] = _Trace()
            order.append(node)
        _apply(trace, event)

    session_ref = Reference(target_type=_SESSION_TARGET_TYPE, identifier=session_id)
    requests = tuple(
        ApprovalRequest(
            node=node,
            session_ref=session_ref,
            taxonomy=traces[node].taxonomy,
            state=traces[node].state,
            requested_at=traces[node].requested_at,
            decided_at=traces[node].decided_at,
            decided_by=traces[node].decided_by,
            reason=traces[node].reason,
            expires_at=traces[node].expires_at,
        )
        for node in order
    )
    return ApprovalSession(identity=session_id, requests=requests)


def _apply(trace: _Trace, event: Event) -> None:
    payload = event.payload
    if event.type == aevents.APPROVAL_REQUESTED:
        trace.state = ApprovalLifecycle.REQUESTED
        trace.taxonomy = str(payload.get("taxonomy", ""))
        trace.requested_at = event.timestamp
        trace.expires_at = _opt(payload.get("expires_at"))
    elif event.type == aevents.APPROVAL_PENDING:
        trace.state = ApprovalLifecycle.PENDING
    elif event.type == aevents.APPROVAL_APPROVED:
        _decide(trace, ApprovalLifecycle.APPROVED, event)
    elif event.type == aevents.APPROVAL_DENIED:
        _decide(trace, ApprovalLifecycle.DENIED, event)
    elif event.type == aevents.APPROVAL_EXPIRED:
        _decide(trace, ApprovalLifecycle.EXPIRED, event)


def _decide(trace: _Trace, state: ApprovalLifecycle, event: Event) -> None:
    trace.state = state
    trace.decided_at = event.timestamp
    trace.decided_by = _opt(event.payload.get("decided_by"))
    trace.reason = _opt(event.payload.get("reason"))


def _opt(value: object) -> str | None:
    return None if value is None else str(value)
