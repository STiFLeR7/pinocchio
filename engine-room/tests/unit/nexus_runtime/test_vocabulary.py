"""Unit tests for nexus_runtime.vocabulary.

Verifies RuntimeLifecycleState member names/values and all canonical
Reference target_type string constants.
"""

from __future__ import annotations

from nexus_runtime.vocabulary import (
    ALLOCATION_TARGET_TYPE,
    CAPABILITY_TARGET_TYPE,
    CONTEXT_TARGET_TYPE,
    EXECUTION_MANIFEST_TARGET_TYPE,
    EXECUTION_PACKAGE_TARGET_TYPE,
    RUNTIME_SESSION_TARGET_TYPE,
    RUNTIME_TARGET_TYPE,
    SESSION_TARGET_TYPE,
    STRATEGY_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
    RuntimeLifecycleState,
)

# --------------------------------------------------------------------------- #
# RuntimeLifecycleState — members exist and carry the right string values      #
# --------------------------------------------------------------------------- #


def test_runtime_lifecycle_state_created_value() -> None:
    assert RuntimeLifecycleState.CREATED == "created"


def test_runtime_lifecycle_state_registered_value() -> None:
    assert RuntimeLifecycleState.REGISTERED == "registered"


def test_runtime_lifecycle_state_allocated_value() -> None:
    assert RuntimeLifecycleState.ALLOCATED == "allocated"


def test_runtime_lifecycle_state_prepared_value() -> None:
    assert RuntimeLifecycleState.PREPARED == "prepared"


def test_runtime_lifecycle_state_ready_value() -> None:
    assert RuntimeLifecycleState.READY == "ready"


def test_runtime_lifecycle_state_released_value() -> None:
    assert RuntimeLifecycleState.RELEASED == "released"


def test_runtime_lifecycle_state_failed_value() -> None:
    assert RuntimeLifecycleState.FAILED == "failed"


def test_runtime_lifecycle_state_is_str_enum() -> None:
    # StrEnum members compare equal to their string values
    assert str(RuntimeLifecycleState.CREATED) == "created"
    assert str(RuntimeLifecycleState.RELEASED) == "released"


def test_runtime_lifecycle_state_has_all_realized_canon_members() -> None:
    # Preparation slice (6) + execution/teardown slice (4) + terminal error (1).
    # Paused/Waiting remain deferred (suspend/resume/approval outside the minimal engine).
    assert len(RuntimeLifecycleState) == 11


def test_runtime_lifecycle_state_execution_slice_values() -> None:
    assert RuntimeLifecycleState.RUNNING == "running"
    assert RuntimeLifecycleState.COMPLETED == "completed"
    assert RuntimeLifecycleState.CANCELLED == "cancelled"
    assert RuntimeLifecycleState.DESTROYED == "destroyed"


def test_runtime_lifecycle_state_members_are_unique() -> None:
    values = [s.value for s in RuntimeLifecycleState]
    assert len(values) == len(set(values))


# --------------------------------------------------------------------------- #
# Target-type constants                                                         #
# --------------------------------------------------------------------------- #


def test_runtime_target_type_is_harness() -> None:
    assert RUNTIME_TARGET_TYPE == "harness"


def test_capability_target_type_value() -> None:
    assert CAPABILITY_TARGET_TYPE == "capability"


def test_work_package_target_type_value() -> None:
    assert WORK_PACKAGE_TARGET_TYPE == "work_package"


def test_context_target_type_value() -> None:
    assert CONTEXT_TARGET_TYPE == "context_package"


def test_strategy_target_type_value() -> None:
    assert STRATEGY_TARGET_TYPE == "execution_strategy"


def test_session_target_type_value() -> None:
    assert SESSION_TARGET_TYPE == "execution_session"


def test_execution_package_target_type_value() -> None:
    assert EXECUTION_PACKAGE_TARGET_TYPE == "execution_package"


def test_execution_manifest_target_type_value() -> None:
    assert EXECUTION_MANIFEST_TARGET_TYPE == "execution_manifest"


def test_runtime_session_target_type_value() -> None:
    assert RUNTIME_SESSION_TARGET_TYPE == "runtime_session"


def test_allocation_target_type_value() -> None:
    assert ALLOCATION_TARGET_TYPE == "runtime_allocation"


def test_target_type_constants_are_strings() -> None:
    constants = [
        RUNTIME_TARGET_TYPE,
        CAPABILITY_TARGET_TYPE,
        WORK_PACKAGE_TARGET_TYPE,
        CONTEXT_TARGET_TYPE,
        STRATEGY_TARGET_TYPE,
        SESSION_TARGET_TYPE,
        EXECUTION_PACKAGE_TARGET_TYPE,
        EXECUTION_MANIFEST_TARGET_TYPE,
        RUNTIME_SESSION_TARGET_TYPE,
        ALLOCATION_TARGET_TYPE,
    ]
    for c in constants:
        assert isinstance(c, str)
        assert c  # non-empty
