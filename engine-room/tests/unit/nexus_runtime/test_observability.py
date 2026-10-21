"""Unit tests for nexus_runtime.observability — 100% line+branch coverage."""

from __future__ import annotations

from nexus_infra import InMemoryObservability, NullObservability
from nexus_runtime.observability import (
    ALLOCATED,
    DISCOVERED,
    FAILED,
    REGISTERED,
    RELEASED,
    SESSION_CREATED,
    SESSION_READY,
    RuntimeObservability,
)

# ---------------------------------------------------------------------------
# RuntimeObservability with InMemoryObservability sink
# ---------------------------------------------------------------------------


class TestRuntimeObservabilityWithSink:
    def setup_method(self) -> None:
        self.sink = InMemoryObservability()
        self.obs = RuntimeObservability(self.sink)

    def test_registered_increments_counter(self) -> None:
        self.obs.registered()
        assert self.sink.counters.get(REGISTERED) == 1

    def test_registered_multiple_times(self) -> None:
        self.obs.registered()
        self.obs.registered()
        assert self.sink.counters.get(REGISTERED) == 2

    def test_discovered_increments_counter(self) -> None:
        self.obs.discovered(3)
        assert self.sink.counters.get(DISCOVERED) == 1

    def test_discovered_also_calls_observe(self) -> None:
        self.obs.discovered(7)
        observations = self.sink.observations.get("runtime.candidates_resolved_count", [])
        assert observations == [7.0]

    def test_discovered_zero_count(self) -> None:
        self.obs.discovered(0)
        assert self.sink.counters.get(DISCOVERED) == 1
        observations = self.sink.observations.get("runtime.candidates_resolved_count", [])
        assert observations == [0.0]

    def test_session_created_increments_counter(self) -> None:
        self.obs.session_created()
        assert self.sink.counters.get(SESSION_CREATED) == 1

    def test_allocated_increments_counter(self) -> None:
        self.obs.allocated()
        assert self.sink.counters.get(ALLOCATED) == 1

    def test_session_ready_increments_counter(self) -> None:
        self.obs.session_ready()
        assert self.sink.counters.get(SESSION_READY) == 1

    def test_released_increments_counter(self) -> None:
        self.obs.released()
        assert self.sink.counters.get(RELEASED) == 1

    def test_failed_increments_counter(self) -> None:
        self.obs.failed()
        assert self.sink.counters.get(FAILED) == 1

    def test_all_counters_independent(self) -> None:
        self.obs.registered()
        self.obs.discovered(2)
        self.obs.session_created()
        self.obs.allocated()
        self.obs.session_ready()
        self.obs.released()
        self.obs.failed()

        assert self.sink.counters[REGISTERED] == 1
        assert self.sink.counters[DISCOVERED] == 1
        assert self.sink.counters[SESSION_CREATED] == 1
        assert self.sink.counters[ALLOCATED] == 1
        assert self.sink.counters[SESSION_READY] == 1
        assert self.sink.counters[RELEASED] == 1
        assert self.sink.counters[FAILED] == 1


# ---------------------------------------------------------------------------
# RuntimeObservability default constructor (NullObservability)
# ---------------------------------------------------------------------------


class TestRuntimeObservabilityDefaultConstructor:
    def test_no_arg_uses_null_observability(self) -> None:
        obs = RuntimeObservability()
        assert isinstance(obs._obs, NullObservability)

    def test_none_arg_uses_null_observability(self) -> None:
        obs = RuntimeObservability(None)
        assert isinstance(obs._obs, NullObservability)

    def test_default_registered_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.registered()  # must not raise

    def test_default_discovered_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.discovered(5)  # must not raise

    def test_default_session_created_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.session_created()

    def test_default_allocated_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.allocated()

    def test_default_session_ready_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.session_ready()

    def test_default_released_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.released()

    def test_default_failed_does_not_raise(self) -> None:
        obs = RuntimeObservability()
        obs.failed()


# ---------------------------------------------------------------------------
# Counter name constants
# ---------------------------------------------------------------------------


class TestCounterNameConstants:
    def test_counter_names(self) -> None:
        assert REGISTERED == "runtime.registered"
        assert DISCOVERED == "runtime.discovered"
        assert ALLOCATED == "runtime.allocated"
        assert SESSION_CREATED == "runtime.session_created"
        assert SESSION_READY == "runtime.session_ready"
        assert RELEASED == "runtime.released"
        assert FAILED == "runtime.failed"
