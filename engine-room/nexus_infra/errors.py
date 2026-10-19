"""Infrastructure error hierarchy.

Distinct from :class:`nexus_core.validation.errors.ContractViolation` (which is a
*domain contract* failure). These errors are raised by the operational substrate
— the store, bus, projection engine, snapshot store, repositories, and unit of
work — when an infrastructure invariant is broken. Every error fails fast and
carries an explainable message (no silent correction).
"""

from __future__ import annotations


class InfrastructureError(Exception):
    """Base for every failure raised by the infrastructure layer."""


class ConcurrencyConflictError(InfrastructureError):
    """Optimistic-concurrency check failed: the expected version is stale.

    Raised when an append (or repository write) declares an expected version that
    no longer matches the current version — another writer advanced it first. The
    caller should re-read and retry; nothing was mutated (INV-13: the log is
    append-only and consistent).
    """

    def __init__(self, stream: str, expected: int, actual: int) -> None:
        self.stream = stream
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"concurrency conflict on {stream!r}: expected version {expected}, found {actual}"
        )


class DuplicateEventError(InfrastructureError):
    """An event identifier was re-appended with a *different* payload.

    Re-appending an *identical* event is idempotent (a no-op); re-using an
    identifier for a different fact is a programming error and corrupts the log.
    """

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"event identifier {identifier!r} already exists with different content")


class EventOrderingError(InfrastructureError):
    """An event's declared stream position is inconsistent with the stream."""


class IntegrityError(InfrastructureError):
    """A stored artifact failed its integrity check (content hash mismatch)."""


class SnapshotExpiredError(InfrastructureError):
    """A snapshot was requested past its declared expiry log position."""

    def __init__(self, snapshot_identifier: str, expires_at: int, current: int) -> None:
        self.snapshot_identifier = snapshot_identifier
        self.expires_at = expires_at
        self.current = current
        super().__init__(
            f"snapshot {snapshot_identifier!r} expired: valid through sequence "
            f"{expires_at}, current sequence {current}"
        )


class SnapshotNotFoundError(InfrastructureError):
    """No snapshot exists for the requested key."""


class UpcastError(InfrastructureError):
    """An event could not be upcast to the current schema version."""


class TransactionError(InfrastructureError):
    """A unit-of-work operation was used outside a valid transaction state."""


class DeadLetterError(InfrastructureError):
    """An event could not be delivered to a handler and was dead-lettered."""

    def __init__(self, event_identifier: str, cause: BaseException) -> None:
        self.event_identifier = event_identifier
        self.cause = cause
        super().__init__(f"event {event_identifier!r} dead-lettered: {cause}")
