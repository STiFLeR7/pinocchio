"""Determinism proofs for Nexus Context Engineering — the core Phase 4 guarantee.

The headline invariant of Phase 4 is that context engineering is a *pure,
reproducible* function of its inputs: identical Goals with identical
:class:`ContextRequest` inputs produce byte-identical Context Packages, items,
conflicts, and event streams. There is no clock, counter, or randomness in
identifier derivation, and the only captured-as-data value (the event timestamp)
is injected (``FixedTimestampSource``) so it can be pinned. These tests prove that
guarantee end to end:

* the same Goal + Request engineered in two independent environments yields equal
  Context Packages, items, conflicts, *and* equal event ``(identifier, type)``
  streams;
* a rich request (many fragments across categories/sources, a missing declared
  dependency, an explicit freshness policy, relevance overrides, and supporting
  references/artifacts/resources) is equally reproducible;
* fragment order does not matter — the normalizer sorts by identity, so two
  requests built from the same distinct fragments in different orders produce an
  equal Context Package;
* confidence, known-unknowns, and validation status are stable across runs.
"""

from __future__ import annotations

from nexus_context import ContextCategory, ContextSource, FreshnessPolicy
from nexus_core.contracts.base import Constraint, Reference
from tests.unit.nexus_context.helpers import (
    context_env,
    fragment,
    make_goal,
    request,
)

# --------------------------------------------------------------------------- #
# Shared deterministic fixtures (plain builders, no pytest fixtures needed).   #
# --------------------------------------------------------------------------- #


def _simple_request() -> object:
    """A small but non-trivial request: two distinct fragments, one dependency."""
    return request(
        fragment("repo", source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE),
        fragment("env", source=ContextSource.ENVIRONMENT, category=ContextCategory.OPERATIONAL),
        declared_dependencies=("repo",),
    )


def _rich_fragments() -> tuple[object, ...]:
    """Several distinct fragments spanning multiple categories and sources.

    Every ``(source, category, key)`` is unique so the normalizer never collapses
    or reorders them ambiguously — this keeps order-independence well defined.
    """
    return (
        fragment(
            "workspace-repo",
            source=ContextSource.WORKSPACE,
            category=ContextCategory.WORKSPACE,
            payload={"path": "/srv/app"},
            observed_at="2026-06-29T10:00:00Z",
        ),
        fragment(
            "operator-note",
            source=ContextSource.OPERATOR,
            category=ContextCategory.GOAL,
            payload={"note": "prioritize correctness"},
            observed_at="2026-06-29T09:00:00Z",
        ),
        fragment(
            "runtime-state",
            source=ContextSource.RUNTIME,
            category=ContextCategory.EXECUTION,
            payload={"running": 2},
            observed_at="2026-06-29T08:00:00Z",
        ),
        fragment(
            "knowledge-std",
            source=ContextSource.KNOWLEDGE,
            category=ContextCategory.DOMAIN,
            payload={"standard": "ISO-9001"},
            observed_at="2026-06-29T07:00:00Z",
        ),
        fragment(
            "env-budget",
            source=ContextSource.ENVIRONMENT,
            category=ContextCategory.CONSTRAINT,
            payload={"budget": 1000},
            observed_at="2026-06-29T06:00:00Z",
        ),
    )


def _rich_request(*fragments_in_order: object) -> object:
    """A demanding request exercising every deterministic input channel."""
    return request(
        *fragments_in_order,  # type: ignore[arg-type]
        declared_dependencies=("workspace-repo", "absent-dependency"),
        known_unknowns=("unverified-deadline",),
        constraints=(Constraint(kind="deadline", detail={"due": "2026-07-01"}),),
        resources=(Reference(target_type="runtime", identifier="rt-1"),),
        supporting_artifacts=(Reference(target_type="artifact", identifier="art-1"),),
        references=("https://example.test/spec",),
        freshness_policy=FreshnessPolicy(
            evaluation_instant="2026-06-29T12:00:00Z",
            default_max_age_seconds=3600,
            by_category={ContextCategory.WORKSPACE.value: 7200},
        ),
        relevance_weights={
            ContextCategory.WORKSPACE.value: 25,
            ContextSource.RUNTIME.value: 7,
        },
    )


