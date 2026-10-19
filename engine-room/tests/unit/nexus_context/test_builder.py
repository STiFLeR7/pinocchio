"""Unit tests for :class:`~nexus_context.builder.ContextPackageBuilder`.

The builder is the final, deterministic packaging stage: it routes the ranked,
freshness-evaluated item set into the eight canonical Context Categories, derives
confidence from an explicit rule, merges and de-duplicates constraints and
reference collections, and surfaces every gap and conflict in ``known_unknowns`` /
``validation_status`` rather than hiding it. These tests drive real items through
the full pipeline (normalize → rank → freshness → detect → validation status) and
pin the builder's identity, routing, confidence branches, merge/dedup rules,
provenance summaries, immutability, and contract conformance.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_context import ids
from nexus_context.builder import ContextPackageBuilder
from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.conflict_detector import ConflictDetector
from nexus_context.freshness import FreshnessValidator
from nexus_context.normalizer import Normalizer
from nexus_context.relevance import RelevanceRanker
from nexus_context.requests import (
    Conflict,
    ContextItem,
    ContextRequest,
    FreshnessPolicy,
    RawContextFragment,
)
from nexus_context.validators import compute_validation_status
from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import InterpretationConfidence
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.goal import Goal
from tests.unit.nexus_context.helpers import fragment, make_goal, request


def _pipeline(
    goal: Goal, req: ContextRequest
) -> tuple[tuple[ContextItem, ...], tuple[Conflict, ...]]:
    """Run fragments through the real pipeline up to (but excluding) packaging."""
    normalized = Normalizer().normalize(req.fragments)
    ranked = RelevanceRanker().rank(normalized, req)
    evaluated = FreshnessValidator().evaluate(ranked, req.freshness_policy)
    conflicts = ConflictDetector().detect(evaluated, req)
    return evaluated, conflicts


def _build(
    goal: Goal,
    req: ContextRequest,
    *,
    correlation_identifier: str = "cor-x",
) -> ContextPackage:
    """Assemble a Context Package from real pipeline outputs for ``goal`` / ``req``."""
    items, conflicts = _pipeline(goal, req)
    validation_status = compute_validation_status(items, conflicts)
    return ContextPackageBuilder().build(
        goal,
        items,
        conflicts,
        req,
        validation_status,
        correlation_identifier=correlation_identifier,
    )


def _goal_fragment(key: str = "objective") -> RawContextFragment:
    """A GOAL-category fragment so packages can reach the HIGH-confidence branch."""
    return fragment(
        key,
        source=ContextSource.OPERATOR,
        category=ContextCategory.GOAL,
        payload={"value": "ship"},
    )


# -- identity, correlation, goal_ref ----------------------------------------- #


def test_identity_is_derived_from_goal_and_version() -> None:
    goal = make_goal("goal-7")
    req = request(_goal_fragment(), package_version="3")
    package = _build(goal, req)
    assert package.identity == ids.context_id("goal-7", "3")
    assert package.identity == "context-goal-7-v3"


def test_goal_ref_targets_the_goal() -> None:
    goal = make_goal("goal-7")
    package = _build(goal, request(_goal_fragment()))
    assert package.goal_ref == Reference(target_type="goal", identifier="goal-7")


def test_correlation_identifier_is_carried_through() -> None:
    package = _build(
        make_goal(),
        request(_goal_fragment()),
        correlation_identifier="cor-abc",
    )
    assert package.correlation == Correlation(correlation_identifier="cor-abc")
    assert package.correlation.correlation_identifier == "cor-abc"


# -- category routing -------------------------------------------------------- #


def test_workspace_item_routes_into_workspace_context() -> None:
    frag = fragment(
        "repo",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"value": "nexus"},
    )
    package = _build(make_goal(), request(frag))
    workspace = package.context_categories.workspace_context
    assert "repo" in workspace
    entry = workspace["repo"]
    assert entry["value"] == {"value": "nexus"}
    assert entry["source"] == ContextSource.WORKSPACE.value
    assert entry["relevance"] == 30 + 5  # WORKSPACE base + WORKSPACE source
    assert entry["freshness"] == "unknown"


def test_items_route_into_their_respective_categories() -> None:
    goal_frag = _goal_fragment("objective")
    domain_frag = fragment(
        "term",
        source=ContextSource.KNOWLEDGE,
        category=ContextCategory.DOMAIN,
        payload={"value": "ddd"},
    )
    package = _build(make_goal(), request(goal_frag, domain_frag))
    categories = package.context_categories
    assert "objective" in categories.goal_context
    assert "term" in categories.domain_context
    # Categories with no item stay empty.
    assert categories.historical_context == {}
    assert categories.execution_context == {}


def test_empty_categories_when_no_items() -> None:
    package = _build(make_goal(), request())
    categories = package.context_categories
    assert categories.goal_context == {}
    assert categories.workspace_context == {}
    assert categories.resource_context == {}


# -- confidence rule branches ------------------------------------------------ #


def test_confidence_unknown_when_no_items() -> None:
    package = _build(make_goal(), request())
    assert package.confidence is InterpretationConfidence.UNKNOWN


def test_confidence_low_on_missing_dependency_conflict() -> None:
    req = request(_goal_fragment(), declared_dependencies=("absent-key",))
    package = _build(make_goal(), req)
    assert package.confidence is InterpretationConfidence.LOW


def test_confidence_low_on_contradiction_conflict() -> None:
    # Same (category, key) from two sources with differing values -> contradiction.
    first = fragment(
        "shared",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.DOMAIN,
        payload={"value": "a"},
    )
    second = fragment(
        "shared",
        source=ContextSource.KNOWLEDGE,
        category=ContextCategory.DOMAIN,
        payload={"value": "b"},
    )
    package = _build(make_goal(), request(first, second))
    assert package.confidence is InterpretationConfidence.LOW


def test_confidence_high_with_goal_and_two_categories_no_blocking_conflict() -> None:
    goal_frag = _goal_fragment("objective")
    workspace_frag = fragment(
        "repo",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"value": "nexus"},
    )
    package = _build(make_goal(), request(goal_frag, workspace_frag))
    assert package.confidence is InterpretationConfidence.HIGH


def test_confidence_medium_when_goal_category_absent() -> None:
    workspace_frag = fragment(
        "repo",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"value": "nexus"},
    )
    package = _build(make_goal(), request(workspace_frag))
    assert package.confidence is InterpretationConfidence.MEDIUM


def test_confidence_medium_with_only_goal_category() -> None:
    # GOAL present but a single category -> not HIGH, falls through to MEDIUM.
    package = _build(make_goal(), request(_goal_fragment()))
    assert package.confidence is InterpretationConfidence.MEDIUM


# -- constraints merge + dedup ----------------------------------------------- #


def test_constraints_merge_goal_and_request_deduped() -> None:
    shared = Constraint(kind="deadline", detail={"by": "friday"})
    goal_only = Constraint(kind="budget", detail={"cap": 100})
    request_only = Constraint(kind="quality", detail={"min": "high"})
    goal = make_goal(constraints=(shared, goal_only))
    req = request(_goal_fragment(), constraints=(shared, request_only))
    package = _build(goal, req)
    # Order preserved: goal constraints first, then new request constraints.
    assert package.constraints == (shared, goal_only, request_only)
    # The duplicate shared constraint appears exactly once.
    assert package.constraints.count(shared) == 1


# -- resources / supporting_artifacts dedup ---------------------------------- #


def test_resources_deduped_by_target_type_and_identifier() -> None:
    runtime = Reference(target_type="runtime", identifier="r1")
    runtime_dup = Reference(target_type="runtime", identifier="r1")
    tool = Reference(target_type="tool", identifier="r1")  # same id, different type
    req = request(_goal_fragment(), resources=(runtime, runtime_dup, tool))
    package = _build(make_goal(), req)
    assert package.resources == (runtime, tool)


def test_supporting_artifacts_deduped_by_signature() -> None:
    artifact = Reference(target_type="document", identifier="doc-1")
    artifact_dup = Reference(target_type="document", identifier="doc-1")
    other = Reference(target_type="document", identifier="doc-2")
    req = request(
        _goal_fragment(),
        supporting_artifacts=(artifact, artifact_dup, other),
    )
    package = _build(make_goal(), req)
    assert package.supporting_artifacts == (artifact, other)


# -- known_unknowns ---------------------------------------------------------- #


def test_known_unknowns_merge_request_gaps_and_conflict_markers_sorted_unique() -> None:
    req = request(
        _goal_fragment(),
        declared_dependencies=("missing-dep",),
        known_unknowns=("open-question", "open-question"),
    )
    package = _build(make_goal(), req)
    # Request gaps plus the missing_dependency marker, sorted and unique.
    assert package.known_unknowns == (
        "missing_dependency:missing-dep",
        "open-question",
    )


def test_known_unknowns_includes_contradiction_and_stale_markers() -> None:
    fresh = fragment(
        "current",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"value": "new"},
        supersedes=("old",),
    )
    old = fragment(
        "old",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        payload={"value": "stale"},
    )
    contradiction_a = fragment(
        "topic",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.DOMAIN,
        payload={"value": "x"},
    )
    contradiction_b = fragment(
        "topic",
        source=ContextSource.KNOWLEDGE,
        category=ContextCategory.DOMAIN,
        payload={"value": "y"},
    )
    package = _build(
        make_goal(),
        request(fresh, old, contradiction_a, contradiction_b),
    )
    assert "stale:old" in package.known_unknowns
    assert "contradiction:topic" in package.known_unknowns
    assert list(package.known_unknowns) == sorted(set(package.known_unknowns))


# -- references -------------------------------------------------------------- #


def test_references_are_sorted_union_of_request_and_item_references() -> None:
    frag_a = fragment(
        "a",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        references=("ref-z", "ref-a"),
    )
    frag_b = fragment(
        "b",
        source=ContextSource.KNOWLEDGE,
        category=ContextCategory.DOMAIN,
        references=("ref-m", "ref-a"),  # ref-a duplicated across sources
    )
    req = request(frag_a, frag_b, references=("ref-q",))
    package = _build(make_goal(), req)
    assert package.references == ("ref-a", "ref-m", "ref-q", "ref-z")


# -- freshness summary ------------------------------------------------------- #


def test_freshness_summary_carries_instant_and_counts() -> None:
    policy = FreshnessPolicy(
        evaluation_instant="2026-01-01T00:00:00+00:00",
        default_max_age_seconds=10,
    )
    valid_frag = fragment(
        "valid",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
        observed_at="2026-01-01T00:00:00+00:00",  # age 0 -> valid
    )
    expired_frag = fragment(
        "expired",
        source=ContextSource.KNOWLEDGE,
        category=ContextCategory.DOMAIN,
        observed_at="2025-12-31T00:00:00+00:00",  # age >> 2*max_age -> expired
    )
    req = request(valid_frag, expired_frag, freshness_policy=policy)
    package = _build(make_goal(), req)
    assert package.freshness is not None
    assert package.freshness["evaluation_instant"] == "2026-01-01T00:00:00+00:00"
    assert package.freshness["counts"] == {"expired": 1, "valid": 1}


def test_freshness_counts_empty_when_no_items() -> None:
    package = _build(make_goal(), request())
    assert package.freshness is not None
    assert package.freshness["counts"] == {}


# -- source summary ---------------------------------------------------------- #


def test_source_summary_carries_sources_categories_and_count() -> None:
    goal_frag = _goal_fragment("objective")
    workspace_frag = fragment(
        "repo",
        source=ContextSource.WORKSPACE,
        category=ContextCategory.WORKSPACE,
    )
    package = _build(make_goal(), request(goal_frag, workspace_frag))
    assert package.source is not None
    assert package.source["sources"] == ["operator", "workspace"]
    assert package.source["categories"] == ["goal_context", "workspace_context"]
    assert package.source["item_count"] == 2


# -- validation status pass-through ------------------------------------------ #


def test_validation_status_is_the_computed_struct() -> None:
    items, conflicts = _pipeline(make_goal(), request(_goal_fragment()))
    expected = compute_validation_status(items, conflicts)
    package = _build(make_goal(), request(_goal_fragment()))
    assert package.validation_status == expected


# -- immutability + contract conformance ------------------------------------- #


def test_package_is_frozen() -> None:
    package = _build(make_goal(), request(_goal_fragment()))
    with pytest.raises(ValidationError):
        package.identity = "mutated"  # type: ignore[misc]


def test_package_categories_are_frozen() -> None:
    package = _build(make_goal(), request(_goal_fragment()))
    with pytest.raises(ValidationError):
        package.context_categories.goal_context = {}  # type: ignore[misc]


def test_build_produces_a_valid_context_package() -> None:
    package = _build(make_goal(), request(_goal_fragment()))
    # Constructing without error means it conforms to the frozen contract.
    assert isinstance(package, ContextPackage)
    assert package.status is None
    assert package.enrichment_history == ()
