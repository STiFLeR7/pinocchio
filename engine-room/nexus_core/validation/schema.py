"""Schema validation.

The frozen Pydantic models enforce most schema rules at construction (typed
fields, ``extra="forbid"``, frozen). This validator adds two guarantees: that a
constructed object survives a structural serialization round-trip identically,
and a convenience entry point (:func:`validate_schema`) for validating raw data
against a model type, re-raising Pydantic failures as ``SchemaViolation``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from nexus_core.validation.errors import ContractViolation, SchemaViolation
from nexus_core.validation.framework import ValidationIssue, Validator, object_name_of


def validate_schema[T: BaseModel](model_type: type[T], data: Mapping[str, Any]) -> T:
    """Validate ``data`` against ``model_type``; raise ``SchemaViolation`` on failure."""
    try:
        return model_type.model_validate(dict(data))
    except ValidationError as exc:
        name = str(getattr(model_type, "LIFECYCLE_NAME", model_type.__name__))
        raise SchemaViolation(name, f"schema validation failed: {exc}") from exc


class SchemaValidator(Validator):
    """Confirms an object conforms to and round-trips through its canonical schema."""

    category: ClassVar[str] = "schema"
    exception: ClassVar[type[ContractViolation]] = SchemaViolation

    def issues(self, obj: BaseModel) -> Iterator[ValidationIssue]:
        name = object_name_of(obj)
        try:
            rebuilt = type(obj).model_validate(obj.model_dump())
        except ValidationError as exc:
            yield ValidationIssue(
                category=self.category,
                object_name=name,
                message=f"serialization round-trip failed: {exc}",
            )
            return
        if rebuilt != obj:
            yield ValidationIssue(
                category=self.category,
                object_name=name,
                message="serialization round-trip is not identity-preserving",
            )
