"""Repository observability — derived counters over the P1 sink (never authoritative).

Mirrors the policy/estimation/engineering/intent facades. The authoritative record of a scan is the
``repository.*`` event log and the returned :class:`~nexus_repository.profile.RepositoryProfile`;
these counters are a derived convenience and never influence the profile.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class RepositoryObservability:
    """Repository-scoped counters over the P1 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def profiled(
        self, *, repository_type: str, primary_language: str | None, file_count: int
    ) -> None:
        self._obs.increment("repository.profiled")
        self._obs.increment(f"repository.type.{repository_type}")
        if primary_language:
            self._obs.increment(f"repository.language.{primary_language}")
        self._obs.observe("repository.file_count", float(file_count))
