# Knowledge Events

Status: Target Architecture (design only)

---

# Purpose

This document freezes the canonical `knowledge.*` event taxonomy. Knowledge is **event-sourced**
(ADR-001): the durable Knowledge Item and its lifecycle state are *projections* of an append-only
`knowledge.*` stream. The events are the authoritative record; they are the audit; they are what
makes acceptance and evolution replayable. This document **names and shapes** the events; it does
**not** implement them.

---

# Reserved namespace

The `knowledge.*` namespace is reserved for the Knowledge Engine, alongside the existing reserved
namespaces (`runtime.*`, `validation.*`, `recovery.*`, `reflection.*`). Following the established
convention, Knowledge event identifiers carry a **`know` marker** so they never collide with other
producers in the shared, correlated event store (e.g. `evt-{subject_key}-know-{kind}-{seq}`).

- **Producer:** `knowledge`  **Source:** `nexus_knowledge`
- **Ids:** deterministic, pure functions of `(subject_key | candidate identity, kind, sequence)`
  (INV-16) — no clock, no randomness.
- **Timestamps:** recorded as data on the event (INV-17); injected source.
- **Correlation:** each event carries the operation lineage it derives from (INV-39), threaded from
  the candidate's `correlation_identifier`.

---

# The canonical taxonomy

## Ingestion

| Event | Emitted when |
|---|---|
| `knowledge.candidate_received` | a candidate enters the ingest pipeline (before any decision) |
| `knowledge.candidate_accepted` | acceptance succeeds (accompanies a create/evolve) |
| `knowledge.candidate_rejected` | acceptance fails policy — carries the failed requirement (INV-31) |

## Item lifecycle

| Event | Emitted when |
|---|---|
| `knowledge.item_created` | a new Knowledge Item is created (first accepted version) |
| `knowledge.item_evolved` | a new version is appended (evolve or merge: evidence/confidence advance) |
| `knowledge.item_superseded` | a superseding relationship is recorded between two Items |
| `knowledge.item_deprecated` | an Item is withheld from default serving |
| `knowledge.item_expired` | a freshness rule removes an Item from service (`11`) |
| `knowledge.item_archived` | an Item is retained immutably, out of service |

## Serving (optional, governed by observability policy)

| Event | Emitted when |
|---|---|
| `knowledge.item_served` | a consumer retrieval resolves Items (for consumption audit; may be sampled) |

Serving events are **read-only-safe**: emitting them changes no Knowledge state (a retrieval never
mutates an Item). They exist for consumption observability (`12`) and may be disabled without
affecting correctness.

---

# Payloads (shape, not schema)

Each event carries the minimal, deterministic descriptor for its fact — e.g. `candidate_rejected`
carries `{candidate_id, subject_key, failed_requirement, policy_version}`; `item_evolved` carries
`{subject_key, from_version, to_version, confidence_from, confidence_to, evidence_added}`. Payloads
reference artifacts/evidence **by id and never embed content** (INV-27). No payload contains a
secret, raw log, or artifact body.

---

# Projection

The current Knowledge Item, its version chain, its lifecycle state, and its freshness are all
**projections** over this stream. Duplicate or out-of-order delivery is idempotent (INV-16):
projections dedupe by event identifier. Rebuilding Knowledge from the log reproduces byte-identical
Items — the guarantee that underpins auditability and replay.

---

# Boundary

Knowledge events record *decisions about understanding*. They never carry execution, validation, or
recovery facts (those live in their own namespaces), and Knowledge never emits into another
producer's namespace. Consumers observe Knowledge through retrieval (`09`), not by subscribing to
mutate it.

---

# North Star

Every piece of understanding Nexus holds can be traced, event by event, from the candidate that
proposed it to the version it is today. The `knowledge.*` stream is that unbroken record.
