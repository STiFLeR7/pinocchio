"""Grounding value models — the immutable inputs to and outputs of grounded assembly.

Every model here is a frozen value: :class:`GroundingInputs` is the read-only bundle of
upstream grounding/reasoning artifacts (consumed by value, never mutated), and
:class:`SelectionRecord` / :class:`GroundingSelection` are the deterministic, serializable
record of *what was selected and what was omitted, and why* — so the selection embeds in a
``context.grounding.selected`` fact and replays without re-selecting (INV-17).

The upstream artifacts are held by reference-to-object (they are themselves frozen value
objects — Goal, IntentAnalysis, RepositoryProfile, ExecutionHistoryProfile,
EngineeringStrategy, Knowledge). Grounding **reads** them; it owns and writes none of them.
All are absence-tolerant: a first-run goal has no history, a non-repository goal has no
profile, an un-reasoned goal has no strategy. Only the Goal is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus_context.requests import ContextResult
from nexus_core.contracts.base import Struct, ValueObject
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.goal import Goal
from nexus_core.domain.knowledge import Knowledge
from nexus_engineering.model import EngineeringStrategy
from nexus_history.model import ExecutionHistoryProfile
from nexus_intent.model import IntentAnalysis
from nexus_repository.profile import RepositoryProfile


@dataclass(frozen=True, slots=True)
class GroundingInputs:
    """The immutable, read-only bundle of grounding artifacts one assembly consumes.

    Only ``goal`` is required. Every other input is absence-tolerant — grounding degrades to
    exactly the facts it was given, never fails for a missing source, and records the absence
    as an explained omission.
    """

    goal: Goal
    intent: IntentAnalysis | None = None
    repository_profile: RepositoryProfile | None = None
    history_profile: ExecutionHistoryProfile | None = None
    engineering_strategy: EngineeringStrategy | None = None
    knowledge: tuple[Knowledge, ...] = field(default_factory=tuple)


class SelectionRecord(ValueObject):
    """One candidate grounding artifact and the full explanation of its selection verdict.

    Facts only — no scoring model, no confidence. Every field is deterministic and auditable:
    ``selected`` is the verdict; ``reason`` explains it (both inclusions *and* omissions carry
    a reason); ``relationship`` states how the artifact relates to the goal/objectives;
    ``priority`` is the deterministic integer rank; ``source`` names the producing subsystem.
    """

    artifact_type: str
    """adr | contract | invariant | architecture_doc | module | package | file |
    prior_execution | knowledge."""
    identifier: str
    source: str
    """repository | execution_history | knowledge | engineering_strategy | goal."""
    relationship: str
    priority: int
    selected: bool
    reason: str


class GroundingSelection(ValueObject):
    """The complete, deterministic selection verdict: what was included, what was omitted, why.

    Embeds in the ``context.grounding.selected`` fact so the selection is replayable without
    re-selecting. ``objectives`` records the context objectives (or goal-derived keywords) that
    drove the selection, for explainability of the *criteria* as well as the verdicts.
    """

    objectives: tuple[str, ...]
    keywords: tuple[str, ...]
    selected: tuple[SelectionRecord, ...]
    omitted: tuple[SelectionRecord, ...]

    def as_payload(self) -> Struct:
        """A JSON-safe view of the selection (part of the grounding fact payload)."""
        return {
            "objectives": list(self.objectives),
            "keywords": list(self.keywords),
            "selected": [dict(record.model_dump()) for record in self.selected],
            "omitted": [dict(record.model_dump()) for record in self.omitted],
        }


@dataclass(frozen=True, slots=True)
class GroundedContextResult:
    """The output of one grounded assembly: the incumbent result plus the selection record.

    ``package`` / ``items`` / ``conflicts`` come straight from the incumbent Context
    Engineering producer (the single owner of the Context Package); ``selection`` is the
    explainable grounding verdict this submodule contributed.
    """

    result: ContextResult
    selection: GroundingSelection

    @property
    def package(self) -> ContextPackage:
        """The one frozen Context Package (the P9 'ExecutionContext'), produced by the incumbent."""
        return self.result.package
