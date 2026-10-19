"""Unit tests for the small Recovery building blocks — ids, policy, plan, events, wiring."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery import (
    DEFAULT_RECOVERY_POLICY,
    FailureCategory,
    RecoveryDecision,
    RecoveryObservability,
    RecoveryPolicy,
    RecoveryRuleOutcome,
    RetryPolicy,
    build_recovery,
    build_recovery_repositories,
    ids,
)
from nexus_recovery.events import RECOVERY_STARTED, build_event
from nexus_recovery.plan import RecoveryPlan, RecoveryRuleResult
from nexus_recovery.vocabulary import (
    RECOVERY_PLAN_TARGET_TYPE,
    RecoveryStage,
    RetryPolicyKind,
)
from nexus_runtime.events import FixedTimestampSource
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import execution_result, report

# --- ids -------------------------------------------------------------------- #


def test_ids_are_pure_functions_of_session() -> None:
    assert ids.plan_id("s1") == "rp-s1"
    assert ids.event_id("s1", "started", 0) == "evt-s1-rec-started-0000"
    assert ids.event_id("s1", "rule", 3) == "evt-s1-rec-rule-0003"


# --- policy ----------------------------------------------------------------- #


def test_retry_policy_enablement() -> None:
    assert RetryPolicy().retries_enabled is True
    assert RetryPolicy(kind=RetryPolicyKind.NEVER).retries_enabled is False
    assert RetryPolicy(max_attempts=1).retries_enabled is False


def test_default_policy_predicates() -> None:
    policy = DEFAULT_RECOVERY_POLICY
    assert policy.is_retryable(FailureCategory.RUNTIME) is True
    assert policy.is_retryable(FailureCategory.CONTEXT) is False
    assert policy.requires_approval(FailureCategory.GOVERNANCE) is True
    assert policy.requires_approval(FailureCategory.RUNTIME) is False
    assert policy.aborts_on(FailureCategory.RUNTIME) is False
    assert RecoveryPolicy(abort_on=(FailureCategory.RUNTIME,)).aborts_on(FailureCategory.RUNTIME)


# --- plan ------------------------------------------------------------------- #


def test_plan_reference_and_properties() -> None:
    rule_result = RecoveryRuleResult(
        rule_id="recovery_retry",
        outcome=RecoveryRuleOutcome.APPLICABLE,
        proposed_decision=RecoveryDecision.RETRY,
        rationale="retryable",
    )
    plan = RecoveryPlan(
        identity="rp-s1",
        decision=RecoveryDecision.RETRY,
        stage=RecoveryStage.RETRY,
        failure_category=FailureCategory.RUNTIME,
        session_ref=Reference(target_type="runtime_session", identifier="s1"),
        work_package_ref=Reference(target_type="work_package", identifier="wp"),
        validation_report_ref=Reference(target_type="validation_report", identifier="vr-s1"),
        rule_results=(rule_result,),
    )
    assert plan.reference() == Reference(target_type=RECOVERY_PLAN_TARGET_TYPE, identifier="rp-s1")
    assert plan.recovered is False
    assert plan.aborted is False


# --- events ----------------------------------------------------------------- #


def test_build_event_is_a_canonical_recovery_event() -> None:
    event = build_event("evt-s1-rec-started-0000", RECOVERY_STARTED, "cor", {"k": "v"}, "t")
    assert event.producer == "recovery"
    assert event.source == "nexus_recovery"
    assert event.type == RECOVERY_STARTED
    assert event.correlation_identifier == "cor"


# --- observability ---------------------------------------------------------- #


def test_observability_increments_named_counters() -> None:
    sink = InMemoryObservability()
    obs = RecoveryObservability(sink)
    obs.started()
    obs.rule_evaluated()
    obs.decision_created("retry")
    obs.completed()
    obs.failed()
    assert sink.counters["recovery.started"] == 1
    assert sink.counters["recovery.rule_evaluated"] == 1
    assert sink.counters["recovery.decision_created"] == 1
    assert sink.counters["recovery.decision.retry"] == 1
    assert sink.counters["recovery.completed"] == 1
    assert sink.counters["recovery.failed"] == 1


def test_observability_defaults_to_null_sink() -> None:
    RecoveryObservability().started()  # no sink → NullObservability, no error


# --- persistence + composition --------------------------------------------- #


def test_build_recovery_reuses_supplied_repositories() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    repos = build_recovery_repositories(infra.observability)
    ctx = build_recovery(infra, repositories=repos, timestamps=FixedTimestampSource())
    assert ctx.repositories is repos
    plan = ctx.engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert repos.plans.get(plan.identity) == plan


def test_build_recovery_defaults_wire_a_working_engine() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    ctx = build_recovery(infra)  # no timestamps → SystemTimestampSource
    plan = ctx.engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert plan.decision is RecoveryDecision.COMPLETE
    assert plan.timestamp  # a system timestamp was recorded
