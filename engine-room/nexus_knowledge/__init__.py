"""``nexus_knowledge`` -- the Knowledge Engine (deterministic, durable operational memory).

Knowledge is the **persistence layer** at the end of the intelligence pipeline. It consumes the
advisory Knowledge *Candidates* Reflection produces, judges each against a declarative Persistence
Policy, and either accepts it (creating or evolving a durable Knowledge Item), merges it into
existing understanding, or rejects it -- recording every decision as immutable, explainable audit.
It then serves the resulting Knowledge read-only to Planning, Context Engineering, and
Orchestration::

    Reflection --candidates (by value)--> Knowledge --read-only views--> Planning / Context

It **decides, preserves, evolves, expires, and serves** durable understanding; it never executes,
analyses, validates, retries, recovers, or evaluates governance policy (INV-25/INV-26/INV-28). The
durable Item is the frozen core ``Knowledge`` contract (doc 03 -- no competing model); its identity
is the deterministic Knowledge Subject Key, so the same lesson learned twice strengthens one Item
rather than fragmenting.

Dependency direction: ``nexus_knowledge -> {nexus_core, nexus_infra}`` only. It imports no upstream
layer (not Reflection) -- candidates cross the boundary **by value** -- so no consumer can reach
Reflection through Knowledge, preserving INV-26 structurally. It reuses the Phase 2 substrate
(event store, repositories, observability) without modifying it.
"""

from __future__ import annotations

from nexus_knowledge.acceptance import AcceptanceDecision, AcceptanceEngine, SubjectState
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.composition import KnowledgeContextBundle, build_knowledge
from nexus_knowledge.engine import IngestOutcome, KnowledgeEngine
from nexus_knowledge.evolution import EvolutionEngine
from nexus_knowledge.ids import normalize_subject, subject_key, version_id
from nexus_knowledge.lifecycle import freshness_for, is_served, lifecycle_of, status_for
from nexus_knowledge.model import KnowledgeVersion, build_item
from nexus_knowledge.observability import KnowledgeObservability
from nexus_knowledge.persistence import KnowledgeRepositories, build_knowledge_repositories
from nexus_knowledge.policy import (
    DEFAULT_PERSISTENCE_POLICY,
    PersistencePolicy,
    at_least,
    confidence_for,
    ladder_index,
)
from nexus_knowledge.retrieval import KnowledgeQuery, KnowledgeRetrieval
from nexus_knowledge.vocabulary import (
    DuplicateStrategy,
    KnowledgeDecision,
    KnowledgeLifecycle,
)

__version__ = "2.5.0"

__all__ = [
    "DEFAULT_PERSISTENCE_POLICY",
    "AcceptanceDecision",
    "AcceptanceEngine",
    "DuplicateStrategy",
    "EvolutionEngine",
    "IngestOutcome",
    "KnowledgeCandidate",
    "KnowledgeContextBundle",
    "KnowledgeDecision",
    "KnowledgeEngine",
    "KnowledgeLifecycle",
    "KnowledgeObservability",
    "KnowledgeQuery",
    "KnowledgeRepositories",
    "KnowledgeRetrieval",
    "KnowledgeVersion",
    "PersistencePolicy",
    "SubjectState",
    "at_least",
    "build_item",
    "build_knowledge",
    "build_knowledge_repositories",
    "confidence_for",
    "freshness_for",
    "is_served",
    "ladder_index",
    "lifecycle_of",
    "normalize_subject",
    "status_for",
    "subject_key",
    "version_id",
]
