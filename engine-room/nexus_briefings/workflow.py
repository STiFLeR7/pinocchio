"""BriefingWorkflow — turn a brief type into a platform ``WorkflowRequest`` (Milestone 1/2).

This is the seam between a briefing *configuration* and the existing end-to-end pipeline. It builds
the ``nexus_workflows.WorkflowRequest`` the platform already knows how to drive — a briefing Goal,
the Capability and Skills to register, and one declared Work Item per section. It contains **no
planning logic**: the decomposition into Work Packages and an Execution Graph is the existing
Planning engine's job (INV-04); this module only *declares* the sections.

Every object is an existing ``nexus_core`` / engine value. ``run`` distinguishes the Goal identity
per generation (independent event logs) while the shared Knowledge ``subject`` carries learning
across generations (Milestone 5). ``fail`` selects the failing runtime path for failure injection.
"""

from __future__ import annotations

from nexus_briefings.brieftype import BRIEFING_CAPABILITY, BriefSection, BriefType
from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    CapabilityCategory,
    Domain,
    InterpretationConfidence,
    KnowledgeType,
    Priority,
    SkillCategory,
)
from nexus_core.domain import Capability, Goal, Scope
from nexus_core.domain.skill import Skill
from nexus_planning import WorkItemSpec
from nexus_workflows import WorkflowRequest


def _capability() -> Capability:
    return Capability(
        identifier=BRIEFING_CAPABILITY,
        name="Code Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="generate and revise technical briefing content",
        inputs=(),
        outputs=(),
    )


def _skill(section: BriefSection) -> Skill:
    return Skill(
        identity=f"skill-{section.key}",
        name=f"Brief {section.key.replace('-', ' ').title()}",
        version="1",
        purpose=f"perform the {section.key} briefing step",
        inputs=(),
        outputs=(),
        procedure={},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(
            Reference(target_type="capability", identifier=BRIEFING_CAPABILITY),
        ),
    )


def _work_item(section: BriefSection, subject: str) -> WorkItemSpec:
    return WorkItemSpec(
        key=section.key,
        objective=section.objective(subject),
        capability_requirements=(BRIEFING_CAPABILITY,),
        skill_refs=(Reference(target_type="skill", identifier=f"skill-{section.key}"),),
    )


class BriefingWorkflow:
    """Builds the platform ``WorkflowRequest`` for one brief type (no planning logic)."""

    def __init__(self, brief_type: BriefType) -> None:
        self._type = brief_type

    @property
    def brief_type(self) -> BriefType:
        """The brief type this workflow is built from."""
        return self._type

    def request(self, *, run: str = "b1", fail: bool = False) -> WorkflowRequest:
        """Assemble the deterministic ``WorkflowRequest`` for one briefing generation."""
        bt = self._type
        goal_id = f"goal-brief-{bt.key}-{run}"
        goal = Goal(
            identity=goal_id,
            outcome=bt.outcome,
            domain=Domain.SOFTWARE,
            priority=Priority.HIGH,
            confidence=InterpretationConfidence.HIGH,
            constraints=(),
            scope=Scope(included=bt.scope_terms or (bt.corpus_key,), excluded=()),
        )
        return WorkflowRequest(
            goal=goal,
            work_items=tuple(_work_item(s, bt.subject) for s in bt.sections),
            knowledge_subject=bt.knowledge_subject,
            scope=f"briefing-{goal_id}",
            context_fragments=(
                RawContextFragment(
                    source=ContextSource.WORKSPACE,
                    category=ContextCategory.WORKSPACE,
                    key=bt.corpus_key,
                ),
            ),
            capabilities=(_capability(),),
            skills=tuple(_skill(s) for s in bt.sections),
            knowledge_kind=KnowledgeType.LESSON,
            fail=fail,
            correlation_identifier=f"cor-{goal_id}",
        )
