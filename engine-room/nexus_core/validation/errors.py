"""Validation error hierarchy.

These are distinct from Pydantic's ``ValidationError`` (which is raised at model
construction for schema problems). A ``ContractViolation`` is raised by this
layer's validators when an object breaks a contract rule the type system cannot
encode. Every violation carries the logical object name and a complete,
explainable message (no silent correction).
"""

from __future__ import annotations


# The canonical naming is "Violation" (not "...Error") to match the architecture's
# vocabulary; N818 is suppressed deliberately on each class.
class ContractViolation(Exception):  # noqa: N818
    """Base for all contract-validation failures."""

    def __init__(self, object_name: str, message: str) -> None:
        self.object_name = object_name
        self.message = message
        super().__init__(f"[{object_name}] {message}")


class SchemaViolation(ContractViolation):
    """The object/data does not conform to its canonical schema (INV-07)."""


class InvariantViolation(ContractViolation):
    """An architectural invariant on the object's contents is broken."""


class LifecycleViolation(ContractViolation):
    """An illegal lifecycle state or transition (doc 24, INV-15)."""


class RelationshipViolation(ContractViolation):
    """A reference points at the wrong kind of object or is malformed."""
