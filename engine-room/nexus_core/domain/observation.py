"""Observation — Supervision's descriptive account of operational execution.

Contract: ``contracts/observation.md``. Owned by Supervision. Binding: ADR-003
(§3.4 Observation owned by Supervision), ADR-001 (event-sourced state).
Invariants: INV-11 (Observation is owned by Supervision; Execution emits raw
Execution Events, never Observations), descriptive-never-evaluative (an
Observation *describes* execution and never determines completion — Validation
owns completion), INV-23 (Supervision *recommends*; Orchestration *acts* —
``intervention_recommendation`` never controls execution), INV-13/14/15, INV-17,
INV-31.

The Observation is derived (not self-reported): ``derived_from_events`` is
required and non-empty because provenance is mandatory — Supervision determines
health from observable evidence, never assumes it. The ``stage`` field is the
lifecycle status (a projection of the event log), optional until projected.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import InterventionRecommendation, OperationalHealth
from nexus_core.contracts.status import ObservationStage


class Observation(DomainObject):
    """A descriptive account of execution (contract: observation.md). Never evaluative."""

    LIFECYCLE_NAME: ClassVar[str] = "observation"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique Observation identifier; addressable for history and audit."""
    execution_identifier: str = Field(min_length=1)
    """The execution session this Observation describes."""
    correlation_identifier: str = Field(min_length=1)
    """Correlation/trace lineage shared with the derived-from Events and the operation (INV-39)."""
    timestamp: str = Field(min_length=1)
    """When the Observation was derived; recorded as data so replay is deterministic (INV-17)."""
    derived_from_events: tuple[Reference, ...] = Field(min_length=1)
    """References (by id) to the raw Execution Events this was derived from — provenance is mandatory."""
    execution_state: str = Field(min_length=1)
    """The described operational state of execution at this point; descriptive, not an evaluation."""
    progress: Struct
    """Observed progress of the work (doc 09 *Observation Model*: Progress)."""

    # --- optional ---------------------------------------------------------- #
    stage: ObservationStage | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    runtime_activity: Struct | None = None
    """Observed runtime activity/responsiveness; describes behavior, never runtime internals."""
    resource_usage: Struct | None = None
    """Observed resource utilization for the execution."""
    operational_events: tuple[Struct, ...] = ()
    """Observed operational events (Execution Started, Checkpoint Reached, Retry Performed, …)."""
    checkpoint_history: tuple[Reference, ...] = ()
    """References (by id) to Checkpoints observed for this execution; references only."""
    health_indicators: Struct | None = None
    """Observed indicators (progress velocity, checkpoint frequency, retry frequency, …)."""
    health_assessment: OperationalHealth | None = None
    """Supervision's derived health classification; descriptive, distinct from a completion verdict."""
    anomalies: tuple[Struct, ...] = ()
    """Detected anomalies, stalled-work signals, or repeated-failure signals."""
    intervention_recommendation: InterventionRecommendation | None = None
    """A *recommended* intervention only — Orchestration decides and acts (INV-23)."""
    rationale: str | None = None
    """Explanation supporting the assessment/recommendation, recorded for explainability (INV-31)."""
