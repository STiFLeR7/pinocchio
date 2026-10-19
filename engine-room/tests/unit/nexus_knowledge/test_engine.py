"""Unit tests for the Knowledge Engine -- ingest, serve, lifecycle, events, determinism."""

from __future__ import annotations

from nexus_core.contracts.enums import ConfidenceLadder, Freshness, KnowledgeType
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_knowledge import (
    KnowledgeEngine,
    KnowledgeQuery,
    build_knowledge,
)
from nexus_knowledge.lifecycle import lifecycle_of
from nexus_knowledge.policy import PersistencePolicy
from nexus_knowledge.vocabulary import KnowledgeDecision, KnowledgeLifecycle
from nexus_runtime.events import FixedTimestampSource
from tests.unit.nexus_knowledge.helpers import candidate

KEY = "ki-lesson-retry-storm"


def _infra():  # type: ignore[no-untyped-def]
    return build_infrastructure(observability=InMemoryObservability())


def _knowledge(infra=None, *, policy=None):  # type: ignore[no-untyped-def]
    infra = infra or _infra()
    kwargs = {"timestamps": FixedTimestampSource(), "require_source_lineage": False}
    if policy is not None:
        kwargs["policy"] = policy
    return build_knowledge(infra, **kwargs)


def _events(infra):  # type: ignore[no-untyped-def]
    return [e for e in infra.event_store.read_all() if e.type.startswith("knowledge.")]


# --- ingest: create / reject ------------------------------------------------ #


def test_ingest_creates_a_durable_item() -> None:
    ctx = _knowledge()
    outcome = ctx.engine.ingest(candidate())
    assert outcome.accepted
    assert outcome.decision.outcome is KnowledgeDecision.ACCEPT_CREATE
    item = ctx.repositories.items.get(KEY)
    assert item is not None and item.understanding == candidate().statement
    assert lifecycle_of(item) is KnowledgeLifecycle.ACTIVE


def test_ingest_rejects_unvalidated_provenance() -> None:
    ctx = _knowledge()
    outcome = ctx.engine.ingest(candidate(evidence_type="execution_result"))
    assert not outcome.accepted
    assert ctx.repositories.items.get(KEY) is None


def test_ingest_emits_full_event_sequence() -> None:
    infra = _infra()
    ctx = _knowledge(infra)
    ctx.engine.ingest(candidate())
    assert [e.type for e in _events(infra)] == [
        "knowledge.candidate_received",
        "knowledge.candidate_accepted",
        "knowledge.item_created",
    ]


def test_rejection_emits_candidate_rejected() -> None:
    infra = _infra()
    ctx = _knowledge(infra)
    ctx.engine.ingest(candidate(confidence=ConfidenceLadder.EXPERIMENTAL))
    types = [e.type for e in _events(infra)]
    assert types == ["knowledge.candidate_received", "knowledge.candidate_rejected"]


# --- ingest: evolve / merge / duplicate ------------------------------------- #


def test_second_stronger_candidate_evolves_the_item() -> None:
    ctx = _knowledge()
    ctx.engine.ingest(candidate("kc-0001"))
    outcome = ctx.engine.ingest(
        candidate("kc-0002", statement="prefer jittered backoff", evidence=("ev-0002",))
    )
    assert outcome.decision.outcome is KnowledgeDecision.ACCEPT_EVOLVE
    item = ctx.repositories.items.get(KEY)
    assert item is not None and item.understanding == "prefer jittered backoff"
    assert outcome.version is not None and outcome.version.version == 2


def test_corroborating_candidate_merges_and_promotes_confidence() -> None:
    ctx = _knowledge()
    ctx.engine.ingest(candidate("kc-0001"))
    ctx.engine.ingest(candidate("kc-0002", evidence=("ev-0002",)))
    ctx.engine.ingest(candidate("kc-0003", evidence=("ev-0003",)))
    item = ctx.repositories.items.get(KEY)
    assert item is not None
    # three accumulated evidence -> Validated (count-derived promotion).
    assert item.confidence is ConfidenceLadder.VALIDATED


def test_duplicate_candidate_adding_nothing_is_rejected() -> None:
    ctx = _knowledge()
    ctx.engine.ingest(candidate("kc-0001"))
    outcome = ctx.engine.ingest(candidate("kc-0002"))  # same statement, same evidence
    assert outcome.decision.outcome is KnowledgeDecision.REJECT


def test_resubmitting_same_candidate_is_idempotent() -> None:
    infra = _infra()
    ctx = _knowledge(infra)
    ctx.engine.ingest(candidate("kc-0001"))
    before = len(_events(infra))
    outcome = ctx.engine.ingest(candidate("kc-0001"))
    assert outcome.idempotent
    assert len(_events(infra)) == before  # no new events (INV-16)


# --- supersession ----------------------------------------------------------- #


def test_candidate_can_supersede_a_prior_subject() -> None:
    infra = _infra()
    ctx = _knowledge(infra)
    ctx.engine.ingest(candidate("kc-0001", subject="old lesson"))
    outcome = ctx.engine.ingest(
        candidate("kc-0002", subject="retry storm", supersedes_subject="old lesson")
    )
    assert outcome.superseded is not None
    old = ctx.repositories.items.get("ki-lesson-lesson-old")
    assert old is not None and old.freshness is Freshness.SUPERSEDED
    assert old.superseded_by is not None and old.superseded_by.identifier == KEY
    assert "knowledge.item_superseded" in [e.type for e in _events(infra)]


