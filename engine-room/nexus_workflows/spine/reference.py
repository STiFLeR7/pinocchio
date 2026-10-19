"""The reference constitutional-pipeline run — one deterministic Goal→Knowledge request (text-first).

Mirrors :func:`nexus_workflows.reference.reference_request`, but starts from raw operator *text* (so
Intent Resolution produces the Goal) rather than a pre-built Goal. It exercises every constitutional
stage: two independent work items (two ready nodes → two execution episodes → enough for Reflection to
confirm a pattern and propose a Knowledge Candidate), each requiring the ``code_generation`` capability
the Claude runtime advertises. It introduces no new domain concept.
"""

from __future__ import annotations

from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CapabilityCategory, KnowledgeType
from nexus_core.domain import Capability
from nexus_planning import WorkItemSpec
from nexus_workflows.spine.model import SpineRequest

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


def spine_reference_request(
    *, run: str = "r1", fail: bool = False, gated: tuple[str, ...] = ()
) -> SpineRequest:
    """Build the canonical text-first :class:`SpineRequest` for one pipeline execution.

    ``gated`` names the work-item keys that require operator approval (P15) — the planner then marks
    those nodes as approval gates, so Actuation pauses at them until the Approval Exchange authorizes them.
    """
    identity = f"spine-arch-{run}"
    return SpineRequest(
        identity=identity,
        request_text=_REQUEST_TEXT,
        work_items=tuple(
            _work_item(key, requires_approval=key in gated) for key in _WORK_ITEM_KEYS
        ),
        knowledge_subject=KNOWLEDGE_SUBJECT,
        scope=f"spine-{identity}",
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
