"""Unit tests for nexus_harness.context_resolver.

Covers ContextResolver.resolve():
- Returns a ContextView (a ValueObject).
- ContextView.reference carries target_type="context_package" and the package's identity.
- Projected fields: identity, goal_ref, confidence (string), context_categories,
  constraints, resources, validation_status, known_unknowns.
- confidence is a plain string (the StrEnum's value), not the enum member.
- The ContextView is frozen (mutations are rejected).
- The source ContextPackage is not mutated (it is frozen itself; view fields equal the
  projected originals).
- Resolve is deterministic: two calls on the same package produce equal views.
- Edge cases: empty constraints, empty resources, empty known_unknowns.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Constraint, Reference
from nexus_core.contracts.enums import InterpretationConfidence
from nexus_harness.context_resolver import ContextResolver, ContextView
from nexus_harness.vocabulary import CONTEXT_TARGET_TYPE
from tests.unit.nexus_harness.helpers import context_package, ref

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _resolver() -> ContextResolver:
    return ContextResolver()


# ---------------------------------------------------------------------------
# Return type and reference
# ---------------------------------------------------------------------------


def test_resolve_returns_context_view() -> None:
    view = _resolver().resolve(context_package())
    assert isinstance(view, ContextView)


def test_reference_target_type_is_context_package() -> None:
    view = _resolver().resolve(context_package("ctx-42"))
    assert view.reference.target_type == CONTEXT_TARGET_TYPE


def test_reference_identifier_matches_package_identity() -> None:
    view = _resolver().resolve(context_package("ctx-42"))
    assert view.reference.identifier == "ctx-42"


# ---------------------------------------------------------------------------
# Field projection
# ---------------------------------------------------------------------------


def test_identity_projected_from_package() -> None:
    pkg = context_package("ctx-hello")
    view = _resolver().resolve(pkg)
    assert view.identity == "ctx-hello"


def test_goal_ref_projected_from_package() -> None:
    pkg = context_package("ctx-1", goal="goal-xyz")
    view = _resolver().resolve(pkg)
    assert view.goal_ref == pkg.goal_ref
    assert view.goal_ref.target_type == "goal"
    assert view.goal_ref.identifier == "goal-xyz"


def test_confidence_is_string_of_enum_value() -> None:
    pkg = context_package(confidence=InterpretationConfidence.HIGH)
    view = _resolver().resolve(pkg)
    assert view.confidence == "high"
    assert isinstance(view.confidence, str)


def test_confidence_low() -> None:
    pkg = context_package(confidence=InterpretationConfidence.LOW)
    view = _resolver().resolve(pkg)
    assert view.confidence == "low"


def test_confidence_medium() -> None:
    pkg = context_package(confidence=InterpretationConfidence.MEDIUM)
    view = _resolver().resolve(pkg)
    assert view.confidence == "medium"


def test_confidence_unknown() -> None:
    pkg = context_package(confidence=InterpretationConfidence.UNKNOWN)
    view = _resolver().resolve(pkg)
    assert view.confidence == "unknown"


def test_context_categories_projected_is_same_object() -> None:
    pkg = context_package()
    view = _resolver().resolve(pkg)
    assert view.context_categories is pkg.context_categories


def test_constraints_projected_from_package() -> None:
    c = Constraint(kind="time_limit", detail={"hours": 4})
    pkg = context_package(constraints=(c,))
    view = _resolver().resolve(pkg)
    assert view.constraints == (c,)


def test_constraints_empty_when_none_given() -> None:
    pkg = context_package(constraints=())
    view = _resolver().resolve(pkg)
    assert view.constraints == ()


def test_resources_projected_from_package() -> None:
    r = ref("resource", "res-1")
    pkg = context_package(resources=(r,))
    view = _resolver().resolve(pkg)
    assert view.resources == (r,)


def test_resources_empty_when_none_given() -> None:
    pkg = context_package(resources=())
    view = _resolver().resolve(pkg)
    assert view.resources == ()


def test_validation_status_projected_from_package() -> None:
    pkg = context_package()
    view = _resolver().resolve(pkg)
    # helpers.context_package sets validation_status={"validated": True}
    assert view.validation_status == {"validated": True}


def test_known_unknowns_projected_from_package() -> None:
    pkg = context_package(known_unknowns=("unknown-a", "unknown-b"))
    view = _resolver().resolve(pkg)
    assert view.known_unknowns == ("unknown-a", "unknown-b")


def test_known_unknowns_empty_when_none_given() -> None:
    pkg = context_package(known_unknowns=())
    view = _resolver().resolve(pkg)
    assert view.known_unknowns == ()


# ---------------------------------------------------------------------------
# Multiple constraints and resources
# ---------------------------------------------------------------------------


def test_multiple_constraints_preserved_in_order() -> None:
    c1 = Constraint(kind="time_limit", detail={"hours": 1})
    c2 = Constraint(kind="policy", detail={"policy": "pol-a", "version": "1"})
    pkg = context_package(constraints=(c1, c2))
    view = _resolver().resolve(pkg)
    assert view.constraints == (c1, c2)


def test_multiple_resources_preserved_in_order() -> None:
    r1 = ref("resource", "res-1")
    r2 = ref("resource", "res-2")
    pkg = context_package(resources=(r1, r2))
    view = _resolver().resolve(pkg)
    assert view.resources == (r1, r2)


def test_multiple_known_unknowns_preserved_in_order() -> None:
    pkg = context_package(known_unknowns=("unk-1", "unk-2", "unk-3"))
    view = _resolver().resolve(pkg)
    assert view.known_unknowns == ("unk-1", "unk-2", "unk-3")


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_context_view_is_frozen() -> None:
    view = _resolver().resolve(context_package())

    with pytest.raises(ValidationError):
        view.identity = "mutated"  # type: ignore[misc]


def test_context_view_reference_is_frozen() -> None:
    view = _resolver().resolve(context_package())

    with pytest.raises(ValidationError):
        view.reference = Reference(target_type="other", identifier="x")  # type: ignore[misc]


def test_source_package_fields_unchanged_after_resolve() -> None:
    """The view must project from the source; the source package is not altered.

    ContextPackage is itself frozen (Pydantic frozen=True), so any attempted
    mutation during resolve would already raise. We verify that the projected
    values match the original rather than being replaced.
    """
    pkg = context_package(
        "ctx-orig",
        confidence=InterpretationConfidence.HIGH,
        known_unknowns=("x",),
    )
    original_identity = pkg.identity
    original_confidence = pkg.confidence
    original_known_unknowns = pkg.known_unknowns

    view = _resolver().resolve(pkg)

    assert pkg.identity == original_identity
    assert pkg.confidence == original_confidence
    assert pkg.known_unknowns == original_known_unknowns
    # And the view agrees
    assert view.identity == original_identity
    assert view.confidence == original_confidence.value
    assert view.known_unknowns == original_known_unknowns


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolve_is_deterministic() -> None:
    """Two calls on the same package produce equal views."""
    pkg = context_package(
        "ctx-det",
        confidence=InterpretationConfidence.MEDIUM,
        constraints=(Constraint(kind="time_limit", detail={"hours": 2}),),
        known_unknowns=("unk-det",),
    )
    resolver = _resolver()

    view_1 = resolver.resolve(pkg)
    view_2 = resolver.resolve(pkg)

    assert view_1 == view_2


def test_resolve_different_packages_produce_different_views() -> None:
    pkg_a = context_package("ctx-a")
    pkg_b = context_package("ctx-b")
    resolver = _resolver()

    view_a = resolver.resolve(pkg_a)
    view_b = resolver.resolve(pkg_b)

    assert view_a != view_b
    assert view_a.identity == "ctx-a"
    assert view_b.identity == "ctx-b"
