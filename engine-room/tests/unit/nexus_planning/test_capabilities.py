"""Tests for the in-memory Capability Registry and the Capability Resolver.

The registry is the reference implementation of the frozen ``nexus_core``
:class:`CapabilityRegistry` Protocol; the resolver depends only on that Protocol.
Resolution answers *what abstract capabilities the work requires* and which are
known to the registry — required identifiers, resolved references, and missing
identifiers, and **nothing more** (INV-37). It never discovers harnesses, selects
a provider, or allocates a runtime. Outputs are deterministic: sorted and
de-duplicated.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CapabilityCategory
from nexus_planning import (
    CapabilityRequirementSet,
    CapabilityResolver,
    InMemoryCapabilityRegistry,
    PlanningRequest,
)
from tests.unit.nexus_planning.helpers import item, make_capability

# --------------------------------------------------------------------------- #
# InMemoryCapabilityRegistry                                                   #
# --------------------------------------------------------------------------- #


def test_register_then_get_returns_the_capability() -> None:
    registry = InMemoryCapabilityRegistry()
    cap = make_capability("cap.a")

    registry.register(cap)

    assert registry.get("cap.a") == cap


def test_get_unknown_identifier_is_none() -> None:
    registry = InMemoryCapabilityRegistry()

    assert registry.get("cap.missing") is None


def test_get_returns_latest_registered_version() -> None:
    registry = InMemoryCapabilityRegistry()
    v1 = make_capability("cap.a", version="1")
    v2 = make_capability("cap.a", version="2")

    registry.register(v1)
    registry.register(v2)

    assert registry.get("cap.a") == v2


def test_get_with_pinned_version_returns_that_version() -> None:
    registry = InMemoryCapabilityRegistry()
    v1 = make_capability("cap.a", version="1")
    v2 = make_capability("cap.a", version="2")

    registry.register(v1)
    registry.register(v2)

    assert registry.get("cap.a", "1") == v1
    assert registry.get("cap.a", "2") == v2


def test_get_with_unknown_version_is_none() -> None:
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a", version="1"))

    assert registry.get("cap.a", "9") is None


def test_find_by_category_returns_latest_in_category_sorted() -> None:
    registry = InMemoryCapabilityRegistry()
    analysis_b = make_capability("cap.b", category=CapabilityCategory.ANALYSIS)
    analysis_a = make_capability("cap.a", category=CapabilityCategory.ANALYSIS)
    dev = make_capability("cap.c", category=CapabilityCategory.DEVELOPMENT)
    registry.register(analysis_b)
    registry.register(analysis_a)
    registry.register(dev)

    found = registry.find_by_category(CapabilityCategory.ANALYSIS)

    assert found == (analysis_a, analysis_b)


def test_find_by_category_uses_latest_version() -> None:
    registry = InMemoryCapabilityRegistry()
    v1 = make_capability("cap.a", version="1", category=CapabilityCategory.ANALYSIS)
    v2 = make_capability("cap.a", version="2", category=CapabilityCategory.ANALYSIS)
    registry.register(v1)
    registry.register(v2)

    found = registry.find_by_category(CapabilityCategory.ANALYSIS)

    assert found == (v2,)


def test_find_by_category_empty_when_no_match() -> None:
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a", category=CapabilityCategory.ANALYSIS))

    assert registry.find_by_category(CapabilityCategory.OPERATIONS) == ()


def test_list_all_returns_latest_sorted_by_identifier() -> None:
    registry = InMemoryCapabilityRegistry()
    cap_c = make_capability("cap.c")
    cap_a = make_capability("cap.a")
    cap_b = make_capability("cap.b")
    registry.register(cap_c)
    registry.register(cap_a)
    registry.register(cap_b)

    assert registry.list_all() == (cap_a, cap_b, cap_c)


def test_list_all_uses_latest_version() -> None:
    registry = InMemoryCapabilityRegistry()
    v1 = make_capability("cap.a", version="1")
    v2 = make_capability("cap.a", version="2")
    registry.register(v1)
    registry.register(v2)

    assert registry.list_all() == (v2,)


def test_list_all_empty_registry_is_empty() -> None:
    assert InMemoryCapabilityRegistry().list_all() == ()


# --------------------------------------------------------------------------- #
# CapabilityResolver                                                           #
# --------------------------------------------------------------------------- #


def test_resolve_returns_a_requirement_set() -> None:
    resolver = CapabilityResolver(InMemoryCapabilityRegistry())
    request = PlanningRequest(work_items=(item("a"),))

    result = resolver.resolve(request)

    assert isinstance(result, CapabilityRequirementSet)


def test_resolve_required_is_sorted_and_deduplicated_across_items() -> None:
    resolver = CapabilityResolver(InMemoryCapabilityRegistry())
    request = PlanningRequest(
        work_items=(
            item("a", capability_requirements=("cap.b", "cap.a")),
            item("b", capability_requirements=("cap.a",), depends_on=("a",)),
        )
    )

    result = resolver.resolve(request)

    assert result.required == ("cap.a", "cap.b")


def test_resolve_deduplicates_within_a_single_item() -> None:
    resolver = CapabilityResolver(InMemoryCapabilityRegistry())
    request = PlanningRequest(
        work_items=(item("a", capability_requirements=("cap.b", "cap.a", "cap.a")),)
    )

    result = resolver.resolve(request)

    assert result.required == ("cap.a", "cap.b")


def test_resolve_resolved_holds_capability_references_for_registered() -> None:
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a"))
    registry.register(make_capability("cap.b"))
    resolver = CapabilityResolver(registry)
    request = PlanningRequest(work_items=(item("a", capability_requirements=("cap.a", "cap.b")),))

    result = resolver.resolve(request)

    assert result.resolved == (
        Reference(target_type="capability", identifier="cap.a"),
        Reference(target_type="capability", identifier="cap.b"),
    )
    assert result.missing == ()


def test_resolve_missing_lists_unregistered_requirements() -> None:
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a"))
    resolver = CapabilityResolver(registry)
    request = PlanningRequest(work_items=(item("a", capability_requirements=("cap.a", "cap.b")),))

    result = resolver.resolve(request)

    assert result.resolved == (Reference(target_type="capability", identifier="cap.a"),)
    assert result.missing == ("cap.b",)


def test_resolve_inv37_returns_only_requirements_and_candidates() -> None:
    # INV-37: resolution returns requirements/candidates only — never provider,
    # runtime, or harness data. The result has exactly required/resolved/missing,
    # and every resolved entry is a capability reference (target_type "capability").
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a"))
    resolver = CapabilityResolver(registry)
    request = PlanningRequest(work_items=(item("a", capability_requirements=("cap.a", "cap.b")),))

    result = resolver.resolve(request)

    assert set(result.__class__.model_fields) == {"required", "resolved", "missing"}
    for reference in result.resolved:
        assert isinstance(reference, Reference)
        assert reference.target_type == "capability"


def test_resolve_works_with_only_a_capability_registry() -> None:
    # The resolver depends only on the CapabilityRegistry Protocol — nothing else.
    resolver = CapabilityResolver(InMemoryCapabilityRegistry())
    request = PlanningRequest(work_items=(item("a", capability_requirements=("cap.a",)),))

    result = resolver.resolve(request)

    assert result.required == ("cap.a",)
    assert result.resolved == ()
    assert result.missing == ("cap.a",)


def test_resolve_empty_requirements_yields_empty_sets() -> None:
    resolver = CapabilityResolver(InMemoryCapabilityRegistry())
    request = PlanningRequest(work_items=(item("a"), item("b", depends_on=("a",))))

    result = resolver.resolve(request)

    assert result.required == ()
    assert result.resolved == ()
    assert result.missing == ()


def test_resolve_is_deterministic() -> None:
    registry = InMemoryCapabilityRegistry()
    registry.register(make_capability("cap.a"))
    resolver = CapabilityResolver(registry)
    request = PlanningRequest(
        work_items=(
            item("a", capability_requirements=("cap.b", "cap.a")),
            item("b", capability_requirements=("cap.a",), depends_on=("a",)),
        )
    )

    first = resolver.resolve(request)
    second = resolver.resolve(request)

    assert first == second
