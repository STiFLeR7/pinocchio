# Contract — Event

Status: Frozen (Phase 0 contract freeze)
Object: Event
Primary source: `docs/v2/23_EVENT_MODEL.md`
Binding ADRs: ADR-001 (event-sourced state — Event is authoritative), ADR-003 (canonical object model)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

An Event is the **authoritative, immutable, append-only unit of operational truth**
in Nexus (INV-13). Every meaningful operational change — a state transition, a
hand-off between subsystems, a recorded decision, a non-deterministic output — is
represented as exactly one Event. Events are the communication backbone: subsystems
react to Events rather than invoking one another directly (doc 23 *Event Driven*).

The Event does **one job**: record that something happened, as a permanent historical
fact. The append-only Event Log composed of these Events is the single source of
operational truth from which all current State (a projection) and all Checkpoints
(derived snapshots) are reconstructed (ADR-001 §3). Nothing that is not in the log is
true. An Event never performs execution, modifies state directly, evaluates policy, or
creates plans (doc 23 *Architectural Boundaries*).

---

## 2. Ownership

- **Produced by:** every operational layer, at its own transitions. Each layer emits
  the Events for the facts it owns — e.g. Intent Resolution emits Goal Events,
  Execution emits Execution Events, Supervision emits observation-derived Events,
  Validation emits Validation Events, Governance emits audit/decision Events.
- **Owned by (as a record):** the platform's append-only Event Log / event store
  (AP-201). Once published, an Event belongs to the immutable historical record and
  has no further owner that may alter it.
- **No exclusive single producer.** Unlike most contracts, the Event is the *shared*
  envelope every layer produces. Its **schema** is canonical and singular (INV-07);
  its **producer** field records which layer emitted each instance.
- Per the cross-cutting rules, an Event carries **no** provider/runtime/health state
  above the Harness boundary (ADR-002). Provider state lives only in the Harness
  Registry; an Event may *reference* operational facts but never embeds provider
  internals.

---

## 3. Lifecycle

An Event itself is immutable; its "lifecycle" is the progression of a single fixed
record through the delivery substrate, not a mutable object changing state. The
logical stages (doc 23 *Event Lifecycle*):

- **Occurred** — the operational fact happened.
- **Created** — the Event record is constructed with its full identity and payload.
- **Published** — the Event is appended to the log and offered to the bus. From this
  point the Event is **immutable forever** (doc 23 *Immutable*; ADR-001 append-only).
- **Delivered** — transported to one or more consumers (at-least-once; possibly
  duplicated or reordered across correlation streams).
- **Processed** — applied idempotently by each consumer / projection.
- **Persisted** — durably retained as part of the authoritative log.
- **Archived** — moved to cold retention; still replayable, never deleted in a way
  that breaks reconstruction.

There is **no mutation transition**: an Event is never edited or re-stated after
Published. A correction is itself a *new* Event. Replay re-reads published Events in
causal order and never modifies them (doc 23 *Event Replay*).

---

## 4. Required Fields

- **identifier** — stable, globally unique identity for this Event. It is the dedup key
  for idempotent consumption under at-least-once delivery (INV-16; ADR-001 §3.5).
- **type** — the canonical event type (e.g. Goal Created, Plan Created, Execution
  Started, Checkpoint Created, Artifact Produced, Validation Passed). Determines how
  consumers interpret the payload.
- **version** — the schema version of this event type, enabling safe upcasting and
  backward-compatible evolution (doc 23 *Event Versioning*; ADR-001 §6).
- **timestamp** — when the fact occurred / was recorded; captured as data so replay is
  deterministic and never re-derives the clock (INV-17).
- **producer** — the subsystem/layer that emitted the Event (the source of the fact),
  recorded for auditability and attribution.
- **correlation_identifier** — the correlation/trace lineage tying this Event to all
  other Events of the same operational execution (doc 23 *Correlation*; INV-39). All
  Events of one operation share it; it also defines the causal-ordering boundary.
- **execution_identifier** — the execution session/context the Event belongs to, when
  applicable, linking the fact to a specific run.
- **payload** — the event-specific data: the substance of what happened, including any
  non-deterministic value (LLM output, human decision) captured as recorded data, never
  recomputed on replay (INV-17).
- **source** — provenance of the Event beyond the producing layer (originating
  subsystem/surface/runtime adapter), so the fact's origin is fully traceable.

---

## 5. Optional Fields

