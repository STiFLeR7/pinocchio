# Contract — Artifact

Status: Frozen (Phase 0 contract freeze)
Object: Artifact
Primary source: `docs/v2/17_ARTIFACT_MODEL.md`
Binding ADRs: ADR-003 (canonical object model — §3.7 one status vocabulary, Evidence by reference), ADR-001 (event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

An Artifact is the **common, persistent representation of an operational output**
produced, consumed, or transformed across Nexus. Execution creates outputs,
Validation evaluates them, Knowledge preserves them, and Planning may reuse them —
the Artifact is the single shared object that lets every subsystem refer to a work
product without inventing its own representation (doc 17 *Why Artifacts Exist*).

The Artifact does **one job**: be the durable, traceable, immutable-by-default record
of a produced output, with explicit lineage from Goal through Knowledge. It is
**immutable by default** (a new revision is a new version, never an overwrite — doc 17
*Immutable by Default*; INV-12) and it **references Evidence by id**, never embedding
it (ADR-003 §3.7). An Artifact never performs execution, validates itself, stores
operational knowledge, or creates plans (doc 17 *Architectural Boundaries*).

---

## 2. Ownership

- **Produced by:** the producing layer of the output — most often **Execution**, but
  also Planning, Knowledge, Reflection, human operators, or external systems (doc 17
  *Artifact Ownership*). The `producer` field records which one.
- **Status transitions owned by:** the lifecycle is advanced by the layer responsible
  for each stage — Execution produces (Draft → Generated); **Validation** decides
  Validated (it determines operational trust — doc 17 *Validation*); publication/
  archival are governed operational transitions. **Validation is the only producer of
  Evidence** (INV-12); the Artifact merely references it.
- **Owner field.** `owner` is explicit and persists throughout the lifecycle (doc 17
  *Artifact Ownership*), distinct from the original `producer`.
- Per the cross-cutting rules, the Artifact carries **no** provider/runtime/health state
  (ADR-002) and defines no independent authoritative state store — its current status is
  a projection of the event log (ADR-001; INV-14).

---

## 3. Lifecycle

There is **one** Artifact status vocabulary (ADR-003 §3.7); the `Created → Produced →
Validated → Versioned → Referenced → Archived` phrasing in doc 17 is descriptive
narrative, **not a second enum**. State is a projection of the event log (ADR-001;
INV-14), and each transition emits exactly one Event (INV-15). The canonical status
lifecycle:

- **Draft** — an output is being formed; not yet a complete operational asset.
- **Generated** — the output is produced and addressable, but not yet trusted.
- **Validated** — Validation has evaluated it against Evidence and granted operational
  trust (doc 17 *Validation*).
- **Published** — the validated Artifact is released as a durable operational asset
  available for reference and reuse.
- **Archived** — retained for lineage/audit; superseded or retired but never deleted in
  a way that breaks traceability.

Allowed progression is forward through these states; a new revision does **not**
overwrite — it creates a new Artifact **version** (a new immutable record in the
version chain). Non-deterministic content captured during production is recorded as
data, never recomputed on replay (INV-17).

---

## 4. Required Fields

- **identity** — stable, unique Artifact identifier; addressable for discovery,
  reference, and lineage (doc 17 *Discovery*).
- **type** — the artifact category/kind (e.g. source, documentation, research,
  operational, communication, knowledge — doc 17 *Artifact Categories*).
- **owner** — the layer/operator that owns this Artifact throughout its lifecycle.
- **producer** — the layer/runtime/operator that originally produced it.
- **created_time** — when the Artifact was first created; recorded as data (INV-17).
- **updated_time** — when this version was last advanced.
- **version** — this Artifact's version within its immutable version chain (doc 17
  *Versioning*).
- **status** — the single canonical status (§3): Draft / Generated / Validated /
  Published / Archived. Derived projection, never authoritative.
- **lineage** — the operational provenance chain Goal → Plan → Work Package →
  Execution → Artifact → Knowledge (doc 17 *Artifact Lineage*), by reference. Enables
  complete traceability.
- **correlation_identifier** — correlation/trace lineage shared with the producing
  operation's Events, making the Artifact auditable end to end.

---

## 5. Optional Fields

