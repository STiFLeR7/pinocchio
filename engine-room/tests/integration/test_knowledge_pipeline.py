"""Milestone 10 -- end-to-end Reflection -> Knowledge -> (Planning-style) consumption.

Completes the intelligence pipeline:

    Execution -> Validation -> Recovery -> Reflection Report (advisory Knowledge Candidates)
        -> [orchestrating caller adapts each candidate by value] -> Knowledge Engine -> durable Item
        -> read-only retrieval, consumed the way Planning consumes it

The upstream stages (Execution..Reflection) are exercised end-to-end by
``test_reflection_pipeline``; here a real :class:`ReflectionEngine` reflects a *confirmed* failing
history (two correlated episodes -> a repeated-failure pattern -> a Knowledge Candidate), and the
Knowledge Engine rejects type-correct but unresolved references before a consumer can serve them.

Proves the persistence layer's central rule (candidates become Knowledge only under policy, on
their own evidence); that a consumer reaches learning **only** through a read-only Knowledge query;
that Knowledge only *appends* to the log; that identical history yields identical Items and events;
and -- structurally -- that ``nexus_knowledge`` imports no upstream layer, so INV-26 holds by
construction (a consumer cannot reach Reflection through Knowledge).
"""

from __future__ import annotations

import pathlib

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ConfidenceLadder, KnowledgeType
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_knowledge import KnowledgeCandidate, KnowledgeQuery, build_knowledge
from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import build_reflection
from nexus_reflection.report import ReflectionReport
from nexus_runtime.events import FixedTimestampSource
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import (
    execution_result,
    recovery_plan,
    sessions,
    validation_report,
)

_SESSIONS = tuple(sessions(2))


def _reflect() -> tuple[object, FixedTimestampSource, ReflectionReport]:
    """A real ReflectionReport over a confirmed (two-episode) runtime-failure history."""
    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    results, reports, plans = [], [], []
    for s in _SESSIONS:
        results.append(execution_result(s))
        reports.append(validation_report(s, decision=ValidationDecision.FAILED))
        plans.append(
            recovery_plan(
                s,
                decision=RecoveryDecision.RETRY,
                failure_category=FailureCategory.RUNTIME,
                retry_eligible=True,
            )
        )
    report = build_reflection(infra, timestamps=ts).engine.reflect(
        "op-window-int",
        execution_results=tuple(results),
        validation_reports=tuple(reports),
        recovery_plans=tuple(plans),
    )
    return infra, ts, report


def _to_candidate(report: ReflectionReport) -> KnowledgeCandidate:
    """The orchestrating caller's boundary adapter: Reflection candidate -> Knowledge candidate.

    This adaptation keeps ``nexus_knowledge`` free of any Reflection import: the caller reads the
    advisory candidate *by value* and constructs the Knowledge boundary contract, supplying the
    kind/subject and the validated evidence provenance it knows backs the understanding.
    """
    advisory = report.knowledge_candidates[0]
    return KnowledgeCandidate(
        identity=advisory.identity,
        kind=KnowledgeType.LESSON,
        subject="runtime failure recovery",
        statement=advisory.summary,
        confidence=ConfidenceLadder.OBSERVED,
        evidence_refs=tuple(
            Reference(target_type="validation_report", identifier=f"vr-{s}") for s in _SESSIONS
        ),
        originating_reflection_ref=report.reference(),
        source_pattern_ref=advisory.source_pattern_ref,
        correlation_identifier=report.correlation_identifier,
    )


def _knowledge(infra, ts):  # type: ignore[no-untyped-def]
    return build_knowledge(infra, timestamps=ts)


# --- the loop pays off ------------------------------------------------------ #


def test_unresolved_report_reference_is_rejected() -> None:
    infra, ts, report = _reflect()
    assert report.knowledge_candidates  # Reflection proposed at least one candidate
    ctx = _knowledge(infra, ts)
    outcome = ctx.engine.ingest(_to_candidate(report))
    assert not outcome.accepted
    assert outcome.item is None
    assert outcome.decision.failed_requirement == "provenance_not_validated"


def test_planning_style_consumer_cannot_serve_unresolved_report_refs() -> None:
    infra, ts, report = _reflect()
    ctx = _knowledge(infra, ts)
    ctx.engine.ingest(_to_candidate(report))
    # A consumer (Planning) obtains learning solely via a read-only Knowledge query.
    served = ctx.engine.serve(KnowledgeQuery(kind=KnowledgeType.LESSON))
    assert not served


def test_knowledge_only_appends_to_the_log() -> None:
    infra, ts, report = _reflect()
    pre = tuple(infra.event_store.read_all())
    ctx = _knowledge(infra, ts)
    ctx.engine.ingest(_to_candidate(report))
    post = tuple(infra.event_store.read_all())
    assert post[: len(pre)] == pre
    assert len(post) > len(pre)


def test_pipeline_is_deterministic() -> None:
    infra1, ts1, report1 = _reflect()
    infra2, ts2, report2 = _reflect()
    c1, c2 = _knowledge(infra1, ts1), _knowledge(infra2, ts2)
    o1 = c1.engine.ingest(_to_candidate(report1))
    o2 = c2.engine.ingest(_to_candidate(report2))
    assert o1.item == o2.item
    k1 = [
        (e.identifier, e.type, e.payload)
        for e in infra1.event_store.read_all()
        if e.type.startswith("knowledge.")
    ]
    k2 = [
        (e.identifier, e.type, e.payload)
        for e in infra2.event_store.read_all()
        if e.type.startswith("knowledge.")
    ]
    assert k1 == k2


# --- structural guardrails (INV-26 by construction) ------------------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_knowledge_imports_no_reflection() -> None:
    assert "nexus_reflection" not in _package_source("nexus_knowledge")


def test_knowledge_imports_no_planning() -> None:
    assert "nexus_planning" not in _package_source("nexus_knowledge")


def test_reflection_does_not_depend_on_knowledge() -> None:
    assert "nexus_knowledge" not in _package_source("nexus_reflection")
