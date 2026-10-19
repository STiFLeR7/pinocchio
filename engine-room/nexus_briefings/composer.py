"""BriefComposer — compose a :class:`~nexus_briefings.document.Brief` from a workflow run (M3).

The composer reads a :class:`~nexus_workflows.WorkflowRun` and reorganizes it into a briefing. It
composes each section from **validated artifacts, recovery outcomes, reflection reports, and
knowledge items** — and *never consumes raw runtime output directly*:

* the runtime's captured-output stream is explicitly excluded (:func:`_is_raw_output`);
* a section's deliverable artifacts are surfaced only when its Validation verdict is ``passed``;
* the substantiating evidence is the Validation engine's independently collected evidence, not the
  runtime's self-reported output.

The composer holds **no** validation, recovery, reflection, or knowledge logic; it only projects
what those engines already decided. Correlation is by *node*: for one run the execution, validation,
and recovery stages all appear in session order, and ``validation_decisions`` /
``recovery_decisions`` are index-aligned to that same order.
"""

from __future__ import annotations

from nexus_briefings.brieftype import BriefSection, BriefType
from nexus_briefings.document import Brief, BriefSectionView
from nexus_workflows import WorkflowRun

# The runtime's raw stdout capture. Milestone 3: a briefing is never composed from raw runtime
# output, only from the Validation evidence collected over it — so this stream is always excluded.
_RAW_OUTPUT_MARKER = "captured-output"


def _is_raw_output(identifier: str) -> bool:
    return _RAW_OUTPUT_MARKER in identifier


def _node(label: str) -> str:
    """The node a timeline stage ran for, e.g. ``execution:node-survey-signals`` → node id."""
    return label.split(":", 1)[1] if ":" in label else label


class _NodeOutcome:
    """The governed outcome for one node, correlated across execution/validation/recovery stages."""

    __slots__ = ("decision", "deliverables", "evidence", "recovery")

    def __init__(
        self,
        decision: str,
        recovery: str,
        deliverables: tuple[str, ...],
        evidence: tuple[str, ...],
    ) -> None:
        self.decision = decision
        self.recovery = recovery
        self.deliverables = deliverables
        self.evidence = evidence


class BriefComposer:
    """Projects a workflow run into a briefing, from validated evidence only (Milestone 3)."""

    def compose(self, brief_type: BriefType, runtime_identity: str, run: WorkflowRun) -> Brief:
        """Compose the :class:`Brief` for ``brief_type`` from the governed outcomes of ``run``."""
        outcomes = self._outcomes_by_node(run)
        sections = tuple(
            _section_view(section, outcomes.get(f"node-{section.key}"))
            for section in brief_type.sections
        )
        return Brief(
            brief_type=brief_type.key,
            title=brief_type.title,
            subject=brief_type.subject,
            runtime_identity=runtime_identity,
            sections=sections,
            findings=run.reflection_candidates,
            knowledge_item_ids=run.knowledge_item_ids,
            knowledge_consumed=run.knowledge_consumed,
        )

    def _outcomes_by_node(self, run: WorkflowRun) -> dict[str, _NodeOutcome]:
        exec_by_node = {
            _node(stage.label): stage
            for stage in run.timeline.stages
            if stage.engine == "execution"
        }
        validation_stages = [s for s in run.timeline.stages if s.engine == "validation"]
        outcomes: dict[str, _NodeOutcome] = {}
        for index, stage in enumerate(validation_stages):
            node = _node(stage.label)
            decision = _at(run.validation_decisions, index)
            recovery = _at(run.recovery_decisions, index)
            exec_stage = exec_by_node.get(node)
            deliverables = tuple(
                ref.identifier
                for ref in (exec_stage.artifact_refs if exec_stage is not None else ())
                if not _is_raw_output(ref.identifier)
            )
            evidence = tuple(ref.identifier for ref in stage.artifact_refs)
            outcomes[node] = _NodeOutcome(decision, recovery, deliverables, evidence)
        return outcomes


def _at(decisions: tuple[str, ...], index: int) -> str:
    return decisions[index] if index < len(decisions) else "unknown"


def _section_view(section: BriefSection, outcome: _NodeOutcome | None) -> BriefSectionView:
    if outcome is None:
        return BriefSectionView(
            key=section.key,
            heading=section.heading,
            decision="absent",
            validated_artifacts=(),
            evidence_refs=(),
            recovery_decision="none",
        )
    validated = outcome.decision == "passed"
    return BriefSectionView(
        key=section.key,
        heading=section.heading,
        decision=outcome.decision,
        # Gate on the Validation verdict: only validated deliverables enter the brief (M3).
        validated_artifacts=outcome.deliverables if validated else (),
        evidence_refs=outcome.evidence,
        recovery_decision=outcome.recovery,
    )
