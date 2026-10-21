"""Unit tests for the deterministic Freshness Validator (Step 5, Phase 4).

Freshness is measured, never inferred: an item's ``observed_at`` is aged against the
policy's explicit ``evaluation_instant`` (never the wall clock) and the applicable
``max_age`` (per-category override, else the policy default):

- age <= max_age            -> VALID
- max_age < age <= 2*max_age -> STALE
- age > 2*max_age           -> EXPIRED

Missing timestamps, a missing evaluation instant, or an unparseable instant yield
UNKNOWN (never a raise); a future-dated observation is VALID (clock skew, not decay);
absent any applicable threshold a timestamped item is VALID. All ages here are
computed deliberately from ISO-8601 instants exactly one day apart (86400 seconds).
"""

from __future__ import annotations

from nexus_context.categories import ContextCategory, FreshnessState
from nexus_context.freshness import FreshnessValidator
from nexus_context.normalizer import Normalizer
from nexus_context.requests import ContextItem, FreshnessPolicy
from tests.unit.nexus_context.helpers import fragment

# Two instants exactly one day apart -> a deliberate 86400-second age.
_OBSERVED = "1970-01-01T00:00:00+00:00"
_ONE_DAY_LATER = "1970-01-02T00:00:00+00:00"
_ONE_DAY_SECONDS = 86400


def _items(*fragments: object) -> tuple[ContextItem, ...]:
    """Normalize raw fragments into the canonical item set the validator consumes."""
    return Normalizer().normalize(tuple(fragments))  # type: ignore[arg-type]


def _verdict(item_observed_at: str | None, policy: FreshnessPolicy) -> FreshnessState:
    """Evaluate a single workspace item and return its freshness verdict."""
    items = _items(fragment("k", observed_at=item_observed_at))
    evaluated = FreshnessValidator().evaluate(items, policy)
    return evaluated[0].freshness


# --------------------------------------------------------------------------- #
# UNKNOWN branches                                                            #
# --------------------------------------------------------------------------- #


def test_unknown_when_observed_at_missing() -> None:
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=_ONE_DAY_SECONDS
    )
    assert _verdict(None, policy) is FreshnessState.UNKNOWN


def test_unknown_when_evaluation_instant_missing() -> None:
    policy = FreshnessPolicy(default_max_age_seconds=_ONE_DAY_SECONDS)
    assert _verdict(_OBSERVED, policy) is FreshnessState.UNKNOWN


def test_unknown_when_timestamp_unparseable_does_not_raise() -> None:
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=_ONE_DAY_SECONDS
    )
    assert _verdict("not-a-timestamp", policy) is FreshnessState.UNKNOWN


def test_unknown_when_evaluation_instant_unparseable() -> None:
    policy = FreshnessPolicy(evaluation_instant="garbage", default_max_age_seconds=_ONE_DAY_SECONDS)
    assert _verdict(_OBSERVED, policy) is FreshnessState.UNKNOWN


# --------------------------------------------------------------------------- #
# VALID / STALE / EXPIRED bands (age fixed at 86400s)                          #
# --------------------------------------------------------------------------- #


def test_valid_when_age_equals_max_age() -> None:
    # age (86400) <= max_age (86400) -> VALID (boundary inclusive).
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=_ONE_DAY_SECONDS
    )
    assert _verdict(_OBSERVED, policy) is FreshnessState.VALID


def test_valid_when_age_below_max_age() -> None:
    # age (86400) < max_age (100000) -> VALID.
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=100_000)
    assert _verdict(_OBSERVED, policy) is FreshnessState.VALID


def test_stale_when_age_in_upper_band() -> None:
    # max_age (43200) < age (86400) <= 2*max_age (86400) -> STALE (upper boundary inclusive).
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=43_200)
    assert _verdict(_OBSERVED, policy) is FreshnessState.STALE


