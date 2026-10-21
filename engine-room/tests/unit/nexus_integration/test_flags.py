"""Feature-flag infrastructure (``nexus_integration.flags``).

Proves default-off, versioning, durable event emission, single-seam reads, and pure
rebuild-from-log (ADR-007 restart determinism; ADR-008 §3.6 flag model).
"""

from __future__ import annotations

from nexus_infra import InMemoryEventStore, InMemoryObservability
from nexus_integration import CorrelationGateway, FlagState, FlagStore
from nexus_integration.events import MIGRATION_FLAG_SET


def _store_with_log():
    store = InMemoryEventStore(InMemoryObservability())
    flags = FlagStore(gateway=CorrelationGateway(_EmitAdapter(store)), now=lambda: "t")
    return flags, store


def test_default_off() -> None:
    flags = FlagStore()
    assert flags.state("any_owner") is FlagState.DISABLED
    assert flags.version("any_owner") == 0


def test_set_bumps_version_and_state() -> None:
    flags = FlagStore()
    flags.set("owner", FlagState.SHADOW)
    flags.set("owner", FlagState.ENABLED)
    assert flags.state("owner") is FlagState.ENABLED
    assert flags.version("owner") == 2


def test_set_emits_durable_versioned_event() -> None:
    flags, store = _store_with_log()
    flags.set("policy_engine", FlagState.SHADOW)
    events = list(store.read_all())
    assert len(events) == 1
    assert events[0].type == MIGRATION_FLAG_SET
    assert events[0].payload == {"owner": "policy_engine", "state": "shadow", "version": 1}


def test_rebuild_reconstructs_flag_state_from_log() -> None:
    flags, store = _store_with_log()
    flags.set("policy_engine", FlagState.SHADOW)
    flags.set("policy_engine", FlagState.ENABLED)
    flags.set("intent_resolution", FlagState.CANARY)

    rebuilt = FlagStore()
    rebuilt.rebuild(store.read_all())
    assert rebuilt.state("policy_engine") is FlagState.ENABLED
    assert rebuilt.version("policy_engine") == 2
    assert rebuilt.state("intent_resolution") is FlagState.CANARY


def test_snapshot_reports_known_owners() -> None:
    flags = FlagStore()
    flags.set("a", FlagState.ENABLED)
    flags.set("b", FlagState.SHADOW)
    assert flags.snapshot() == {"a": FlagState.ENABLED, "b": FlagState.SHADOW}


class _EmitAdapter:
    def __init__(self, store) -> None:
        self._store = store

    def emit(self, event) -> None:
        self._store.append(event)
