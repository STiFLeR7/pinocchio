"""The Diagnostics service — deterministic diagnostics over the one shared log (P15).

:class:`DiagnosticsService` observes only: it counts the durable log by producer and type and checks
structural consistency (every event names exactly one producer; identifiers are unique — INV-02/13). It
is a pure function of the log, so the same log yields the identical diagnostics.
"""

from __future__ import annotations

from collections import Counter

from nexus_core.domain.event import Event
from nexus_operations.model import Diagnostics
from nexus_workflows.spine import ConstitutionalPipeline


class DiagnosticsService:
    """Deterministic event diagnostics + a structural-consistency verdict (observation only)."""

    def __init__(self, pipeline: ConstitutionalPipeline) -> None:
        self._pipeline = pipeline

    def diagnostics(self) -> Diagnostics:
        """Count the log by producer and type and verify structural consistency (deterministic)."""
        events = self._pipeline.history()
        by_producer = Counter(event.producer for event in events)
        by_type = Counter(event.type for event in events)
        issues = tuple(self._issues(events))
        return Diagnostics(
            total_events=len(events),
            by_producer=tuple(sorted(by_producer.items())),
            by_type=tuple(sorted(by_type.items())),
            consistent=not issues,
            issues=issues,
        )

    @staticmethod
    def _issues(events: tuple[Event, ...]) -> list[str]:
        issues: list[str] = []
        if any(not event.producer for event in events):
            issues.append("event without a producer (INV-02)")
        identifiers = [event.identifier for event in events]
        if len(identifiers) != len(set(identifiers)):
            issues.append("duplicate event identifier on the log (INV-13)")
        return issues
