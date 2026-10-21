"""Identifier factories implementing ``nexus_core.events.IdentifierFactory``.

Identity generation is a side effect (a source of uniqueness), so the foundation
defines only the interface. Production uses UUIDs; tests inject the deterministic
factory so generated identifiers — which are captured *as recorded data* on every
Event — are reproducible across runs (supporting deterministic replay, INV-17).
"""

from __future__ import annotations

import uuid


class UuidIdentifierFactory:
    """Production factory: RFC-4122 v4 identifiers, prefixed by kind."""

    def new_event_identifier(self) -> str:
        return f"evt-{uuid.uuid4()}"

    def new_correlation_identifier(self) -> str:
        return f"cor-{uuid.uuid4()}"

    def new_execution_identifier(self) -> str:
        return f"exe-{uuid.uuid4()}"


class DeterministicIdentifierFactory:
    """Test factory: monotonic, reproducible identifiers per kind.

    Not for production — identifiers are predictable. Useful for replay/property
    tests that must produce byte-identical event streams across runs.
    """

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix
        self._counters: dict[str, int] = {"evt": 0, "cor": 0, "exe": 0}

    def _next(self, kind: str) -> str:
        self._counters[kind] += 1
        return f"{self._prefix}{kind}-{self._counters[kind]:08d}"

    def new_event_identifier(self) -> str:
        return self._next("evt")

    def new_correlation_identifier(self) -> str:
        return self._next("cor")

    def new_execution_identifier(self) -> str:
        return self._next("exe")
