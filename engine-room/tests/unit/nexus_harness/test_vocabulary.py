"""Unit tests for nexus_harness.vocabulary.

Pins the StrEnum members and values for PackageStatus / ManifestStatus, and
asserts that every canonical target-type string constant holds the exact value
expected by upstream layers.
"""

from __future__ import annotations

from enum import StrEnum

from nexus_harness.vocabulary import (
    ARTIFACT_TARGET_TYPE,
    CAPABILITY_TARGET_TYPE,
    CONTEXT_TARGET_TYPE,
    EXECUTION_MANIFEST_TARGET_TYPE,
    EXECUTION_PACKAGE_TARGET_TYPE,
    GOAL_TARGET_TYPE,
    GRAPH_TARGET_TYPE,
    HARNESS_REQUEST_TARGET_TYPE,
    PLAN_TARGET_TYPE,
    POLICY_TARGET_TYPE,
    SESSION_TARGET_TYPE,
    SKILL_TARGET_TYPE,
    STRATEGY_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
    ManifestStatus,
    PackageStatus,
)

# ---------------------------------------------------------------------------
# PackageStatus
# ---------------------------------------------------------------------------


def test_package_status_is_str_enum() -> None:
    assert issubclass(PackageStatus, StrEnum)


def test_package_status_members() -> None:
    members = {m.name for m in PackageStatus}
    assert members == {"COMPILED", "FAILED"}


def test_package_status_compiled_value() -> None:
    assert PackageStatus.COMPILED == "compiled"


def test_package_status_failed_value() -> None:
    assert PackageStatus.FAILED == "failed"


def test_package_status_is_str() -> None:
    # StrEnum values must compare equal to plain strings without casting.
    assert PackageStatus.COMPILED == "compiled"
    assert isinstance(PackageStatus.COMPILED, str)


# ---------------------------------------------------------------------------
# ManifestStatus
# ---------------------------------------------------------------------------


def test_manifest_status_is_str_enum() -> None:
    assert issubclass(ManifestStatus, StrEnum)


def test_manifest_status_members() -> None:
    members = {m.name for m in ManifestStatus}
    assert members == {"CREATED", "FAILED"}


def test_manifest_status_created_value() -> None:
    assert ManifestStatus.CREATED == "created"


def test_manifest_status_failed_value() -> None:
    assert ManifestStatus.FAILED == "failed"


def test_manifest_status_is_str() -> None:
    assert isinstance(ManifestStatus.CREATED, str)


# ---------------------------------------------------------------------------
# Target-type string constants
# ---------------------------------------------------------------------------


def test_goal_target_type() -> None:
    assert GOAL_TARGET_TYPE == "goal"


def test_plan_target_type() -> None:
    assert PLAN_TARGET_TYPE == "plan"


def test_context_target_type() -> None:
    assert CONTEXT_TARGET_TYPE == "context_package"


def test_strategy_target_type() -> None:
    assert STRATEGY_TARGET_TYPE == "execution_strategy"


def test_graph_target_type() -> None:
    assert GRAPH_TARGET_TYPE == "execution_graph"


def test_work_package_target_type() -> None:
    assert WORK_PACKAGE_TARGET_TYPE == "work_package"


def test_skill_target_type() -> None:
    assert SKILL_TARGET_TYPE == "skill"


def test_capability_target_type() -> None:
    assert CAPABILITY_TARGET_TYPE == "capability"


def test_policy_target_type() -> None:
    assert POLICY_TARGET_TYPE == "policy"


def test_artifact_target_type() -> None:
    assert ARTIFACT_TARGET_TYPE == "artifact"


def test_session_target_type() -> None:
    assert SESSION_TARGET_TYPE == "execution_session"


def test_harness_request_target_type() -> None:
    assert HARNESS_REQUEST_TARGET_TYPE == "harness_request"


def test_execution_package_target_type() -> None:
    assert EXECUTION_PACKAGE_TARGET_TYPE == "execution_package"


def test_execution_manifest_target_type() -> None:
    assert EXECUTION_MANIFEST_TARGET_TYPE == "execution_manifest"


def test_all_target_type_constants_are_distinct() -> None:
    constants = [
        GOAL_TARGET_TYPE,
        PLAN_TARGET_TYPE,
        CONTEXT_TARGET_TYPE,
        STRATEGY_TARGET_TYPE,
        GRAPH_TARGET_TYPE,
        WORK_PACKAGE_TARGET_TYPE,
        SKILL_TARGET_TYPE,
        CAPABILITY_TARGET_TYPE,
        POLICY_TARGET_TYPE,
        ARTIFACT_TARGET_TYPE,
        SESSION_TARGET_TYPE,
        HARNESS_REQUEST_TARGET_TYPE,
        EXECUTION_PACKAGE_TARGET_TYPE,
        EXECUTION_MANIFEST_TARGET_TYPE,
    ]
    assert len(constants) == len(set(constants))
