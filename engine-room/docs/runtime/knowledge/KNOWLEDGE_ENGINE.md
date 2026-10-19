# Knowledge Engine -- Implementation

Implements the frozen architecture in `docs/v2/knowledge/` as the `nexus_knowledge` package. The
Knowledge Engine is the deterministic gate between *proposed* understanding (advisory Knowledge
Candidates) and *durable* understanding (Knowledge Items), and the read-only source of that
understanding for consumers.

## Package shape

```
nexus_knowledge/
  vocabulary.py     KnowledgeDecision, KnowledgeLifecycle, DuplicateStrategy, rejection reasons, target-types
  ids.py            Knowledge Subject Key + version/event id derivation (deterministic)
  candidate.py      KnowledgeCandidate -- the by-value boundary contract (doc 02)
  policy.py         PersistencePolicy + confidence ladder helpers + count-derived promotion (doc 04)
  model.py          KnowledgeVersion (version chain) + build_item projection (doc 03)
  acceptance.py     AcceptanceEngine + AcceptanceDecision -- the pure decision function (doc 05)
  evolution.py      EvolutionEngine -- versioning / accumulation / supersession (doc 10)
  lifecycle.py      deterministic transitions projected onto Freshness / status (doc 06/11)
  retrieval.py      KnowledgeQuery + KnowledgeRetrieval -- read-only serve (doc 09)
  events.py         knowledge.* taxonomy + build_event (doc 07)
  observability.py  derived counters over the Phase 2 sink (doc 12)
  persistence.py    KnowledgeRepositories (items / versions / candidates), Phase 2 reused (Milestone 7)
  engine.py         KnowledgeEngine -- ingest / serve / deprecate / expire / archive / maintain
  composition.py    build_knowledge(infrastructure, ...) DI wiring
```

## The durable Item is the frozen core contract

The single most important implementation decision: **the Knowledge Item is
`nexus_core.domain.Knowledge`**, the existing frozen contract -- not a new value object. Doc 03
mandates "an implementable shape without inventing a competing model", and the core contract already
carries every field the design names (`identity`, `type`, `understanding`, `evidence_refs`
(`min_length=1`), `confidence`, `freshness`, `status`, `relationships`, `candidate_ref`,
`superseded_by`, `rationale`, `source`). The layer therefore:

- uses the pre-built `nexus_infra.KnowledgeRepository` for Items;
- adds only what the core contract lacks -- an explicit **version chain** (`KnowledgeVersion`) --
  as a layer value object, because the core contract has no version ordinal.

The core contract's `evidence_refs` `min_length=1` is satisfied structurally because acceptance
requires `minimum_evidence >= 1`, so an Item can never be created without validated evidence
(INV-24).

## The two operations

`KnowledgeEngine.ingest(candidate) -> IngestOutcome` and `serve(query) -> tuple[Knowledge, ...]`
(doc 01). Neither runs inline with an execution. `ingest`:

```
subject_key = ids.subject_key(candidate.kind, candidate.subject)
idempotency guard  (candidate already ingested -> no-op, INV-16)
emit knowledge.candidate_received
state  = SubjectState from repositories (current Item + latest version + recorded evidence ids)
decision = AcceptanceEngine.evaluate(candidate, state, policy, subject_key)
  reject -> emit candidate_rejected (failed requirement)   [+ terminal block if configured]
  accept -> EvolutionEngine builds the version; project the Item; persist;
            emit candidate_accepted + item_created|item_evolved [+ item_superseded]
```

`serve` delegates to `KnowledgeRetrieval` (Active by default, side-effect-free).

## Determinism

No clock in any decision path (timestamps injected via the reused `TimestampSource`, INV-17); no
randomness; no learned/AI scoring. Identical `(candidate, existing state, policy)` yields an
identical decision, Item version, and event stream -- proven by
`test_two_runs_produce_identical_items_and_events` and the integration determinism test.

## Boundaries (enforced)

`nexus_knowledge -> {nexus_core, nexus_infra}` only. It imports no upstream layer (not Reflection);
candidates cross the boundary **by value**. The integration guardrail
`test_knowledge_imports_no_reflection` asserts this over the package source, so INV-26 holds by
construction. The Engine never executes, analyses, validates, retries, recovers, or evaluates
governance policy (INV-25/INV-26/INV-28).
