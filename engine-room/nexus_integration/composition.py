"""Integration composition — dependency-injection wiring for the migration substrate.

Mirrors ``build_policy`` / ``build_validation``: it **reuses** the P1 infrastructure
substrate unchanged — the correlation gateway wraps the infrastructure context (the
durable emitter), the flag store and recorder emit through it, the metrics sink is the
context's observability. Nothing in the infrastructure is modified; the substrate is
purely additive dependency injection (no engine redesign).

Durable persistence is transparent: over a context from ``build_durable_infrastructure``
(ADR-007) all ``migration.*`` facts and flag transitions are durable and replayable with
no substrate-specific durable code. Every dependency is overridable; no module-level state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_integration.comparator import ComparatorRegistry, default_comparators
from nexus_integration.coordinator import RollbackCoordinator, ShadowDecisionCoordinator
from nexus_integration.flags import FlagStore
from nexus_integration.gateway import CorrelationGateway
from nexus_integration.observability import MigrationObservability
from nexus_integration.recorder import DecisionRecorder


@dataclass(frozen=True, slots=True)
class IntegrationContext:
    """The wired migration substrate (immutable wiring, stateful flag store)."""

    infrastructure: InfrastructureContext
    gateway: CorrelationGateway
    flags: FlagStore
    recorder: DecisionRecorder
    comparators: ComparatorRegistry
    coordinator: ShadowDecisionCoordinator
    rollback: RollbackCoordinator


def build_integration(
    infrastructure: InfrastructureContext,
    *,
    comparators: ComparatorRegistry | None = None,
    now: Callable[[], str] | None = None,
) -> IntegrationContext:
    """Wire a migration substrate over an infrastructure context; all parts overridable."""
    obs = MigrationObservability(infrastructure.observability)
    gateway = CorrelationGateway(infrastructure)
    flags = FlagStore(gateway=gateway, observability=obs, now=now)
    recorder = DecisionRecorder(gateway, now=now)
    registry = comparators or default_comparators()
    coordinator = ShadowDecisionCoordinator(flags, recorder, registry, observability=obs)
    rollback = RollbackCoordinator(flags, observability=obs)
    return IntegrationContext(
        infrastructure=infrastructure,
        gateway=gateway,
        flags=flags,
        recorder=recorder,
        comparators=registry,
        coordinator=coordinator,
        rollback=rollback,
    )
