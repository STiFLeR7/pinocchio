# Knowledge Model

Status: Target Architecture (design only)

---

# Purpose

This document freezes the object model of durable Knowledge: the **Knowledge Item**, its
deterministic identity, its versioning, and how items relate. It expands the "Knowledge Objects"
and "Knowledge Relationships" sections of the frozen `../10_KNOWLEDGE.md` into an implementable
shape — without inventing a competing model.

---

# The Knowledge Item

A **Knowledge Item** is the durable unit of operational understanding. Unlike a Candidate (a fixed
proposal), an Item is **mutable only through controlled, versioned evolution** (`10`): every change
is a new immutable version appended to the item's event stream; the current Item is a *projection*
of that stream (ADR-001). History is never rewritten.

| Field | Meaning |
|---|---|
| `identity` | the deterministic Knowledge Subject Key (below) |
| `kind` | the knowledge kind (pattern / decision / lesson / finding / strategy / constraint / capability / relationship / observation — per `../10_KNOWLEDGE.md`) |
| `subject` | the canonical subject the understanding is about |
| `statement` | the current operational understanding (an operational object, not raw text) |
| `confidence` | the current doc-26 level (Experimental / Observed / Validated / Proven) |
| `lifecycle_state` | the current lifecycle state (`06`) |
| `version` | the current version ordinal (monotonic, per item) |
| `provenance` | the accepted candidate refs, source pattern refs, and evidence refs — **by id** |
| `supersedes` / `superseded_by` | relationships to other items (versioning across subjects) |
| `related_refs` | typed links to related items (the operational graph) |
| `first_accepted` / `last_evolved` | recorded timestamps (INV-17, captured-as-data) |
| `freshness` | Current / Historical / Deprecated / Superseded / Archived (`11`) |

An Item references artifacts and evidence **by id and never duplicates their content** (INV-27).

---

# Knowledge Subject Key (deterministic identity)

The Item identity is a **deterministic function of `(kind, canonical_subject)`** — the *Knowledge
Subject Key*. This is the model's keystone: recurring Candidates about the *same* subject resolve
to the *same* Item, which is what makes deduplication and cross-run evolution deterministic.

```
subject_key(kind, subject) = ki-{kind}-{normalized-subject}
```

- The subject is normalised by a fixed, documented canonicalisation (lower-case, trimmed, stable
  token order) so equivalent subjects collide intentionally.
- No clock, no randomness — the same recurring pattern always maps to the same Item across runs.
- A candidate whose subject key matches an existing Item is an **evolution**; a new subject key is
  a **creation**.

Version ids derive from `(subject_key, version_ordinal)`; event ids from `(subject_key, kind,
sequence)` (`07`). All are pure functions of stable identity (INV-16).

---

# Immutable version records

Each accepted change produces an immutable **Knowledge Version** record: `{subject_key, version,
statement, confidence, provenance_added, decided_by_policy, rationale, timestamp}`. The current
Item is the projection of the latest version; the full version chain is the auditable history of
how the understanding evolved (`08`/`10`). A version is never mutated or deleted — supersession and
expiration are new versions/states, not rewrites.

---

# Knowledge kinds

The kinds are those of `../10_KNOWLEDGE.md` (Pattern, Decision, Lesson, Finding, Relationship,
Strategy, Constraint, Capability, Artifact reference, Observation). Reflection's actionable
candidate kinds (repeated failure, bottleneck, retry frequency, repeated success) map onto these
(e.g. a confirmed repeated-failure candidate becomes a **Lesson** or **Anti-Pattern**; a repeated
success becomes a **Pattern**/**Strategy**). The mapping table is fixed at implementation time from
this canon; it introduces no new kinds.

---

# Relationships (the operational graph)

Knowledge is **connected, not isolated** (`../10_KNOWLEDGE.md`). Items carry typed `related_refs`
(e.g. *supersedes*, *contradicts*, *supports*, *derived-from*, *applies-to*). Relationships are
themselves provenance-bearing and are established deterministically during ingestion/evolution
(e.g. a new item that supersedes an older one records the link on both sides). The graph is a
projection over item events; it is never a separate mutable store.

---

# Boundary

The Knowledge Model defines *what durable understanding looks like*. It does **not** define how it
is decided (`04`/`05`), how it changes state (`06`/`10`/`11`), or how it is served (`09`). Those
concerns reference this model but never redefine it.

---

# North Star

One subject, one Item, one auditable version chain. The model makes understanding *addressable*
and *accumulable*: the same lesson learned twice strengthens one Item rather than scattering into
duplicates, and every strengthening is a recorded, reversible step in that item's history.
