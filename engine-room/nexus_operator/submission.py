"""GoalSubmission — an operator's plain description of a Goal (Milestone 1).

A :class:`GoalSubmission` is *what* an operator wants, expressed in operator terms: an outcome and
an ordered list of steps. It names no engine, no runtime, and no plan. The :func:`submission_request`
builder turns it into the platform ``WorkflowRequest`` the existing pipeline already knows how to
drive — a Goal, the Capability + Skills to register, and one declared Work Item per step. It
contains **no planning logic**: the decomposition into Work Packages and an Execution Graph is the
existing Planning engine's job (INV-04); this module only *declares* the steps.

Each step maps onto the existing ``code_generation`` capability every runtime advertises, so a
submitted Goal is eligible on any governed runtime without an adapter change.
"""

from __future__ import annotations

from dataclasses import dataclass

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

# The abstract capability an operator step requires — the existing ``code_generation`` capability
# the shipped runtimes advertise. Submitting a Goal adds no capability and no adapter change.
OPERATOR_CAPABILITY = "code_generation"


@dataclass(frozen=True, slots=True)
class GoalSubmission:
    """The immutable, operator-facing description of one Goal submission."""

    identifier: str
    outcome: str
    steps: tuple[str, ...]
    knowledge_subject: str
    scope_terms: tuple[str, ...] = ()
    corpus_key: str = "operations-corpus"


def reference_submission() -> GoalSubmission:
    """The canonical example: ship a small, validated feature increment."""
    return GoalSubmission(
        identifier="ship-feature",
        outcome="Ship a small, validated feature increment.",
        steps=("design the change", "implement the change", "verify the change"),
        knowledge_subject="feature delivery",
        scope_terms=("feature", "delivery"),
        corpus_key="delivery-corpus",
    )


def _capability() -> Capability:
    return Capability(
        identifier=OPERATOR_CAPABILITY,
        name="Code Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="generate and revise operational content",
        inputs=(),
        outputs=(),
    )


def _step_key(index: int) -> str:
    return f"step-{index}"


def _skill(index: int) -> Skill:
    key = _step_key(index)
    return Skill(
        identity=f"skill-{key}",
        name=f"Operator {key.replace('-', ' ').title()}",
        version="1",
        purpose=f"perform operator {key}",
        inputs=(),
        outputs=(),
        procedure={},
        category=SkillCategory.DEVELOPMENT,
        required_capabilities=(
            Reference(target_type="capability", identifier=OPERATOR_CAPABILITY),
        ),
    )


def _work_item(index: int, step: str) -> WorkItemSpec:
    key = _step_key(index)
    return WorkItemSpec(
        key=key,
        objective=step,
        capability_requirements=(OPERATOR_CAPABILITY,),
        skill_refs=(Reference(target_type="skill", identifier=f"skill-{key}"),),
    )


def submission_request(
    submission: GoalSubmission, *, run: str, fail: bool = False
) -> WorkflowRequest:
    """Assemble the deterministic ``WorkflowRequest`` for one Goal submission."""
    goal_id = f"goal-op-{submission.identifier}-{run}"
    goal = Goal(
        identity=goal_id,
        outcome=submission.outcome,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=submission.scope_terms or (submission.corpus_key,), excluded=()),
    )
    indexed = tuple(enumerate(submission.steps, start=1))
    return WorkflowRequest(
        goal=goal,
        work_items=tuple(_work_item(i, step) for i, step in indexed),
        knowledge_subject=submission.knowledge_subject,
        scope=f"operator-{goal_id}",
        context_fragments=(
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.WORKSPACE,
                key=submission.corpus_key,
            ),
        ),
        capabilities=(_capability(),),
        skills=tuple(_skill(i) for i, _ in indexed),
        knowledge_kind=KnowledgeType.LESSON,
        fail=fail,
        correlation_identifier=f"cor-{goal_id}",
    )
