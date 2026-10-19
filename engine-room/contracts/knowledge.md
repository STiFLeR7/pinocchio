# Contract — Knowledge Entry

Status: Frozen (Phase 0 contract freeze)
Object: Knowledge Entry
Primary source: `docs/v2/10_KNOWLEDGE.md`
Binding ADRs: ADR-001 (event-sourced state; knowledge from authoritative log),
ADR-003 (canonical object model; reflection produces candidates)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Knowledge Entry is a unit of **persistent operational understanding** — accumulated
operational intelligence that improves planning, context engineering, supervision, and
future execution. Unlike Memory (which records information), Knowledge **explains**: it
captures *what was learned* and *why an outcome occurred*, expressed as an operational
object rather than raw text (doc 10 *Purpose*, *Relationship with Memory*,
*Knowledge Objects*).

It does **one job**: hold a single, **evidence-backed** piece of operational
understanding so that future operations begin with greater understanding than the last.
A Knowledge Entry is **never** created from assumptions or unvalidated execution — only
validated outcomes become Knowledge (INV-24; doc 10 *Evidence Driven*). Knowledge never
performs execution, never creates plans, never validates, and never supervises (doc 10
*Architectural Boundaries*).

Knowledge Entries are **connected**, forming an **operational graph** of understanding,
not isolated records (doc 10 *Knowledge Relationships*).

---

## 2. Ownership

- **Produced by / owned by:** the **Knowledge System** exclusively. It decides what
  becomes persistent operational understanding; it is the only producer and the only
  owner of Knowledge Entry state transitions (doc 10 *Relationship with Reflection*).
- **Ingestion source:** Knowledge Entries are *created from* **Knowledge Candidates**
  produced by Reflection (`reflection.md`), and may also originate from Validation,
  documentation, research, operator decisions, architecture, and external systems
  (doc 10 *Sources*) — but in every case the entry must be evidence-backed (INV-24).
  **Reflection never writes Knowledge directly** (INV-25); it proposes candidates that
  Knowledge accepts or rejects.
- **Ingestion is validation-gated.** An incoming candidate becomes a Knowledge Entry
  only after validation gating; unvalidated understanding is rejected (doc 10
  *Validation*; INV-24, enforced at AP-602).
- **Consumed by (read-only):** Context Engineering and Planning consume Knowledge;
  neither owns it (INV-06; Knowledge is read-only to Context). **Planning consumes
  Knowledge, never Reflection directly** (INV-26).
- A Knowledge Entry carries **no** provider/runtime/health state (ADR-002) and defines
  **no** independent authoritative store — its current state is a projection of the
  event log (INV-13/14).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14). Every transition emits
exactly one event (INV-15). A Knowledge Entry has two orthogonal axes — an **ingestion
lifecycle** and a **freshness lifecycle** — plus a **confidence ladder**.

**Ingestion lifecycle** (how an entry comes to exist and persist):

- **Candidate** — proposed (from Reflection or another source) but not yet admitted;
  owned by the proposing source, advisory only.
- **Validating** — the Knowledge System is gating the candidate against its supporting
  evidence (validation-gated ingestion).
- **Accepted** — admitted as a persistent Knowledge Entry; now an active node in the
  operational graph.
- **Rejected** — failed validation gating (e.g., insufficient evidence); does not become
  Knowledge. Terminal.

**Freshness lifecycle** of an Accepted entry (doc 10 *Freshness*): **Current →
Historical → Deprecated → Archived → Superseded**. Planning should prefer **Current**
knowledge (doc 10 *Freshness*). `Superseded` references the entry that replaced it.

**Confidence ladder** (doc 10 *Validation*; shared with `reflection.md`):
**Experimental → Observed → Validated → Proven**. Confidence may rise as repeated
evidence accrues (doc 10 *Evolution*). Planning may choose strategies based on
confidence.

---

## 4. Required Fields

- **identity** — stable, unique identifier for this Knowledge Entry; addressable and
  replayable for the life of the platform; a stable node id in the operational graph.
- **correlation** — correlation / trace lineage tying the entry to the operations and
  evidence it was derived from, so its provenance is auditable end to end.
- **type** — the Knowledge object type (doc 10 *Knowledge Objects*): one of `Pattern`,
  `Decision`, `Lesson`, `Finding`, `Relationship`, `Strategy`, `Constraint`,
  `Capability`, `Artifact-ref`, `Observation-ref`. Understanding is represented through
  these operational objects, not raw text.
- **understanding** — the operational understanding the entry asserts (the explanation /
  insight / pattern / lesson). This is the substance: it explains, it does not merely
  record (doc 10 *Relationship with Memory*).
- **evidence_refs** — references (by id) to the validated evidence and validated
  outcomes that back this entry. **Required and non-empty** — Knowledge is evidence-
  backed (INV-24); an entry with no supporting evidence cannot exist.
- **confidence** — the entry's place on the confidence ladder (Experimental / Observed /
  Validated / Proven — doc 10 *Validation*). Derived from supporting evidence.
- **freshness** — the entry's freshness state (Current / Historical / Deprecated /
  Archived / Superseded — doc 10 *Freshness*). Derived, never authoritative.
- **status** — the projected ingestion-lifecycle state (§3). Derived, never
  authoritative.

---

## 5. Optional Fields

- **category** — the knowledge category (Repository / Workspace / Skill / Operational /
  Organizational / Personal — doc 10 *Categories*), used for retrieval scoping.
- **domain** — operational domain the understanding applies to (Software, Research,
  Documentation, Planning, Business, Personal, …); Knowledge is domain-agnostic by
  design (doc 10 *Domain Agnostic*), so this scopes rather than restricts.
