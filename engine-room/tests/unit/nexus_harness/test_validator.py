"""Unit tests for nexus_harness.validator — HarnessValidator and ValidatedRequest.

Verifies that HarnessValidator resolves primary references deterministically,
raises UnresolvedReferenceError for any dangling reference (fail-closed), returns
None for an absent execution_strategy_ref, and that ValidatedRequest is frozen.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_harness.validator import HarnessValidator, ValidatedRequest
from nexus_harness.validators import UnresolvedReferenceError
from tests.unit.nexus_harness.helpers import (
    context_package,
    harness_env,
    hrequest,
    standard_env,
    strategy,
    work_package,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _validator(env_result) -> HarnessValidator:
    return HarnessValidator(env_result.harness.sources)


# --------------------------------------------------------------------------- #
# Success — all references present                                              #
# --------------------------------------------------------------------------- #


def test_validate_returns_validated_request_when_all_sources_populated() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")

    result = _validator(env).validate(request)

    assert isinstance(result, ValidatedRequest)


def test_validate_resolves_work_package() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")

    result = _validator(env).validate(request)

    assert result.work_package is not None
    assert result.work_package.identifier == "wp-1"


def test_validate_resolves_context_package() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")

    result = _validator(env).validate(request)

    assert result.context_package is not None
    assert result.context_package.identity == "ctx-1"


def test_validate_resolves_execution_strategy() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")

    result = _validator(env).validate(request)

    assert result.strategy is not None
    assert result.strategy.identity == "strat-1"


def test_validate_carries_original_request() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")

    result = _validator(env).validate(request)

    assert result.request is request


# --------------------------------------------------------------------------- #
# strategy is None when no execution_strategy_ref                               #
# --------------------------------------------------------------------------- #


def test_validate_strategy_is_none_when_no_execution_strategy_ref() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref=None)

    result = _validator(env).validate(request)

    assert result.strategy is None


# --------------------------------------------------------------------------- #
# UnresolvedReferenceError — work package missing                               #
# --------------------------------------------------------------------------- #


def test_validate_raises_when_work_package_not_in_sources() -> None:
    env = harness_env(
        context_packages=(context_package(),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", work_package="wp-missing", context="ctx-1", strategy_ref="strat-1")

    with pytest.raises(UnresolvedReferenceError):
        _validator(env).validate(request)


def test_validate_work_package_missing_raises_unresolved_reference_error() -> None:
    env = harness_env(
        context_packages=(context_package(),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", work_package="wp-ghost", context="ctx-1", strategy_ref="strat-1")

    with pytest.raises(UnresolvedReferenceError) as exc_info:
        _validator(env).validate(request)

    assert "wp-ghost" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# UnresolvedReferenceError — context ref missing / None                         #
# --------------------------------------------------------------------------- #


def test_validate_raises_when_context_ref_is_none() -> None:
    env = harness_env(
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", work_package="wp-1", context=None, strategy_ref="strat-1")

    with pytest.raises(UnresolvedReferenceError):
        _validator(env).validate(request)


def test_validate_raises_when_context_package_not_in_sources() -> None:
    env = harness_env(
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", work_package="wp-1", context="ctx-missing", strategy_ref="strat-1")

    with pytest.raises(UnresolvedReferenceError):
        _validator(env).validate(request)


def test_validate_context_missing_raises_unresolved_reference_error() -> None:
    env = harness_env(
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", work_package="wp-1", context="ctx-ghost", strategy_ref="strat-1")

    with pytest.raises(UnresolvedReferenceError) as exc_info:
        _validator(env).validate(request)

    assert "ctx-ghost" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# UnresolvedReferenceError — strategy ref present but unresolvable              #
# --------------------------------------------------------------------------- #


def test_validate_raises_when_strategy_ref_present_but_not_in_sources() -> None:
    env = harness_env(
        work_packages=(work_package("wp-1"),),
        context_packages=(context_package(),),
    )
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-missing")

    with pytest.raises(UnresolvedReferenceError):
        _validator(env).validate(request)


def test_validate_unresolvable_strategy_raises_unresolved_reference_error() -> None:
    env = harness_env(
        work_packages=(work_package("wp-1"),),
        context_packages=(context_package(),),
    )
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-ghost")

    with pytest.raises(UnresolvedReferenceError) as exc_info:
        _validator(env).validate(request)

    assert "strat-ghost" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# ValidatedRequest is frozen (immutable)                                        #
# --------------------------------------------------------------------------- #


def test_validated_request_rejects_mutation() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")
    result = _validator(env).validate(request)

    with pytest.raises((TypeError, AttributeError, ValidationError)):
        result.strategy = None  # type: ignore[misc]


def test_validated_request_rejects_work_package_mutation() -> None:
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1", context="ctx-1", strategy_ref="strat-1")
    result = _validator(env).validate(request)
    other_wp = work_package("wp-other")

    with pytest.raises((TypeError, AttributeError, ValidationError)):
        result.work_package = other_wp  # type: ignore[misc]