def test_stale_just_past_max_age() -> None:
    # max_age (86399) < age (86400) <= 2*max_age (172798) -> STALE.
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=86_399)
    assert _verdict(_OBSERVED, policy) is FreshnessState.STALE


def test_expired_when_age_beyond_double_max_age() -> None:
    # age (86400) > 2*max_age (40000) -> EXPIRED.
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=20_000)
    assert _verdict(_OBSERVED, policy) is FreshnessState.EXPIRED


# --------------------------------------------------------------------------- #
# No applicable threshold & future observation                                #
# --------------------------------------------------------------------------- #


def test_valid_when_no_applicable_max_age_but_timestamps_present() -> None:
    # default None and no by_category entry -> VALID rather than guessed.
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER)
    assert _verdict(_OBSERVED, policy) is FreshnessState.VALID


def test_valid_for_future_observation_negative_age() -> None:
    # observed_at is after evaluation_instant -> negative age -> VALID (clock skew).
    policy = FreshnessPolicy(evaluation_instant=_OBSERVED, default_max_age_seconds=10)
    assert _verdict(_ONE_DAY_LATER, policy) is FreshnessState.VALID


# --------------------------------------------------------------------------- #
# by_category override                                                        #
# --------------------------------------------------------------------------- #


def test_by_category_override_beats_default() -> None:
    # Default would mark VALID (100000), but the WORKSPACE override (20000) expires it.
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER,
        default_max_age_seconds=100_000,
        by_category={ContextCategory.WORKSPACE.value: 20_000},
    )
    assert _verdict(_OBSERVED, policy) is FreshnessState.EXPIRED


def test_by_category_override_only_applies_to_matching_category() -> None:
    # The override targets a different category, so the default (100000) governs -> VALID.
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER,
        default_max_age_seconds=100_000,
        by_category={ContextCategory.GOAL.value: 1},
    )
    assert _verdict(_OBSERVED, policy) is FreshnessState.VALID


def test_bool_in_by_category_is_ignored_and_falls_back_to_default() -> None:
    # bool is excluded as a max_age even though bool is an int subclass -> default applies.
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER,
        default_max_age_seconds=20_000,
        by_category={ContextCategory.WORKSPACE.value: True},
    )
    # Falls back to default (20000): age 86400 > 2*20000 -> EXPIRED.
    assert _verdict(_OBSERVED, policy) is FreshnessState.EXPIRED


def test_bool_in_by_category_falls_back_to_none_default() -> None:
    # bool ignored and no default -> no applicable threshold -> VALID.
    policy = FreshnessPolicy(
        evaluation_instant=_ONE_DAY_LATER,
        by_category={ContextCategory.WORKSPACE.value: True},
    )
    assert _verdict(_OBSERVED, policy) is FreshnessState.VALID


# --------------------------------------------------------------------------- #
# Determinism & immutability                                                  #
# --------------------------------------------------------------------------- #


def test_evaluate_is_deterministic() -> None:
    items = _items(
        fragment("a", observed_at=_OBSERVED),
        fragment("b", observed_at=None),
        fragment("c", observed_at="not-a-timestamp"),
    )
    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=43_200)
    validator = FreshnessValidator()

    first = validator.evaluate(items, policy)
    second = validator.evaluate(items, policy)

    assert first == second


def test_evaluate_returns_frozen_copies_leaving_originals_unchanged() -> None:
    items = _items(fragment("k", observed_at=_OBSERVED))
    original = items[0]
    assert original.freshness is FreshnessState.UNKNOWN

    policy = FreshnessPolicy(evaluation_instant=_ONE_DAY_LATER, default_max_age_seconds=43_200)
    evaluated = FreshnessValidator().evaluate(items, policy)

    # The original is untouched; the evaluated item is a distinct enriched copy.
    assert original.freshness is FreshnessState.UNKNOWN
    assert evaluated[0] is not original
    assert evaluated[0].freshness is FreshnessState.STALE
    assert evaluated[0].identity == original.identity
