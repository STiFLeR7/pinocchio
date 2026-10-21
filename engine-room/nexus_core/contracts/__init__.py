"""Contract primitives — the strongly-typed source-of-truth vocabulary.

Implements the frozen logical contracts in ``contracts/`` as typed Python:
the immutable base objects (``base``), the shared value enums and category
taxonomies (``enums``), and the per-object lifecycle status enums (``status``).

Domain models compose these; they never redefine them (INV-07).
"""

from nexus_core.contracts import enums, status
from nexus_core.contracts.base import (
    Constraint,
    Correlation,
    DomainObject,
    Reference,
    ValueObject,
)

__all__ = [
    "Constraint",
    "Correlation",
    "DomainObject",
    "Reference",
    "ValueObject",
    "enums",
    "status",
]
