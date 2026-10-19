"""Contract validation layer.

Validates that domain objects conform to their frozen contracts along four
dimensions: **schema**, **invariants**, **lifecycle**, and **relationships**.

Validation fails fast and never silently corrects: ``validate`` raises a
``ContractViolation`` on the first problem; ``check`` returns a non-raising
``ValidationReport`` listing every issue. Schema validation is largely enforced
at construction time by the frozen Pydantic models; this layer adds the
cross-field, lifecycle, and relationship rules that the type system cannot
express, each tied to an architectural invariant (``INV-xx``).
"""

from nexus_core.validation.errors import (
    ContractViolation,
    InvariantViolation,
    LifecycleViolation,
    RelationshipViolation,
    SchemaViolation,
)
from nexus_core.validation.framework import (
    ValidationIssue,
    ValidationReport,
    Validator,
)
from nexus_core.validation.invariants import InvariantValidator
from nexus_core.validation.lifecycle import LifecycleValidator
from nexus_core.validation.relationships import (
    EXPECTED_REFERENCE_TYPES,
    RelationshipValidator,
)
from nexus_core.validation.schema import SchemaValidator, validate_schema

__all__ = [
    "EXPECTED_REFERENCE_TYPES",
    "ContractViolation",
    "InvariantValidator",
    "InvariantViolation",
    "LifecycleValidator",
    "LifecycleViolation",
    "RelationshipValidator",
    "RelationshipViolation",
    "SchemaValidator",
    "SchemaViolation",
    "ValidationIssue",
    "ValidationReport",
    "Validator",
    "validate_schema",
]
