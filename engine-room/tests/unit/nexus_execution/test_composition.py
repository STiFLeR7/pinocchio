"""Unit tests for nexus_execution.composition — DI wiring over the Phase 2 substrate."""

from __future__ import annotations

from nexus_execution import ExecutionEngine, build_execution
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_runtime import FixedTimestampSource


def test_build_execution_wires_an_engine_over_infrastructure() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    context = build_execution(infra, timestamps=FixedTimestampSource())
    assert isinstance(context.engine, ExecutionEngine)
    assert context.infrastructure is infra


def test_build_execution_defaults_timestamps() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    context = build_execution(infra)
    assert isinstance(context.engine, ExecutionEngine)
