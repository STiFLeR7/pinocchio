"""Unit tests for nexus_runtime.runtime_session.

Covers RuntimeSessionBuilder.build and the RuntimeSession value-object methods:
reference(), transitioned_to(), bound_to(), and with_telemetry().  Every test is
deterministic — no clock, no randomness.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_runtime.lifecycle import IllegalTransitionError
from nexus_runtime.requests import RuntimeIntake
from nexus_runtime.runtime_session import RuntimeSession, RuntimeSessionBuilder
from nexus_runtime.vocabulary import (
    RUNTIME_SESSION_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
    RuntimeLifecycleState,
)
from tests.unit.nexus_runtime.helpers import intake, ref

# --------------------------------------------------------------------------- #
# Shared builder and correlation fixture                                        #
# --------------------------------------------------------------------------- #

_BUILDER = RuntimeSessionBuilder()
_CORRELATION = "cor-test-001"


def _build(
    rtintake: RuntimeIntake | None = None, *, correlation: str = _CORRELATION
) -> RuntimeSession:
    """Convenience wrapper around the builder."""
    return _BUILDER.build(rtintake or intake(), correlation_identifier=correlation)


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — identity                                        #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderIdentity:
    def test_identity_follows_rts_package_attempt_pattern(self) -> None:
        session = _build(intake(package_identity="pkg-abc", attempt=1))

        assert session.identity == "rts-pkg-abc-01"

    def test_attempt_is_zero_padded_to_two_digits(self) -> None:
        session = _build(intake(package_identity="pkg-x", attempt=3))

        assert session.identity == "rts-pkg-x-03"

    def test_attempt_double_digit_is_not_padded_further(self) -> None:
        session = _build(intake(package_identity="pkg-y", attempt=10))

        assert session.identity == "rts-pkg-y-10"

    def test_different_attempts_yield_different_identities(self) -> None:
        s1 = _build(intake(package_identity="pkg-z", attempt=1))
        s2 = _build(intake(package_identity="pkg-z", attempt=2))

        assert s1.identity != s2.identity


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — lifecycle and structural fields                 #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderLifecycle:
    def test_initial_lifecycle_state_is_created(self) -> None:
        session = _build()

        assert session.lifecycle_state is RuntimeLifecycleState.CREATED

    def test_attempt_field_matches_intake(self) -> None:
        session = _build(intake(attempt=5))

        assert session.attempt == 5

    def test_node_field_matches_intake(self) -> None:
        session = _build(intake(node="node-x"))

        assert session.node == "node-x"


class TestRuntimeSessionBuilderRefs:
    def test_execution_package_ref_has_correct_type(self) -> None:
        session = _build(intake(package_identity="pkg-ref-test"))

        assert session.execution_package_ref.target_type == "execution_package"

    def test_execution_package_ref_identifier_matches_package_identity(self) -> None:
        session = _build(intake(package_identity="pkg-ref-test"))

        assert session.execution_package_ref.identifier == "pkg-ref-test"

    def test_work_package_ref_has_correct_type(self) -> None:
        session = _build(intake(work_package_id="wp-001"))

        assert session.work_package_ref.target_type == WORK_PACKAGE_TARGET_TYPE

    def test_work_package_ref_identifier_matches_work_package(self) -> None:
        session = _build(intake(work_package_id="wp-001"))

        assert session.work_package_ref.identifier == "wp-001"

    def test_session_ref_matches_intake_session_ref(self) -> None:
        rtintake = intake(session="session-abc")
        session = _build(rtintake)

        assert session.session_ref.identifier == "session-abc"
        assert session.session_ref.target_type == "execution_session"


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — optional refs (None vs populated)               #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderOptionalRefs:
    def test_context_view_ref_is_none_when_not_provided(self) -> None:
        session = _build(intake(context_view=None))

        assert session.context_view_ref is None

    def test_manifest_ref_is_none_when_not_provided(self) -> None:
        session = _build(intake(manifest=None))

        assert session.manifest_ref is None

    def test_execution_strategy_ref_is_none_when_not_provided(self) -> None:
        session = _build(intake(strategy=None))

        assert session.execution_strategy_ref is None

    def test_context_view_ref_is_set_when_provided(self) -> None:
        session = _build(intake(context_view="ctx-v1"))

        assert session.context_view_ref is not None
        assert session.context_view_ref.identifier == "ctx-v1"

    def test_manifest_ref_is_set_when_provided(self) -> None:
        session = _build(intake(manifest="manifest-v1"))

        assert session.manifest_ref is not None
        assert session.manifest_ref.identifier == "manifest-v1"

    def test_execution_strategy_ref_is_set_when_provided(self) -> None:
        session = _build(intake(strategy="strat-v1"))

        assert session.execution_strategy_ref is not None
        assert session.execution_strategy_ref.identifier == "strat-v1"

    def test_all_optional_refs_set_together(self) -> None:
        session = _build(intake(context_view="c", manifest="m", strategy="s"))

        assert session.context_view_ref is not None
        assert session.manifest_ref is not None
        assert session.execution_strategy_ref is not None


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — runtime/allocation refs start None             #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderRuntimeAllocationRefsInitiallyNone:
    def test_runtime_ref_is_none_on_creation(self) -> None:
        session = _build()

        assert session.runtime_ref is None

    def test_allocation_ref_is_none_on_creation(self) -> None:
        session = _build()

        assert session.allocation_ref is None

    def test_telemetry_refs_is_empty_on_creation(self) -> None:
        session = _build()

        assert session.telemetry_refs == ()


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — metadata                                        #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderMetadata:
    def test_metadata_contains_node_key(self) -> None:
        session = _build(intake(node="node-meta"))

        assert session.metadata["node"] == "node-meta"

    def test_metadata_contains_package_key(self) -> None:
        session = _build(intake(package_identity="pkg-meta"))

        assert session.metadata["package"] == "pkg-meta"

    def test_metadata_contains_work_package_key(self) -> None:
        session = _build(intake(work_package_id="wp-meta"))

        assert session.metadata["work_package"] == "wp-meta"

    def test_metadata_contains_candidate_count(self) -> None:
        session = _build(intake(candidates=("rt-a", "rt-b")))

        assert session.metadata["candidate_count"] == 2

    def test_metadata_contains_required_capability_count(self) -> None:
        session = _build(intake(required=("cap-1", "cap-2", "cap-3")))

        assert session.metadata["required_capability_count"] == 3

    def test_metadata_candidate_count_zero_when_no_candidates(self) -> None:
        session = _build(intake(candidates=()))

        assert session.metadata["candidate_count"] == 0

    def test_metadata_required_count_zero_when_no_requirements(self) -> None:
        session = _build(intake(required=()))

        assert session.metadata["required_capability_count"] == 0


# --------------------------------------------------------------------------- #
# RuntimeSessionBuilder.build — correlation                                     #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBuilderCorrelation:
    def test_correlation_identifier_matches_supplied_value(self) -> None:
        session = _build(correlation="cor-specific-001")

        assert session.correlation.correlation_identifier == "cor-specific-001"

    def test_different_correlations_stored_correctly(self) -> None:
        s1 = _build(correlation="cor-aaa")
        s2 = _build(correlation="cor-bbb")

        assert s1.correlation.correlation_identifier == "cor-aaa"
        assert s2.correlation.correlation_identifier == "cor-bbb"


# --------------------------------------------------------------------------- #
# RuntimeSession.reference()                                                    #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionReference:
    def test_reference_target_type_is_runtime_session(self) -> None:
        session = _build()
        r = session.reference()

        assert r.target_type == RUNTIME_SESSION_TARGET_TYPE

    def test_reference_identifier_equals_session_identity(self) -> None:
        session = _build(intake(package_identity="pkg-ref", attempt=1))
        r = session.reference()

        assert r.identifier == session.identity

    def test_reference_is_consistent_with_identity(self) -> None:
        session = _build(intake(package_identity="pkg-q", attempt=7))
        r = session.reference()

        assert r.identifier == "rts-pkg-q-07"


# --------------------------------------------------------------------------- #
# RuntimeSession.transitioned_to — legal transitions                            #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionTransitionedToLegal:
    def test_created_to_registered_returns_new_session(self) -> None:
        original = _build()
        updated = original.transitioned_to(RuntimeLifecycleState.REGISTERED)

        assert updated.lifecycle_state is RuntimeLifecycleState.REGISTERED

    def test_transition_returns_new_instance(self) -> None:
        original = _build()
        updated = original.transitioned_to(RuntimeLifecycleState.REGISTERED)

        assert updated is not original

    def test_original_is_unchanged_after_transition(self) -> None:
        original = _build()
        _ = original.transitioned_to(RuntimeLifecycleState.REGISTERED)

        assert original.lifecycle_state is RuntimeLifecycleState.CREATED

    def test_chain_created_registered_allocated(self) -> None:
        session = _build()
        session = session.transitioned_to(RuntimeLifecycleState.REGISTERED)
        session = session.transitioned_to(RuntimeLifecycleState.ALLOCATED)

        assert session.lifecycle_state is RuntimeLifecycleState.ALLOCATED

    def test_chain_to_ready(self) -> None:
        session = _build()
        for state in (
            RuntimeLifecycleState.REGISTERED,
            RuntimeLifecycleState.ALLOCATED,
            RuntimeLifecycleState.PREPARED,
            RuntimeLifecycleState.READY,
        ):
            session = session.transitioned_to(state)

        assert session.lifecycle_state is RuntimeLifecycleState.READY

    def test_created_to_failed_is_legal(self) -> None:
        session = _build()
        failed = session.transitioned_to(RuntimeLifecycleState.FAILED)

        assert failed.lifecycle_state is RuntimeLifecycleState.FAILED

    def test_created_to_released_is_legal(self) -> None:
        session = _build()
        released = session.transitioned_to(RuntimeLifecycleState.RELEASED)

        assert released.lifecycle_state is RuntimeLifecycleState.RELEASED

    def test_failed_to_released_is_legal(self) -> None:
        session = _build()
        session = session.transitioned_to(RuntimeLifecycleState.FAILED)
        released = session.transitioned_to(RuntimeLifecycleState.RELEASED)

        assert released.lifecycle_state is RuntimeLifecycleState.RELEASED

    def test_other_fields_are_preserved_through_transition(self) -> None:
        original = _build(intake(package_identity="pkg-preserve", node="node-p"))
        updated = original.transitioned_to(RuntimeLifecycleState.REGISTERED)

        assert updated.identity == original.identity
        assert updated.node == original.node
        assert updated.execution_package_ref == original.execution_package_ref


# --------------------------------------------------------------------------- #
# RuntimeSession.transitioned_to — illegal transitions                          #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionTransitionedToIllegal:
    def test_created_to_allocated_raises_illegal_transition_error(self) -> None:
        session = _build()

        with pytest.raises(IllegalTransitionError):
            session.transitioned_to(RuntimeLifecycleState.ALLOCATED)

    def test_created_to_prepared_raises_illegal_transition_error(self) -> None:
        session = _build()

        with pytest.raises(IllegalTransitionError):
            session.transitioned_to(RuntimeLifecycleState.PREPARED)

    def test_created_to_ready_raises_illegal_transition_error(self) -> None:
        session = _build()

        with pytest.raises(IllegalTransitionError):
            session.transitioned_to(RuntimeLifecycleState.READY)

    def test_released_to_anything_raises_illegal_transition_error(self) -> None:
        session = _build()
        session = session.transitioned_to(RuntimeLifecycleState.RELEASED)

        with pytest.raises(IllegalTransitionError):
            session.transitioned_to(RuntimeLifecycleState.FAILED)

    def test_original_unchanged_after_illegal_transition_attempt(self) -> None:
        session = _build()

        with pytest.raises(IllegalTransitionError):
            session.transitioned_to(RuntimeLifecycleState.ALLOCATED)

        assert session.lifecycle_state is RuntimeLifecycleState.CREATED


# --------------------------------------------------------------------------- #
# RuntimeSession.bound_to                                                       #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionBoundTo:
    def test_bound_to_sets_runtime_ref(self) -> None:
        session = _build()
        runtime_r = ref("harness", "claude-code")
        allocation_r = ref("runtime_allocation", "alloc-001")

        updated = session.bound_to(runtime_ref=runtime_r, allocation_ref=allocation_r)

        assert updated.runtime_ref == runtime_r

    def test_bound_to_sets_allocation_ref(self) -> None:
        session = _build()
        runtime_r = ref("harness", "claude-code")
        allocation_r = ref("runtime_allocation", "alloc-001")

        updated = session.bound_to(runtime_ref=runtime_r, allocation_ref=allocation_r)

        assert updated.allocation_ref == allocation_r

    def test_bound_to_returns_new_instance(self) -> None:
        session = _build()
        runtime_r = ref("harness", "claude-code")
        allocation_r = ref("runtime_allocation", "alloc-001")

        updated = session.bound_to(runtime_ref=runtime_r, allocation_ref=allocation_r)

        assert updated is not session

    def test_original_unchanged_after_bound_to(self) -> None:
        session = _build()
        runtime_r = ref("harness", "claude-code")
        allocation_r = ref("runtime_allocation", "alloc-001")

        _ = session.bound_to(runtime_ref=runtime_r, allocation_ref=allocation_r)

        assert session.runtime_ref is None
        assert session.allocation_ref is None

    def test_other_fields_preserved_through_bound_to(self) -> None:
        original = _build(intake(package_identity="pkg-bnd"))
        runtime_r = ref("harness", "rt-x")
        allocation_r = ref("runtime_allocation", "alloc-x")

        updated = original.bound_to(runtime_ref=runtime_r, allocation_ref=allocation_r)

        assert updated.identity == original.identity
        assert updated.lifecycle_state == original.lifecycle_state


# --------------------------------------------------------------------------- #
# RuntimeSession.with_telemetry                                                 #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionWithTelemetry:
    def test_with_telemetry_appends_a_single_ref(self) -> None:
        session = _build()
        tref = ref("telemetry_stream", "tel-001")

        updated = session.with_telemetry(tref)

        assert tref in updated.telemetry_refs

    def test_with_telemetry_returns_new_instance(self) -> None:
        session = _build()

        updated = session.with_telemetry(ref("telemetry_stream", "tel-001"))

        assert updated is not session

    def test_original_unchanged_after_with_telemetry(self) -> None:
        session = _build()

        _ = session.with_telemetry(ref("telemetry_stream", "tel-001"))

        assert session.telemetry_refs == ()

    def test_with_telemetry_appends_multiple_refs(self) -> None:
        session = _build()
        t1 = ref("telemetry_stream", "tel-001")
        t2 = ref("telemetry_stream", "tel-002")

        updated = session.with_telemetry(t1, t2)

        assert t1 in updated.telemetry_refs
        assert t2 in updated.telemetry_refs
        assert len(updated.telemetry_refs) == 2

    def test_with_telemetry_accumulates_across_calls(self) -> None:
        session = _build()
        t1 = ref("telemetry_stream", "tel-001")
        t2 = ref("telemetry_stream", "tel-002")

        session = session.with_telemetry(t1)
        session = session.with_telemetry(t2)

        assert t1 in session.telemetry_refs
        assert t2 in session.telemetry_refs
        assert len(session.telemetry_refs) == 2

    def test_with_telemetry_preserves_other_fields(self) -> None:
        original = _build(intake(package_identity="pkg-tel"))
        tref = ref("telemetry_stream", "tel-001")

        updated = original.with_telemetry(tref)

        assert updated.identity == original.identity
        assert updated.lifecycle_state == original.lifecycle_state


# --------------------------------------------------------------------------- #
# RuntimeSession immutability                                                   #
# --------------------------------------------------------------------------- #


class TestRuntimeSessionImmutability:
    def test_direct_field_assignment_raises(self) -> None:
        session = _build()

        with pytest.raises((TypeError, AttributeError, ValidationError)):
            session.lifecycle_state = RuntimeLifecycleState.REGISTERED  # type: ignore[misc]

    def test_runtime_ref_direct_assignment_raises(self) -> None:
        session = _build()

        with pytest.raises((TypeError, AttributeError, ValidationError)):
            session.runtime_ref = ref("harness", "rt-a")  # type: ignore[misc]
