"""Goal — a normalized desired outcome plus metadata (never a procedure).

Contract: ``contracts/goal.md``. Owned by Intent Resolution. Binding: ADR-003.
Invariants: INV-08 (outcomes never procedures — the primary invariant here),
INV-07, INV-13/14/15, INV-20.

This module is the reference exemplar for domain models: frozen ``DomainObject``,
``tuple`` for sequences, ``Reference`` for by-id pointers, a ``LIFECYCLE_NAME``
class var tying it to ``nexus_core.state``, and a nested frozen ``ValueObject``
(``Scope``) for composed structures.
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import Constraint, Correlation, DomainObject, Struct, ValueObject
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.contracts.status import GoalStatus


class Scope(ValueObject):
    """The authoritative, closed boundary of a Goal: what is in and out of scope."""

    included: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()


class Goal(DomainObject):
    """A desired operational outcome (contract: goal.md). Never describes steps."""

    LIFECYCLE_NAME: ClassVar[str] = "goal"

    # --- required ---------------------------------------------------------- #
    identity: str
    outcome: str
    """Declarative desired-outcome statement (a result, never a procedure) — locus of INV-08."""
    domain: Domain
    priority: Priority
    confidence: InterpretationConfidence
    """Intent Resolution's confidence in the normalized Goal (distinct from the Knowledge ladder)."""
    constraints: tuple[Constraint, ...]
    """Declared operational boundaries; always override execution preferences."""
    scope: Scope

    # --- optional ---------------------------------------------------------- #
    correlation: Correlation | None = None
    clarifications: tuple[Struct, ...] = ()
    source: Struct | None = None
    assumptions: tuple[str, ...] = ()
    rationale: str | None = None
    success_definition: str | None = None
    """Observable success-signal elaboration of ``outcome`` — still an outcome, never a procedure."""
    status: GoalStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001), optional until projected."""
