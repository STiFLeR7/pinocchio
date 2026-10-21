"""Intent Resolution value objects — the Understand capability's inputs and outputs.

Intent Resolution owns understanding *what the operator wants* (`docs/v2/16`; frozen
``contracts/intent.md``). Its canonical artifact is the **frozen** :class:`~nexus_core.domain.intent.Intent`
(the one schema for an operator request / resolved intent — INV-07) and, when resolved, a frozen
:class:`~nexus_core.domain.goal.Goal`. This module adds no competing representation of intent: the
:class:`IntentAnalysis` result **bundles** those frozen objects (the way ``PlanningResult`` bundles
``Plan``/graph), and :class:`ClarificationRequest` is the *typed* form of the entries the frozen
Intent already carries as open ``clarification_requests`` Structs.

Every output is immutable and deterministic (identical request → identical analysis → identical id).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from nexus_core.contracts.base import ValueObject
from nexus_core.contracts.enums import InterpretationConfidence, Modality
from nexus_core.domain.goal import Goal
from nexus_core.domain.intent import Intent


class ClarificationKind(StrEnum):
    """Why a clarification is needed (drives the request, never the resolution)."""

    AMBIGUITY = "ambiguity"
    MISSING_INFORMATION = "missing_information"
    CONFLICT = "conflict"


class ClarificationRequest(ValueObject):
    """An immutable request for operator clarification — *emitted*, never handled here.

    Intent Resolution identifies insufficiency and emits these; Human Interaction (a later
    program) reaches the operator. This object is the typed form of an entry the frozen Intent
    carries in ``clarification_requests`` (INV-07: it types the open Struct, it adds no schema).
    """

    identity: str
    kind: ClarificationKind
    subject: str
    question: str
    reason: str


class IntentConfidence(ValueObject):
    """The confidence assessment of one interpretation (the canonical level + an explainable score)."""

    level: InterpretationConfidence
    score: float
    factors: tuple[str, ...] = ()


class IntentAnalysis(ValueObject):
    """The result of one resolution: the frozen Intent, the Goal (if resolved), and clarifications.

    A bundle (not a new schema): ``intent`` is the canonical frozen object; ``goal`` is present
    only when the interpretation resolved (no blocking clarification — "clarification preferred over
    incorrect execution"). ``interaction_required`` flips when clarification is needed.
    """

    identity: str
    correlation_identifier: str
    interpreter_version: str
    intent: Intent
    goal: Goal | None
    clarifications: tuple[ClarificationRequest, ...]
    confidence: IntentConfidence
    interaction_required: bool
    resolved: bool
    operator_preferences: Mapping[str, str] = {}
    """Extracted operator preferences (bias only) — consumed read-only by Engineering Intelligence."""
    reasoning_trace: tuple[str, ...] = ()
    """Explicit operator-declared work steps, captured as data for Planning to assemble."""
    declared_steps: tuple[Mapping[str, Any], ...] = ()
    timestamp: str = ""


@dataclass(frozen=True, slots=True)
class IntentRequest:
    """The immutable input to Intent Resolution: a raw operator request in some modality.

    The engine is a pure function of this request and the interpreter version — identical request →
    identical analysis. ``source`` is opaque provenance (which operator/surface), captured as data.
    """

    identity: str
    raw_request: str
    modality: Modality = Modality.NATURAL_LANGUAGE
    correlation_identifier: str = ""
    source: Mapping[str, Any] | None = None
    provided_priority: str | None = None

    def normalized(self) -> dict[str, Any]:
        """A deterministic, JSON-safe digest of the request for the analysis identity."""
        return {
            "identity": self.identity,
            "raw_request": self.raw_request,
            "modality": self.modality.value,
            "correlation": self.correlation_identifier,
            "priority": self.provided_priority or "",
        }


# convenience default for callers that only have a bare string
def request_from_text(
    identity: str,
    text: str,
    *,
    correlation_identifier: str = "",
    source: Mapping[str, Any] | None = None,
) -> IntentRequest:
    """Build a natural-language :class:`IntentRequest` from raw text."""
    return IntentRequest(
        identity=identity,
        raw_request=text,
        correlation_identifier=correlation_identifier or identity,
        source=source,
    )
