"""P14/A — the constitutional learning loop (Knowledge → Engineering → Context → Planning).

End-to-end proof that prior Knowledge becomes an optional, governed, deterministic grounding input to a
future execution — flowing through Engineering and Context (INV-06), never directly into Planning
(INV-26), owned throughout by the Knowledge engine (read-only serve). Real engines, no mocks.
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request
from nexus_workflows.spine.learning import KNOWLEDGE_GROUNDING_ACTION


def _seed_run():
    """Run one execution so Knowledge is recorded; return the shared Knowledge repositories."""
    ctx = build_constitutional_pipeline(build_infrastructure())
    run = ctx.coordinator.run(spine_reference_request(run="r1"))
    return ctx.pipeline.knowledge.repositories, run


def test_first_execution_records_second_execution_consumes() -> None:
    repositories, run1 = _seed_run()
    assert run1.knowledge_grounding.consumed == 0  # nothing to learn from yet
    assert run1.knowledge_item_ids  # run one recorded Knowledge

    # Run two shares only the Knowledge store (learning flows across time via the record — INV-26).
    ctx2 = build_constitutional_pipeline(
        build_infrastructure(), knowledge_repositories=repositories
    )
    run2 = ctx2.coordinator.run(spine_reference_request(run="r2"))
    assert run2.knowledge_grounding.consumed >= 1  # run one's Knowledge grounded run two
    assert run2.knowledge_grounding.governed is True
    assert run2.succeeded  # the grounded run still reaches Knowledge, evidence-backed


def test_second_execution_grounding_is_deterministic() -> None:
    repositories, _ = _seed_run()

    def once():
        ctx = build_constitutional_pipeline(
            build_infrastructure(), knowledge_repositories=repositories
        )
        run = ctx.coordinator.run(spine_reference_request(run="r2"))
        return (
            run.plan_ref.identifier,
            run.execution_state.identity,
            run.knowledge_grounding.selected_ids,
        )

    assert once() == once()  # identical plan / state / grounding across independent runs


def test_governance_filters_grounding_in_the_pipeline() -> None:
    repositories, _ = _seed_run()
    ctx = build_constitutional_pipeline(build_infrastructure(), knowledge_repositories=repositories)
    # Register a higher-specificity deny — governance excludes the grounding (fail-closed-consistent).
    ctx.coordinator._policy.registry.register(
        Policy(
            identity="policy.knowledge.deny-grounding",
            version="1",
            purpose="deny grounding",
            conditions={"attr": "action_class", "op": "eq", "value": KNOWLEDGE_GROUNDING_ACTION},
            decision=PolicyDecision.DENY,
            priority=100,
            owner="governance",
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.GOVERNANCE,
            governed_action_class=KNOWLEDGE_GROUNDING_ACTION,
        )
    )
    run = ctx.coordinator.run(spine_reference_request(run="r2"))
    assert run.knowledge_grounding.consumed == 0  # governance filtered it out
    assert run.knowledge_grounding.governed is False and run.succeeded


def test_grounding_provenance_is_durable_and_references_only(tmp_path) -> None:
    repositories, _ = _seed_run()
    db = str(tmp_path / "ground.db")
    ctx = build_constitutional_pipeline(
        build_durable_infrastructure(db), knowledge_repositories=repositories
    )
    ctx.coordinator.run(spine_reference_request(run="r2"))

    events = build_durable_infrastructure(db).event_store.read_all()  # reopened file
    facts = [e for e in events if e.type == "pipeline.knowledge_grounded"]
    assert len(facts) == 1  # the grounding provenance is durable
    payload = facts[0].payload
    assert payload["count"] >= 1 and payload["references"]  # references-only provenance
    assert "items" not in payload  # never the Knowledge objects themselves


def test_learning_disabled_is_the_p13_driver() -> None:
    repositories, _ = _seed_run()
    ctx = build_constitutional_pipeline(
        build_infrastructure(), knowledge_repositories=repositories, learning=False
    )
    run = ctx.coordinator.run(spine_reference_request(run="r2"))
    assert run.knowledge_grounding is not None and run.knowledge_grounding.consumed == 0
    assert run.succeeded  # no grounding, still the full P13 Goal→Knowledge pipeline
    grounded = [e for e in run.events if e.type == "pipeline.knowledge_grounded"]
    assert grounded == []  # learning off → no grounding fact recorded
