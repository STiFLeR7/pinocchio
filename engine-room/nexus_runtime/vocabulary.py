"""Runtime vocabularies — the closed, runtime-local enumerations and reference tags.

The Runtime Manager *prepares*; these name the preparation states it records and the
canonical ``Reference`` ``target_type`` strings this layer emits and consumes.

There is no frozen core contract for a Runtime Session, an Allocation, or a Runtime
Intake — those are Runtime *outputs/inputs* (docs 00, 02), exactly as the Execution
Package / Execution Manifest were Harness outputs. The one shared allocation vocabulary
(``ResourceAllocationState``) is **reused** from ``nexus_core`` and never redefined here
(INV-36: availability/health belong to the Registry; ``ResourceAllocationState`` is RM's
own bookkeeping — doc 04 §6).

``RuntimeLifecycleState`` realizes doc 07's canonical session machine. The **preparation**
slice (``Created → Registered → Allocated → Prepared → Ready``, plus ``Released`` as the
preparation-abandon terminal) was implemented in Phase 8A when RM stops at ``Ready``
(handoff). The **execution/teardown** slice (``Running → Completed / Cancelled / Failed →
Destroyed``) is realized by the Execution Engine phase (this vertical slice); it was the
canon of doc 07 all along, merely deferred in code (doc 07 §1, §4).

The suspend/resume/approval-block states (``Paused / Waiting``) remain deferred: the
minimal Execution Engine implements no scheduling, recovery, or approval pause, so those
canonical states are not yet driven. They stay reserved for a later phase and are not
modeled here to avoid unexercised vocabulary.
"""

from __future__ import annotations

from enum import StrEnum


class RuntimeLifecycleState(StrEnum):
    """The Runtime Session lifecycle (doc 07 canon; ``Paused``/``Waiting`` deferred)."""

    # --- preparation (Phase 8A) --------------------------------------------- #
    CREATED = "created"
    REGISTERED = "registered"
    ALLOCATED = "allocated"
    PREPARED = "prepared"
    READY = "ready"
    RELEASED = "released"
    # --- execution + teardown (Execution Engine phase) ---------------------- #
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DESTROYED = "destroyed"
    # --- terminal error (reachable from either slice) ----------------------- #
    FAILED = "failed"


# --- canonical Reference target_type strings (must match upstream layers') ----- #
# A "Runtime" is a Harness of category RUNTIME (ADR-002); its Reference target_type is
# therefore the same ``"harness"`` string Orchestration's candidate_harness_refs use.
RUNTIME_TARGET_TYPE = "harness"
CAPABILITY_TARGET_TYPE = "capability"
WORK_PACKAGE_TARGET_TYPE = "work_package"
CONTEXT_TARGET_TYPE = "context_package"
STRATEGY_TARGET_TYPE = "execution_strategy"
SESSION_TARGET_TYPE = "execution_session"
EXECUTION_PACKAGE_TARGET_TYPE = "execution_package"
EXECUTION_MANIFEST_TARGET_TYPE = "execution_manifest"
RUNTIME_SESSION_TARGET_TYPE = "runtime_session"
ALLOCATION_TARGET_TYPE = "runtime_allocation"
