"""Thin Human Interaction -- the minimum reusable governed-approval capability (A1).

This is *not* the full Human Interaction subsystem (`docs/v2/human_interaction/`). It is the thinnest
reusable core that proves one real governed approval loop, mirroring the fail-closed governance v1
already ships (`nexus/approvals/service.py::evaluate_approval` -- A-001):

* **fail-closed** -- no authorization, no/late/ambiguous answer never grants (INV-30);
* **authority-bound** -- only the named authority (owner) may grant (v1 owner-id semantics);
* **idempotent** -- a duplicate answer returns the settled outcome, never re-acts (INV-16);
* **late-safe** -- an answer arriving after the gate closed is ignored, never flips it;
* **correlated + audited** -- every step is a correlated `interaction.*` event (INV-39).

Channels are pluggable: the same governed core is driven by a CLI/operator channel (a real human via
the operator surface) or a Discord channel that *bridges* v1's proven Discord delivery -- adding a
channel is an adapter, never a change to this core (the Human Interaction thesis).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ApprovalOutcome(StrEnum):
    """The closed set of settled outcomes for one governed approval."""

    GRANTED = "granted"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    IGNORED_LATE = "ignored_late"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """An immutable request for a human decision before a dangerous operation."""

    correlation_id: str
    operation: str
    detail: str
    authority: str  # the identity/role permitted to answer (v1 owner-id concept)
    taxonomy: str = "human_review"


@dataclass(frozen=True, slots=True)
class ApprovalResponse:
    """A human's recorded answer (captured once as data -- INV-17)."""

    correlation_id: str
    granted: bool
    approver: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    """One correlated audit event in the approval's life (INV-39)."""

    type: str
    correlation_id: str
    payload: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class ApprovalChannel(Protocol):
    """Delivers a request to a human and collects the answer (None == no answer / timeout)."""

    name: str

    def deliver_and_collect(self, request: ApprovalRequest) -> ApprovalResponse | None:
        """Present ``request`` on this channel and return the human's answer, or None on timeout."""
        ...


@dataclass
class _Record:
    request: ApprovalRequest
    outcome: ApprovalOutcome | None = None
    response: ApprovalResponse | None = None


