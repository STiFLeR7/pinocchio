# Contract — Checkpoint

Status: Frozen (Phase 0 contract freeze)
Object: Checkpoint
Primary source: `docs/v2/25_CHECKPOINT_MODEL.md`
Binding ADRs: ADR-001 (event-sourced state — Checkpoint is derived, never authoritative)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Checkpoint is a **derived, reference-not-copy snapshot** of execution-relevant
state at a specific position in the authoritative Event Log. It exists so that
long-running operations can resume from interruption without repeating completed
work: Recovery restores the nearest valid Checkpoint and **replays the event tail**
from the log position the Checkpoint records (ADR-001 §3.3; INV-18).

The Checkpoint does **one job**: bound replay cost by capturing *where* an execution
was and *what it referenced*, so recovery is fast and exact. It is **not an
independent source of truth** (INV-14) — it can always be regenerated from the log.
It references persistent operational objects rather than duplicating them (doc 25
*What a Checkpoint Does NOT Contain*). A Checkpoint never performs execution, creates
plans, or validates outcomes (doc 25 *Architectural Boundaries*).

---

## 2. Ownership

- **Produced by:** the **Execution** layer, during long-running work (doc 25
  *Relationship with Execution*: "Execution creates checkpoints. Execution never
  restores checkpoints."). Checkpoint creation emits a Checkpoint Created Event.
- **Restored by:** the **Recovery** layer. Recovery restores Checkpoints but never
  defines their structure (doc 25 *Relationship with Recovery*).
- **Owned by (as a record):** the materialized checkpoint store (AP-204), which is a
  snapshot of projected state, not a third authoritative store (ADR-001 §3.3).
- Per the cross-cutting rules, a Checkpoint captures **operational** state only — never
  runtime-specific implementation details (doc 25 *Runtime Independent*) and no
  provider/health state (ADR-002). Its current existence and validity are themselves a
  projection of Checkpoint Events in the log (INV-14).

---

## 3. Lifecycle

A Checkpoint is an immutable snapshot; subsequent execution creates *new* Checkpoints
rather than mutating one (doc 25 *Immutable*). State is a projection of the event log
(ADR-001; INV-14), and each transition below corresponds to exactly one Event
(INV-15). The logical stages (doc 25 *Checkpoint Lifecycle*):

- **Created** — a snapshot of execution-relevant projected state is captured at a log
  position.
- **Persisted** — the snapshot is durably recorded.
- **Available** — the Checkpoint is eligible for restoration (subject to validation).
- **Restored** — Recovery has restored from it and replays the event tail from its
  recorded log position.
- **Superseded** — a later Checkpoint for the same execution has been created; this one
  is no longer the nearest valid restore point.
- **Archived** — retained for audit/lineage; still regenerable from the log.

Restoration is gated by **pre-restore validation** (§6): a Checkpoint that fails
integrity, artifact-availability, context-validity, graph-compatibility, or
policy-compatibility checks must never be restored (doc 25 *Checkpoint Validation*).

---

## 4. Required Fields

- **identifier** — stable, unique Checkpoint identity, addressable for restoration and
  audit (doc 25 *Checkpoint Versioning*).
- **execution_identifier** — the execution session this Checkpoint belongs to.
- **log_position** — the Event Log sequence/position the Checkpoint corresponds to;
  the anchor from which Recovery replays the event tail (ADR-001 §3.3). This is what
  makes the Checkpoint a derived snapshot rather than an independent store.
- **timestamp** — when the Checkpoint was created; recorded as data (INV-17).
- **execution_state** — the projected execution state captured at this point (a
  reference to / value of the projected lifecycle state, not a re-derivation).
- **current_work_package** — reference (by id) to the Work Package in progress at the
  checkpoint (`work_package.md`).
- **execution_graph_position** — reference to the current Execution Graph and current
  node within it (`execution_graph.md`; doc 25 *Relationship with Execution Graph*).
- **completed_nodes** — the set of Execution Graph nodes already completed at this
  position (by reference), so completed work is not repeated.
- **pending_nodes** — the set of nodes still to execute (by reference).
- **context_references** — references (by id) to the validated Context Package(s) in
  effect (`context_package.md`); never embedded copies.
- **artifacts_produced** — references (by id) to Artifacts produced so far
  (`artifact.md`); references only, never the artifact contents (doc 25 *What a
  Checkpoint Does NOT Contain*).
- **evidence_collected** — references (by id) to Evidence Candidates / Evidence
  gathered so far; references only.
- **correlation_identifier** — correlation/trace lineage shared with the operation's
  Events (doc 25 *Checkpoint Metadata*).

---

## 5. Optional Fields

- **parent_checkpoint** — reference to the prior Checkpoint in this execution's chain,
  enabling deterministic, ordered restoration (doc 25 *Checkpoint Versioning*).
- **version** — Checkpoint version marker for the chain.
- **checkpoint_type** — the captured concern (Execution, Workflow, Context, Validation,
  or Recovery checkpoint — doc 25 *Checkpoint Types*).
- **recovery_metadata** — recovery-specific hints: retry context, failure context, and
  the policy-compatibility data Recovery needs to decide continuation.
- **execution_metadata** — auditing context (doc 25 *Checkpoint Metadata*): goal, plan,
  work package, execution strategy, runtime, creator. Carried by reference; provider
  details stay in the Harness Registry (ADR-002).
- **synchronization_state** — graph synchronization/barrier state at the checkpoint, for
  resuming parallel/coordinated execution (doc 25 *Relationship with Execution Graph*).
- **validation_status** — result of the most recent pre-restore validation, when
  recorded (integrity / artifact availability / context validity / graph compatibility
  / policy compatibility).

---

## 6. Invariants

- **INV-14.** A Checkpoint is **derived, never authoritative**. It is a snapshot tied to
  a `log_position` and is rebuildable from the Event Log; it is not a third source of
  truth.
- **INV-18.** Every execution is checkpoint-aware: long-running work resumes from the
  nearest valid Checkpoint plus event-tail replay — **never from operator intent or the
  Goal** (doc 25 *Recoverable*; INV-22).
- **INV-15.** Checkpoint creation, validation, restoration, and archival each emit
  exactly one Event (doc 25 *Relationship with Events*).
- **Reference-not-copy.** A Checkpoint references persistent objects (Artifacts,
  Context, Evidence, Graph) by id and never duplicates Knowledge, repository contents,
  large artifacts, operator history, or long-term memory (doc 25 *What a Checkpoint Does
  NOT Contain*).
- **Immutability.** A Checkpoint is an immutable snapshot; new progress creates new
  Checkpoints, never edits an existing one.
- **Pre-restore validation mandatory.** An invalid Checkpoint is never restored;
  restoration requires passing integrity, artifact-availability, context-validity,
  graph-compatibility, and policy-compatibility checks (doc 25 *Checkpoint Validation*).
- **Determinism (INV-17).** Restoration + tail replay reproduces governed outcomes
  without re-inference; captured non-deterministic values are not recomputed.
- **Runtime independence.** Captures operational state only, never runtime-specific
  implementation details (doc 25 *Runtime Independent*; ADR-002).

---

## 7. Relationships

- **Derived from →** `event.md`. A Checkpoint snapshots projected state at a log
  position; the authoritative facts live in the Event Log (ADR-001).
- **References →** `work_package.md` (current WP), `execution_graph.md` (position,
  completed/pending nodes), `context_package.md` (context refs), `artifact.md`
  (artifacts produced, by ref), and Evidence/Evidence-Candidate objects (evidence
  collected, by ref).
- **Created by:** Execution (emits Checkpoint Created). **Restored by:** Recovery
  (restore nearest valid Checkpoint → replay tail).
- **Consumed by:** Recovery (restoration), Supervision (Checkpoint History is an input
  to health derivation — doc 09 *Inputs* / *Observation Model*; feeds `observation.md`),
  and Knowledge (may *reference* a Checkpoint but never stores its state — doc 25
  *Relationship with Knowledge*; INV-27).
- **Correlation lineage:** shares `correlation_identifier` with the operation's Events
  and derived objects, keeping restoration auditable.

---

## 8. Versioning Rules

- **Additive evolution only.** New optional fields (e.g. incremental-checkpoint deltas,
  distributed-checkpoint coordinates — doc 25 *Future Evolution*) may be added without
  breaking restoration of existing Checkpoints.
- **Snapshot shape stability.** The meaning of an existing field is never changed in
  place; an old Checkpoint must remain restorable under its original version, and any
  schema change is bridged by upcasting (ADR-001 §6).
- **Regenerability preserved.** Because Checkpoints are derived, a schema change may also
  be satisfied by regenerating Checkpoints from the log; new fields must not make a
  Checkpoint un-regenerable from its `log_position`.
- **Required fields are stable.** Promoting an optional field to required, or removing a
  field, requires a new object version (and an ADR if it alters recovery semantics).
- **Determinism preserved.** Any new field influencing restoration must be captured as
  recorded data so recover-and-resume stays deterministic (INV-17/INV-18).
