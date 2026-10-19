"""Harness vocabularies — the closed, harness-local enumerations.

The Harness *compiles*; these name the compilation states it records. They are
intentionally harness-local: there is no frozen core contract for an Execution
Package or an Execution Manifest — those are Harness *outputs* (doc 11), exactly as
the Execution Session / Harness Request were Orchestration outputs. Target-type
constants are the canonical ``Reference`` ``target_type`` strings this layer emits
and consumes, kept here as one source of truth so they never drift from the strings
Planning / Orchestration already use.
"""

from __future__ import annotations

from enum import StrEnum


class PackageStatus(StrEnum):
    """Lifecycle of one compiled Execution Package (descriptive projection)."""

    COMPILED = "compiled"
    FAILED = "failed"


class ManifestStatus(StrEnum):
    """Lifecycle of one Execution Manifest (descriptive projection)."""

    CREATED = "created"
    FAILED = "failed"


# --- canonical Reference target_type strings (must match upstream layers') ----- #
GOAL_TARGET_TYPE = "goal"
PLAN_TARGET_TYPE = "plan"
CONTEXT_TARGET_TYPE = "context_package"
STRATEGY_TARGET_TYPE = "execution_strategy"
GRAPH_TARGET_TYPE = "execution_graph"
WORK_PACKAGE_TARGET_TYPE = "work_package"
SKILL_TARGET_TYPE = "skill"
CAPABILITY_TARGET_TYPE = "capability"
POLICY_TARGET_TYPE = "policy"
ARTIFACT_TARGET_TYPE = "artifact"
SESSION_TARGET_TYPE = "execution_session"
HARNESS_REQUEST_TARGET_TYPE = "harness_request"
EXECUTION_PACKAGE_TARGET_TYPE = "execution_package"
EXECUTION_MANIFEST_TARGET_TYPE = "execution_manifest"
