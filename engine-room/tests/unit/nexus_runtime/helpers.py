"""Shared, deterministic builders for the runtime test suite.

A single source of truth for constructing the objects the Runtime Manager prepares over —
Runtime Descriptors (seen through the ``RUNTIME`` Registry lens), Work Packages, and the
``nexus_core``-projected :class:`RuntimeIntake` inputs — plus a fully-wired runtime
environment with a fixed timestamp source and an inspectable observability sink, so runtime
tests read as intent and stay reproducible.

Intakes are built directly from ``nexus_core`` primitives (no dependency on Harness or
Orchestration correctness); a dedicated integration test exercises the real
Harness → Runtime seam separately. Every builder is deterministic — no clock, no
randomness — so a replay reproduces identical objects and event streams.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nexus_core.contracts.base import Correlation, Reference, Struct
from nexus_core.contracts.enums import (
    CoordinationModel,
    Priority,
    ResourceAvailability,
)
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_infra import InfrastructureContext, InMemoryObservability, build_infrastructure
from nexus_runtime import (
    FixedTimestampSource,
    PreparationRequest,
    RuntimeContext,
    RuntimeIntake,
    TimestampSource,
    build_runtime,
)

DEFAULT_GOAL = "goal-1"
DEFAULT_PLAN = "plan-goal-1-v1"
DEFAULT_CONTEXT = "ctx-1"
DEFAULT_SESSION = "session-goal-1-v1"
DEFAULT_CORRELATION = "cor-goal-1"


def ref(target_type: str, identifier: str) -> Reference:
    """Build a typed :class:`Reference`."""
    return Reference(target_type=target_type, identifier=identifier)


def work_package(
    identifier: str,
    *,
    goal: str = DEFAULT_GOAL,
    plan: str = DEFAULT_PLAN,
    context: str = DEFAULT_CONTEXT,
    skills: Sequence[Reference] = (),
    inputs: Sequence[Reference] = (),
    priority: Priority = Priority.MEDIUM,
) -> WorkPackage:
    """Build a valid :class:`WorkPackage` (the payload RM hands the runtime, INV-09)."""
    return WorkPackage(
        identifier=identifier,
        parent_goal=ref("goal", goal),
        parent_plan=ref("plan", plan),
        priority=priority,
        objective=f"accomplish {identifier}",
        context=ref("context_package", context),
        constraints=(),
        resources=(),
        skills=tuple(skills),
        inputs=tuple(inputs),
        outputs=(),
        evidence={},
        completion_criteria={},
    )


def descriptor(
    identity: str,
    *,
    capabilities: Sequence[str] = ("code_generation",),
    category: HarnessCategory = HarnessCategory.RUNTIME,
    version: str = "1",
    availability: ResourceAvailability = ResourceAvailability.AVAILABLE,
    health: ResourceAvailability = ResourceAvailability.AVAILABLE,
    metadata: Struct | None = None,
) -> HarnessDescriptor:
    """Build a Runtime :class:`HarnessDescriptor` (advertised capabilities by reference)."""
    return HarnessDescriptor(
        identity=identity,
        category=category,
        version=version,
        advertised_capabilities=tuple(ref("capability", c) for c in capabilities),
        availability=availability,
        health=health,
        metadata=metadata,
    )


def standard_runtimes() -> tuple[HarnessDescriptor, ...]:
    """Three deterministic runtimes with overlapping/distinct capabilities."""
    return (
        descriptor("claude-code", capabilities=("code_generation", "file_write")),
        descriptor("gemini-cli", capabilities=("code_generation",)),
        descriptor("shell", capabilities=("shell_exec",)),
    )


def intake(
    *,
    package_identity: str = "pkg-hr-node-a",
    node: str = "node-a",
    session: str = DEFAULT_SESSION,
    work_package_id: str = "wp-node-a",
    required: Sequence[str] = ("code_generation",),
    candidates: Sequence[str] = ("claude-code", "gemini-cli"),
    runtime_policy: Struct | None = None,
    coordination: CoordinationModel = CoordinationModel.SEQUENTIAL,
    attempt: int = 1,
    correlation: str | None = DEFAULT_CORRELATION,
    context_view: str | None = None,
    manifest: str | None = None,
    strategy: str | None = None,
) -> RuntimeIntake:
    """Build a deterministic :class:`RuntimeIntake` (the ``nexus_core`` projection RM prepares)."""
    return RuntimeIntake(
        package_identity=package_identity,
        node=node,
        session_ref=ref("execution_session", session),
        work_package=work_package(work_package_id),
        required_capability_refs=tuple(ref("capability", c) for c in required),
        candidate_harness_refs=tuple(ref("harness", c) for c in candidates),
        runtime_policy=runtime_policy or {},
        coordination=coordination,
        context_view_ref=ref("context_package", context_view) if context_view else None,
        manifest_ref=ref("execution_manifest", manifest) if manifest else None,
        execution_strategy_ref=ref("execution_strategy", strategy) if strategy else None,
        attempt=attempt,
        correlation=(
            Correlation(correlation_identifier=correlation) if correlation is not None else None
        ),
    )


def preparation_request(
    *intakes: RuntimeIntake,
    session_ref: Reference | None = None,
    correlation_identifier: str | None = DEFAULT_CORRELATION,
) -> PreparationRequest:
    """Bundle intakes into a :class:`PreparationRequest`."""
    return PreparationRequest(
        intakes=tuple(intakes),
        session_ref=session_ref,
        correlation_identifier=correlation_identifier,
    )


@dataclass(frozen=True, slots=True)
class RuntimeEnv:
    """A fully-wired runtime environment for tests (deterministic, inspectable)."""

    infrastructure: InfrastructureContext
    context: RuntimeContext
    observability: InMemoryObservability

    @property
    def manager(self):  # type: ignore[no-untyped-def]
        return self.context.manager

    @property
    def registry(self):  # type: ignore[no-untyped-def]
        return self.context.registry

    @property
    def repositories(self):  # type: ignore[no-untyped-def]
        return self.context.repositories

    def event_types(self) -> tuple[str, ...]:
        """Every emitted event type, in global append order."""
        return tuple(e.type for e in self.infrastructure.event_store.read_all())

    def events(self) -> tuple:  # type: ignore[type-arg]
        """Every emitted event, in global append order."""
        return tuple(self.infrastructure.event_store.read_all())

    def session_event_types(self, session_identity: str) -> tuple[str, ...]:
        """The ordered ``runtime.*`` event types scoped to one session (for projection)."""
        return tuple(
            e.type
            for e in self.infrastructure.event_store.read_all()
            if e.identifier.startswith(f"evt-{session_identity}-")
        )


def runtime_env(
    *,
    timestamps: TimestampSource | None = None,
    runtimes: Sequence[HarnessDescriptor] | None = None,
    register: bool = True,
) -> RuntimeEnv:
    """Wire an infrastructure + runtime context, registering the given runtimes."""
    observability = InMemoryObservability()
    infrastructure = build_infrastructure(observability=observability)
    context = build_runtime(infrastructure, timestamps=timestamps or FixedTimestampSource())
    descriptors = standard_runtimes() if runtimes is None else tuple(runtimes)
    if register:
        for runtime in descriptors:
            context.manager.register_runtime(runtime)
    return RuntimeEnv(infrastructure=infrastructure, context=context, observability=observability)
