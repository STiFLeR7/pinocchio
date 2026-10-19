"""Runtime inputs — the ``nexus_core``-only projection RM prepares from.

Per doc 00 §4 the Runtime Manager imports **only** ``nexus_core`` and ``nexus_infra`` —
never ``nexus_harness`` or ``nexus_orchestration``. It therefore does **not** consume the
``ExecutionPackage`` / ``ExecutionManifest`` / ``RuntimeRequest`` *types*; it consumes a
:class:`RuntimeIntake` — their ``nexus_core``-expressible projection — assembled at the
integration boundary (which may import the upstream layers). This is the same
"consume outputs by value/reference, never reach back" rule every prior layer followed,
applied one level stricter.

The intake carries exactly what preparation needs: the embedded **Work Package** RM will
hand the runtime (INV-09), the required capability references, the Orchestration-supplied
**candidate** harness references (candidates only, INV-37), the declarative
``runtime_policy``, and the correlation lineage (INV-39). It names no runtime and ranks
none — selection is RM's (doc 06, INV-21).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Correlation, Reference, Struct, ValueObject
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.work_package import WorkPackage


class RuntimeIntake(ValueObject):
    """One package's preparation inputs, projected into ``nexus_core`` terms only."""

    package_identity: str
    node: str
    session_ref: Reference
    work_package: WorkPackage
    required_capability_refs: tuple[Reference, ...] = ()
    candidate_harness_refs: tuple[Reference, ...] = ()
    runtime_policy: Struct = Field(default_factory=dict)
    coordination: CoordinationModel = CoordinationModel.SEQUENTIAL
    context_view_ref: Reference | None = None
    manifest_ref: Reference | None = None
    execution_strategy_ref: Reference | None = None
    attempt: int = 1
    correlation: Correlation | None = None


class PreparationRequest(ValueObject):
    """The complete, immutable input to one preparation cycle (a batch of intakes)."""

    intakes: tuple[RuntimeIntake, ...]
    session_ref: Reference | None = None
    correlation_identifier: str | None = None