def _event_signatures(env: object) -> list[tuple[str, str]]:
    """The ordered ``(identifier, type)`` pairs of every emitted event."""
    store = env.infrastructure.event_store  # type: ignore[attr-defined]
    return [(e.identifier, e.type) for e in store.read_all()]


# --------------------------------------------------------------------------- #
# 1. Two independent environments produce equal results (simple request).     #
# --------------------------------------------------------------------------- #


def test_two_environments_yield_equal_results() -> None:
    goal = make_goal()
    req = _simple_request()

    env1 = context_env()
    env2 = context_env()

    result1 = env1.context.service.engineer(goal, req)  # type: ignore[arg-type]
    result2 = env2.context.service.engineer(goal, req)  # type: ignore[arg-type]

    assert result1.package == result2.package
    assert result1.items == result2.items
    assert result1.conflicts == result2.conflicts


def test_two_environments_emit_identical_event_streams() -> None:
    goal = make_goal()
    req = _simple_request()

    env1 = context_env()
    env2 = context_env()

    env1.context.service.engineer(goal, req)  # type: ignore[arg-type]
    env2.context.service.engineer(goal, req)  # type: ignore[arg-type]

    assert _event_signatures(env1) == _event_signatures(env2)


# --------------------------------------------------------------------------- #
# 2. A rich request is equally reproducible across fresh environments.        #
# --------------------------------------------------------------------------- #


def test_rich_request_is_deterministic_across_environments() -> None:
    goal = make_goal("goal-rich", outcome="Deliver a validated release")
    req = _rich_request(*_rich_fragments())

    env1 = context_env()
    env2 = context_env()

    result1 = env1.context.service.engineer(goal, req)  # type: ignore[arg-type]
    result2 = env2.context.service.engineer(goal, req)  # type: ignore[arg-type]

    assert result1.package == result2.package
    assert result1.items == result2.items
    assert result1.conflicts == result2.conflicts
    assert _event_signatures(env1) == _event_signatures(env2)


def test_rich_request_surfaces_missing_dependency_conflict() -> None:
    goal = make_goal("goal-rich", outcome="Deliver a validated release")
    req = _rich_request(*_rich_fragments())

    result = context_env().context.service.engineer(goal, req)  # type: ignore[arg-type]

    missing = [
        conflict.key for conflict in result.conflicts if conflict.kind.value == "missing_dependency"
    ]
    assert "absent-dependency" in missing


# --------------------------------------------------------------------------- #
# 3. Order-independence — distinct fragments in any order give equal packages.#
# --------------------------------------------------------------------------- #


def test_fragment_order_does_not_change_package() -> None:
    goal = make_goal("goal-order")
    fragments = _rich_fragments()
    reversed_fragments = tuple(reversed(fragments))

    req_forward = _rich_request(*fragments)
    req_reversed = _rich_request(*reversed_fragments)

    result_forward = context_env().context.service.engineer(goal, req_forward)  # type: ignore[arg-type]
    result_reversed = context_env().context.service.engineer(goal, req_reversed)  # type: ignore[arg-type]

    assert result_forward.package == result_reversed.package
    assert result_forward.items == result_reversed.items
    assert result_forward.conflicts == result_reversed.conflicts


# --------------------------------------------------------------------------- #
# 4. Confidence / known-unknowns / validation status are stable across runs.  #
# --------------------------------------------------------------------------- #


def test_confidence_and_validation_status_are_stable() -> None:
    goal = make_goal("goal-stable")
    req = _rich_request(*_rich_fragments())

    package1 = context_env().context.service.engineer(goal, req).package  # type: ignore[arg-type]
    package2 = context_env().context.service.engineer(goal, req).package  # type: ignore[arg-type]

    assert package1.confidence == package2.confidence
    assert package1.known_unknowns == package2.known_unknowns
    assert package1.validation_status == package2.validation_status
