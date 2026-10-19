"""Unit tests for the small Validation modules: vocabulary, ids, evidence, report,
events, observability, persistence, composition."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_validation import (
    Evidence,
    RuleResult,
    ValidationDecision,
    ValidationReport,
    ValidationStage,
    build_validation,
    build_validation_repositories,
    ids,
)
from nexus_validation import events as vevents
from nexus_validation.observability import ValidationObservability
from nexus_validation.vocabulary import EvidenceSource, RuleOutcome

# --- vocabulary ------------------------------------------------------------- #


def test_decision_vocabulary_is_doc14_canon() -> None:
    assert {d.value for d in ValidationDecision} == {
        "passed",
        "failed",
        "partial",
        "requires_review",
    }


def test_evidence_sources_present() -> None:
    assert EvidenceSource.ARTIFACT.value == "artifact"
    assert EvidenceSource.EXECUTION_METRIC.value == "execution_metric"


def test_rule_outcomes_present() -> None:
    assert {o.value for o in RuleOutcome} == {
        "satisfied",
        "violated",
        "insufficient_evidence",
        "partial",
        "not_applicable",
    }


# --- ids -------------------------------------------------------------------- #


def test_ids_are_deterministic_pure_functions() -> None:
    assert ids.report_id("s") == "vr-s"
    assert ids.evidence_id("s", "artifact", 3) == "ev-s-artifact-0003"
    assert ids.event_id("s", "started", 0) == "evt-s-val-started-0000"


def test_validation_event_ids_carry_val_marker() -> None:
    # Guarantees no collision with runtime's evt-<session>-<kind> ids in the shared store.
    assert "-val-" in ids.event_id("s", "rule", 1)


# --- evidence --------------------------------------------------------------- #


def test_evidence_reference_is_by_id() -> None:
    ev = Evidence(identity="ev-1", source=EvidenceSource.ARTIFACT, kind="file")
    assert ev.reference() == Reference(target_type="evidence", identifier="ev-1")


def test_evidence_is_immutable() -> None:
    ev = Evidence(identity="ev-1", source=EvidenceSource.STDOUT, kind="stdout")
    try:
        ev.kind = "x"  # type: ignore[misc]
    except (ValueError, AttributeError, TypeError):
        return
    raise AssertionError("Evidence must be immutable")


# --- report ----------------------------------------------------------------- #


def _report(decision: ValidationDecision) -> ValidationReport:
    return ValidationReport(
        identity="vr-s",
        decision=decision,
        stage=ValidationStage.PASSED,
        confidence=1.0,
        session_ref=Reference(target_type="runtime_session", identifier="s"),
        work_package_ref=Reference(target_type="work_package", identifier="wp"),
        execution_result_ref=Reference(target_type="execution_result", identifier="s"),
    )


def test_report_passed_property() -> None:
    assert _report(ValidationDecision.PASSED).passed is True
    assert _report(ValidationDecision.FAILED).passed is False


def test_report_reference() -> None:
    assert _report(ValidationDecision.PASSED).reference().target_type == "validation_report"


def test_rule_result_holds_outcome_and_rationale() -> None:
    r = RuleResult(rule_id="x", outcome=RuleOutcome.SATISFIED, rationale="ok")
    assert r.outcome is RuleOutcome.SATISFIED


# --- events ----------------------------------------------------------------- #


def test_build_event_stamps_validation_provenance() -> None:
    event = vevents.build_event("evt-1", vevents.VALIDATION_STARTED, "cor", {"k": 1}, "t")
    assert event.producer == "validation"
    assert event.source == "nexus_validation"
    assert event.type == "validation.started"


# --- observability ---------------------------------------------------------- #


def test_observability_counters() -> None:
    sink = InMemoryObservability()
    obs = ValidationObservability(sink)
    obs.started()
    obs.evidence_collected(3)
    obs.rule_evaluated()
    obs.completed()
    obs.failed()
    assert sink.counters["validation.started"] == 1
    assert sink.counters["validation.failed"] == 1


def test_observability_defaults_to_null_sink() -> None:
    ValidationObservability().started()  # must not raise


# --- persistence + composition ---------------------------------------------- #


def test_build_repositories_roundtrip() -> None:
    repos = build_validation_repositories()
    ev = Evidence(identity="ev-1", source=EvidenceSource.ARTIFACT, kind="file")
    repos.evidence.add(ev)
    assert repos.evidence.get("ev-1") == ev


def test_build_validation_wires_engine_and_repositories() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    ctx = build_validation(infra)
    assert ctx.engine is not None
    assert ctx.repositories is not None
    assert ctx.infrastructure is infra


def test_build_validation_accepts_explicit_repositories() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    repos = build_validation_repositories()
    ctx = build_validation(infra, repositories=repos)
    assert ctx.repositories is repos
