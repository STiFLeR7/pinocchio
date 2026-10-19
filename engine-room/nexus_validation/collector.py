"""Evidence collection — promoting Execution's Evidence Candidates into immutable Evidence.

Milestone 1. The :class:`EvidenceCollector` composes three inspectors, each deterministic
and ordered:

* :class:`ArtifactInspector` — reads ``runtime.artifact_emitted`` events from the log (the
  **independent** record, not the runtime's self-report) and promotes each into ARTIFACT
  Evidence, referencing the artifact by id (INV-12);
* :class:`OutputCollector` — promotes captured stdout/stderr/structured output into Evidence
  as **structural descriptors** (length, line count) — never the raw content (no duplication);
* :class:`MetadataCollector` — promotes runtime metadata (outcome, final state, exit status,
  error, cleanup) and execution metrics into Evidence.

Evidence is immutable and its ids are pure functions of the session identity, so identical
executions yield identical Evidence sets (doc 14 *Deterministic*).
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_execution.results import ExecutionResult
from nexus_runtime.events import RUNTIME_ARTIFACT_EMITTED
from nexus_validation import ids
from nexus_validation.evidence import Evidence
from nexus_validation.vocabulary import ARTIFACT_TARGET_TYPE, EvidenceSource


class ArtifactInspector:
    """Promotes ``runtime.artifact_emitted`` log events into ARTIFACT Evidence."""

    def inspect(
        self, scope: str, correlation: str, events: tuple[Event, ...]
    ) -> tuple[Evidence, ...]:
        collected: list[Evidence] = []
        prefix = f"evt-{scope}-"
        for event in events:
            if event.type != RUNTIME_ARTIFACT_EMITTED or not event.identifier.startswith(prefix):
                continue
            artifact_id = str(event.payload.get("artifact", ""))
            kind = str(event.payload.get("kind", "artifact"))
            collected.append(
                Evidence(
                    identity=ids.evidence_id(scope, "artifact", len(collected)),
                    source=EvidenceSource.ARTIFACT,
                    kind=kind,
                    subject_ref=Reference(target_type=ARTIFACT_TARGET_TYPE, identifier=artifact_id),
                    observed={"artifact": artifact_id, "kind": kind},
                    derived_from=(Reference(target_type="event", identifier=event.identifier),),
                    correlation_identifier=correlation,
                )
            )
        return tuple(collected)


class OutputCollector:
    """Promotes captured stdout/stderr/structured output into structural Evidence."""

    def collect(
        self, scope: str, correlation: str, result: ExecutionResult
    ) -> tuple[Evidence, ...]:
        collected: list[Evidence] = []
        session_ref = result.session_ref
        for source, tag, text in (
            (EvidenceSource.STDOUT, "stdout", result.stdout),
            (EvidenceSource.STDERR, "stderr", result.stderr),
        ):
            if not text:
                continue
            collected.append(self._descriptor(scope, correlation, session_ref, source, tag, text))
        if result.structured:
            joined = "".join(result.structured)
            collected.append(
                Evidence(
                    identity=ids.evidence_id(scope, "structured", 0),
                    source=EvidenceSource.STRUCTURED_OUTPUT,
                    kind="structured_output",
                    subject_ref=session_ref,
                    observed={"count": len(result.structured), "length": len(joined)},
                    derived_from=(session_ref,),
                    correlation_identifier=correlation,
                )
            )
        return tuple(collected)

    def _descriptor(
        self,
        scope: str,
        correlation: str,
        session_ref: Reference,
        source: EvidenceSource,
        tag: str,
        text: str,
    ) -> Evidence:
        observed: Struct = {"length": len(text), "lines": text.count("\n")}
        return Evidence(
            identity=ids.evidence_id(scope, tag, 0),
            source=source,
            kind=tag,
            subject_ref=session_ref,
            observed=observed,
            derived_from=(session_ref,),
            correlation_identifier=correlation,
        )


class MetadataCollector:
    """Promotes runtime metadata and execution metrics into Evidence."""

    def collect(
        self, scope: str, correlation: str, result: ExecutionResult
    ) -> tuple[Evidence, ...]:
        metadata = Evidence(
            identity=ids.evidence_id(scope, "metadata", 0),
            source=EvidenceSource.RUNTIME_METADATA,
            kind="runtime_metadata",
            subject_ref=result.session_ref,
            observed={
                "outcome": result.outcome.value,
                "final_state": result.final_state.value,
                "exit_status": result.exit_status,
                "error_class": result.error_class,
                "cleanup_ok": result.cleanup_ok,
                "runtime": result.runtime_ref.identifier if result.runtime_ref else None,
            },
            derived_from=(result.session_ref,),
            correlation_identifier=correlation,
        )
        metrics = Evidence(
            identity=ids.evidence_id(scope, "metric", 0),
            source=EvidenceSource.EXECUTION_METRIC,
            kind="execution_metrics",
            subject_ref=result.session_ref,
            observed=dict(result.metrics),
            derived_from=(result.session_ref,),
            correlation_identifier=correlation,
        )
        return (metadata, metrics)


class EvidenceCollector:
    """Collects the full, ordered, immutable Evidence set for one execution result."""

    def __init__(self) -> None:
        self._artifacts = ArtifactInspector()
        self._outputs = OutputCollector()
        self._metadata = MetadataCollector()

    def collect(
        self, result: ExecutionResult, events: tuple[Event, ...] = ()
    ) -> tuple[Evidence, ...]:
        """Promote every Evidence Candidate into immutable Evidence (deterministic order)."""
        scope = result.session_ref.identifier
        correlation = self._correlation(result, events)
        return (
            *self._artifacts.inspect(scope, correlation, events),
            *self._outputs.collect(scope, correlation, result),
            *self._metadata.collect(scope, correlation, result),
        )

    def _correlation(self, result: ExecutionResult, events: tuple[Event, ...]) -> str:
        prefix = f"evt-{result.session_ref.identifier}-"
        for event in events:
            if event.identifier.startswith(prefix):
                return event.correlation_identifier
        return result.session_ref.identifier
