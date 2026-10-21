"""Correlation derivation for the Harness Service (precedence rules).

The compile cycle stamps one correlation identifier on every emitted event. Its
source has a deterministic precedence: an explicit ``correlation_identifier`` on the
:class:`CompilationRequest` wins; otherwise the first Harness Request's own
correlation is used; otherwise it is derived from that request's session reference;
and with no requests at all it falls back to a constant seed. These tests pin each
rung of that ladder (the genuinely-reachable branches of ``_correlation``).
"""

from __future__ import annotations

from nexus_harness import CompilationRequest
from tests.unit.nexus_harness.helpers import hrequest, ref, standard_env


def _events(infrastructure):
    return tuple(infrastructure.event_store.read_all())


def test_explicit_correlation_identifier_wins() -> None:
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(hrequest("node-research", work_package="wp-1"),),
        correlation_identifier="cor-explicit-override",
    )
    env.harness.service.compile(request)
    correlations = {event.correlation_identifier for event in _events(env.infrastructure)}
    assert correlations == {"cor-explicit-override"}


def test_correlation_derived_from_session_when_request_has_none() -> None:
    env = standard_env()
    # A request whose own correlation is absent and with no explicit override:
    # correlation derives from the first request's session reference.
    request = CompilationRequest(
        harness_requests=(hrequest("node-research", work_package="wp-1", correlation=None),)
    )
    env.harness.service.compile(request)
    correlations = {event.correlation_identifier for event in _events(env.infrastructure)}
    assert correlations == {"cor-session-goal-1-v1"}


def test_first_request_correlation_used_when_present() -> None:
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(
            hrequest("node-research", work_package="wp-1", correlation="cor-from-request"),
        )
    )
    env.harness.service.compile(request)
    correlations = {event.correlation_identifier for event in _events(env.infrastructure)}
    assert correlations == {"cor-from-request"}


def test_empty_batch_falls_back_to_constant_seed() -> None:
    env = standard_env()
    env.harness.service.compile(CompilationRequest(harness_requests=()))
    events = _events(env.infrastructure)
    assert events  # the trailing completed event is still emitted
    assert {event.correlation_identifier for event in events} == {"cor-harness"}


def test_session_ref_overrides_request_scope_but_not_correlation() -> None:
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(hrequest("node-research", work_package="wp-1", correlation=None),),
        session_ref=ref("execution_session", "session-goal-1-v1"),
    )
    env.harness.service.compile(request)
    # session_ref drives the event-id scope; correlation still derives from the request.
    correlations = {event.correlation_identifier for event in _events(env.infrastructure)}
    assert correlations == {"cor-session-goal-1-v1"}
