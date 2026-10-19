"""The research brief — the structured deliverable projected from a workflow run.

The "Research Brief" the mission asks for is not a new artifact type: it is a *projection* of the
existing :class:`~nexus_workflows.WorkflowRun` into research terms — the sources gathered, the
briefing produced, the Validation evidence collected, the governed decisions, the reusable
findings Reflection surfaced, and the Knowledge persisted. It duplicates nothing (references by
id only, INV-27); it reads the run and reorganizes it for a research consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_research.topic import ResearchTopic
from nexus_workflows import WorkflowRun


@dataclass(frozen=True, slots=True)
class ResearchBrief:
    """A research-shaped view over one workflow run (all references, no duplicated content)."""

    subject: str
    question: str
    runtime_identity: str
    work_packages: tuple[str, ...]
    source_artifacts: tuple[str, ...]
    briefing_artifacts: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    validation_decisions: tuple[str, ...]
    recovery_decisions: tuple[str, ...]
    findings: tuple[str, ...]
    knowledge_item_ids: tuple[str, ...]
    knowledge_consumed: int

    @property
    def is_validated(self) -> bool:
        """Whether every research work package passed independent Validation (INV-20)."""
        return bool(self.validation_decisions) and all(
            decision == "passed" for decision in self.validation_decisions
        )

    @property
    def recovered(self) -> bool:
        """Whether any stage needed a governed recovery continuation (not a plain completion)."""
        return any(decision != "complete" for decision in self.recovery_decisions)

    @property
    def is_actionable(self) -> bool:
        """A brief is actionable when it is validated and produced a briefing artifact."""
        return self.is_validated and bool(self.briefing_artifacts)


def _phase_artifacts(artifact_ids: tuple[str, ...], phase_key: str) -> tuple[str, ...]:
    return tuple(a for a in artifact_ids if f"-{phase_key}-" in a)


def build_brief(topic: ResearchTopic, runtime_identity: str, run: WorkflowRun) -> ResearchBrief:
    """Project ``run`` into a :class:`ResearchBrief` for ``topic`` on ``runtime_identity``."""
    # Produced deliverables come from Execution stages; Validation evidence from Validation stages
    # — kept distinct so a phase's artifacts never conflate with the evidence that judged them.
    execution_artifacts = tuple(
        ref.identifier
        for stage in run.timeline.stages
        if stage.engine == "execution"
        for ref in stage.artifact_refs
    )
    evidence_refs = tuple(
        ref.identifier
        for stage in run.timeline.stages
        if stage.engine == "validation"
        for ref in stage.artifact_refs
    )
    return ResearchBrief(
        subject=topic.subject,
        question=topic.question,
        runtime_identity=runtime_identity,
        work_packages=run.work_package_ids,
        source_artifacts=_phase_artifacts(execution_artifacts, "gather-sources"),
        briefing_artifacts=_phase_artifacts(execution_artifacts, "generate-briefing"),
        evidence_refs=evidence_refs,
        validation_decisions=run.validation_decisions,
        recovery_decisions=run.recovery_decisions,
        findings=run.reflection_candidates,
        knowledge_item_ids=run.knowledge_item_ids,
        knowledge_consumed=run.knowledge_consumed,
    )
