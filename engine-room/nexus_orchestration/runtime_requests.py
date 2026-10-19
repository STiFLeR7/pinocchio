"""Step 6 — Runtime Request Builder (requirements only; never allocation).

Determines the runtime *requirements* for each Harness Request from the Execution
Strategy's capability-based ``runtime_policy`` and the request's required
capabilities, and (optionally, via an injected ``HarnessRegistry``) lists the
harness **candidates** that advertise those capabilities — candidates only, never a
selection (INV-37). It produces immutable Runtime Requests.

It does **not** allocate a provider, reserve a runtime, or read live health beyond
the registry's advertised candidates — allocation belongs to a later phase
(doc 07 *Runtime Assignment*; the prompt defers allocation explicitly).
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.registries.interfaces import HarnessRegistry
from nexus_orchestration import ids
from nexus_orchestration.execution_session import ExecutionSession
from nexus_orchestration.harness_requests import HarnessRequest
from nexus_orchestration.vocabulary import (
    HARNESS_REQUEST_TARGET_TYPE,
    HARNESS_TARGET_TYPE,
)


class RuntimeRequest(ValueObject):
    """An immutable runtime *requirement* derived from a Harness Request (no allocation)."""

    identity: str
    session_ref: Reference
    node: str
    harness_request_ref: Reference
    work_package_ref: Reference
    runtime_policy: Struct
    coordination: CoordinationModel
    required_capability_refs: tuple[Reference, ...] = ()
    candidate_harness_refs: tuple[Reference, ...] = ()
    correlation: Correlation | None = None


class RuntimeRequestBuilder:
    """Builds one immutable Runtime Request per Harness Request (candidates only)."""

    def __init__(self, registry: HarnessRegistry | None = None) -> None:
        self._registry = registry

    def build(
        self,
        session: ExecutionSession,
        strategy: ExecutionStrategy,
        harness_requests: tuple[HarnessRequest, ...],
        *,
        correlation_identifier: str,
    ) -> tuple[RuntimeRequest, ...]:
        """Produce a Runtime Request for each Harness Request, in the same order."""
        correlation = Correlation(correlation_identifier=correlation_identifier)
        return tuple(
            self._build(session, strategy, request, correlation=correlation)
            for request in harness_requests
        )

    def _build(
        self,
        session: ExecutionSession,
        strategy: ExecutionStrategy,
        request: HarnessRequest,
        *,
        correlation: Correlation,
    ) -> RuntimeRequest:
        return RuntimeRequest(
            identity=ids.runtime_request_id(session.identity, request.node),
            session_ref=request.session_ref,
            node=request.node,
            harness_request_ref=Reference(
                target_type=HARNESS_REQUEST_TARGET_TYPE, identifier=request.identity
            ),
            work_package_ref=request.work_package_ref,
            runtime_policy=strategy.runtime_policy,
            coordination=session.coordination,
            required_capability_refs=request.required_capability_refs,
            candidate_harness_refs=self._candidates(request.required_capability_refs),
            correlation=correlation,
        )

    def _candidates(self, capabilities: tuple[Reference, ...]) -> tuple[Reference, ...]:
        if self._registry is None:
            return ()
        identities: set[str] = set()
        for capability in capabilities:
            for descriptor in self._registry.discover_by_capability(capability.identifier):
                identities.add(descriptor.identity)
        return tuple(
            Reference(target_type=HARNESS_TARGET_TYPE, identifier=identity)
            for identity in sorted(identities)
        )