- **workspace** — the operational workspace/context the Artifact belongs to (doc 17
  *Discovery*).
- **metadata** — descriptive attributes and tags supporting discovery and reuse
  (doc 17 *Discovery*).
- **evidence_ref** — reference(s) **by id** to the Evidence (owned by Validation) that
  supports this Artifact's Validated status. The Artifact **references** Evidence and
  **never embeds** an Evidence object (ADR-003 §3.7; INV-12). Present once evidence
  exists.
- **references** — references to related objects the Artifact draws on or relates to:
  `goal.md`, `plan.md`, `work_package.md`, `skill.md`, execution sessions,
  `knowledge.md`, `policy.md`, and other Artifacts (doc 17 *Artifact Relationships*).
- **parent_version** — reference to the prior version in the immutable version chain.
- **change_summary** — for a new version, the summary of what changed, with creator,
  timestamp, and originating execution (doc 17 *Versioning*). Each version preserves its
  own provenance and never overwrites a previous one.
- **source** — provenance when the Artifact originates outside Execution (human
  operator, external system).

---

## 6. Invariants

- **INV-12.** The Artifact **references Evidence by id and never embeds it**. Evidence is
  a first-class object produced only by Validation; Execution produces only Evidence
  Candidates (ADR-003 §3.7, §3.8).
- **One status vocabulary (ADR-003 §3.7).** Exactly one status lifecycle (Draft →
  Generated → Validated → Published → Archived); no subsystem introduces a second status
  or lifecycle enum (INV-07).
- **Immutable by default.** A produced Artifact is never modified in place; a revision
  creates a new version. Version history never overwrites previous versions (doc 17
  *Immutable by Default* / *Versioning*).
- **INV-27.** Knowledge **references** Artifacts and never duplicates their content;
  Artifacts remain the authoritative operational outputs (doc 17 *Relationship with
  Knowledge*).
- **INV-13 / INV-14.** Current status is a projection of the append-only Event Log;
  nothing not in the log is true.
- **INV-15.** Each Artifact status transition (creation, validation, publication,
  versioning, archival) emits exactly one Event.
- **Trust from Evidence (INV-20).** An Artifact becomes Validated only on independently
  verifiable Evidence, never on runtime self-report.
- **Provider independence (ADR-002).** No provider/runtime/health state is embedded.

---

## 7. Relationships

- **Produced by →** Execution (primarily), and Planning / Knowledge / Reflection /
  operators / external systems. Production and each transition are recorded as
  `event.md` instances.
- **References →** `goal.md`, `plan.md`, `work_package.md`, `skill.md`,
  `knowledge.md`, `policy.md`, execution sessions, and other Artifacts (doc 17
  *Artifact Relationships*). **References (by id) →** Evidence (owned by Validation) via
  `evidence_ref` — never embedded.
- **Referenced by:** `checkpoint.md` (artifacts produced so far, by reference);
  `knowledge.md` (Knowledge references, never duplicates — INV-27);
  `context_package.md` (Context Packages may include Artifacts as reusable context —
  doc 17 *Relationship with Context Engineering*).
- **Evaluated by:** Validation, which grants the Validated status and owns the Evidence
  the Artifact references (validation and the artifact stay distinct objects).
- **Correlation lineage:** shares `correlation_identifier` and the Goal→…→Knowledge
  lineage chain, giving complete operational traceability.

---

## 8. Versioning Rules

- **New version, never overwrite.** Every revision is a new immutable Artifact version
  preserving creator, timestamp, change summary, and originating execution; prior
  versions are retained (doc 17 *Versioning*; INV-12).
- **Additive evolution only.** New optional fields (e.g. semantic-graph links,
  similarity/recommendation metadata — doc 17 *Future Evolution*) may be added without
  breaking existing consumers.
- **Status vocabulary is fixed.** Adding, renaming, or splitting a status value requires
  an ADR superseding ADR-003 §3.7; no subsystem may introduce a parallel status set.
- **Required fields are stable.** Promoting an optional field to required, or removing a
  field, requires a new object version. Old Artifacts remain readable/replayable via
  upcasting (ADR-001 §6).
- **Determinism preserved.** Any new field influencing validation or lineage must be
  captured as recorded data so replay stays deterministic (INV-17).