class ApprovalGateway:
    """Channel-agnostic governed approval: fail-closed, authority-bound, idempotent, late-safe.

    Holds a per-correlation ledger so duplicate and late answers are handled deterministically.
    Emits correlated ``interaction.*`` events through an optional sink and records them for audit.
    """

    def __init__(self, *, emitter: Callable[[InteractionEvent], None] | None = None) -> None:
        self._records: dict[str, _Record] = {}
        self._events: list[InteractionEvent] = []
        self._emitter = emitter

    @property
    def events(self) -> tuple[InteractionEvent, ...]:
        return tuple(self._events)

    def request_approval(
        self, request: ApprovalRequest, channel: ApprovalChannel
    ) -> ApprovalOutcome:
        """Run one governed loop: emit, deliver, collect, settle (fail-closed)."""
        record = self._records.get(request.correlation_id)
        if record is not None and record.outcome is not None:
            return record.outcome  # idempotent: already settled, never re-deliver
        self._records[request.correlation_id] = _Record(request)
        self._record_event(
            "interaction.requested",
            request.correlation_id,
            {"operation": request.operation, "channel": channel.name},
        )
        response = channel.deliver_and_collect(request)
        return self._settle(request.correlation_id, response)

    def submit(self, response: ApprovalResponse) -> ApprovalOutcome:
        """Settle an out-of-band answer (async channels, duplicate/late arrivals)."""
        return self._settle(response.correlation_id, response)

    def time_out(self, correlation_id: str) -> ApprovalOutcome:
        """Force-close a pending gate as fail-closed timeout."""
        return self._settle(correlation_id, None)

    def outcome_of(self, correlation_id: str) -> ApprovalOutcome | None:
        record = self._records.get(correlation_id)
        return record.outcome if record is not None else None

    # -- settlement (the one place an outcome is decided) -------------------- #

    def _settle(self, correlation_id: str, response: ApprovalResponse | None) -> ApprovalOutcome:
        record = self._records.get(correlation_id)
        if record is None:
            # An answer for an unknown/never-opened gate -> ignored late (never grants).
            self._record_event("interaction.ignored_late", correlation_id, {})
            return ApprovalOutcome.IGNORED_LATE
        if record.outcome is not None:
            # Already settled: duplicate is idempotent; a late answer cannot flip a closed gate.
            self._record_event(
                "interaction.duplicate_ignored",
                correlation_id,
                {"settled_as": record.outcome.value},
            )
            return record.outcome
        if response is None:
            record.outcome = ApprovalOutcome.TIMED_OUT
            self._record_event("interaction.timed_out", correlation_id, {})
            return record.outcome
        if response.correlation_id != correlation_id:
            record.outcome = ApprovalOutcome.DENIED
            self._record_event(
                "interaction.responded",
                correlation_id,
                {"granted": False, "reason": "correlation mismatch"},
            )
            return record.outcome
        # Fail-closed authority binding (v1 A-001 owner semantics).
        if response.approver != record.request.authority:
            record.outcome = ApprovalOutcome.DENIED
            self._record_event(
                "interaction.responded",
                correlation_id,
                {"granted": False, "reason": f"unauthorized approver '{response.approver}'"},
            )
            return record.outcome
        record.response = response
        record.outcome = ApprovalOutcome.GRANTED if response.granted else ApprovalOutcome.DENIED
        self._record_event(
            "interaction.responded",
            correlation_id,
            {"granted": response.granted, "approver": response.approver, "reason": response.reason},
        )
        return record.outcome

    def _record_event(
        self, event_type: str, correlation_id: str, payload: dict[str, object]
    ) -> None:
        event = InteractionEvent(type=event_type, correlation_id=correlation_id, payload=payload)
        self._events.append(event)
        if self._emitter is not None:
            self._emitter(event)


# --------------------------------------------------------------------------- #
# Channel adapters
# --------------------------------------------------------------------------- #


class CallableApprovalChannel:
    """A channel whose answer is produced by an injected callable.

    This is the reusable seam for a **real** operator decision: the Claude Code operator relays the
    request to the human and feeds the human's real answer back through the callable. It is also the
    deterministic seam for tests (approve / reject / timeout fakes). It is NOT a mock of the human --
    the callable returns whatever real answer it is given.
    """

    def __init__(
        self,
        responder: Callable[[ApprovalRequest], ApprovalResponse | None],
        *,
        name: str = "operator-cli",
    ) -> None:
        self._responder = responder
        self.name = name

    def deliver_and_collect(self, request: ApprovalRequest) -> ApprovalResponse | None:
        return self._responder(request)


def parse_discord_decision(
    messages: list[dict[str, object]], *, correlation_id: str, authority_id: str
) -> ApprovalResponse | None:
    """Pure decision parser over Discord channel messages (bridged v1 delivery; no network).

    Looks for a message authored by ``authority_id`` (the owner) that references ``correlation_id``
    and contains ``approve`` or ``reject``. Fail-closed: anything ambiguous returns None. This is the
    testable heart of the Discord channel -- the network transport is a thin shell around it.
    """
    token = correlation_id.lower()
    for message in messages:
        author = message.get("author")
        author_id = author.get("id") if isinstance(author, dict) else None
        content = str(message.get("content", "")).lower()
        if str(author_id) != str(authority_id) or token not in content:
            continue
        if "approve" in content:
            return ApprovalResponse(
                correlation_id=correlation_id,
                granted=True,
                approver=str(authority_id),
                reason="approved via Discord",
            )
        if "reject" in content:
            return ApprovalResponse(
                correlation_id=correlation_id,
                granted=False,
                approver=str(authority_id),
                reason="rejected via Discord",
            )
    return None
