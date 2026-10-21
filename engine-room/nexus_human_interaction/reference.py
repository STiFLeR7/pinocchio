"""The reference operator request — one canonical operator submission for tests + demos."""

from __future__ import annotations

from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CapabilityCategory, KnowledgeType
from nexus_core.domain import Capability
from nexus_human_interaction.model import OperatorRequest
from nexus_planning import WorkItemSpec

CODE_GENERATION = "code_generation"
KNOWLEDGE_SUBJECT = "architecture summary generation"
_REQUEST_TEXT = "Generate a technical architecture summary for the repository"
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


def _work_item(key: str, *, requires_approval: bool = False) -> WorkItemSpec:
    return WorkItemSpec(
        key=key,
        objective=f"{key} the technical architecture summary",
        capability_requirements=(CODE_GENERATION,),
        skill_refs=(Reference(target_type="skill", identifier=f"skill-{key}"),),
        requires_approval=requires_approval,
    )


def reference_operator_request(
    *, run: str = "r1", fail: bool = False, gated: tuple[str, ...] = ()
) -> OperatorRequest:
    """Build the canonical operator request for one pipeline submission.

    ``gated`` names the work-item keys requiring operator approval (P15): those nodes become approval
    gates, so a submit pauses there until the operator approves/denies through the Human-Interaction surface.
    """
    identity = f"op-arch-{run}"
    return OperatorRequest(
        identity=identity,
        request_text=_REQUEST_TEXT,
        work_items=tuple(
            _work_item(key, requires_approval=key in gated) for key in _WORK_ITEM_KEYS
        ),
        knowledge_subject=KNOWLEDGE_SUBJECT,
        scope=f"op-{identity}",
        knowledge_kind=KnowledgeType.LESSON,
        context_fragments=(
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.WORKSPACE,
                key="repository",
            ),
        ),
        capabilities=(_capability(),),
        fail=fail,
        correlation_identifier=f"cor-{identity}",
    )
