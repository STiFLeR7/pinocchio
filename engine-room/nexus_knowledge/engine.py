"""The Knowledge Engine -- deterministically turns advisory Candidates into durable Knowledge.

Milestones 1-10. The Engine exposes two deterministic operations that never run inline with an
execution (doc 01):

1. **ingest** (candidate -> decision): emit ``candidate_received``; build the Subject-Key state
   from the repositories; run the :class:`~nexus_knowledge.acceptance.AcceptanceEngine`; apply the
   decision through the :class:`~nexus_knowledge.evolution.EvolutionEngine` (create / evolve /
   merge / supersede); persist the Item projection + version chain; emit the ``knowledge.*`` facts.
2. **serve** (query -> read-only views): delegate to
   :class:`~nexus_knowledge.retrieval.KnowledgeRetrieval` (Active by default, side-effect-free).

Plus the deterministic lifecycle operations (doc 06/11): ``deprecate`` / ``expire`` / ``archive``
and a ``maintain`` freshness pass. The Engine **coordinates**; it performs no AI reasoning, never
executes or analyses work, and never evaluates governance policy (INV-25/INV-26/INV-28). Given the
same candidate, the same existing state, and the same policy, it yields the same decision, the same
Item version, and the same event stream (doc 01 determinism).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_core.contracts.base import Reference, Struct
from nexus_core.contracts.enums import Freshness
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_core.domain.event import Event
from nexus_core.domain.knowledge import Knowledge
from nexus_core.events.interfaces import EventEmitter
from nexus_knowledge import events as kevents
from nexus_knowledge import ids
from nexus_knowledge.acceptance import AcceptanceDecision, AcceptanceEngine, SubjectState
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.evolution import EvolutionEngine
from nexus_knowledge.lifecycle import freshness_for, is_stale, lifecycle_of
from nexus_knowledge.model import KnowledgeVersion, build_item
from nexus_knowledge.observability import KnowledgeObservability
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_knowledge.provenance import verify_candidate_sources
from nexus_knowledge.retrieval import KnowledgeQuery, KnowledgeRetrieval
from nexus_knowledge.vocabulary import (
    KNOWLEDGE_ITEM_TARGET_TYPE,
    KnowledgeDecision,
    KnowledgeLifecycle,
)
from nexus_runtime.events import SystemTimestampSource, TimestampSource


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    """The immutable result of ingesting one candidate: the decision and the resulting Item."""

    decision: AcceptanceDecision
    item: Knowledge | None = None
    version: KnowledgeVersion | None = None
    superseded: Reference | None = None
    idempotent: bool = False

    @property
    def accepted(self) -> bool:
        """Whether the ingestion created or changed durable Knowledge."""
        return self.decision.accepted


class KnowledgeEngine:
    """Coordinates acceptance, evolution, persistence, and serving of durable Knowledge."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        repositories: KnowledgeRepositories | None = None,
        observability: KnowledgeObservability | None = None,
        timestamps: TimestampSource | None = None,
        policy: PersistencePolicy = DEFAULT_PERSISTENCE_POLICY,
        acceptance: AcceptanceEngine | None = None,
        evolution: EvolutionEngine | None = None,
        event_reader: Callable[[], tuple[Event, ...]] | None = None,
        require_source_lineage: bool = True,
    ) -> None:
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or KnowledgeObservability()
        self._timestamps = timestamps or SystemTimestampSource()
        self._policy = policy
        self._acceptance = acceptance or AcceptanceEngine()
        self._evolution = evolution or EvolutionEngine()
        self._event_reader = event_reader
        self._require_source_lineage = require_source_lineage
        self._terminally_rejected: set[str] = set()
        self._retrieval = (
            KnowledgeRetrieval(repositories.items, policy, self._obs) if repositories else None
        )

    @property
    def policy(self) -> PersistencePolicy:
        """The Persistence Policy this Engine evaluates against (doc 04)."""
        return self._policy

    # -- ingest -------------------------------------------------------------- #

    def ingest(self, candidate: KnowledgeCandidate) -> IngestOutcome:
        """Judge one candidate under policy; emit events, persist, and return the outcome."""
        key = ids.subject_key(candidate.kind, candidate.subject)
        correlation = candidate.correlation_identifier or key

        if self._already_ingested(candidate):
            return IngestOutcome(
                decision=self._noop_decision(candidate, key),
                item=self._repos.items.get(key) if self._repos else None,
                idempotent=True,
            )

        seq = 0
        seq = self._emit(
            candidate.identity,
            kevents.KNOWLEDGE_CANDIDATE_RECEIVED,
            "received",
            seq,
            correlation,
            {"candidate": candidate.identity, "subject_key": key, "kind": candidate.kind.value},
        )
        self._obs.candidate_received()

        state = self._subject_state(key)
        source_verifier = None
        if self._require_source_lineage and self._event_reader is not None:
            event_reader = self._event_reader

            def source_verifier(item: KnowledgeCandidate) -> bool:
                return verify_candidate_sources(item, event_reader())

        decision = self._acceptance.evaluate(
            candidate,
            state,
            self._policy,
            key,
            source_verifier=source_verifier,
        )

        if decision.outcome is KnowledgeDecision.REJECT:
            return self._apply_rejection(candidate, decision, key, correlation, seq)
        return self._apply_acceptance(candidate, decision, key, correlation, seq)

    def _apply_rejection(
        self,
        candidate: KnowledgeCandidate,
        decision: AcceptanceDecision,
        key: str,
        correlation: str,
        seq: int,
    ) -> IngestOutcome:
        self._emit(
            candidate.identity,
            kevents.KNOWLEDGE_CANDIDATE_REJECTED,
            "rejected",
            seq,
            correlation,
            {
                "candidate": candidate.identity,
                "candidate_data": candidate.model_dump(mode="json"),
                "subject_key": key,
                "failed_requirement": decision.failed_requirement,
                "policy_version": decision.policy_version,
            },
        )
        self._obs.candidate_rejected(decision.failed_requirement or "unknown")
        if self._policy.rejection_is_terminal:
            self._terminally_rejected.add(key)
        self._record_candidate(candidate)
        return IngestOutcome(
            decision=decision, item=self._repos.items.get(key) if self._repos else None
        )

    def _apply_acceptance(
        self,
        candidate: KnowledgeCandidate,
        decision: AcceptanceDecision,
        key: str,
        correlation: str,
        seq: int,
    ) -> IngestOutcome:
        if decision.outcome is KnowledgeDecision.ACCEPT_CREATE:
            version = self._evolution.create_version(candidate, decision, self._timestamps.now())
            item_event, kind = kevents.KNOWLEDGE_ITEM_CREATED, "created"
        else:
            prior = self._subject_state(key).latest_version
            assert prior is not None
            version = self._evolution.next_version(
                prior, candidate, decision, self._timestamps.now()
            )
            item_event, kind = kevents.KNOWLEDGE_ITEM_EVOLVED, "evolved"

        superseded = self._maybe_supersede(candidate, key)
        related = (superseded,) if superseded is not None else ()
        if superseded is not None:
            version = version.model_copy(
                update={
                    "supersedes": superseded,
                    "provenance_added": (*version.provenance_added, superseded),
                }
            )

        item = build_item(
            version,
            status=KnowledgeIngestionStatus.ACCEPTED,
            freshness=Freshness.CURRENT,
            related_refs=related,
        )
        prior_item = self._repos.items.get(key) if self._repos is not None else None
        if prior_item is not None and prior_item.metadata is not None:
            retained_feedback = prior_item.metadata.get("feedback_refs", [])
            if isinstance(retained_feedback, list) and retained_feedback:
                metadata = dict(item.metadata or {})
                metadata["feedback_refs"] = retained_feedback
                item = item.model_copy(update={"metadata": metadata})
        self._persist(item, version, candidate)

        seq = self._emit(
            candidate.identity,
            kevents.KNOWLEDGE_CANDIDATE_ACCEPTED,
            "accepted",
            seq,
            correlation,
            {
                "candidate": candidate.identity,
                "candidate_data": candidate.model_dump(mode="json"),
                "subject_key": key,
                "outcome": decision.outcome.value,
            },
        )
        self._obs.candidate_accepted()
        seq = self._emit(
            candidate.identity,
            item_event,
            kind,
            seq,
            correlation,
            {
                "subject_key": key,
                "version": version.version,
                "confidence": version.confidence.value,
                "evidence": len(version.evidence_refs),
                "item_data": item.model_dump(mode="json"),
                "version_data": version.model_dump(mode="json"),
            },
        )
        if decision.outcome is KnowledgeDecision.ACCEPT_CREATE:
            self._obs.item_created(version.confidence)
        else:
            self._obs.item_evolved(version.confidence)

        if superseded is not None:
            self._emit_supersession(superseded, candidate.identity, key, correlation, seq)

        return IngestOutcome(decision=decision, item=item, version=version, superseded=superseded)

    # -- supersession -------------------------------------------------------- #

    def _maybe_supersede(self, candidate: KnowledgeCandidate, key: str) -> Reference | None:
        """Resolve the Item this candidate replaces, if any (deterministic, doc 10)."""
        if not candidate.supersedes_subject or self._repos is None:
            return None
        old_key = ids.subject_key(candidate.kind, candidate.supersedes_subject)
        if old_key == key or self._repos.items.get(old_key) is None:
            return None
        return Reference(target_type=KNOWLEDGE_ITEM_TARGET_TYPE, identifier=old_key)

    def _emit_supersession(
        self, superseded: Reference, id_scope: str, key: str, correlation: str, seq: int
    ) -> None:
        assert self._repos is not None
        old = self._repos.items.get(superseded.identifier)
        assert old is not None
        retired = old.model_copy(
            update={
                "freshness": Freshness.SUPERSEDED,
                "superseded_by": Reference(target_type=KNOWLEDGE_ITEM_TARGET_TYPE, identifier=key),
            }
        )
        self._repos.items.add(retired)
        self._emit(
            id_scope,
            kevents.KNOWLEDGE_ITEM_SUPERSEDED,
            "superseded",
            seq,
            correlation,
            {
                "subject_key": key,
                "superseded": superseded.identifier,
                "item_data": retired.model_dump(mode="json"),
            },
        )
        self._obs.item_superseded()

    # -- lifecycle maintenance (doc 06/11) ----------------------------------- #

    def deprecate(self, subject_key: str, *, correlation: str = "") -> Knowledge | None:
        """Withhold an Item from default serving (contradiction / policy deprecation, doc 11)."""
        return self._transition(
            subject_key,
            KnowledgeLifecycle.DEPRECATED,
            kevents.KNOWLEDGE_ITEM_DEPRECATED,
            "deprecated",
            correlation,
            self._obs.item_deprecated,
        )

    def expire(self, subject_key: str, *, correlation: str = "") -> Knowledge | None:
        """Remove an Item from service by staleness/obsolescence (retained, doc 11)."""
        return self._transition(
            subject_key,
            KnowledgeLifecycle.EXPIRED,
            kevents.KNOWLEDGE_ITEM_EXPIRED,
            "expired",
            correlation,
            self._obs.item_expired,
        )

    def archive(self, subject_key: str, *, correlation: str = "") -> Knowledge | None:
        """Retain an Item immutably, out of service (terminal retention, doc 11)."""
        return self._transition(
            subject_key,
            KnowledgeLifecycle.ARCHIVED,
            kevents.KNOWLEDGE_ITEM_ARCHIVED,
            "archived",
            correlation,
            self._obs.item_archived,
        )

    def record_feedback(
        self,
        subject_key: str,
        *,
        actor: str,
        source_run_ref: Reference,
        effect: str,
        feedback_id: str,
    ) -> Reference:
        """Record attributable operator feedback; contradictory feedback deprecates the Item."""
        if not actor.strip() or not feedback_id.strip():
            raise ValueError("feedback requires actor and stable feedback_id")
        if effect not in {"support", "contradict"}:
            raise ValueError("feedback effect must be 'support' or 'contradict'")
        if self._repos is None or self._repos.items.get(subject_key) is None:
            raise ValueError(f"unknown Knowledge subject {subject_key!r}")
        item = self._repos.items.get(subject_key)
        assert item is not None
        if source_run_ref.target_type != "runtime_session":
            raise ValueError("feedback source_run_ref must identify a runtime session")
        source_refs = (item.metadata or {}).get("source_run_refs", [])
        if (
            isinstance(source_refs, list)
            and source_refs
            and not any(
                isinstance(ref, dict) and ref.get("identifier") == source_run_ref.identifier
                for ref in source_refs
            )
        ):
            raise ValueError("feedback source run is not part of this Knowledge item's provenance")
        feedback_ref = Reference(
            target_type="knowledge_feedback",
            identifier=ids.event_id(feedback_id, "feedback", 0),
        )
        if self._event_reader is not None:
            existing = next(
                (
                    event
                    for event in self._event_reader()
                    if event.identifier == feedback_ref.identifier
                ),
                None,
            )
            if existing is not None:
                expected = {
                    "feedback_id": feedback_id,
                    "subject_key": subject_key,
                    "actor": actor,
                    "source_run_ref": source_run_ref.model_dump(mode="json"),
                    "effect": effect,
                }
                if any(existing.payload.get(key) != value for key, value in expected.items()):
                    raise ValueError("feedback_id already records different feedback")
                return feedback_ref
        metadata = dict(item.metadata or {})
        prior_feedback = metadata.get("feedback_refs", [])
        if not isinstance(prior_feedback, list):
            prior_feedback = []
        metadata["feedback_refs"] = [*prior_feedback, feedback_ref.model_dump(mode="json")]
        updated_item = item.model_copy(update={"metadata": metadata})
        self._repos.items.add(updated_item)
        self._emit(
            feedback_id,
            kevents.KNOWLEDGE_FEEDBACK_RECORDED,
            "feedback",
            0,
            source_run_ref.identifier,
            {
                "feedback_id": feedback_id,
                "subject_key": subject_key,
                "actor": actor,
                "source_run_ref": source_run_ref.model_dump(mode="json"),
                "effect": effect,
                "item_data": updated_item.model_dump(mode="json"),
            },
        )
        if effect == "contradict":
            self.deprecate(subject_key, correlation=source_run_ref.identifier)
        return feedback_ref

    def maintain(self, as_of: str) -> tuple[Knowledge, ...]:
        """A deterministic freshness pass: expire Active Items past the TTL (doc 11).

        Pure function of ``(Items, recorded version timestamps, as_of, policy)`` -- running it
        twice on the same state yields the same transitions. No wall-clock decision.
        """
        ttl = self._policy.freshness_ttl_seconds
        if self._repos is None or ttl is None:
            return ()
        expired: list[Knowledge] = []
        for item in self._repos.items.list_all():
            if lifecycle_of(item) is not KnowledgeLifecycle.ACTIVE:
                continue
            version = self._latest_version(item.identity)
            if version is not None and is_stale(version.timestamp, as_of, ttl):
                transitioned = self.expire(item.identity, correlation=item.correlation_identifier)
                if transitioned is not None:
                    expired.append(transitioned)
        return tuple(expired)

    def _transition(
        self,
        subject_key: str,
        state: KnowledgeLifecycle,
        event_type: str,
        kind: str,
        correlation: str,
        counter: Callable[[], None],
    ) -> Knowledge | None:
        if self._repos is None:
            return None
        item = self._repos.items.get(subject_key)
        if item is None:
            return None
        updated = item.model_copy(update={"freshness": freshness_for(state)})
        self._repos.items.add(updated)
        self._emit(
            f"{subject_key}-{state.value}",
            event_type,
            kind,
            0,
            correlation or item.correlation_identifier,
            {
                "subject_key": subject_key,
                "state": state.value,
                "item_data": updated.model_dump(mode="json"),
            },
        )
        counter()
        return updated

    # -- serve --------------------------------------------------------------- #

    def serve(self, query: KnowledgeQuery) -> tuple[Knowledge, ...]:
        """Read-only retrieval of Active Knowledge (INV-26 boundary; doc 09)."""
        if self._retrieval is None:
            return ()
        return self._retrieval.resolve(query)

    # -- state + persistence ------------------------------------------------- #

    def _subject_state(self, key: str) -> SubjectState:
        if self._repos is None:
            return SubjectState(terminally_rejected=key in self._terminally_rejected)
        item = self._repos.items.get(key)
        latest = self._latest_version(key)
        evidence = (
            frozenset(ref.identifier for ref in latest.evidence_refs) if latest else frozenset()
        )
        return SubjectState(
            item=item,
            latest_version=latest,
            recorded_evidence_ids=evidence,
            terminally_rejected=key in self._terminally_rejected,
        )

    def _latest_version(self, key: str) -> KnowledgeVersion | None:
        assert self._repos is not None  # callers guard; narrows for the type-checker
        candidates = [v for v in self._repos.versions.list_all() if v.subject_key == key]
        if not candidates:
            return None
        return max(candidates, key=lambda v: v.version)

    def _already_ingested(self, candidate: KnowledgeCandidate) -> bool:
        return (
            self._repos is not None and self._repos.candidates.get(candidate.identity) is not None
        )

    def _noop_decision(self, candidate: KnowledgeCandidate, key: str) -> AcceptanceDecision:
        return AcceptanceDecision(
            outcome=KnowledgeDecision.REJECT,
            subject_key=key,
            candidate_id=candidate.identity,
            policy_version=self._policy.version,
            rationale=("idempotent: candidate already ingested (INV-16)",),
            failed_requirement="already_ingested",
        )

    def _persist(
        self, item: Knowledge, version: KnowledgeVersion, candidate: KnowledgeCandidate
    ) -> None:
        if self._repos is None:
            return
        self._repos.versions.add(version)
        self._repos.items.add(item)
        self._record_candidate(candidate)

    def _record_candidate(self, candidate: KnowledgeCandidate) -> None:
        if self._repos is not None:
            self._repos.candidates.add(candidate)

    def _emit(
        self,
        id_scope: str,
        event_type: str,
        kind: str,
        seq: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        identifier = ids.event_id(id_scope, kind, seq)
        self._emitter.emit(
            kevents.build_event(
                identifier, event_type, correlation, payload, self._timestamps.now()
            )
        )
        return seq + 1
