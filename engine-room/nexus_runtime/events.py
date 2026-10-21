"""Runtime events — the ``runtime.*`` facts the Runtime Manager emits to the log.

Each fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="runtime"`` and ``source="nexus_runtime"`` and a deterministic identifier, so
a preparation cycle replays identically. The Runtime Session's lifecycle state is a
*projection* of this stream (ADR-001; doc 15). Timestamps are the one captured-as-data,
non-structural value (INV-17); their source is injected (:class:`TimestampSource`) so
tests are reproducible and the produced *value objects* (Sessions / Allocations) stay
timestamp-free and deterministic.

``TimestampSource`` is re-declared here (rather than imported from an earlier layer) to
keep the dependency direction clean: RM is downstream of Harness/Orchestration and never
depends on them for this primitive (doc 00 §4 — RM imports only ``nexus_core`` /
``nexus_infra``).

Event names are the canonical ``runtime.*`` taxonomy of doc 15. The *preparation* slice was
implemented in Phase 8A; the *execution/teardown* slice (``runtime.started`` …
``runtime.destroyed``) is realized by the Execution Engine phase (this vertical slice) —
these were canonical event names in doc 15 §2 all along, merely deferred in code. No new
event shape is coined: every name below is verbatim from doc 15 §2.
``runtime.registered`` is the one registry-plane event Phase 8A adds for registration
observability (doc 15 §2 enumerates session-scoped events only) — recorded as an
implementation observation in ``docs/v2/PHASE_8A_RUNTIME_CORE.md``, not a contract change.

The suspend/resume/heartbeat/approval events (``runtime.paused`` / ``runtime.waiting_approval``
/ ``runtime.resumed`` / ``runtime.heartbeat`` / ``runtime.checkpoint_captured``) remain
deferred with their ``Paused``/``Waiting`` states — the minimal Execution Engine drives none
of them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

RUNTIME_PRODUCER = "runtime"
RUNTIME_SOURCE = "nexus_runtime"
EVENT_VERSION = "1"

# --- canonical runtime.* taxonomy (doc 15 §2) ----------------------------------- #
# Preparation (Phase 8A).
RUNTIME_REGISTERED = "runtime.registered"
RUNTIME_DISCOVERED = "runtime.candidates_resolved"
RUNTIME_CAPABILITIES_MATCHED = "runtime.capabilities_matched"
RUNTIME_SESSION_CREATED = "runtime.session_created"
RUNTIME_ALLOCATED = "runtime.allocated"
RUNTIME_PREPARED = "runtime.prepared"
RUNTIME_READY = "runtime.ready"
RUNTIME_RELEASED = "runtime.released"
RUNTIME_FAILED = "runtime.failed"
# Execution + teardown (Execution Engine phase — this vertical slice).
RUNTIME_STARTED = "runtime.started"
RUNTIME_OUTPUT = "runtime.output"
RUNTIME_PROGRESS = "runtime.progress"
RUNTIME_ARTIFACT_EMITTED = "runtime.artifact_emitted"
RUNTIME_TIMED_OUT = "runtime.timed_out"
RUNTIME_COMPLETED = "runtime.completed"
RUNTIME_CANCELLED = "runtime.cancelled"
RUNTIME_DESTROYED = "runtime.destroyed"


@runtime_checkable
class TimestampSource(Protocol):
    """Supplies the ISO-8601 timestamp recorded on each emitted event."""

    def now(self) -> str: ...


class FixedTimestampSource:
    """Deterministic timestamp source for tests and reproducible cycles."""

    def __init__(self, value: str = "1970-01-01T00:00:00+00:00") -> None:
        self._value = value

    def now(self) -> str:
        return self._value


class SystemTimestampSource:
    """Production timestamp source — UTC wall clock, ISO-8601."""

    def now(self) -> str:
        return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    sequence_position: int | None = None,
    causation_identifier: str | None = None,
) -> Event:
    """Construct a canonical runtime Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=RUNTIME_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=RUNTIME_SOURCE,
        sequence_position=sequence_position,
        causation_identifier=causation_identifier,
    )
