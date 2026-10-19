"""Unit tests for nexus_runtime.allocation — 100% line+branch coverage."""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.contracts.enums import ResourceAllocationState, ResourceAvailability
from nexus_runtime.allocation import (
    Allocation,
    AllocationLedger,
    CandidateMatch,
    RuntimeSelector,
    SelectionResult,
)
from nexus_runtime.runtime_registry import InMemoryHarnessRegistry, RuntimeRegistry
from nexus_runtime.validators import (
    AllocationError,
    CapabilityMismatchError,
    NoEligibleRuntimeError,
    UnresolvedRuntimeError,
)
from nexus_runtime.vocabulary import ALLOCATION_TARGET_TYPE
from tests.unit.nexus_runtime.helpers import descriptor, ref

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _corr(id_: str = "cor-1") -> Correlation:
    return Correlation(correlation_identifier=id_)


def _session_ref(id_: str = "ses-1") -> Reference:
    return ref("execution_session", id_)


def _make_registry(*descriptors_) -> tuple[RuntimeRegistry, InMemoryHarnessRegistry]:
    harness_reg = InMemoryHarnessRegistry()
    rt_reg = RuntimeRegistry(harness_reg)
    for d in descriptors_:
        rt_reg.register(d)
    return rt_reg, harness_reg


def _make_selector(*descriptors_) -> RuntimeSelector:
    rt_reg, _ = _make_registry(*descriptors_)
    return RuntimeSelector(rt_reg)


# ---------------------------------------------------------------------------
# CandidateMatch
# ---------------------------------------------------------------------------


class TestCandidateMatch:
    def test_defaults(self) -> None:
        cm = CandidateMatch(runtime_identity="rt-a")
        assert cm.runtime_identity == "rt-a"
        assert cm.satisfied == ()
        assert cm.unsupported == ()
        assert cm.eligible is False

    def test_eligible_true(self) -> None:
        cm = CandidateMatch(
            runtime_identity="rt-a",
            satisfied=("cap-x",),
            unsupported=(),
            eligible=True,
        )
        assert cm.eligible is True


# ---------------------------------------------------------------------------
# SelectionResult.chosen_match
# ---------------------------------------------------------------------------


class TestSelectionResultChosenMatch:
    def _build_result(self, chosen_identity: str, match_identities: list[str]) -> SelectionResult:
        chosen = descriptor(chosen_identity)
        matches = tuple(
            CandidateMatch(runtime_identity=mid, eligible=True) for mid in match_identities
        )
        return SelectionResult(
            required=("cap-x",),
            matches=matches,
            eligible_ids=(chosen_identity,),
            reachable_ids=(chosen_identity,),
            permitted_ids=(chosen_identity,),
            chosen=chosen,
        )

    def test_chosen_match_found(self) -> None:
        result = self._build_result("rt-a", ["rt-a", "rt-b"])
        cm = result.chosen_match
        assert cm.runtime_identity == "rt-a"

    def test_chosen_match_not_found_raises(self) -> None:
        """matches list does not include the chosen runtime → AllocationError."""
        result = self._build_result("rt-z", ["rt-a", "rt-b"])
        with pytest.raises(AllocationError, match="no match recorded"):
            _ = result.chosen_match


# ---------------------------------------------------------------------------
# Allocation.reference() and .in_state()
# ---------------------------------------------------------------------------


class TestAllocation:
    def _make(self) -> Allocation:
        return Allocation(
            identity="alloc-ses-1-rt-a",
            session_ref=_session_ref(),
            runtime_ref=ref("harness", "rt-a"),
            allocation_state=ResourceAllocationState.RESERVED,
            correlation=_corr(),
        )

    def test_reference_target_type(self) -> None:
        alloc = self._make()
        r = alloc.reference()
        assert r.target_type == ALLOCATION_TARGET_TYPE
        assert r.identifier == "alloc-ses-1-rt-a"

    def test_in_state_returns_new_allocation(self) -> None:
        alloc = self._make()
        advanced = alloc.in_state(ResourceAllocationState.ALLOCATED)
        assert advanced.allocation_state is ResourceAllocationState.ALLOCATED
        # original is unchanged (immutable value object)
        assert alloc.allocation_state is ResourceAllocationState.RESERVED

    def test_in_state_released(self) -> None:
        alloc = self._make()
        released = alloc.in_state(ResourceAllocationState.RELEASED)
        assert released.allocation_state is ResourceAllocationState.RELEASED


