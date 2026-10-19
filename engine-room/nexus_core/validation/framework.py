"""Validation framework: the ``Validator`` base, report value objects, and the
reflection helper used to walk an object's references.

A validator yields ``ValidationIssue``s; ``check`` collects them into a
``ValidationReport`` (non-raising), and ``validate`` raises the validator's
``ContractViolation`` subclass on the first issue (fail fast).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.validation.errors import ContractViolation


def object_name_of(obj: BaseModel) -> str:
    """The logical object name for messages (the ``LIFECYCLE_NAME`` or class name)."""
    return str(getattr(type(obj), "LIFECYCLE_NAME", type(obj).__name__))


def iter_references(obj: BaseModel) -> Iterator[tuple[str, Reference]]:
    """Yield ``(dotted_path, Reference)`` for every Reference reachable in ``obj``.

    Recurses through nested value objects and ``tuple`` sequences so deeply
    nested references (e.g. graph node ``work_package_ref``) are reached.
    """
    for field_name in type(obj).model_fields:
        yield from _walk(field_name, getattr(obj, field_name))


def _walk(path: str, value: object) -> Iterator[tuple[str, Reference]]:
    if isinstance(value, Reference):
        yield path, value
    elif isinstance(value, BaseModel):
        for sub in type(value).model_fields:
            yield from _walk(f"{path}.{sub}", getattr(value, sub))
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from _walk(f"{path}[{index}]", item)


class ValidationIssue(ValueObject):
    """One validation problem: its dimension, the object, and a message."""

    category: str
    object_name: str
    message: str
    location: str | None = None


class ValidationReport(ValueObject):
    """The non-raising result of a ``check``: zero or more issues."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    def raise_for_issues(self) -> None:
        """Raise a ``ContractViolation`` for the first issue, if any (fail fast)."""
        if self.issues:
            first = self.issues[0]
            raise ContractViolation(first.object_name, first.message)


class Validator(ABC):
    """Base class for the four validation dimensions.

    Subclasses implement :meth:`issues`. ``check`` is non-raising; ``validate``
    fails fast by raising :attr:`exception` on the first issue.
    """

    category: ClassVar[str]
    exception: ClassVar[type[ContractViolation]]

    @abstractmethod
    def issues(self, obj: BaseModel) -> Iterator[ValidationIssue]:
        """Yield every contract issue found in ``obj`` (possibly none)."""

    def check(self, obj: BaseModel) -> ValidationReport:
        return ValidationReport(issues=tuple(self.issues(obj)))

    def validate(self, obj: BaseModel) -> None:
        for issue in self.issues(obj):
            raise self.exception(issue.object_name, issue.message)
