"""Unit tests for the reference Context Collectors (Step 1, Phase 4).

Every shipped collector is deterministic and I/O-free: the same Goal and request
always yield the same fragment tuple. These tests pin the GoalContextCollector's
derived goal/domain fragments, the RequestFragmentCollector's identity passthrough,
the StaticContextCollector's fixed set, and the runtime-checkable Protocol contract.
"""

from __future__ import annotations

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.collectors import (
    ContextCollector,
    GoalContextCollector,
    RequestFragmentCollector,
    StaticContextCollector,
)
from nexus_core.contracts.enums import Domain, Priority
from tests.unit.nexus_context.helpers import fragment, make_goal, request

# --------------------------------------------------------------------------- #
# GoalContextCollector                                                        #
# --------------------------------------------------------------------------- #


def test_goal_collector_emits_goal_and_domain_fragments() -> None:
    goal = make_goal(success_definition="users can ship")
    fragments = GoalContextCollector().collect(goal, request())

    assert len(fragments) == 2
    goal_fragment, domain_fragment = fragments

    assert goal_fragment.source is ContextSource.OPERATOR
    assert goal_fragment.category is ContextCategory.GOAL
    assert goal_fragment.key == "objective"

    assert domain_fragment.source is ContextSource.OPERATOR
    assert domain_fragment.category is ContextCategory.DOMAIN
    assert domain_fragment.key == "domain"


def test_goal_fragment_payload_includes_present_optionals() -> None:
    # make_goal always sets scope.included == ("x",); success_definition is supplied.
    goal = make_goal(outcome="Ship the feature", success_definition="users can ship")
    goal_fragment, _ = GoalContextCollector().collect(goal, request())

    payload = goal_fragment.payload
    assert payload["outcome"] == "Ship the feature"
    assert payload["success_definition"] == "users can ship"
    assert payload["included"] == ["x"]
    # excluded and rationale are absent on this goal -> omitted, never None.
    assert "excluded" not in payload
    assert "rationale" not in payload


def test_goal_fragment_payload_omits_absent_optionals() -> None:
    # A minimal goal: no success_definition, no rationale, empty excluded scope.
    goal = make_goal()
    goal_fragment, _ = GoalContextCollector().collect(goal, request())

    payload = goal_fragment.payload
    assert payload["outcome"] == "Ship the feature"
    assert "success_definition" not in payload
    assert "rationale" not in payload
    assert "excluded" not in payload
    # included is non-empty on every make_goal, so it is always present.
    assert payload["included"] == ["x"]


def test_goal_domain_fragment_payload_is_domain_and_priority() -> None:
    goal = make_goal()
    _, domain_fragment = GoalContextCollector().collect(goal, request())

    assert domain_fragment.payload == {
        "domain": Domain.SOFTWARE.value,
        "priority": Priority.HIGH.value,
    }


def test_goal_collector_is_deterministic() -> None:
    goal = make_goal(success_definition="users can ship")
    collector = GoalContextCollector()

    first = collector.collect(goal, request())
    second = collector.collect(goal, request())

    assert first == second


# --------------------------------------------------------------------------- #
# RequestFragmentCollector                                                    #
# --------------------------------------------------------------------------- #


def test_request_collector_returns_request_fragments_identically() -> None:
    a = fragment("a")
    b = fragment("b")
    req = request(a, b)

    collected = RequestFragmentCollector().collect(make_goal(), req)

    # Identity and order are preserved exactly.
    assert collected == (a, b)
    assert collected is req.fragments
    assert collected[0] is a
    assert collected[1] is b


def test_request_collector_empty_when_no_fragments() -> None:
    collected = RequestFragmentCollector().collect(make_goal(), request())

    assert collected == ()


# --------------------------------------------------------------------------- #
# StaticContextCollector                                                      #
# --------------------------------------------------------------------------- #


def test_static_collector_returns_fixed_fragments() -> None:
    a = fragment("a")
    b = fragment("b")
    collector = StaticContextCollector(a, b)

    collected = collector.collect(make_goal(), request())

    assert collected == (a, b)


def test_static_collector_ignores_goal_and_request() -> None:
    a = fragment("fixed")
    collector = StaticContextCollector(a)

    one = collector.collect(make_goal("goal-1"), request(fragment("seed")))
    two = collector.collect(make_goal("goal-2"), request())

    # Goal identity and request fragments have no effect on the fixed output.
    assert one == (a,)
    assert two == (a,)
    assert one == two


def test_static_collector_empty_when_no_fragments() -> None:
    collected = StaticContextCollector().collect(make_goal(), request())

    assert collected == ()


# --------------------------------------------------------------------------- #
# Protocol conformance                                                        #
# --------------------------------------------------------------------------- #


def test_all_collectors_satisfy_runtime_checkable_protocol() -> None:
    assert isinstance(GoalContextCollector(), ContextCollector)
    assert isinstance(RequestFragmentCollector(), ContextCollector)
    assert isinstance(StaticContextCollector(), ContextCollector)


def test_non_collector_object_is_not_a_collector() -> None:
    # Negative case: an object without collect() must not satisfy the Protocol.
    assert not isinstance(object(), ContextCollector)
