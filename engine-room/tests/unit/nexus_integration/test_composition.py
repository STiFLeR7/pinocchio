"""Integration composition wiring (``nexus_integration.composition``)."""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_integration import (
    ComparatorRegistry,
    DecisionIdentity,
    DeterminismClass,
    FlagState,
    IntegrationContext,
    build_integration,
)


def test_build_integration_wires_the_substrate() -> None:
    ctx = build_integration(build_infrastructure(), now=lambda: "t")
    assert isinstance(ctx, IntegrationContext)
    assert ctx.flags.state("anything") is FlagState.DISABLED  # default-off
    assert ctx.coordinator is not None and ctx.rollback is not None


def test_build_integration_reuses_infrastructure_emitter() -> None:
    infra = build_infrastructure()
    ctx = build_integration(infra, now=lambda: "t")
    ctx.flags.set("policy_engine", FlagState.SHADOW)
    ctx.coordinator.adjudicate(
        DecisionIdentity(owner="policy_engine", decision_id="d1", correlation_identifier="cor"),
        legacy=lambda: "allow",
        shadow=lambda: "allow",
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    # Everything landed in the shared infrastructure log (no separate store).
    assert any(e.type.startswith("migration.") for e in infra.event_store.read_all())


def test_custom_comparator_registry_is_accepted() -> None:
    registry = ComparatorRegistry()
    ctx = build_integration(build_infrastructure(), comparators=registry, now=lambda: "t")
    assert ctx.comparators is registry
