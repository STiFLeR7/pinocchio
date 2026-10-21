"""Synthesis — turning deterministic patterns into report summaries and Knowledge Candidates.

Milestone 3 (aggregation). A pure function of the collected history and the analyzer patterns —
no AI, no speculation (doc 26). It computes the execution/validation/recovery summaries
(counts), the overall confidence (derived from the number of operations reflected on), the
*confirmed* observations (patterns corroborated at least twice), the advisory Knowledge
Candidates (only from *actionable* confirmed patterns — doc 26 *Actionable*; INV-25), and a
one-line-per-pattern reasoning trace (INV-31).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexus_core.contracts.base import Reference, Struct
from nexus_reflection import ids
from nexus_reflection.collector import OperationalHistory
from nexus_reflection.patterns import KnowledgeCandidate, OperationalPattern, confidence_for
from nexus_reflection.vocabulary import ConfidenceLevel, PatternKind

# Confirmed patterns of these kinds carry actionable insight → a Knowledge Candidate.
_ACTIONABLE = {
    PatternKind.REPEATED_FAILURE: "investigate recurring {subject} failures",
    PatternKind.BOTTLENECK: "address the '{subject}' operational bottleneck",
    PatternKind.RETRY_FREQUENCY: "reduce retry frequency across the operation set",
    PatternKind.REPEATED_SUCCESS: "promote the reusable successful approach on {subject}",
}


@dataclass(frozen=True, slots=True)
class ReflectionInsight:
    """The synthesised, report-ready analysis of one operational window."""

    confidence: ConfidenceLevel
    execution_summary: Struct
    validation_summary: Struct
    recovery_summary: Struct
    confirmed_observations: tuple[str, ...]
    knowledge_candidates: tuple[KnowledgeCandidate, ...]
    recommendations: tuple[str, ...]
    evidence_refs: tuple[Reference, ...]
    reasoning_trace: tuple[str, ...]


class ReflectionSynthesizer:
    """Aggregates history + patterns into a deterministic, explainable :class:`ReflectionInsight`."""

    def synthesize(
        self, history: OperationalHistory, patterns: tuple[OperationalPattern, ...]
    ) -> ReflectionInsight:
        episodes = history.episodes
        confirmed = tuple(p for p in patterns if p.is_confirmed)
        candidates = self._candidates(history.scope, patterns)
        return ReflectionInsight(
            confidence=confidence_for(len(episodes)),
            execution_summary=self._execution_summary(history),
            validation_summary=self._validation_summary(history),
            recovery_summary=self._recovery_summary(history),
            confirmed_observations=tuple(p.description for p in confirmed),
            knowledge_candidates=candidates,
            recommendations=tuple(c.summary for c in candidates),
            evidence_refs=self._evidence_refs(patterns),
            reasoning_trace=tuple(
                f"{p.kind.value}: {p.subject} — {p.occurrences} occurrence(s) ({p.confidence.value})"
                for p in patterns
            ),
        )

    def _execution_summary(self, history: OperationalHistory) -> Struct:
        episodes = history.episodes
        summary: dict[str, Any] = {
            "total": len(episodes),
            "succeeded": sum(1 for e in episodes if e.succeeded),
            "failed": sum(1 for e in episodes if e.is_failure),
            "by_runtime": _counts(e.runtime or "unknown" for e in episodes),
        }
        if history.metrics:
            summary["metrics"] = dict(history.metrics)
        return summary

    def _validation_summary(self, history: OperationalHistory) -> Struct:
        decisions = [e.validation_decision.value for e in history.episodes if e.validation_decision]
        return {"validated": len(decisions), "by_decision": _counts(decisions)}

    def _recovery_summary(self, history: OperationalHistory) -> Struct:
        decisions = [e.recovery_decision.value for e in history.episodes if e.recovery_decision]
        return {
            "recovered": len(decisions),
            "by_decision": _counts(decisions),
            "retry_eligible": sum(1 for e in history.episodes if e.retry_eligible),
        }

    def _candidates(
        self, scope: str, patterns: tuple[OperationalPattern, ...]
    ) -> tuple[KnowledgeCandidate, ...]:
        candidates: list[KnowledgeCandidate] = []
        for pattern in patterns:
            template = _ACTIONABLE.get(pattern.kind)
            if template is None or not pattern.is_confirmed:
                continue
            candidates.append(
                KnowledgeCandidate(
                    identity=ids.candidate_id(scope, len(candidates)),
                    summary=template.format(subject=pattern.subject),
                    confidence=pattern.confidence,
                    source_pattern_ref=pattern.reference(),
                    evidence_refs=pattern.evidence_refs,
                )
            )
        return tuple(candidates)

    def _evidence_refs(self, patterns: tuple[OperationalPattern, ...]) -> tuple[Reference, ...]:
        seen: dict[tuple[str, str], Reference] = {}
        for pattern in patterns:
            for ref in pattern.evidence_refs:
                seen.setdefault((ref.target_type, ref.identifier), ref)
        return tuple(seen.values())


def _counts(values) -> Struct:  # type: ignore[no-untyped-def]
    """A deterministic {value: count} map, in first-seen order."""
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
