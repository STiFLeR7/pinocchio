"""ResearchWorkflow — turn a research topic into a platform ``WorkflowRequest`` (Milestone 2).

This is the seam between a research *topic* and the existing end-to-end pipeline. It builds the
``nexus_workflows.WorkflowRequest`` the platform already knows how to drive — a research Goal, the
Capability and Skills to register, and one declared Work Item per research phase. It contains **no
planning logic**: the actual decomposition into Work Packages and an Execution Graph is the
existing Planning engine's job (INV-04); this module only *declares* the phases.

Every object is an existing ``nexus_core`` / engine value. ``run`` distinguishes the Goal identity
per execution (independent event logs) while the shared Knowledge ``subject`` carries learning
across runs (Milestone 6). ``fail`` selects the failing runtime path for failure injection
(Milestone 5).
"""

from __future__ import annotations

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
from nexus_research.topic import RESEARCH_CAPABILITY, ResearchPhase, ResearchTopic
from nexus_workflows import WorkflowRequest


def _capability() -> Capability:
    return Capability(
        identifier=RESEARCH_CAPABILITY,
        name="Code Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="generate and revise technical research content",
        inputs=(),
        outputs=(),
    )


def _skill(phase: ResearchPhase) -> Skill:
    return Skill(
        identity=f"skill-{phase.key}",
        name=f"Research {phase.key.replace('-', ' ').title()}",
        version="1",
        purpose=f"perform the {phase.key} research step",
        inputs=(),
        outputs=(),
        procedure={},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(
            Reference(target_type="capability", identifier=RESEARCH_CAPABILITY),
        ),
    )


def _work_item(phase: ResearchPhase, subject: str) -> WorkItemSpec:
    return WorkItemSpec(
        key=phase.key,
        objective=phase.objective(subject),
        capability_requirements=(RESEARCH_CAPABILITY,),
        skill_refs=(Reference(target_type="skill", identifier=f"skill-{phase.key}"),),
    )


class ResearchWorkflow:
    """Builds the platform ``WorkflowRequest`` for one research topic (no planning logic)."""

    def __init__(self, topic: ResearchTopic) -> None:
        self._topic = topic

    @property
    def topic(self) -> ResearchTopic:
        """The research topic this workflow is built from."""
        return self._topic

    def request(self, *, run: str = "r1", fail: bool = False) -> WorkflowRequest:
        """Assemble the deterministic ``WorkflowRequest`` for one research execution."""
        topic = self._topic
        goal_id = f"goal-research-{run}"
        goal = Goal(
            identity=goal_id,
            outcome=topic.question,
            domain=Domain.SOFTWARE,
            priority=Priority.HIGH,
            confidence=InterpretationConfidence.HIGH,
            constraints=(),
            scope=Scope(included=topic.scope_terms or (topic.corpus_key,), excluded=()),
        )
        return WorkflowRequest(
            goal=goal,
            work_items=tuple(_work_item(p, topic.subject) for p in topic.phases),
            knowledge_subject=topic.knowledge_subject,
            scope=f"research-{goal_id}",
            context_fragments=(
                RawContextFragment(
                    source=ContextSource.WORKSPACE,
                    category=ContextCategory.WORKSPACE,
                    key=topic.corpus_key,
                ),
            ),
            capabilities=(_capability(),),
            skills=tuple(_skill(p) for p in topic.phases),
            knowledge_kind=KnowledgeType.LESSON,
            fail=fail,
            correlation_identifier=f"cor-{goal_id}",
        )
