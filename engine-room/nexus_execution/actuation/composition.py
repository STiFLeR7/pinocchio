"""Execution-actuation composition — DI wiring over a P1/P2 infrastructure context.

Wires the traversal driver over the incumbent Runtime + Execution engines (built on the shared
infrastructure, durable transparently over ``build_durable_infrastructure`` — ADR-007). The runtime
adapter is injected — the one provider-specific choice (Runtime independence). Its descriptor is
registered with the Orchestration Harness Registry (so Orchestration's runtime assignment offers it as
a *candidate* — INV-37) and with the Runtime Manager (the selection/allocation source), mirroring the
incumbent ``nexus_workflows`` wiring. No incumbent engine is modified.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_execution.actuation.actuator import ExecutionActuator
from nexus_execution.actuation.dispatch import RuntimeDispatcher
from nexus_execution.actuation.observability import ActuationObservability
from nexus_execution.adapter import RuntimeAdapter
from nexus_execution.composition import ExecutionContext, build_execution
from nexus_infra import InfrastructureContext
from nexus_orchestration import InMemoryHarnessRegistry
from nexus_runtime import RuntimeContext, build_runtime
from nexus_runtime.events import SystemTimestampSource, TimestampSource


@dataclass(frozen=True, slots=True)
class ExecutionActuationContext:
    """The wired execution-actuation layer (immutable wiring; stateful actuator + incumbent engines)."""

    infrastructure: InfrastructureContext
    harness_registry: InMemoryHarnessRegistry
    runtime: RuntimeContext
    execution: ExecutionContext
    actuator: ExecutionActuator


def build_execution_actuation(
    infrastructure: InfrastructureContext,
    *,
    adapter: RuntimeAdapter,
    harness_registry: InMemoryHarnessRegistry | None = None,
    timestamps: TimestampSource | None = None,
) -> ExecutionActuationContext:
    """Wire an execution-actuation context over an infrastructure context; parts are overridable."""
    ts = timestamps or SystemTimestampSource()
    registry = harness_registry or InMemoryHarnessRegistry()
    registry.register(
        adapter.descriptor()
    )  # candidate discovery for Orchestration (INV-37); no event

    runtime = build_runtime(infrastructure, harness_registry=registry, timestamps=ts)
    execution = build_execution(infrastructure, timestamps=ts)
    # The Runtime Manager registration (which emits ``runtime.registered`` and sizes capacity) is done
    # per-run by the actuator (idempotent), so a restart over a reopened durable log re-populates the
    # Manager's in-memory registry without a duplicate-content event.

    dispatcher = RuntimeDispatcher(runtime.manager, execution.engine, adapter)
    actuator = ExecutionActuator(
        dispatcher,
        registry,
        infrastructure,
        timestamps=ts,
        observability=ActuationObservability(infrastructure.observability),
    )
    return ExecutionActuationContext(
        infrastructure=infrastructure,
        harness_registry=registry,
        runtime=runtime,
        execution=execution,
        actuator=actuator,
    )
