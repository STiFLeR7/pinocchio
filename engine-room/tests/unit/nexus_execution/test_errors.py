"""Unit tests for nexus_execution.errors — the doc-11 error-class mapping."""

from __future__ import annotations

import pytest

from nexus_execution.errors import (
    ExecutionError,
    ExecutionStartupError,
    InfrastructureError,
    ProviderError,
    RuntimeTimeoutError,
    TeardownError,
    TransportError,
    UserCancellationError,
)


def test_base_error_carries_detail() -> None:
    err = ExecutionError("boom")
    assert err.detail == "boom"
    assert err.error_class == "execution-failure"
    assert err.owner == "runtime"


@pytest.mark.parametrize(
    ("cls", "error_class", "owner"),
    [
        (ExecutionStartupError, "execution-startup-failure", "runtime"),
        (TransportError, "transport-failure", "transport"),
        (ProviderError, "provider-failure", "provider"),
        (RuntimeTimeoutError, "timeout", "runtime"),
        (UserCancellationError, "user-cancellation", "user"),
        (InfrastructureError, "infrastructure-failure", "infrastructure"),
        (TeardownError, "teardown-failure", "runtime"),
    ],
)
def test_subclasses_map_to_doc11_class_and_owner(
    cls: type[ExecutionError], error_class: str, owner: str
) -> None:
    err = cls("detail")
    assert err.error_class == error_class
    assert err.owner == owner
    assert isinstance(err, ExecutionError)


def test_errors_are_raisable() -> None:
    with pytest.raises(ProviderError):
        raise ProviderError("x")
