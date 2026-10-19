"""The Runtime Adapter Registry — discover, register, resolve, expose capabilities (Milestone 1).

A runtime-**independent** registry of :class:`~nexus_execution.adapter.RuntimeAdapter`
factories keyed by runtime identity. It is the missing seam between the Harness/Runtime
Registry (which holds *descriptors* — what a runtime advertises) and the Execution Engine
(which needs a concrete *adapter instance* to drive). It names no provider: Claude, Gemini,
and Shell are wired *into* it from the outside (:mod:`nexus_runtime_adapters.catalog`), so a
new execution environment is added by registering a factory, never by changing this module.

Dependency direction: ``nexus_runtime_adapters.registry → {nexus_execution, nexus_core}`` —
it imports the *protocol*, never any concrete adapter (the litmus of doc 03 §3). Each
registration carries the adapter's own ``HarnessDescriptor`` (the abstract capabilities it
advertises), so the registry can answer capability queries without instantiating anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_execution.adapter import RuntimeAdapter


class AdapterRegistryError(Exception):
    """Base for every adapter-registry fault (unknown, duplicate, category error)."""


class UnknownAdapterError(AdapterRegistryError):
    """No adapter is registered under the requested runtime identity."""


class DuplicateAdapterError(AdapterRegistryError):
    """An adapter is already registered under this runtime identity."""


class NotARuntimeError(AdapterRegistryError):
    """A registration's descriptor is not of category ``RUNTIME`` (a category error)."""


@dataclass(frozen=True, slots=True)
class RuntimeInvocationProfile:
    """How a stub-backed adapter's underlying invoker should behave for a deterministic run.

    These are the reproducible-run knobs every stub invoker in the codebase honors — a fault
    injection (``fail``) and an unbounded-stream injection (``hang``) for exercising the
    engine's failure and cancel/timeout paths. A profile is *not* a provider choice or a
    selection input; it only shapes the deterministic event stream a chosen adapter produces.
    """

    fail: bool = False
    hang: bool = False


AdapterFactory = Callable[[RuntimeInvocationProfile], RuntimeAdapter]
"""Builds a fresh adapter honoring a deterministic-run profile."""


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    """One runtime's registration: its identity, advertised descriptor, and factory."""

    identity: str
    descriptor: HarnessDescriptor
    factory: AdapterFactory


class AdapterRegistry:
    """A deterministic, runtime-independent registry of runtime-adapter factories."""

    def __init__(self) -> None:
        self._by_identity: dict[str, AdapterRegistration] = {}

    # -- registration -------------------------------------------------------- #

    def register(self, registration: AdapterRegistration) -> AdapterRegistration:
        """Accept a ``RUNTIME`` registration (fail-fast on category or duplicate errors)."""
        descriptor = registration.descriptor
        if descriptor.category is not HarnessCategory.RUNTIME:
            raise NotARuntimeError(
                f"adapter registry only accepts RUNTIME adapters, got "
                f"{descriptor.category.value!r} for {registration.identity!r}"
            )
        if registration.identity != descriptor.identity:
            raise AdapterRegistryError(
                f"registration identity {registration.identity!r} does not match descriptor "
                f"identity {descriptor.identity!r}"
            )
        if registration.identity in self._by_identity:
            raise DuplicateAdapterError(
                f"an adapter is already registered under {registration.identity!r}"
            )
        self._by_identity[registration.identity] = registration
        return registration

    # -- resolution (adapter side) ------------------------------------------- #

    def resolve(self, identity: str) -> AdapterRegistration:
        """The registration for ``identity`` (raises :class:`UnknownAdapterError`)."""
        registration = self._by_identity.get(identity)
        if registration is None:
            raise UnknownAdapterError(f"no adapter registered under {identity!r}")
        return registration

    def create(
        self, identity: str, *, profile: RuntimeInvocationProfile | None = None
    ) -> RuntimeAdapter:
        """Build a fresh adapter instance for ``identity`` under a deterministic-run profile."""
        registration = self.resolve(identity)
        return registration.factory(profile or RuntimeInvocationProfile())

    # -- discovery (capability side; all reads) ------------------------------ #

    def __contains__(self, identity: str) -> bool:
        return identity in self._by_identity

    def identities(self) -> tuple[str, ...]:
        """Every registered runtime identity, in deterministic order."""
        return tuple(sorted(self._by_identity))

    def descriptor(self, identity: str) -> HarnessDescriptor:
        """The advertised descriptor for ``identity`` (raises :class:`UnknownAdapterError`)."""
        return self.resolve(identity).descriptor

    def descriptors(self) -> tuple[HarnessDescriptor, ...]:
        """Every registered runtime's descriptor, in deterministic identity order."""
        return tuple(self._by_identity[i].descriptor for i in self.identities())

    def capabilities(self, identity: str) -> tuple[str, ...]:
        """The abstract capability identifiers ``identity`` advertises, sorted."""
        descriptor = self.descriptor(identity)
        return tuple(sorted(c.identifier for c in descriptor.advertised_capabilities))

    def discover_by_capability(self, capability_identifier: str) -> tuple[HarnessDescriptor, ...]:
        """Every registered runtime advertising ``capability_identifier`` — candidates only.

        This is discovery, never selection (INV-37): it returns advertising runtimes in
        deterministic identity order and ranks nothing.
        """
        return tuple(
            descriptor
            for descriptor in self.descriptors()
            if any(
                c.identifier == capability_identifier for c in descriptor.advertised_capabilities
            )
        )
