"""Execution timeline — the ordered sequence of authoritative facts (deterministic, by reference).

The timeline is a read-only projection: each in-scope event becomes one :class:`TimelineEntry` in the
log's global order. For very large logs the timeline is windowed to its most recent
:data:`TIMELINE_LIMIT` entries (recorded via ``timeline_truncated``) so the embedded profile stays
bounded — deterministic either way.

# ponytail: fixed tail window; widen or add position-range paging if long histories need the head.
"""

from __future__ import annotations

from collections.abc import Sequence

from nexus_core.domain.event import Event
from nexus_history.model import TimelineEntry

TIMELINE_LIMIT = 2000


def build_timeline(events: Sequence[Event]) -> tuple[tuple[TimelineEntry, ...], bool]:
    """The ordered timeline entries and whether it was windowed to the most recent entries."""
    truncated = len(events) > TIMELINE_LIMIT
    windowed = events[-TIMELINE_LIMIT:] if truncated else events
    offset = len(events) - len(windowed)
    entries = tuple(
        TimelineEntry(
            sequence=offset + i,
            type=e.type,
            correlation_identifier=e.correlation_identifier,
            producer=e.producer,
            timestamp=e.timestamp,
        )
        for i, e in enumerate(windowed)
    )
    return entries, truncated