- **relationships** — typed edges to other Knowledge Entries (and to referenced objects),
  forming the operational graph (doc 10 *Knowledge Relationships*). Edges express how
  understanding connects (e.g., repository → architecture → module → observation →
  knowledge).
- **artifact_refs** — references (by id) to Artifacts the understanding concerns.
  Knowledge **references** Artifacts and **never duplicates their content** (INV-27;
  doc 10 implied by *Knowledge Objects* `Artifact`).
- **observation_refs** — references (by id) to Supervision Observations that informed the
  understanding (the `Observation-ref` object type).
- **source** — provenance of the understanding (Execution / Reflection / Validation /
  Documentation / Research / Operator Decisions / Architecture / External Systems —
  doc 10 *Sources*).
- **candidate_ref** — reference (by id) to the originating Knowledge Candidate produced
  by Reflection (`reflection.md`), preserving the candidate→entry provenance chain.
- **superseded_by** — reference (by id) to the Knowledge Entry that replaced this one
  when freshness is `Superseded`.
- **rationale** — explanation of why this understanding is held and how the evidence
  supports it (explainability).
- **applicability** — conditions under which the understanding is relevant (helps
  retrieval answer "what operational understanding is relevant now?" — doc 10
  *Retrieval*).
- **metadata** — non-behavioral descriptive attributes (tags, ownership notes) that do
  not affect the understanding.

---

## 6. Invariants

- **INV-24 — Evidence-backed.** Only validated outcomes become Knowledge; an entry
  **never** originates from assumptions or unvalidated execution. `evidence_refs` is
  required and non-empty. Ingestion is validation-gated (doc 10 *Evidence Driven*,
  *Validation*).
- **INV-25 — Reflection never writes Knowledge directly.** Knowledge Entries derive from
  **Knowledge Candidates**; the Knowledge System alone decides persistence
  (`Candidate → Accepted`). Reflection output is advisory until Knowledge accepts.
- **INV-26 — Planning depends on Knowledge, not Reflection.** Learning reaches Planning
  only indirectly, through persisted Knowledge; no Knowledge field exposes a direct
  Reflection dependency for Planning.
- **INV-27 — References, never duplicates.** Knowledge references Artifacts (and
  Observations, Evidence) by id; it never copies their content into the entry.
- **INV-06.** Knowledge is read-only to Context Engineering; Context consumes but never
  owns Knowledge.
- **INV-07.** Exactly one canonical schema for a Knowledge Entry; no subsystem
  introduces an alternative representation of operational understanding (distinct from
  Memory, which records information — doc 10 *Relationship with Memory*).
- **INV-13 / INV-14.** The entry's current state, freshness, and confidence are derived
  projections of the append-only event log; nothing not in the log is true.
- **INV-15.** Every Knowledge Entry state transition (ingestion and freshness) emits
  exactly one event.
- **INV-31 (explainable & auditable).** Each entry's provenance — its evidence, source,
  and confidence basis — is reconstructable from log data.
- **Confidence is earned.** An entry's confidence reflects its supporting evidence and
  may rise only as repeated validated evidence accrues (doc 10 *Evolution*); it is never
  asserted without evidence.
- **Graph integrity.** `relationships`, `superseded_by`, `artifact_refs`,
  `observation_refs`, `evidence_refs`, and `candidate_ref` reference objects by id;
  Knowledge forms a graph of references, not nested copies.
- **Provider independence (ADR-002).** No provider/runtime/health state is embedded.

---

## 7. Relationships

- **Ingested from →** `reflection.md` Knowledge Candidates (`candidate_ref`). Reflection
  proposes; Knowledge disposes (INV-25). May also ingest from Validation, documentation,
  research, operator decisions, architecture, and external systems (doc 10 *Sources*).
- **References →** `artifact.md` (`artifact_refs`, never duplicated — INV-27),
  Observations (`observation_refs`), and Evidence (`evidence_refs`, the validated basis).
- **Consumed by →** Context Engineering (read-only — INV-06) and Planning. Planning
  consumes Knowledge and **never depends directly on Reflection** (INV-26). Also serves
  Skill Selection, Supervision, and Reflection retrieval (doc 10 *Retrieval*).
- **References →** `policy.md` when a `Constraint`-type entry captures understood
  organizational policy (by reference, never duplicated).
- **Connected to →** other Knowledge Entries via `relationships`, forming the operational
  graph; `superseded_by` links an entry to its replacement.
- **Distinct from Memory.** Memory records information; Knowledge stores understanding —
  they are separate concepts and are never merged (doc 10 *Relationship with Memory*;
  INV-07).

---

## 8. Versioning Rules

- **Additive evolution only.** New optional fields (e.g., richer graph edge types,
  confidence-scoring metadata, semantic-graph attributes — doc 10 *Future Evolution*)
  may be added without breaking existing consumers.
- **Supersession, not mutation.** Understanding evolves by **freshness transition** and
  **supersession** (a new entry marked `superseded_by` ← prior), never by overwriting an
  Accepted entry's asserted understanding in place. The historical entry remains
  addressable and replayable (ADR-001 append-only).
- **Confidence and freshness are state, not edits.** Changes to `confidence` and
  `freshness` are recorded transitions (events), not in-place field rewrites.
- **Evidence backing is permanent.** A field change that would let an entry exist without
  non-empty `evidence_refs` is forbidden and would require superseding the INV-24
  decision.
- **Required fields are stable.** Promoting an optional field to required, or removing
  any field, requires a new object version (and an ADR if it alters the evidence-backing
  or candidate-gating semantics). Old entries remain replayable under their original
  version via upcasting.