- **metadata** — observability and routing context (doc 23 *Event Metadata* /
  *Observability*): subsystem, execution session, goal, work package, priority, trace
  identifier, delivery status, retry count, latency. Enables distributed observability
  without altering the meaning of the fact.
- **schema_version** — an explicit schema-version marker distinct from event `version`
  where the substrate distinguishes the two (doc 23 *Event Versioning*); when absent,
  `version` carries schema identity.
- **causation_identifier** — reference (by id) to the Event that directly caused this
  one, sharpening causal ordering within a correlation stream.
- **sequence_position** — the Event's ordered position within its correlation stream /
  log, supporting deterministic ordering and the log-position binding that
  `checkpoint.md` records. (Logical ordering reference, not a storage offset.)
- **priority** — operational priority hint carried for delivery/observability; never a
  governance decision.

---

## 6. Invariants

- **INV-13.** The append-only Event Log composed of these Events is the single source
  of operational truth. Nothing not in the log is true; State and Checkpoints derive
  from it.
- **INV-15.** Every operational state transition emits **exactly one** Event — no more,
  no fewer. (One fact, one record.)
- **INV-16.** Delivery is at-least-once; consumers must be idempotent, deduplicating by
  `identifier` (+ sequence). Duplicate or out-of-order delivery causes no duplicate
  state change.
- **INV-17.** Non-deterministic values (LLM/human/clock outputs) are captured as Event
  `payload` data and reproduced on replay, never recomputed.
- **INV-07.** Exactly one canonical Event schema (this contract); no subsystem
  introduces an alternative event envelope.
- **INV-39.** Every cross-subsystem interaction is an Event carrying correlation and
  trace identity; subsystems never bypass the log with direct calls.
- **Immutability.** A published Event is never mutated or deleted. Corrections are new
  Events; a published event type is never changed in place (ADR-001 §6 upcasting).
- **Causal ordering.** Within one `correlation_identifier`, ordering is deterministic;
  e.g. Validation Completed never processes before Execution Started (doc 23 *Event
  Ordering*).
- **No silent loss.** Undeliverable Events move to dead-letter handling for
  investigation/replay; no Event disappears silently (doc 23 *Dead Letter Handling*).
- **Provider independence (ADR-002).** No provider/runtime/health internals are embedded
  above the Harness boundary.

---

## 7. Relationships

- **Authoritative for →** State (a projection; not a separate contract per
  `README.md`) and `checkpoint.md` (a derived snapshot tied to a log position). Both are
  rebuildable from Events; neither is authoritative (INV-14).
- **Produced about →** every operational object: `goal.md`, `plan.md`,
  `work_package.md`, `execution_graph.md`, `artifact.md`, `checkpoint.md`,
  `observation.md`, `knowledge.md`, etc. Their transitions are recorded as Events.
- **Execution Events.** Execution emits raw Execution Events (telemetry, progress,
  artifact, failure); these are the inputs from which Supervision derives
  `observation.md` (ADR-003 §3.4). Execution does not emit Observation objects.
- **Consumed by:** Orchestration (reacts to Events), Supervision (derives health from
  Event patterns — doc 23 *Relationship with Supervision*), Validation, Recovery
  (replay), and Knowledge (mines validated Events — doc 23 *Relationship with
  Knowledge*; INV-24).
- **Governance audit:** governance decisions are themselves Events; the log *is* the
  immutable audit record (ADR-001 §6; INV-31). No separate audit store may disagree.
- **Correlation lineage:** shares `correlation_identifier` across the whole operation,
  making every derived object traceable back to its originating Event chain.

---

## 8. Versioning Rules

- **Append-only, upcastable.** Event schemas evolve by adding new optional payload
  fields or new event versions. A **published event type is never mutated in place**;
  old Events remain replayable forever via upcasting (ADR-001 §6; doc 23 *Event
  Versioning*).
- **Backward compatibility.** Consumers must process older `version`s safely; new
  required payload fields require a new event version, never a redefinition of an
  existing one.
- **Type stability.** An event `type`'s meaning is fixed once published; a changed
  meaning is a new type, not a redefinition (preserves replay determinism).
- **Determinism preserved.** Any new field influencing downstream state must be carried
  as recorded data so replay stays deterministic (INV-17).
- **No removal.** Fields and types are never removed in a way that breaks reconstruction
  of historical operations; deprecation is additive and upcasting bridges old records.
