"""P14/A unit — the deterministic, governed Knowledge selector."""

from __future__ import annotations

from nexus_core.contracts.enums import KnowledgeType, PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_infra import build_infrastructure
from nexus_knowledge import build_knowledge
from nexus_policy import build_policy
from nexus_workflows.spine.learning import (
    KNOWLEDGE_GROUNDING_ACTION,
    KnowledgeSelector,
    knowledge_grounding_baseline,
)
from tests.unit.nexus_engineering.fixtures import make_goal


def _selector(*, deny: bool = False) -> KnowledgeSelector:
    infra = build_infrastructure()
    knowledge = build_knowledge(infra)
    policy = build_policy(infra)
    policy.registry.register(knowledge_grounding_baseline())
    if deny:
        policy.registry.register(
            Policy(
                identity="policy.knowledge.deny-grounding",
                version="1",
                purpose="deny grounding for the test",
                conditions={
                    "attr": "action_class",
                    "op": "eq",
                    "value": KNOWLEDGE_GROUNDING_ACTION,
                },
                decision=PolicyDecision.DENY,
                priority=100,
                owner="governance",
                status=PolicyStatus.ENABLED,
                category=PolicyCategory.GOVERNANCE,
                governed_action_class=KNOWLEDGE_GROUNDING_ACTION,
            )
        )
    return KnowledgeSelector(knowledge.engine, policy.engine)


def _select(selector: KnowledgeSelector):
    return selector.select(
        goal=make_goal(), subject="architecture", kind=KnowledgeType.LESSON, correlation="cor1"
    )


def test_baseline_governs_grounding_on_and_is_explainable() -> None:
    selection = _select(_selector())
    assert selection.governed is True  # the allow-baseline admits grounding
    assert selection.decision == "allow"
    assert selection.reasoning  # every governed verdict is explainable (INV-31)


def test_a_deny_policy_filters_grounding_out() -> None:
    selection = _select(_selector(deny=True))
    assert selection.governed is False  # governance excluded the grounding
    assert selection.decision == "deny"
    assert selection.items == () and selection.references == ()  # nothing admitted


def test_selection_is_deterministic() -> None:
    selector = _selector()
    first, second = _select(selector), _select(selector)
    assert (first.governed, first.decision, first.selected_ids) == (
        second.governed,
        second.decision,
        second.selected_ids,
    )


def test_provenance_records_replayable_selection() -> None:
    selection = _select(_selector())
    provenance = selection.provenance()
    assert set(provenance) == {
        "subject",
        "kind",
        "governed",
        "decision",
        "reasoning",
        "references",
        "selected_ids",
        "count",
        "item_snapshots",
    }
    assert [item["identity"] for item in provenance["item_snapshots"]] == list(
        selection.selected_ids
    )