# ---------------------------------------------------------------------------
# RuntimeSelector.select — error paths
# ---------------------------------------------------------------------------


class TestRuntimeSelectorErrors:
    def test_empty_resolved_raises_unresolved(self) -> None:
        selector = _make_selector()  # no descriptors registered
        with pytest.raises(UnresolvedRuntimeError):
            selector.select((), (), {})

    def test_no_capability_match_raises_capability_mismatch(self) -> None:
        d = descriptor("rt-a", capabilities=("shell_exec",))
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "code_generation"),)
        with pytest.raises(CapabilityMismatchError):
            selector.select(resolved, required, {})

    def test_all_unreachable_raises_no_eligible(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",), availability=ResourceAvailability.BUSY)
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "code_gen"),)
        with pytest.raises(NoEligibleRuntimeError):
            selector.select(resolved, required, {})

    def test_excluded_ids_removes_all_eligible(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",))
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "code_gen"),)
        with pytest.raises(NoEligibleRuntimeError):
            selector.select(resolved, required, {}, excluded_ids=frozenset({"rt-a"}))

    def test_policy_denylist_removes_all(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",))
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "code_gen"),)
        policy = {"denied_runtimes": ["rt-a"]}
        with pytest.raises(NoEligibleRuntimeError):
            selector.select(resolved, required, policy)

    def test_policy_allowlist_excludes_all(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",))
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "code_gen"),)
        policy = {"allowed_runtimes": ["rt-other"]}
        with pytest.raises(NoEligibleRuntimeError):
            selector.select(resolved, required, policy)

    def test_cost_ceiling_excludes_expensive_runtime(self) -> None:
        d = descriptor("rt-a", capabilities=("cap",), metadata={"cost": 10.0})
        selector = _make_selector(d)
        resolved = (d,)
        required = (ref("capability", "cap"),)
        policy = {"cost_ceiling": 5.0}
        with pytest.raises(NoEligibleRuntimeError):
            selector.select(resolved, required, policy)


# ---------------------------------------------------------------------------
# RuntimeSelector.select — happy path and policy branches
# ---------------------------------------------------------------------------


