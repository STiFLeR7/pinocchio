"""Intent — a raw operator request plus its progressive interpretation.

Contract: ``contracts/intent.md``. Owned by Intent Resolution. Binding: ADR-003
(canonical object model), ADR-001 (event-sourced state). Invariants: INV-07,
INV-08 (an Intent carries a detected outcome, never a procedure/plan/runtime),
INV-13/14/15, INV-17, INV-39.

The Intent is the bridge object between natural human communication and the
deterministic ``goal.md``. It holds and progressively interprets an operator
request until it is resolved into a Goal or abandoned; it never plans, builds
context, selects runtimes, or executes.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import Correlation, DomainObject, Reference, Struct
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Modality, Priority
from nexus_core.contracts.status import IntentStatus


class Intent(DomainObject):
    """A raw operator request and its current interpretation (contract: intent.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "intent"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier; addressable and replayable for the platform's life."""
    correlation: Correlation
    """Correlation / trace lineage tying this Intent to its session and derived objects."""
    raw_request: str
    """The operator's request, preserved verbatim and modality-agnostic in meaning."""
    modality: Modality
    """The channel/form the request arrived in; must not change operational behavior."""
    detected_intent: str
    """Current interpretation of the desired outcome (a candidate objective, never a procedure)."""
    confidence: InterpretationConfidence
    """Confidence of the current interpretation; drives whether clarification is required."""

    # --- optional ---------------------------------------------------------- #
    status: IntentStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    ambiguity: tuple[Struct, ...] = ()
    """Detected ambiguities preventing confident resolution; absent when none detected."""
    clarification_requests: tuple[Struct, ...] = ()
    """Questions issued to the operator to resolve ambiguity, with each reason."""
    clarification_responses: tuple[Struct, ...] = ()
    """Operator answers received against prior clarification requests, recorded as data."""
    missing_information: tuple[str, ...] = ()
    """Information identified as absent but required to construct a confident Goal."""
    detected_domain: Domain | None = None
    """Provisional operational domain classification before it is finalized on the Goal."""
    priority_estimate: Priority | None = None
    """Provisional urgency estimate before it is finalized on the Goal."""
    assumptions: tuple[str, ...] = ()
    """Assumptions made during interpretation, recorded for explainability."""
    interpretation_rationale: str | None = None
    """Explanation of what was understood, assumed, missing, and why clarification was asked."""
    source: Struct | None = None
    """Provenance of the request (which operator, which surface/session)."""
    resolved_goal_ref: Reference | None = None
    """Reference (by id) to the Goal produced once Resolved; present only in the Resolved state."""
