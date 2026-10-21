"""Runtime Registry — the ``RUNTIME``-category **view** over the Harness Registry.

There is no second registry (doc 04 §1). The Runtime Registry is a *lens*: "all
descriptors where ``category == RUNTIME``" over the existing ``HarnessRegistry`` (ADR-002),
which remains the sole owner of provider ``availability`` and ``health`` (INV-36). RM
**reads** through this lens and resolves the Orchestration-supplied candidate references
against it; adapters **register** into the underlying store. RM re-owns nothing.

Because no standalone registry phase exists yet, a deterministic in-memory reference
``HarnessRegistry`` (:class:`InMemoryHarnessRegistry`) ships here — mirroring how the
in-memory reference registries shipped in Harness/Orchestration. Every consumer depends on
the ``HarnessRegistry`` Protocol (dependency inversion), so the reference is swappable.

This module owns **no allocation state** and makes **no selection** (doc 04 sections 6-7):
it advertises what exists, what each can do, and how each is faring, and stops there.
Selection and allocation are :mod:`nexus_runtime.allocation`.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor, HarnessRegistry

# The availability values RM treats as "reachable" at intake (doc 06 §5). ``UNKNOWN`` is
# resolved conservatively as *not* reachable — no silent optimistic assumption.
_REACHABLE: frozenset[ResourceAvailability] = frozenset({ResourceAvailability.AVAILABLE})


class InMemoryHarnessRegistry:
    """A deterministic in-memory ``HarnessRegistry`` (reference implementation, INV-36).

    Owns availability/health as the descriptor carries them; ``discover_by_capability``
    returns advertising harnesses — *candidates only*, never a selection (INV-37).
    """

    def __init__(self) -> None:
        self._by_identity: dict[str, HarnessDescriptor] = {}

    def register(self, descriptor: HarnessDescriptor) -> None:
        self._by_identity[descriptor.identity] = descriptor

    def get(self, identity: str) -> HarnessDescriptor | None:
        return self._by_identity.get(identity)

    def discover_by_capability(self, capability_identifier: str) -> tuple[HarnessDescriptor, ...]:
        return tuple(
            sorted(
                (
                    descriptor
                    for descriptor in self._by_identity.values()
                    if any(
                        cap.identifier == capability_identifier
                        for cap in descriptor.advertised_capabilities
                    )
                ),
                key=lambda d: d.identity,
            )
        )

    def availability(self, identity: str) -> ResourceAvailability | None:
        descriptor = self._by_identity.get(identity)
        return descriptor.availability if descriptor is not None else None

    def list_all(self) -> tuple[HarnessDescriptor, ...]:
        return tuple(sorted(self._by_identity.values(), key=lambda d: d.identity))


class RuntimeRegistry:
    """The ``RUNTIME``-category read view over a ``HarnessRegistry`` (not a new store)."""

    def __init__(self, harness_registry: HarnessRegistry) -> None:
        self._registry = harness_registry

    # -- registration (adapter side; delegates to the underlying store) ------- #

    def register(self, descriptor: HarnessDescriptor) -> HarnessDescriptor:
        """Accept a ``RUNTIME`` descriptor into the underlying registry (fail-fast otherwise).

        Registering a non-``RUNTIME`` harness through the Runtime view is a category error:
        the view is exactly the ``RUNTIME`` lens, so it refuses to widen it.
        """
        if descriptor.category is not HarnessCategory.RUNTIME:
            raise ValueError(
                f"runtime registry only accepts RUNTIME harnesses, "
                f"got {descriptor.category.value!r} for {descriptor.identity!r}"
            )
        self._registry.register(descriptor)
        return descriptor

    # -- discovery (RM side; all reads, filtered to RUNTIME) ------------------ #

    def get(self, identity: str) -> HarnessDescriptor | None:
        """The ``RUNTIME`` descriptor for ``identity``, or ``None`` (non-runtimes are invisible)."""
        descriptor = self._registry.get(identity)
        if descriptor is None or descriptor.category is not HarnessCategory.RUNTIME:
            return None
        return descriptor

    def list_runtimes(self) -> tuple[HarnessDescriptor, ...]:
        """Every registered ``RUNTIME`` descriptor, in deterministic identity order."""
        return tuple(d for d in self._registry.list_all() if d.category is HarnessCategory.RUNTIME)

    def resolve_candidates(
        self, candidate_refs: tuple[Reference, ...]
    ) -> tuple[HarnessDescriptor, ...]:
        """Resolve candidate references to ``RUNTIME`` descriptors (candidate-scoped discovery).

        Returns the resolved descriptors in deterministic identity order. References that
        do not resolve to a ``RUNTIME`` descriptor are simply absent from the result — the
        caller (selection) decides whether an empty/short result is a fail-closed error.
        """
        resolved: dict[str, HarnessDescriptor] = {}
        for reference in candidate_refs:
            descriptor = self.get(reference.identifier)
            if descriptor is not None:
                resolved[descriptor.identity] = descriptor
        return tuple(sorted(resolved.values(), key=lambda d: d.identity))

    def is_reachable(self, descriptor: HarnessDescriptor) -> bool:
        """Whether the Registry reports ``descriptor`` as reachable (INV-36 — RM only reads)."""
        return descriptor.availability in _REACHABLE
