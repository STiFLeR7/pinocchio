"""Unit tests for evidence collection — artifact/output/metadata inspectors."""

from __future__ import annotations

from nexus_validation import EvidenceCollector
from nexus_validation.collector import ArtifactInspector, MetadataCollector, OutputCollector
from nexus_validation.vocabulary import EvidenceSource
from tests.unit.nexus_validation.helpers import (
    SESSION,
    artifact_event,
    artifact_events,
    execution_result,
)


def test_artifact_inspector_promotes_emitted_events() -> None:
    evidence = ArtifactInspector().inspect(SESSION, "cor", artifact_events(("a.py", "b.py")))
    assert len(evidence) == 2
    assert all(e.source is EvidenceSource.ARTIFACT for e in evidence)
    assert evidence[0].subject_ref is not None
    assert evidence[0].subject_ref.identifier == "a.py"


def test_artifact_inspector_ignores_other_events_and_sessions() -> None:
    foreign = artifact_event("x.py", session="rts-other-01")
    same = artifact_event("y.py")
    evidence = ArtifactInspector().inspect(SESSION, "cor", (foreign, same))
    assert [e.subject_ref.identifier for e in evidence if e.subject_ref] == ["y.py"]


def test_output_collector_stdout_and_stderr() -> None:
    result = execution_result(stdout="a\nb\n", stderr="warn\n")
    evidence = OutputCollector().collect(SESSION, "cor", result)
    sources = {e.source for e in evidence}
    assert EvidenceSource.STDOUT in sources
    assert EvidenceSource.STDERR in sources
    stdout_ev = next(e for e in evidence if e.source is EvidenceSource.STDOUT)
    assert stdout_ev.observed["lines"] == 2


def test_output_collector_empty_output_yields_nothing() -> None:
    evidence = OutputCollector().collect(SESSION, "cor", execution_result(stdout="", stderr=""))
    assert evidence == ()


def test_output_collector_structured_output() -> None:
    evidence = OutputCollector().collect(
        SESSION, "cor", execution_result(stdout="", structured=('{"k":1}',))
    )
    assert evidence[0].source is EvidenceSource.STRUCTURED_OUTPUT
    assert evidence[0].observed["count"] == 1


def test_metadata_collector_emits_metadata_and_metrics() -> None:
    evidence = MetadataCollector().collect(SESSION, "cor", execution_result())
    sources = [e.source for e in evidence]
    assert EvidenceSource.RUNTIME_METADATA in sources
    assert EvidenceSource.EXECUTION_METRIC in sources


def test_metadata_collector_handles_missing_runtime_ref() -> None:
    evidence = MetadataCollector().collect(SESSION, "cor", execution_result(runtime=None))
    metadata = next(e for e in evidence if e.source is EvidenceSource.RUNTIME_METADATA)
    assert metadata.observed["runtime"] is None


def test_collector_orders_artifacts_then_output_then_metadata() -> None:
    evidence = EvidenceCollector().collect(execution_result(), artifact_events(("a.py",)))
    sources = [e.source for e in evidence]
    assert sources[0] is EvidenceSource.ARTIFACT
    assert sources[-1] is EvidenceSource.EXECUTION_METRIC


def test_collector_is_deterministic() -> None:
    result = execution_result()
    events = artifact_events(("a.py",))
    assert EvidenceCollector().collect(result, events) == EvidenceCollector().collect(
        result, events
    )


def test_collector_correlation_from_events() -> None:
    evidence = EvidenceCollector().collect(
        execution_result(), artifact_events(("a.py",), correlation="cor-xyz")
    )
    assert all(e.correlation_identifier == "cor-xyz" for e in evidence)


def test_collector_correlation_fallback_to_session() -> None:
    # No events → correlation falls back to the session identity.
    evidence = EvidenceCollector().collect(execution_result(), ())
    assert all(e.correlation_identifier == SESSION for e in evidence)
