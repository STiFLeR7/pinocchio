"""Checkpoint — a derived, reference-not-copy snapshot of execution state.

Contract: ``contracts/checkpoint.md``. Created by Execution, restored by Recovery.
Binding: ADR-001 (event-sourced state — a Checkpoint is derived, never
authoritative). Invariants: INV-14 (a Checkpoint is a derived snapshot tied to a
``log_position`` and rebuildable from the Event Log — never a third source of
truth), INV-18 (long-running work resumes from the nearest valid Checkpoint plus
event-tail replay, never from operator intent or the Goal), reference-not-copy (it
references persistent objects by id and never duplicates their content), INV-15,
INV-17.

The ``stage`` field is the lifecycle status (a projection of the event log),
optional until projected.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import CheckpointType
from nexus_core.contracts.status import CheckpointStage


class Checkpoint(DomainObject):
    """A derived execution snapshot (contract: checkpoint.md). Never authoritative."""

    LIFECYCLE_NAME: ClassVar[str] = "checkpoint"

    # --- required ---------------------------------------------------------- #
    identifier: str = Field(min_length=1)
    """Stable, unique Checkpoint identity; addressable for restoration and audit."""
    execution_identifier: str = Field(min_length=1)
    """The execution session this Checkpoint belongs to."""
    log_position: int
    """The Event Log position this Checkpoint corresponds to; the anchor for tail replay (INV-14)."""
    timestamp: str = Field(min_length=1)
    """When the Checkpoint was created; recorded as data (INV-17)."""
    execution_state: str = Field(min_length=1)
    """The projected execution state captured at this point (a reference/value, not a re-derivation)."""
    current_work_package: Reference
    """Reference (by id) to the Work Package in progress at the checkpoint."""
    execution_graph_position: Reference
    """Reference to the current Execution Graph and current node within it."""
    completed_nodes: tuple[str, ...]
    """Execution Graph nodes already completed at this position, so completed work is not repeated."""
    pending_nodes: tuple[str, ...]
    """Execution Graph nodes still to execute."""
    context_references: tuple[Reference, ...]
    """References (by id) to the validated Context Package(s) in effect; never embedded copies."""
    artifacts_produced: tuple[Reference, ...]
    """References (by id) to Artifacts produced so far; references only, never the contents."""
    evidence_collected: tuple[Reference, ...]
    """References (by id) to Evidence gathered so far; references only."""
    correlation_identifier: str = Field(min_length=1)
    """Correlation/trace lineage shared with the operation's Events (INV-39)."""

    # --- optional ---------------------------------------------------------- #
    stage: CheckpointStage | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    parent_checkpoint: Reference | None = None
    """Reference to the prior Checkpoint in this execution's chain, for ordered restoration."""
    version: str | None = None
    """Checkpoint version marker for the chain."""
    checkpoint_type: CheckpointType | None = None
    """The captured concern (Execution / Workflow / Context / Validation / Recovery)."""
    recovery_metadata: Struct | None = None
    """Recovery-specific hints: retry context, failure context, policy-compatibility data."""
    execution_metadata: Struct | None = None
    """Auditing context (goal, plan, work package, strategy, runtime, creator) carried by reference."""
    synchronization_state: Struct | None = None
    """Graph synchronization/barrier state, for resuming parallel/coordinated execution."""
    validation_status: Struct | None = None
    """Result of the most recent pre-restore validation, when recorded."""
