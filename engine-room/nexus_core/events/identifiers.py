"""Identifier generation interface.

Event identity, correlation, and causation are stable strings (see the Event
model). Generating them requires a source of uniqueness, which is a side effect;
the foundation therefore defines only the *interface*. A later phase provides an
implementation (e.g. UUID-based). Keeping this an interface preserves
determinism in the pure foundation and lets tests inject deterministic factories.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IdentifierFactory(Protocol):
    """Produces the stable identifiers Events and correlation lineages require."""

    def new_event_identifier(self) -> str:
        """A globally unique Event identifier (the idempotency dedup key, INV-16)."""
        ...

    def new_correlation_identifier(self) -> str:
        """A new operation-wide correlation identifier (the causal-ordering boundary)."""
        ...

    def new_execution_identifier(self) -> str:
        """A new execution-session identifier."""
        ...