def test_supersedes_unknown_subject_is_a_noop() -> None:
    ctx = _knowledge()
    outcome = ctx.engine.ingest(candidate(supersedes_subject="never existed"))
    assert outcome.superseded is None


# --- lifecycle maintenance -------------------------------------------------- #


def test_deprecate_expire_archive_transitions() -> None:
    ctx = _knowledge()
    ctx.engine.ingest(candidate())
    assert ctx.engine.deprecate(KEY) is not None
    assert ctx.repositories.items.get(KEY).freshness is Freshness.DEPRECATED  # type: ignore[union-attr]
    assert ctx.engine.archive(KEY) is not None
    assert ctx.repositories.items.get(KEY).freshness is Freshness.ARCHIVED  # type: ignore[union-attr]


def test_transition_of_unknown_subject_returns_none() -> None:
    ctx = _knowledge()
    assert ctx.engine.deprecate("ki-lesson-missing") is None


def test_maintain_expires_stale_items() -> None:
    policy = PersistencePolicy(freshness_ttl_seconds=3600)
    ctx = _knowledge(policy=policy)
    ctx.engine.ingest(candidate())  # timestamp fixed at epoch
    expired = ctx.engine.maintain("1970-01-02T00:00:00+00:00")
    assert len(expired) == 1
    assert ctx.repositories.items.get(KEY).freshness is Freshness.HISTORICAL  # type: ignore[union-attr]


def test_maintain_without_ttl_is_a_noop() -> None:
    ctx = _knowledge()  # default policy has no TTL
    ctx.engine.ingest(candidate())
    assert ctx.engine.maintain("2999-01-01T00:00:00+00:00") == ()


def test_maintain_keeps_fresh_items() -> None:
    policy = PersistencePolicy(freshness_ttl_seconds=3600)
    ctx = _knowledge(policy=policy)
    ctx.engine.ingest(candidate())
    assert ctx.engine.maintain("1970-01-01T00:00:01+00:00") == ()


# --- serve ------------------------------------------------------------------ #


def test_serve_returns_active_items() -> None:
    ctx = _knowledge()
    ctx.engine.ingest(candidate())
    served = ctx.engine.serve(KnowledgeQuery(kind=KnowledgeType.LESSON))
    assert len(served) == 1 and served[0].identity == KEY


def test_serve_without_repositories_returns_empty() -> None:
    engine = KnowledgeEngine(_infra(), timestamps=FixedTimestampSource())
    assert engine.serve(KnowledgeQuery()) == ()


def test_engine_without_repositories_still_creates_and_returns_outcome() -> None:
    engine = KnowledgeEngine(_infra(), timestamps=FixedTimestampSource())
    outcome = engine.ingest(candidate())
    assert outcome.accepted and outcome.item is not None


def test_engine_without_repositories_rejects_and_transitions_are_noops() -> None:
    engine = KnowledgeEngine(_infra(), timestamps=FixedTimestampSource())
    rejected = engine.ingest(candidate(evidence=()))  # insufficient evidence, repos-free path
    assert not rejected.accepted
    assert engine.deprecate(KEY) is None  # lifecycle transitions need repositories


def test_policy_property_exposes_the_configured_policy() -> None:
    policy = PersistencePolicy(minimum_evidence=3)
    ctx = _knowledge(policy=policy)
    assert ctx.engine.policy is policy


# --- terminal rejection ----------------------------------------------------- #


def test_terminal_rejection_blocks_later_candidates_for_the_subject() -> None:
    policy = PersistencePolicy(rejection_is_terminal=True)
    ctx = _knowledge(policy=policy)
    ctx.engine.ingest(candidate("kc-0001", confidence=ConfidenceLadder.EXPERIMENTAL))  # rejected
    # a later, valid candidate for the same subject is now blocked.
    outcome = ctx.engine.ingest(candidate("kc-0002"))
    assert outcome.decision.failed_requirement == "rejection_terminal"


# --- determinism ------------------------------------------------------------ #


def test_two_runs_produce_identical_items_and_events() -> None:
    infra1, infra2 = _infra(), _infra()
    c1 = _knowledge(infra1)
    c2 = _knowledge(infra2)
    for ctx in (c1, c2):
        ctx.engine.ingest(candidate("kc-0001"))
        ctx.engine.ingest(candidate("kc-0002", evidence=("ev-0002",)))
    assert c1.repositories.items.get(KEY) == c2.repositories.items.get(KEY)
    t1 = [(e.identifier, e.type, e.payload) for e in _events(infra1)]
    t2 = [(e.identifier, e.type, e.payload) for e in _events(infra2)]
    assert t1 == t2


def test_observability_counts_acceptance_and_rejection() -> None:
    infra = _infra()
    ctx = _knowledge(infra)
    ctx.engine.ingest(candidate("kc-0001"))
    ctx.engine.ingest(candidate("kc-0002", confidence=ConfidenceLadder.EXPERIMENTAL))
    sink = infra.observability
    assert sink.counters["knowledge.item_created"] == 1
    assert sink.counters["knowledge.candidate_rejected"] == 1
