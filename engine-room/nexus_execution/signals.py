"""Runtime signals — the ordered facts an adapter surfaces while driving a Work Package.

An adapter's ``execute`` generator yields a stream of these **provider-independent**
signals (doc 03 concerns D/E/F/H). The Execution Engine consumes them in order, records
each as a canonical ``runtime.*`` event (doc 15), and folds the terminal signal into the
session's lifecycle (doc 07). Signals carry no provider vocabulary — the adapter has
already performed the semantic normalization (doc 22 §3); the engine only records facts.

Signals are small, frozen, engine-internal values (never persisted, never an event
payload), so plain dataclasses suffice — the by-reference discipline (INV-12, ADR-003)
applies to what becomes an *event* or *evidence*, which the engine controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nexus_core.contracts.base import Reference


class StreamChannel(StrEnum):
    """The stream an output chunk came from (doc 08)."""

    STDOUT = "stdout"
    STDERR = "stderr"
    STRUCTURED = "structured"


class TerminalOutcome(StrEnum):
    """How a runtime *process* ended — not whether the work was validated (INV-20)."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class OutputSignal:
    """A stdout/stderr/structured chunk the adapter surfaced (concern D, doc 08)."""

    channel: StreamChannel
    text: str


@dataclass(frozen=True, slots=True)
class ProgressSignal:
    """A progress update; ``fraction is None`` is the honest 'unknown' (concern E, doc 12)."""

    phase: str
    fraction: float | None = None
    milestone: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactSignal:
    """An Evidence Candidate referenced by id — never by content (concern F, doc 13)."""

    artifact_ref: Reference
    kind: str


@dataclass(frozen=True, slots=True)
class TerminalSignal:
    """The runtime process ended; ``error_class`` is set only when ``outcome`` is FAILED."""

    outcome: TerminalOutcome
    exit_status: int | None = None
    detail: str | None = None
    error_class: str | None = None


RuntimeSignal = OutputSignal | ProgressSignal | ArtifactSignal | TerminalSignal
