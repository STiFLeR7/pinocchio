"""Immutable base types for all Nexus v2 domain objects.

Pure business objects: no persistence, no API, no transport, no runtime logic,
no I/O. Every domain object is immutable by construction (Pydantic ``frozen``).

The architecture mandates **references over embedding** (Evidence always by id,
the Execution Graph as a sibling reference, Context-by-reference for large Work
Packages). ``Reference`` is the canonical typed, by-id pointer used for that.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

# An opaque, logically-immutable structured value. Used for contract fields whose
# internal shape is intentionally unspecified at Phase 1 (e.g. metadata, source,
# payload, opaque constraint structs). Modeled as a read-only mapping.
Struct = Mapping[str, Any]


class ValueObject(BaseModel):
    """Frozen base for small, composed value objects.

    ``extra="forbid"`` makes schema conformance strict: an unknown field is an
    error, never silently accepted (fail fast, no silent correction).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class DomainObject(ValueObject):
    """Base for top-level Nexus operational domain objects.

    Immutable. Holds only business data. A domain object never performs
    persistence, transport, validation orchestration, registry lookup, or
    runtime logic — those live in other foundation packages and in later phases.
    """


class Reference(ValueObject):
    """A typed, by-id pointer to another domain object.

    A Reference never embeds the target's content; it records *what kind* of
    object is referenced and *which* one. References keep the object graph
    acyclic-by-construction at the data level and honor the architecture's
    reference-not-copy rule (INV-12, INV-27, ADR-003 §3.3).
    """

    target_type: str
    identifier: str


class Correlation(ValueObject):
    """Correlation / trace lineage shared across one operation.

    All objects and events of a single operation share a ``correlation_identifier``;
    it is the causal-ordering boundary (INV-39). ``trace_identifier`` is an
    optional finer-grained distributed-trace handle.
    """

    correlation_identifier: str
    trace_identifier: str | None = None


class Constraint(ValueObject):
    """A declared operational boundary (time, budget, governance, quality, …).

    Constraints always override execution preferences. Their detailed internal
    shape is intentionally open at Phase 1; ``kind`` names the boundary and
    ``detail`` carries its specifics.
    """

    kind: str
    detail: Struct = {}
