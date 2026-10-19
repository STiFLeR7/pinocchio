"""The reference workflow -- one deterministic Goal->Knowledge run (Milestone 2).

Builds a canonical :class:`WorkflowRequest` that exercises **every** implemented layer: a Goal to
"Generate a technical architecture summary", decomposed into two independent work items (so both
become ready nodes and yield two operational episodes -- enough for Reflection to confirm a pattern
and propose a Knowledge Candidate), each requiring the ``code_generation`` capability the Claude
runtime advertises. It introduces no new domain concept; every object is an existing engine value.

``run`` distinguishes the Goal identity per execution (so two runs on independent event logs never
collide) while keeping one shared Knowledge ``subject`` (so learning from run 1 is retrievable in
run 2). ``fail`` selects the failing runtime path for failure-scenario validation (Milestone 6).
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
from nexus_workflows.request import WorkflowRequest

CODE_GENERATION = "code_generation"
KNOWLEDGE_SUBJECT = "architecture summary generation"
_WORK_ITEM_KEYS = ("draft", "review")


def _capability() -> Capability:
    return Capability(
        identifier=CODE_GENERATION,
        name="Code Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="generate and revise technical content",
        inputs=(),
        outputs=(),
    )


def _skill(key: str) -> Skill:
    return Skill(
        identity=f"skill-{key}",
        name=f"Skill {key.title()}",
        version="1",
        purpose=f"perform the {key} step",
        inputs=(),
        outputs=(),
        procedure={},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(Reference(target_type="capability", identifier=CODE_GENERATION),),
    )


def _work_item(key: str) -> WorkItemSpec:
    return WorkItemSpec(
        key=key,
        objective=f"{key} the technical architecture summary",
        capability_requirements=(CODE_GENERATION,),
        skill_refs=(Reference(target_type="skill", identifier=f"skill-{key}"),),
    )


def reference_request(*, run: str = "r1", fail: bool = False) -> WorkflowRequest:
    """Build the canonical reference :class:`WorkflowRequest` for one execution."""
    goal_id = f"goal-arch-{run}"
    goal = Goal(
        identity=goal_id,
        outcome="Generate a technical architecture summary",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("architecture",), excluded=()),
    )
    return WorkflowRequest(
        goal=goal,
        work_items=tuple(_work_item(key) for key in _WORK_ITEM_KEYS),
        knowledge_subject=KNOWLEDGE_SUBJECT,
        scope=f"wf-{goal_id}",
        context_fragments=(
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.WORKSPACE,
                key="repository",
            ),
        ),
        capabilities=(_capability(),),
        skills=tuple(_skill(key) for key in _WORK_ITEM_KEYS),
        knowledge_kind=KnowledgeType.LESSON,
        fail=fail,
        correlation_identifier=f"cor-{goal_id}",
    )
