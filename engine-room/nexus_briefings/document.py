"""The composed briefing document — the structured product projected from a workflow run.

A :class:`Brief` is not a new artifact type: it is a *projection* of the existing
:class:`~nexus_workflows.WorkflowRun` into briefing terms — one section per declared brief section,
each carrying the validated artifacts, the Validation evidence that substantiates it, and the
governed recovery decision; plus the reusable findings Reflection surfaced and the Knowledge the
run persisted / consumed. It duplicates nothing (references by id only, INV-27).

Crucially (Milestone 3) a section surfaces only **validated** artifacts and never the raw runtime
output — the composer that builds a :class:`Brief` excludes the runtime's captured-output stream
and gates deliverables on the Validation verdict.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BriefSectionView:
    """One composed section: what the governed pipeline validated for this part of the brief."""

    key: str
    heading: str
    decision: str
    validated_artifacts: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    recovery_decision: str

    @property
    def validated(self) -> bool:
        """Whether this section's work package passed independent Validation (INV-20)."""
        return self.decision == "passed"

    @property
    def is_present(self) -> bool:
        """Whether the section is both validated and carries a validated deliverable."""
        return self.validated and bool(self.validated_artifacts)


@dataclass(frozen=True, slots=True)
class Brief:
    """A briefing-shaped view over one workflow run (all references, no duplicated content)."""

    brief_type: str
    title: str
    subject: str
    runtime_identity: str
    sections: tuple[BriefSectionView, ...]
    findings: tuple[str, ...]
    knowledge_item_ids: tuple[str, ...]
    knowledge_consumed: int

    @property
    def validation_decisions(self) -> tuple[str, ...]:
        """The Validation verdict for each section, in section order."""
        return tuple(section.decision for section in self.sections)

    @property
    def recovery_decisions(self) -> tuple[str, ...]:
        """The governed recovery decision for each section, in section order."""
        return tuple(section.recovery_decision for section in self.sections)

    @property
    def is_validated(self) -> bool:
        """Whether every section passed independent Validation."""
        return bool(self.sections) and all(section.validated for section in self.sections)

    @property
    def recovered(self) -> bool:
        """Whether any section needed a governed recovery continuation (not a plain completion)."""
        return any(decision != "complete" for decision in self.recovery_decisions)

    @property
    def is_publishable(self) -> bool:
        """A brief is publishable only when every section is validated and carries a deliverable."""
        return self.is_validated and all(section.validated_artifacts for section in self.sections)
