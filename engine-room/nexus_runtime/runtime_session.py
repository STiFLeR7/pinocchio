"""Runtime Session — the central stateful object of the subsystem (immutable projection).

A Runtime Session binds **one Execution Package** to **one allocated runtime** for **one
execution attempt** (doc 02 §1). It is small and immutable-by-construction: it references
the package, the allocated runtime, and the allocation *by id*, never embedding their
content. Its ``lifecycle_state`` is a projection of the ``runtime.*`` log (ADR-001,
doc 02 §5); here it is realized as an immutable field advanced through legal transitions,
each producing a *new* frozen instance while the manager records the driving event.

There is no frozen core contract for a Runtime Session — it is a Runtime output (doc 02
§1, mirroring the Harness's Execution Package and Orchestration's Execution Session) — so
the value object is defined here in the runtime layer.

A retry is a *new* session with a new deterministic id (attempt ordinal in the id), not a
mutation of the prior one (doc 02 §6).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_runtime import ids
from nexus_runtime.lifecycle import validate_transition
from nexus_runtime.requests import RuntimeIntake
from nexus_runtime.vocabulary import (
    RUNTIME_SESSION_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
    RuntimeLifecycleState,
)


class RuntimeSession(ValueObject):
    """One immutable binding of a package to an allocated runtime for one attempt."""

    identity: str
    execution_package_ref: Reference
    work_package_ref: Reference
    session_ref: Reference
    node: str
    attempt: int
    lifecycle_state: RuntimeLifecycleState
    context_view_ref: Reference | None = None
    manifest_ref: Reference | None = None
    execution_strategy_ref: Reference | None = None
    runtime_ref: Reference | None = None
    allocation_ref: Reference | None = None
    telemetry_refs: tuple[Reference, ...] = ()
    metadata: Struct = Field(default_factory=dict)
    correlation: Correlation

    def reference(self) -> Reference:
        """A typed by-id pointer to this session."""
        return Reference(target_type=RUNTIME_SESSION_TARGET_TYPE, identifier=self.identity)

    def transitioned_to(self, target: RuntimeLifecycleState) -> RuntimeSession:
        """Return a new session advanced to ``target`` (illegal transitions fail-fast)."""
        validate_transition(self.lifecycle_state, target)
        return self.model_copy(update={"lifecycle_state": target})

    def bound_to(self, *, runtime_ref: Reference, allocation_ref: Reference) -> RuntimeSession:
        """Return a new session carrying the chosen runtime and allocation references."""
        return self.model_copy(
            update={"runtime_ref": runtime_ref, "allocation_ref": allocation_ref}
        )

    def with_telemetry(self, *references: Reference) -> RuntimeSession:
        """Return a new session with additional telemetry references attached."""
        return self.model_copy(update={"telemetry_refs": self.telemetry_refs + references})


class RuntimeSessionBuilder:
    """Creates the ``Created`` session shell for one intake (deterministic identity)."""

    def build(self, intake: RuntimeIntake, *, correlation_identifier: str) -> RuntimeSession:
        """Assemble the ``Created`` Runtime Session for one preparation intake."""
        identity = ids.runtime_session_id(intake.package_identity, intake.attempt)
        return RuntimeSession(
            identity=identity,
            execution_package_ref=Reference(
                target_type="execution_package", identifier=intake.package_identity
            ),
            work_package_ref=Reference(
                target_type=WORK_PACKAGE_TARGET_TYPE,
                identifier=intake.work_package.identifier,
            ),
            session_ref=intake.session_ref,
            node=intake.node,
            attempt=intake.attempt,
            lifecycle_state=RuntimeLifecycleState.CREATED,
            context_view_ref=intake.context_view_ref,
            manifest_ref=intake.manifest_ref,
            execution_strategy_ref=intake.execution_strategy_ref,
            metadata={
                "node": intake.node,
                "package": intake.package_identity,
                "work_package": intake.work_package.identifier,
                "candidate_count": len(intake.candidate_harness_refs),
                "required_capability_count": len(intake.required_capability_refs),
            },
            correlation=Correlation(correlation_identifier=correlation_identifier),
        )