class TestRuntimeSelectorHappyPath:
    def test_happy_path_returns_selection_result(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",))
        selector = _make_selector(d)
        result = selector.select((d,), (ref("capability", "code_gen"),), {})
        assert result.chosen.identity == "rt-a"
        assert "rt-a" in result.eligible_ids
        assert "rt-a" in result.reachable_ids
        assert "rt-a" in result.permitted_ids

    def test_happy_path_no_required_caps(self) -> None:
        d = descriptor("rt-a", capabilities=("code_gen",))
        selector = _make_selector(d)
        result = selector.select((d,), (), {})
        assert result.chosen.identity == "rt-a"

    def test_allowlist_permits_matching_runtime(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",))
        d_b = descriptor("rt-b", capabilities=("cap",))
        selector = _make_selector(d_a, d_b)
        result = selector.select(
            (d_a, d_b), (ref("capability", "cap"),), {"allowed_runtimes": ["rt-a"]}
        )
        assert result.chosen.identity == "rt-a"

    def test_cost_ceiling_permits_cheap_runtime(self) -> None:
        d = descriptor("rt-a", capabilities=("cap",), metadata={"cost": 3.0})
        selector = _make_selector(d)
        result = selector.select((d,), (ref("capability", "cap"),), {"cost_ceiling": 5.0})
        assert result.chosen.identity == "rt-a"

    def test_cost_absent_passes_ceiling(self) -> None:
        """A descriptor with no cost metadata is not filtered by cost_ceiling."""
        d = descriptor("rt-a", capabilities=("cap",))
        selector = _make_selector(d)
        result = selector.select((d,), (ref("capability", "cap"),), {"cost_ceiling": 1.0})
        assert result.chosen.identity == "rt-a"

    def test_multiple_candidates_eligible_and_reachable(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",))
        d_b = descriptor("rt-b", capabilities=("cap",))
        selector = _make_selector(d_a, d_b)
        result = selector.select((d_a, d_b), (ref("capability", "cap"),), {})
        assert set(result.reachable_ids) == {"rt-a", "rt-b"}


# ---------------------------------------------------------------------------
# RuntimeSelector._choose — preference branches
# ---------------------------------------------------------------------------


class TestRuntimeSelectorChoose:
    def test_preferred_runtimes_wins(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",))
        d_b = descriptor("rt-b", capabilities=("cap",))
        selector = _make_selector(d_a, d_b)
        result = selector.select(
            (d_a, d_b),
            (ref("capability", "cap"),),
            {"preferred_runtimes": ["rt-b", "rt-a"]},
        )
        assert result.chosen.identity == "rt-b"

    def test_cost_preference_lowest(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",), metadata={"cost": 5.0})
        d_b = descriptor("rt-b", capabilities=("cap",), metadata={"cost": 2.0})
        selector = _make_selector(d_a, d_b)
        result = selector.select(
            (d_a, d_b),
            (ref("capability", "cap"),),
            {"cost_preference": "lowest"},
        )
        assert result.chosen.identity == "rt-b"

    def test_cost_preference_highest(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",), metadata={"cost": 5.0})
        d_b = descriptor("rt-b", capabilities=("cap",), metadata={"cost": 2.0})
        selector = _make_selector(d_a, d_b)
        result = selector.select(
            (d_a, d_b),
            (ref("capability", "cap"),),
            {"cost_preference": "highest"},
        )
        assert result.chosen.identity == "rt-a"

    def test_no_preference_identity_tiebreak(self) -> None:
        d_a = descriptor("rt-a", capabilities=("cap",))
        d_b = descriptor("rt-b", capabilities=("cap",))
        selector = _make_selector(d_a, d_b)
        result = selector.select((d_a, d_b), (ref("capability", "cap"),), {})
        # identity tiebreak: "rt-a" < "rt-b"
        assert result.chosen.identity == "rt-a"

    def test_cost_preference_lowest_absent_cost_is_infinity(self) -> None:
        """A descriptor with no numeric cost ranks last (infinity) under cost_preference=lowest."""
        d_cheap = descriptor("rt-cheap", capabilities=("cap",), metadata={"cost": 1.0})
        d_nocost = descriptor("rt-nocost", capabilities=("cap",))
        selector = _make_selector(d_cheap, d_nocost)
        result = selector.select(
            (d_cheap, d_nocost),
            (ref("capability", "cap"),),
            {"cost_preference": "lowest"},
        )
        assert result.chosen.identity == "rt-cheap"

    def test_cost_preference_highest_absent_cost_is_infinity(self) -> None:
        """A descriptor with no numeric cost ranks last (infinity) under cost_preference=highest."""
        d_expensive = descriptor("rt-exp", capabilities=("cap",), metadata={"cost": 9.0})
        d_nocost = descriptor("rt-nocost", capabilities=("cap",))
        selector = _make_selector(d_expensive, d_nocost)
        result = selector.select(
            (d_expensive, d_nocost),
            (ref("capability", "cap"),),
            {"cost_preference": "highest"},
        )
        assert result.chosen.identity == "rt-exp"

    def test_cost_non_numeric_string_treated_as_absent(self) -> None:
        """Non-numeric cost in metadata → _cost returns None → treated as absent."""
        d_a = descriptor("rt-a", capabilities=("cap",), metadata={"cost": "expensive"})
        d_b = descriptor("rt-b", capabilities=("cap",), metadata={"cost": 1.0})
        selector = _make_selector(d_a, d_b)
        result = selector.select(
            (d_a, d_b),
            (ref("capability", "cap"),),
            {"cost_preference": "lowest"},
        )
        # rt-b has cost=1.0, rt-a has None (→ infinity), so rt-b wins
        assert result.chosen.identity == "rt-b"


# ---------------------------------------------------------------------------
# AllocationLedger
# ---------------------------------------------------------------------------


class TestAllocationLedger:
    def test_active_count_default_zero(self) -> None:
        ledger = AllocationLedger()
        assert ledger.active_count("rt-a") == 0

    def test_at_capacity_false_initially(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        assert ledger.at_capacity(d) is False

    def test_at_capacity_true_after_reserve(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")  # default capacity = 1
        ledger.reserve(_session_ref(), d, correlation=_corr())
        assert ledger.at_capacity(d) is True

    def test_capacity_from_metadata(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a", metadata={"capacity": 2})
        ledger.reserve(_session_ref("s1"), d, correlation=_corr())
        assert ledger.at_capacity(d) is False
        ledger.reserve(_session_ref("s2"), d, correlation=_corr())
        assert ledger.at_capacity(d) is True

    def test_capacity_invalid_zero_falls_back_to_one(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a", metadata={"capacity": 0})
        ledger.reserve(_session_ref(), d, correlation=_corr())
        assert ledger.at_capacity(d) is True

    def test_capacity_invalid_string_falls_back_to_one(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a", metadata={"capacity": "x"})
        ledger.reserve(_session_ref(), d, correlation=_corr())
        assert ledger.at_capacity(d) is True

    def test_capacity_missing_defaults_to_one(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a", metadata={})
        ledger.reserve(_session_ref(), d, correlation=_corr())
        assert ledger.at_capacity(d) is True

    def test_at_capacity_ids(self) -> None:
        ledger = AllocationLedger()
        d_a = descriptor("rt-a")  # capacity 1
        d_b = descriptor("rt-b")  # capacity 1
        ledger.reserve(_session_ref("s1"), d_a, correlation=_corr())
        ids = ledger.at_capacity_ids((d_a, d_b))
        assert ids == frozenset({"rt-a"})

    def test_reserve_returns_reserved_allocation(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        assert alloc.allocation_state is ResourceAllocationState.RESERVED
        assert alloc.runtime_ref.identifier == "rt-a"
        assert alloc.session_ref == _session_ref()

    def test_reserve_raises_when_at_capacity(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        ledger.reserve(_session_ref("s1"), d, correlation=_corr())
        with pytest.raises(AllocationError, match="at capacity"):
            ledger.reserve(_session_ref("s2"), d, correlation=_corr())

    def test_allocate_advances_to_allocated(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        allocated = ledger.allocate(alloc)
        assert allocated.allocation_state is ResourceAllocationState.ALLOCATED

    def test_allocate_raises_when_not_reserved(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        # advance to ALLOCATED first, then try again
        allocated = ledger.allocate(alloc)
        with pytest.raises(AllocationError, match="expected RESERVED"):
            ledger.allocate(allocated)

    def test_release_advances_to_released(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        released = ledger.release(alloc)
        assert released.allocation_state is ResourceAllocationState.RELEASED

    def test_release_decrements_active_count(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a", metadata={"capacity": 2})
        alloc1 = ledger.reserve(_session_ref("s1"), d, correlation=_corr())
        ledger.reserve(_session_ref("s2"), d, correlation=_corr())
        assert ledger.active_count("rt-a") == 2
        ledger.release(alloc1)
        assert ledger.active_count("rt-a") == 1

    def test_release_raises_when_already_released(self) -> None:
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        released = ledger.release(alloc)
        with pytest.raises(AllocationError, match="already released"):
            ledger.release(released)

    def test_release_never_drops_below_zero(self) -> None:
        """Active count is clamped to 0; no negative counts even on double-release bypass."""
        ledger = AllocationLedger()
        d = descriptor("rt-a")
        alloc = ledger.reserve(_session_ref(), d, correlation=_corr())
        # Force active to 0 before releasing to exercise the max(0, ...) branch
        ledger._active["rt-a"] = 0
        # release should raise because state is still RESERVED (not RELEASED)
        # but we want to exercise the max(0,...) line by tricking the state
        # Construct an allocation that appears released-state-from-scratch:
        unreleased_but_count_zero = alloc  # still RESERVED, count already 0
        released = ledger.release(unreleased_but_count_zero)
        assert released.allocation_state is ResourceAllocationState.RELEASED
        assert ledger.active_count("rt-a") == 0  # never goes negative
