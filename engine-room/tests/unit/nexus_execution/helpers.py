"""Shared, deterministic builders for the Execution Engine test suite.

Provides a prepared ``Ready`` Runtime Session (built through the real RM preparation
pipeline, so the execution tests exercise the genuine handoff), a fully-wired execution
environment over a fixed timestamp source, and a :class:`FakeAdapter` — a scriptable
:class:`~nexus_execution.adapter.RuntimeAdapter` that yields a caller-supplied signal list
and can raise, cancel, or fail cleanup on demand. The fake keeps engine tests provider-free
(no Claude) so each engine branch is exercised in isolation.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_execution import ExecutionContext, build_execution
from nexus_execution.adapter import (
    AdapterConfig,
    ConfiguredRuntime,
    ExecutionControl,
    TeardownReport,
)
from nexus_execution.signals import RuntimeSignal
from nexus_infra import InfrastructureContext, InMemoryObservability, build_infrastructure
from nexus_runtime import FixedTimestampSource, TimestampSource, build_runtime
from nexus_runtime.runtime_session import RuntimeSession
from tests.unit.nexus_runtime.helpers import intake, preparation_request

FAKE_RUNTIME_IDENTITY = "fake-runtime"


def fake_descriptor(identity: str = FAKE_RUNTIME_IDENTITY) -> HarnessDescriptor:
    """A RUNTIME descriptor advertising ``code_generation`` (matches the default intake)."""
    return HarnessDescriptor(
        identity=identity,
        category=HarnessCategory.RUNTIME,
        version="1",
        advertised_capabilities=(
            Reference(target_type="capability", identifier="code_generation"),
        ),
        availability=ResourceAvailability.AVAILABLE,
        health=ResourceAvailability.AVAILABLE,
        metadata=None,
    )


@dataclass(frozen=True, slots=True)
class SliceEnv:
    """A wired preparation + execution environment sharing one event store."""

    infrastructure: InfrastructureContext
    execution: ExecutionContext
    session: RuntimeSession
    work_package: WorkPackage

    def event_types(self, session_identity: str | None = None) -> tuple[str, ...]:
        """The ordered event types (optionally scoped to one session)."""
        scope = session_identity or self.session.identity
        return tuple(
            e.type
            for e in self.infrastructure.event_store.read_all()
            if e.identifier.startswith(f"evt-{scope}-")
        )

    def events(self) -> tuple:  # type: ignore[type-arg]
        return tuple(self.infrastructure.event_store.read_all())


def prepared_slice(
    *,
    runtime_descriptor: HarnessDescriptor | None = None,
    timestamps: TimestampSource | None = None,
) -> SliceEnv:
    """Prepare a Ready session through the real RM pipeline and wire an execution context."""
    descriptor = runtime_descriptor or fake_descriptor()
    ts = timestamps or FixedTimestampSource()
    infra = build_infrastructure(observability=InMemoryObservability())
    runtime = build_runtime(infra, timestamps=ts)
    runtime.manager.register_runtime(descriptor)
    itk = intake(candidates=(descriptor.identity,), required=("code_generation",))
    result = runtime.manager.prepare(preparation_request(itk))
    execution = build_execution(infra, timestamps=ts)
    return SliceEnv(
        infrastructure=infra,
        execution=execution,
        session=result.sessions[0],
        work_package=itk.work_package,
    )


class FakeAdapter:
    """A scriptable :class:`RuntimeAdapter` for exercising engine branches provider-free."""

    def __init__(
        self,
        signals: Sequence[RuntimeSignal],
        *,
        identity: str = FAKE_RUNTIME_IDENTITY,
        raise_at: int | None = None,
        raise_exc: Exception | None = None,
        cleanup: TeardownReport | None = None,
        cleanup_raise: Exception | None = None,
        cancel_after: int | None = None,
    ) -> None:
        self._signals = tuple(signals)
        self._identity = identity
        self._raise_at = raise_at
        self._raise_exc = raise_exc
        self._cleanup = cleanup or TeardownReport(ok=True)
        self._cleanup_raise = cleanup_raise
        self._cancel_after = cancel_after
        self.configured_with: AdapterConfig | None = None
        self.cleaned_up = False

    def descriptor(self) -> HarnessDescriptor:
        return fake_descriptor(self._identity)

    def configure(self, config: AdapterConfig) -> ConfiguredRuntime:
        self.configured_with = config
        return ConfiguredRuntime(
            runtime_identity=self._identity,
            isolation_profile=config.isolation_profile,
            working_dir=config.working_dir,
            env_keys=config.env_keys,
        )

    def execute(
        self,
        *,
        session_ref: Reference,
        work_package: WorkPackage,
        control: ExecutionControl,
    ) -> Iterator[RuntimeSignal]:
        for index, signal in enumerate(self._signals):
            if self._raise_exc is not None and index == self._raise_at:
                raise self._raise_exc
            yield signal
            if self._cancel_after is not None and index + 1 >= self._cancel_after:
                control.cancel()

    def cleanup(self) -> TeardownReport:
        self.cleaned_up = True
        if self._cleanup_raise is not None:
            raise self._cleanup_raise
        return self._cleanup
