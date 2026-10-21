"""Knowledge composition -- dependency-injection wiring for the Knowledge Engine.

Mirrors ``build_validation`` / ``build_recovery`` / ``build_reflection``: it **reuses** the Phase 2
infrastructure substrate (the event emitter is the infrastructure context; the repositories are the
Phase 2 ``InMemoryRepository`` / ``KnowledgeRepository``; the metrics sink is its observability)
rather than inventing anything. The infrastructure is not modified. Every dependency is overridable
and there is no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.event import Event
from nexus_core.domain.knowledge import Knowledge
from nexus_infra import InfrastructureContext
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.engine import KnowledgeEngine
from nexus_knowledge.model import KnowledgeVersion
from nexus_knowledge.observability import KnowledgeObservability
from nexus_knowledge.persistence import KnowledgeRepositories, build_knowledge_repositories
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_runtime.events import TimestampSource


@dataclass(frozen=True, slots=True)
class KnowledgeContextBundle:
    """The wired knowledge layer (immutable wiring, stateful engine + repositories)."""

    infrastructure: InfrastructureContext
    repositories: KnowledgeRepositories
    engine: KnowledgeEngine


def build_knowledge(
    infrastructure: InfrastructureContext,
    *,
    repositories: KnowledgeRepositories | None = None,
    timestamps: TimestampSource | None = None,
    policy: PersistencePolicy = DEFAULT_PERSISTENCE_POLICY,
    require_source_lineage: bool = True,
) -> KnowledgeContextBundle:
    """Wire a knowledge context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_knowledge_repositories(obs)
    engine = KnowledgeEngine(
        infrastructure,
        repositories=resolved,
        observability=KnowledgeObservability(obs),
        timestamps=timestamps,
        policy=policy,
        event_reader=lambda: tuple(infrastructure.event_store.read_all()),
        require_source_lineage=require_source_lineage,
    )
    _restore_from_events(resolved, tuple(infrastructure.event_store.read_all()))
    return KnowledgeContextBundle(
        infrastructure=infrastructure, repositories=resolved, engine=engine
    )


def _restore_from_events(repositories: KnowledgeRepositories, events: tuple[Event, ...]) -> None:
    """Rebuild Knowledge projections from immutable owner events without emitting new facts."""
    for event in events:
        if event.producer != "knowledge":
            continue
        payload = event.payload
        candidate_data = payload.get("candidate_data")
        if isinstance(candidate_data, dict):
            repositories.candidates.add(KnowledgeCandidate.model_validate(candidate_data))
        version_data = payload.get("version_data")
        if isinstance(version_data, dict):
            repositories.versions.add(KnowledgeVersion.model_validate(version_data))
        item_data = payload.get("item_data")
        if isinstance(item_data, dict):
            repositories.items.add(Knowledge.model_validate(item_data))
