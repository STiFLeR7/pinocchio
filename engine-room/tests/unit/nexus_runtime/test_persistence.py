"""Unit tests for nexus_runtime.persistence — 100% line+branch coverage."""

from __future__ import annotations

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.contracts.enums import ResourceAllocationState
from nexus_infra import InMemoryObservability
from nexus_runtime.allocation import Allocation
from nexus_runtime.persistence import RuntimeRepositories, build_runtime_repositories
from tests.unit.nexus_runtime.helpers import ref, runtime_env

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _corr(id_: str = "cor-1") -> Correlation:
    return Correlation(correlation_identifier=id_)


def _session_ref(id_: str = "ses-1") -> Reference:
    return ref("execution_session", id_)


def _make_allocation(
    identity: str = "alloc-ses-1-rt-a",
    session_id: str = "ses-1",
    runtime_id: str = "rt-a",
    state: ResourceAllocationState = ResourceAllocationState.RESERVED,
) -> Allocation:
    return Allocation(
        identity=identity,
        session_ref=_session_ref(session_id),
        runtime_ref=ref("harness", runtime_id),
        allocation_state=state,
        correlation=_corr(),
        metadata={"runtime": runtime_id, "capacity": 1},
    )


# ---------------------------------------------------------------------------
# build_runtime_repositories — structure
# ---------------------------------------------------------------------------


class TestBuildRuntimeRepositories:
    def test_returns_runtime_repositories_instance(self) -> None:
        repos = build_runtime_repositories()
        assert isinstance(repos, RuntimeRepositories)

    def test_has_sessions_and_allocations(self) -> None:
        repos = build_runtime_repositories()
        assert repos.sessions is not None
        assert repos.allocations is not None

    def test_with_observability_arg(self) -> None:
        obs = InMemoryObservability()
        repos = build_runtime_repositories(observability=obs)
        assert repos.sessions is not None
        assert repos.allocations is not None

    def test_without_observability_arg(self) -> None:
        repos = build_runtime_repositories(observability=None)
        assert repos.sessions is not None
        assert repos.allocations is not None


# ---------------------------------------------------------------------------
# RuntimeRepositories — round-trip for RuntimeSession
# ---------------------------------------------------------------------------


class TestRuntimeSessionRepository:
    def _make_session(self, env):
        """Build a RuntimeSession via the manager's builder (exactly as production does)."""
        from tests.unit.nexus_runtime.helpers import intake

        i = intake(package_identity="pkg-a", node="node-a")
        return env.manager._session_builder.build(i, correlation_identifier="cor-a")

    def test_session_add_and_get_roundtrip(self) -> None:
        env = runtime_env()
        repos = build_runtime_repositories()
        session = self._make_session(env)

        repos.sessions.add(session)
        retrieved = repos.sessions.get(session.identity)

        assert retrieved is not None
        assert retrieved.identity == session.identity

    def test_session_get_missing_returns_none(self) -> None:
        repos = build_runtime_repositories()
        assert repos.sessions.get("nonexistent") is None

    def test_sessions_list_all(self) -> None:
        env = runtime_env()
        repos = build_runtime_repositories()
        session = self._make_session(env)

        repos.sessions.add(session)
        all_sessions = repos.sessions.list_all()
        assert len(all_sessions) == 1
        assert all_sessions[0].identity == session.identity


# ---------------------------------------------------------------------------
# RuntimeRepositories — round-trip for Allocation
# ---------------------------------------------------------------------------


class TestAllocationRepository:
    def test_allocation_add_and_get_roundtrip(self) -> None:
        repos = build_runtime_repositories()
        alloc = _make_allocation()

        repos.allocations.add(alloc)
        retrieved = repos.allocations.get(alloc.identity)

        assert retrieved is not None
        assert retrieved.identity == alloc.identity
        assert retrieved.allocation_state is ResourceAllocationState.RESERVED

    def test_allocation_get_missing_returns_none(self) -> None:
        repos = build_runtime_repositories()
        assert repos.allocations.get("nonexistent") is None

    def test_allocations_list_all(self) -> None:
        repos = build_runtime_repositories()
        alloc = _make_allocation()

        repos.allocations.add(alloc)
        all_allocs = repos.allocations.list_all()
        assert len(all_allocs) == 1

    def test_allocation_replace_on_state_change(self) -> None:
        repos = build_runtime_repositories()
        alloc = _make_allocation()
        repos.allocations.add(alloc)

        advanced = alloc.in_state(ResourceAllocationState.ALLOCATED)
        repos.allocations.add(advanced)

        retrieved = repos.allocations.get(alloc.identity)
        assert retrieved is not None
        assert retrieved.allocation_state is ResourceAllocationState.ALLOCATED

    def test_with_observability_records_writes(self) -> None:
        obs = InMemoryObservability()
        repos = build_runtime_repositories(observability=obs)
        alloc = _make_allocation()

        repos.allocations.add(alloc)

        assert obs.counters.get("repository.write", 0) >= 1
