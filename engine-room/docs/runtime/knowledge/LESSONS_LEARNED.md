# Knowledge Engine -- Lessons Learned

## Architectural assumptions confirmed

- **The frozen architecture was implementable without a single new decision.** Every doc
  (`docs/v2/knowledge/` 00-14) mapped directly to code; no `ARCHITECTURAL_CONFLICT` was needed. The
  ratification review's answer ("build the core with no new architectural decisions") held.
- **The durable Item already existed.** `nexus_core.domain.Knowledge` -- a frozen contract from
  Phase 1 -- carries exactly the fields doc 03 specifies, down to `evidence_refs` `min_length=1`
  (INV-24), `candidate_ref` (INV-25 provenance), `superseded_by`, and `freshness`/`status`. Doc 03's
  instruction to "not invent a competing model" was literal: the layer's job was to *decide,
  evolve, and project* the existing contract, not redefine it. This is the single biggest reason the
  layer is small (~530 statements).
- **Dependency direction preserved INV-26 for free.** `nexus_knowledge -> {nexus_core, nexus_infra}`
  with candidates consumed by value means no consumer can reach Reflection through Knowledge. The
  guardrail is a source-substring assertion -- crude but effective; it caught an early docstring that
  merely *mentioned* the Reflection package name.
- **The Phase 2 substrate absorbed the layer unchanged.** Event store, repositories (including the
  pre-built `KnowledgeRepository`), observability, unit-of-work, and the injected `TimestampSource`
  needed no modification -- the fourth engine in a row to reuse them verbatim.

## Engineering refinements

- **The G9 candidate-ownership choice was made in favour of boundary adaptation.** Rather than
  promote the candidate to a shared `nexus_core` contract, the layer defines its own
  `KnowledgeCandidate` and the orchestrating caller adapts a Reflection candidate by value. This
  keeps the dependency graph strictly acyclic and left Reflection untouched.
- **Event id scoping by candidate identity, not subject key.** The first cut keyed ingest events by
  `(subject_key, seq)`; the second ingest of the same subject re-emitted a colliding id and the
  event store (correctly) rejected it. Doc 07 already allowed keying by *candidate identity*, which
  is unique per ingest -- the fix was a one-line scope change, and it is the right canonical choice.
- **Lifecycle projects onto `Freshness`, and Expired -> HISTORICAL.** The core `Freshness` enum has
  no `expired` member; mapping doc-06 Expired onto `HISTORICAL` (true-but-aged, not served) kept the
  full lifecycle expressible without touching a frozen enum -- a good example of projecting a rich
  design onto a constrained vocabulary instead of widening the vocabulary.
- **Confidence promotion reused Reflection's count ladder.** `confidence_for` is the same
  count-derived mapping Reflection uses, keeping "the same lesson learned N times" deterministic and
  consistent across the two layers.
- **Serving threshold via a predicate, not a state.** The core `KnowledgeIngestionStatus` has no
  `ACTIVE`; the Accepted -> Active distinction is modelled as a query-time predicate
  (`is_served`) rather than an invented status -- less state, same behaviour.

## Future extension points (named, non-blocking)

Inherited from `docs/v2/knowledge/14_KNOWLEDGE_GAPS.md`, unchanged by implementation:

- **Memory** -- a separate subsystem Knowledge references rather than embeds (INV-27); the ingestion
  boundary is generic enough to admit it.
- **External / non-Reflection ingestion & Research** -- the `KnowledgeCandidate` contract already
  carries generic provenance fields; a future adapter can supply candidates from other validated
  sources without touching the Acceptance Engine.
- **Semantic retrieval** -- `KnowledgeRetrieval` is deterministic subject/kind/confidence filtering
  today; embedding-based similarity is a future, clearly-marked non-deterministic addition.
- **Retention & compaction at scale** -- archival is a state; log compaction/snapshot policy for
  very large knowledge bases is deferred (the event model already supports snapshots).
- **Richer confidence & conflict handling** -- context-scoped truth and confidence-weighted
  coexistence would attach at subject-key canonicalisation; the current model handles contradiction
  via deprecation/supersession.

None require reopening the frozen core; each is a defined seam.
