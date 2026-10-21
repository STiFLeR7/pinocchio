"""The version-addressable Policy Registry (``nexus_policy.registry``).

Proves version addressability (INV-17 replay), latest-per-identity ``enabled``/``list_all``,
category lookup, event-sourced registration, and pure rebuild-from-log (ADR-007 restart).
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_infra import InMemoryEventStore, InMemoryObservability
from nexus_policy.events import POLICY_REGISTERED
from nexus_policy.registry import InMemoryPolicyRegistry


def _policy(
    identity: str, version: str, *, status=PolicyStatus.ENABLED, category=PolicyCategory.EXECUTION
) -> Policy:
    return Policy(
        identity=identity,
        version=version,
        purpose="test",
        conditions={},
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner="governance",
        status=status,
        category=category,
    )


def test_get_by_exact_version_stays_addressable() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(_policy("p", "1"))
    reg.register(_policy("p", "2"))
    assert reg.get("p", "1").version == "1"
    assert reg.get("p", "2").version == "2"
    assert reg.get("p").version == "2"  # latest by default
    assert reg.get("missing") is None
    assert reg.get("p", "99") is None


def test_enabled_is_latest_enabled_version_per_identity() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(_policy("p", "1"))
    reg.register(_policy("p", "2", status=PolicyStatus.DISABLED))
    reg.register(_policy("q", "1"))
    enabled = reg.enabled()
    assert {p.identity: p.version for p in enabled} == {"p": "1", "q": "1"}


def test_find_by_category() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(_policy("gov", "1", category=PolicyCategory.GOVERNANCE))
    reg.register(_policy("exec", "1", category=PolicyCategory.EXECUTION))
    assert [p.identity for p in reg.find_by_category(PolicyCategory.GOVERNANCE)] == ["gov"]


def test_register_emits_one_registered_event() -> None:
    store = InMemoryEventStore(InMemoryObservability())
    reg = InMemoryPolicyRegistry(emitter=_EmitAdapter(store), now=lambda: "t")
    reg.register(_policy("p", "1"))
    events = list(store.read_all())
    assert len(events) == 1
    assert events[0].type == POLICY_REGISTERED
    assert events[0].payload["identity"] == "p"


def test_pure_registry_emits_nothing() -> None:
    # No emitter, no repository → a side-effect-free registry (used for simulation).
    reg = InMemoryPolicyRegistry()
    reg.register(_policy("p", "1"))
    assert len(reg.enabled()) == 1  # registered in-memory, no external effect to assert absent


def test_rebuild_reconstructs_from_log() -> None:
    store = InMemoryEventStore(InMemoryObservability())
    reg = InMemoryPolicyRegistry(emitter=_EmitAdapter(store), now=lambda: "t")
    reg.register(_policy("p", "1"))
    reg.register(_policy("p", "2", status=PolicyStatus.DISABLED))
    reg.register(_policy("q", "1"))

    rebuilt = InMemoryPolicyRegistry()
    rebuilt.rebuild(store.read_all())
    assert {p.identity for p in rebuilt.list_all()} == {"p", "q"}
    assert rebuilt.get("p", "2").status is PolicyStatus.DISABLED
    assert {p.identity: p.version for p in rebuilt.enabled()} == {"p": "1", "q": "1"}


class _EmitAdapter:
    """Minimal EventEmitter over a store (append only) for registry tests."""

    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    def emit(self, event) -> None:
        self._store.append(event)
