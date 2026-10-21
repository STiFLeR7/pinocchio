"""Invariant validation — cross-field architectural rules the type system can't encode.

Two layers of checks:

- **Universal:** every :class:`Reference` anywhere in the object is well-formed
  (non-empty ``target_type`` and ``identifier``).
- **Per-object:** specific architectural invariants keyed by the object's
  ``LIFECYCLE_NAME`` — e.g. a Capability carries no provider/health state
  (INV-32), Knowledge is evidence-backed (INV-24), an Observation records its
  provenance (INV-11).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import ClassVar

from pydantic import BaseModel

from nexus_core.validation.errors import ContractViolation, InvariantViolation
from nexus_core.validation.framework import (
    ValidationIssue,
    Validator,
    iter_references,
    object_name_of,
)

# Fields a Capability must never carry — provider state lives in the Harness
# Registry (INV-32 / ADR-002).
_CAPABILITY_FORBIDDEN_FIELDS = frozenset({"provider", "availability", "health"})


def _issue(name: str, message: str, location: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        category="invariant", object_name=name, message=message, location=location
    )


def _capability_invariants(obj: BaseModel) -> Iterator[ValidationIssue]:
    present = _CAPABILITY_FORBIDDEN_FIELDS & set(type(obj).model_fields)
    if present:
        yield _issue(
            "capability",
            f"Capability must not carry provider state {sorted(present)} (INV-32); "
            "availability/health live only in the Harness Registry",
        )


def _knowledge_invariants(obj: BaseModel) -> Iterator[ValidationIssue]:
    evidence = getattr(obj, "evidence_refs", ())
    if not evidence:
        yield _issue(
            "knowledge",
            "Knowledge must be evidence-backed: evidence_refs is empty (INV-24)",
        )


def _observation_invariants(obj: BaseModel) -> Iterator[ValidationIssue]:
    provenance = getattr(obj, "derived_from_events", ())
    if not provenance:
        yield _issue(
            "observation",
            "Observation must record provenance: derived_from_events is empty (INV-11)",
        )


def _reflection_invariants(obj: BaseModel) -> Iterator[ValidationIssue]:
    inputs = getattr(obj, "inputs", ())
    if not inputs:
        yield _issue(
            "reflection",
            "Reflection must analyze validated inputs: inputs is empty (INV-25)",
        )


_PER_OBJECT_INVARIANTS: dict[str, Callable[[BaseModel], Iterator[ValidationIssue]]] = {
    "capability": _capability_invariants,
    "knowledge": _knowledge_invariants,
    "observation": _observation_invariants,
    "reflection": _reflection_invariants,
}


class InvariantValidator(Validator):
    """Validates universal and per-object architectural invariants."""

    category: ClassVar[str] = "invariant"
    exception: ClassVar[type[ContractViolation]] = InvariantViolation

    def issues(self, obj: BaseModel) -> Iterator[ValidationIssue]:
        name = object_name_of(obj)
        for path, ref in iter_references(obj):
            if not ref.target_type or not ref.identifier:
                yield _issue(
                    name,
                    f"malformed reference at {path}: target_type and identifier are required",
                    location=path,
                )
        per_object = _PER_OBJECT_INVARIANTS.get(name)
        if per_object is not None:
            yield from per_object(obj)
