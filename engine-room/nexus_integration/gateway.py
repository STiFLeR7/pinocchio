"""Correlation gateway — the transport seam for correlated cross-subsystem events (WP-P3.3).

The gateway carries correlated events across package boundaries **within the process**,
replacing direct coupling to a single :class:`~nexus_infra.event_bus.InProcessEventBus`.
It is **transport only, no logic** (guardrail against a god-object, INV-02): it forwards
each :class:`~nexus_core.domain.event.Event` to the wrapped emitter unchanged, so the
event's ``correlation_identifier`` (INV-39) is preserved end to end. It is
forward-compatible: swapping the wrapped emitter for an out-of-process transport later
changes nothing in the recording contract.
"""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter


class CorrelationGateway:
    """A correlation-preserving passthrough over an :class:`EventEmitter` (transport only)."""

    def __init__(self, emitter: EventEmitter) -> None:
        self._emitter = emitter

    def emit(self, event: Event) -> None:
        """Forward ``event`` to the wrapped emitter, preserving its correlation (INV-39)."""
        self._emitter.emit(event)
