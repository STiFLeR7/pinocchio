"""The Policy Registry — a version-addressable projection of the policy log.

Implements the frozen :class:`~nexus_core.registries.interfaces.PolicyRegistry`
protocol. Policies are versioned (contract §8): the registry keys by
``(identity, version)`` so every historical version stays addressable for
replay-without-reinference (INV-17), while ``enabled``/``list_all``/``find_by_category``
expose the *latest* version per identity for live evaluation.

Registration is event-sourced: :meth:`register` emits a ``policy.registered`` fact
(the authority, INV-15) *then* updates the in-memory index and the injected
:class:`~nexus_core.persistence.interfaces.Repository` (a projection, never CRUD
authority — ADR-001/ADR-007). Because the fact embeds the serialized policy,
:meth:`rebuild` reconstructs the whole registry from the durable log after a restart —
same events → same registry → same verdicts.

The emitter and repository are optional: a registry with neither is a pure, in-memory,
side-effect-free store — exactly what side-effect-free policy simulation needs
(contract §6).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from nexus_core.contracts.enums import PolicyCategory
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.event import Event
from nexus_core.domain.policy import Policy
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import Repository
from nexus_policy.events import POLICY_REGISTERED, build_event, system_now
from nexus_policy.ids import registered_event_id
from nexus_policy.observability import PolicyObservability
from nexus_policy.precedence import version_key


class InMemoryPolicyRegistry:
    """A version-addressable, event-sourced projection of the registered policy set."""

    def __init__(
        self,
        *,
        emitter: EventEmitter | None = None,
        repository: Repository[Policy] | None = None,
        observability: PolicyObservability | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._by_key: dict[tuple[str, str], Policy] = {}
        self._emitter = emitter
        self._repo = repository
        self._obs = observability or PolicyObservability()
        self._now = now or system_now

    # -- PolicyRegistry protocol -------------------------------------------- #

    def register(self, policy: Policy) -> None:
        """Admit ``policy`` at its ``(identity, version)``; emit the fact, then project.

        A no-op when this exact ``(identity, version)`` is already known with identical content —
        restart-safe even under a real, advancing clock. Without this, re-registering an
        already-durable baseline policy (as every composition root that seeds one unconditionally
        does) would re-emit the same event identifier with a fresh timestamp, which a durable store
        correctly rejects as a content mismatch rather than silently ignoring (only a byte-identical
        re-emission — e.g. under a frozen test clock — is treated as a harmless duplicate).
        """
        if self._by_key.get((policy.identity, policy.version)) == policy:
            return
        if self._emitter is not None:
            payload = {
                "policy": policy.model_dump(mode="json"),
                "identity": policy.identity,
                "version": policy.version,
            }
            self._emitter.emit(
                build_event(
                    registered_event_id(policy.identity, policy.version),
                    POLICY_REGISTERED,
                    policy.identity,
                    payload,
                    self._now(),
                )
            )
            self._obs.registered()
        self._by_key[(policy.identity, policy.version)] = policy
        if self._repo is not None:
            self._repo.add(policy)

    def get(self, identity: str, version: str | None = None) -> Policy | None:
        """The exact ``version`` (replay), or the latest enabled/known version by identity."""
        if version is not None:
            return self._by_key.get((identity, version))
        candidates = [p for (ident, _), p in self._by_key.items() if ident == identity]
        if not candidates:
            return None
        enabled = [p for p in candidates if p.status is PolicyStatus.ENABLED]
        pool = enabled or candidates
        return max(pool, key=lambda p: version_key(p.version))

    def find_by_category(self, category: PolicyCategory) -> tuple[Policy, ...]:
        """The latest version per identity whose category is ``category``."""
        return self._latest(lambda p: p.category is category)

    def enabled(self) -> tuple[Policy, ...]:
        """The latest ENABLED version per identity — the set the engine evaluates against."""
        return self._latest(lambda p: p.status is PolicyStatus.ENABLED)

    def list_all(self) -> tuple[Policy, ...]:
        """The latest version per identity, ordered by identity (deterministic)."""
        return self._latest(lambda _p: True)

    # -- projection rebuild (ADR-007 restart determinism) ------------------- #

    def rebuild(self, events: Iterable[Event]) -> None:
        """Reconstruct the registry purely from ``policy.registered`` facts (no re-emit)."""
        self._by_key.clear()
        for event in events:
            if event.type == POLICY_REGISTERED:
                policy = Policy.model_validate(event.payload["policy"])
                self._by_key[(policy.identity, policy.version)] = policy

    # -- internals ---------------------------------------------------------- #

    def _latest(self, predicate: Callable[[Policy], bool]) -> tuple[Policy, ...]:
        latest: dict[str, Policy] = {}
        for policy in self._by_key.values():
            if not predicate(policy):
                continue
            current = latest.get(policy.identity)
            if current is None or version_key(policy.version) > version_key(current.version):
                latest[policy.identity] = policy
        return tuple(sorted(latest.values(), key=lambda p: p.identity))
