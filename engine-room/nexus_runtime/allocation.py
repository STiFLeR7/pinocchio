"""Runtime allocation — the deterministic selection funnel and RM-owned reservation.

This is where allocation lives (doc 06, INV-37): a candidate set is narrowed — match →
health → policy — to survivors, exactly one survivor is chosen *deterministically*, and
that choice is reserved then allocated in ``ResourceAllocationState``. Selection only ever
*removes* candidates (or is empty); it never invents one, lowers a requirement, or picks a
non-candidate — an empty survivor set is a typed error, never a silent default (doc 06 §3).

Allocation is **RM's own bookkeeping** (doc 04 §6): the :class:`AllocationLedger` tracks
``ResourceAllocationState`` and per-runtime capacity so a batch never double-books a
runtime. It never overwrites the Registry-owned ``availability``/``health`` (INV-36).

Capability matching here is **provider-independent** (INV-32): it compares the intake's
required capability *references* to a candidate descriptor's ``advertised_capabilities``
by identifier. Version-aware compatibility (doc 05 §4) is deferred until capability
references carry versions — recorded as an implementation observation, not a silent
assumption.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_core.contracts.enums import ResourceAllocationState
from nexus_core.registries.interfaces import HarnessDescriptor
from nexus_runtime import ids
from nexus_runtime.runtime_registry import RuntimeRegistry
from nexus_runtime.validators import (
    AllocationError,
    CapabilityMismatchError,
    NoEligibleRuntimeError,
    UnresolvedRuntimeError,
)
from nexus_runtime.vocabulary import ALLOCATION_TARGET_TYPE, RUNTIME_TARGET_TYPE

_INFINITY = float("inf")


class CandidateMatch(ValueObject):
    """The capability-match outcome for one candidate (recorded, never dropped — doc 05 §2)."""

    runtime_identity: str
    satisfied: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    eligible: bool = False


class SelectionResult(ValueObject):
    """The full, auditable outcome of the selection funnel for one intake."""

    required: tuple[str, ...] = ()
    matches: tuple[CandidateMatch, ...] = ()
    eligible_ids: tuple[str, ...] = ()
    reachable_ids: tuple[str, ...] = ()
    permitted_ids: tuple[str, ...] = ()
    chosen: HarnessDescriptor

    @property
    def chosen_match(self) -> CandidateMatch:
        """The match record of the chosen runtime."""
        for match in self.matches:
            if match.runtime_identity == self.chosen.identity:
                return match
        # Unreachable: a chosen runtime always has a recorded match.
        raise AllocationError(f"no match recorded for chosen runtime {self.chosen.identity!r}")


class Allocation(ValueObject):
    """A reservation of one runtime for one session; state via ``ResourceAllocationState``."""

    identity: str
    session_ref: Reference
    runtime_ref: Reference
    allocation_state: ResourceAllocationState
    correlation: Correlation
    metadata: Struct = Field(default_factory=dict)

    def reference(self) -> Reference:
        """A typed by-id pointer to this allocation."""
        return Reference(target_type=ALLOCATION_TARGET_TYPE, identifier=self.identity)

    def in_state(self, state: ResourceAllocationState) -> Allocation:
        """Return a copy of this allocation advanced to ``state``."""
        return self.model_copy(update={"allocation_state": state})


class RuntimeSelector:
    """Runs the match → health → policy → select funnel, deterministically (doc 06 §3)."""

    def __init__(self, registry: RuntimeRegistry) -> None:
        self._registry = registry

    def select(
        self,
        resolved: tuple[HarnessDescriptor, ...],
        required_capability_refs: tuple[Reference, ...],
        runtime_policy: Struct,
        *,
        excluded_ids: frozenset[str] = frozenset(),
    ) -> SelectionResult:
        """Narrow ``resolved`` candidates to exactly one chosen runtime (fail-closed)."""
        if not resolved:
            raise UnresolvedRuntimeError("no candidate runtime resolved to a Registry descriptor")

        required = tuple(sorted({ref.identifier for ref in required_capability_refs}))
        matches = tuple(self._match(descriptor, required) for descriptor in resolved)
        eligible = tuple(d for d in resolved if self._is_eligible(d, required))
        if not eligible:
            raise CapabilityMismatchError(
                f"no candidate advertises every required capability {list(required)!r}"
            )

        reachable = tuple(
            d for d in eligible if self._registry.is_reachable(d) and d.identity not in excluded_ids
        )
        if not reachable:
            raise NoEligibleRuntimeError(
                "every eligible runtime is unavailable or at capacity (doc 06 §5)"
            )

        permitted = tuple(d for d in reachable if self._is_permitted(d, runtime_policy))
        if not permitted:
            raise NoEligibleRuntimeError(
                "every reachable runtime is disallowed by policy (doc 06 §6)"
            )

        chosen = self._choose(permitted, runtime_policy)
        return SelectionResult(
            required=required,
            matches=matches,
            eligible_ids=tuple(d.identity for d in eligible),
            reachable_ids=tuple(d.identity for d in reachable),
            permitted_ids=tuple(d.identity for d in permitted),
            chosen=chosen,
        )

    # -- stage B: capability matching (provider-independent, INV-32) --------- #

    def _match(self, descriptor: HarnessDescriptor, required: tuple[str, ...]) -> CandidateMatch:
        advertised = {cap.identifier for cap in descriptor.advertised_capabilities}
        satisfied = tuple(r for r in required if r in advertised)
        unsupported = tuple(r for r in required if r not in advertised)
        return CandidateMatch(
            runtime_identity=descriptor.identity,
            satisfied=satisfied,
            unsupported=unsupported,
            eligible=not unsupported,
        )

    def _is_eligible(self, descriptor: HarnessDescriptor, required: tuple[str, ...]) -> bool:
        advertised = {cap.identifier for cap in descriptor.advertised_capabilities}
        return all(r in advertised for r in required)

    # -- stage D: declarative policy (RM applies; never derives — doc 06 §6) -- #

    def _is_permitted(self, descriptor: HarnessDescriptor, runtime_policy: Struct) -> bool:
        policy: Mapping[str, Any] = runtime_policy
        allowed = policy.get("allowed_runtimes")
        if allowed is not None and descriptor.identity not in allowed:
            return False
        denied = policy.get("denied_runtimes")
        if denied is not None and descriptor.identity in denied:
            return False
        ceiling = policy.get("cost_ceiling")
        if ceiling is not None:
            cost = self._cost(descriptor)
            if cost is not None and cost > ceiling:
                return False
        return True

    # -- stage F: deterministic, total selection (doc 06 §8) ------------------ #

    def _choose(
        self, survivors: tuple[HarnessDescriptor, ...], runtime_policy: Struct
    ) -> HarnessDescriptor:
        policy: Mapping[str, Any] = runtime_policy
        preferred = policy.get("preferred_runtimes") or ()
        preference = policy.get("cost_preference")

        def preferred_rank(descriptor: HarnessDescriptor) -> int:
            return (
                preferred.index(descriptor.identity)
                if descriptor.identity in preferred
                else len(preferred)
            )

        def cost_rank(descriptor: HarnessDescriptor) -> float:
            cost = self._cost(descriptor)
            if preference == "lowest":
                return cost if cost is not None else _INFINITY
            if preference == "highest":
                return -cost if cost is not None else _INFINITY
            return 0.0

        return min(
            survivors,
            key=lambda d: (preferred_rank(d), cost_rank(d), d.identity),
        )

    def _cost(self, descriptor: HarnessDescriptor) -> float | None:
        metadata: Mapping[str, Any] = descriptor.metadata or {}
        cost = metadata.get("cost")
        return float(cost) if isinstance(cost, (int, float)) else None


class AllocationLedger:
    """RM's own reservation bookkeeping — capacity + ``ResourceAllocationState`` (doc 04 §6)."""

    def __init__(self) -> None:
        self._active: dict[str, int] = {}

    def active_count(self, runtime_identity: str) -> int:
        """How many live (RESERVED/ALLOCATED) reservations a runtime currently holds."""
        return self._active.get(runtime_identity, 0)

    def at_capacity(self, descriptor: HarnessDescriptor) -> bool:
        """Whether ``descriptor`` has no free capacity (default capacity 1 — doc 06 §9)."""
        return self.active_count(descriptor.identity) >= self._capacity(descriptor)

    def at_capacity_ids(self, descriptors: tuple[HarnessDescriptor, ...]) -> frozenset[str]:
        """The identities among ``descriptors`` that currently have no free capacity."""
        return frozenset(d.identity for d in descriptors if self.at_capacity(d))

    def reserve(
        self,
        session_ref: Reference,
        descriptor: HarnessDescriptor,
        *,
        correlation: Correlation,
    ) -> Allocation:
        """Claim capacity (``AVAILABLE → RESERVED``) so a batch cannot double-book it."""
        if self.at_capacity(descriptor):
            raise AllocationError(f"runtime {descriptor.identity!r} is at capacity; cannot reserve")
        self._active[descriptor.identity] = self.active_count(descriptor.identity) + 1
        return Allocation(
            identity=ids.allocation_id(session_ref.identifier, descriptor.identity),
            session_ref=session_ref,
            runtime_ref=Reference(target_type=RUNTIME_TARGET_TYPE, identifier=descriptor.identity),
            allocation_state=ResourceAllocationState.RESERVED,
            correlation=correlation,
            metadata={"runtime": descriptor.identity, "capacity": self._capacity(descriptor)},
        )

    def allocate(self, allocation: Allocation) -> Allocation:
        """Confirm a reservation into a live allocation (``RESERVED → ALLOCATED``)."""
        if allocation.allocation_state is not ResourceAllocationState.RESERVED:
            raise AllocationError(
                f"cannot allocate {allocation.identity!r} from state "
                f"{allocation.allocation_state.value!r}; expected RESERVED"
            )
        return allocation.in_state(ResourceAllocationState.ALLOCATED)

    def release(self, allocation: Allocation) -> Allocation:
        """Return capacity (``* → RELEASED``) so it is never leaked (doc 07 §6)."""
        if allocation.allocation_state is ResourceAllocationState.RELEASED:
            raise AllocationError(f"allocation {allocation.identity!r} is already released")
        runtime_identity = allocation.runtime_ref.identifier
        self._active[runtime_identity] = max(0, self.active_count(runtime_identity) - 1)
        return allocation.in_state(ResourceAllocationState.RELEASED)

    def _capacity(self, descriptor: HarnessDescriptor) -> int:
        metadata: Mapping[str, Any] = descriptor.metadata or {}
        capacity = metadata.get("capacity", 1)
        return int(capacity) if isinstance(capacity, int) and capacity > 0 else 1
