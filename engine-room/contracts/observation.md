# Contract — Observation

Status: Frozen (Phase 0 contract freeze)
Object: Observation
Primary source: `docs/v2/09_SUPERVISION.md`
Binding ADRs: ADR-003 (canonical object model — §3.4 Observation owned by Supervision), ADR-001 (event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

An Observation is the **descriptive, Supervision-owned account of operational
execution**, derived from raw Execution Events. It exists so the platform can
distinguish healthy, waiting, paused, degraded, stalled, failed, and completed
execution — the operational awareness Supervision provides (doc 09 *Purpose*).

The Observation does **one job**: *describe* what execution is doing, never *evaluate*
whether it is correct or complete. It is derived (not authored by Execution) and is the
input from which Supervision produces Health Assessments and Intervention
**Recommendations** — but Supervision **recommends; Orchestration acts** (INV-23).
Observation never performs execution, validates completion, changes plans, or modifies
work packages (doc 09 *Architectural Boundaries*).

---

## 2. Ownership

- **Produced by / owned by:** the **Supervision** layer exclusively (INV-11; ADR-003
  §3.4). Supervision is the single owner and producer of the Observation object.
- **Derived from:** raw **Execution Events** emitted by Execution (telemetry, progress,
  artifacts, failures). **Execution does NOT produce Observation objects** — it emits
  Execution Events; only Supervision derives Observations from them (ADR-003 §3.4;
  doc 08 *Outputs* notwithstanding, the canonical owner is Supervision).
- **State transitions owned by:** Supervision exclusively. No downstream layer mutates
  an Observation.
- Per the cross-cutting rules, the Observation carries **no** provider/runtime/health
  *control* state and no provider internals (ADR-002); it *describes* observable
  operational behavior only (doc 09 *Runtime Independent*). Its current state is a
  projection of the event log (ADR-001; INV-14).

---

## 3. Lifecycle

Supervision observes continuously until work completes (doc 09 *Continuous
Observation*). An Observation is a recorded descriptive account; state is a projection
of the event log (ADR-001; INV-14), and each recorded Observation/derivation emits
exactly one Event (INV-15). The logical stages:

- **Derived** — Supervision has folded one or more Execution Events into a descriptive
  Observation of current execution.
- **Recorded** — the Observation is appended to Observation History, supporting
  auditing, reflection, and operational learning (doc 09 *Observation History*).
- **Superseded** — a later Observation describes a more recent state of the same
  execution; the prior Observation remains in history (immutable record).

An Observation is **descriptive and immutable once recorded** — it is never edited to
re-evaluate execution; new behavior produces a new Observation. Non-deterministic
inputs (e.g. timestamps, runtime-reported values) are captured as recorded data and not
recomputed on replay (INV-17).

---

## 4. Required Fields

- **identity** — stable, unique Observation identifier; addressable for history and
  audit.
- **execution_identifier** — the execution session this Observation describes.
- **correlation_identifier** — correlation/trace lineage shared with the Execution
  Events it was derived from and the operation's other objects (doc 09 *Observation
  History* → auditing; INV-39).
- **timestamp** — when the Observation was derived; recorded as data (INV-17).
- **derived_from_events** — references (by id) to the raw Execution Events this
  Observation was derived from (provenance; ADR-003 §3.4). Establishes that Observation
  is derived, not self-reported.
- **execution_state** — the described operational state of execution at this point
  (doc 09 *Observation Model*: Execution State). Descriptive, not an evaluation.
- **progress** — observed progress of the work (doc 09 *Observation Model*: Progress).

---

## 5. Optional Fields

- **runtime_activity** — observed runtime activity/responsiveness (doc 09 *Observation
  Model*). Describes behavior, never runtime implementation details.
- **resource_usage** — observed resource utilization for the execution (doc 09
  *Observation Model*: Resource Usage; *Inputs*: Resource Metrics).
- **operational_events** — the operational events observed (e.g. Execution Started,
  Checkpoint Reached, Runtime Switched, Retry Performed, Artifact Generated — doc 09
  *Observation History*).
- **checkpoint_history** — references (by id) to Checkpoints observed for this execution
  (`checkpoint.md`; doc 09 *Observation Model*: Checkpoint History). References only.
- **health_indicators** — observed indicators (progress velocity, checkpoint frequency,
  runtime responsiveness, artifact generation, retry frequency, execution duration,
  dependency delays — doc 09 *Health Indicators*). Describe execution quality.
- **health_assessment** — Supervision's derived operational health classification
  (Healthy / Waiting / Paused / Degraded / Stalled / Failed / Completed — doc 09
  *Operational Health*). A *descriptive* assessment, distinct from any
  completion verdict (which Validation owns).
- **anomalies** — detected anomalies, stalled-work signals, or repeated-failure signals
  (doc 09 *Failure Detection*).
- **intervention_recommendation** — Supervision's *recommended* intervention (Continue /
  Pause / Resume / Retry / Escalate / Request Context / Switch Runtime / Cancel — doc 09
  *Intervention*), with rationale. **A recommendation only**: Orchestration decides and
  acts (INV-23).
- **rationale** — explanation supporting the assessment/recommendation, so every
  derived health judgment and intervention is explainable (doc 09 *Explainable*;
  INV-31).

---

## 6. Invariants

- **INV-11.** Observation is **owned by Supervision**. Execution emits raw Execution
  Events; only Supervision produces Observations (ADR-003 §3.4).
- **Descriptive, never evaluative.** An Observation *describes* execution and never
  determines completion — Validation determines completion; Observation and Validation
  remain independent (doc 09 *Relationship with Validation*).
- **INV-23.** Supervision **recommends**; Orchestration **acts**. An
  `intervention_recommendation` never directly controls execution; pause/resume/cancel
  control belongs solely to Orchestration.
- **Derived, not self-reported.** Observations derive from Execution Events
  (`derived_from_events`); Supervision never assumes health, it determines it from
  observable evidence (doc 09 *Evidence Driven*).
- **INV-13 / INV-14.** Current state and any snapshot are projections of the append-only
  Event Log; nothing not in the log is true.
- **INV-15.** Each recorded Observation derivation emits exactly one Event.
- **INV-17.** Non-deterministic observed values (clock, runtime-reported figures) are
  captured as recorded data and reproduced on replay, never recomputed.
- **INV-31.** Every health assessment and intervention recommendation records its
  rationale as log data (explainable and auditable).
- **Provider independence (ADR-002).** No provider/runtime/health implementation state
  is embedded; only observable operational behavior is described.

---

## 7. Relationships

- **Derived from →** `event.md` (specifically the raw **Execution Events** emitted by
  Execution). Observation references those Events by id as provenance.
- **References →** `checkpoint.md` (Checkpoint History input — doc 09 *Inputs* /
  *Observation Model*) and Resource metrics / Execution Strategy / Policy as observation
  inputs (doc 09 *Inputs*), by reference.
- **Produced by:** Supervision only. **Consumed by:** Orchestration (acts on
  Supervision's recommendations — INV-23); Knowledge (stores Observations — doc 09
  *Relationship with Knowledge*); Reflection (interprets Observations into Knowledge
  Candidates — `reflection.md`, INV-25). These responsibilities stay separate (doc 09).
- **Distinct from:** `artifact.md` Evidence and Validation verdicts — Observation never
  evaluates completion; it feeds health awareness, not the completion decision.
- **Correlation lineage:** shares `correlation_identifier` with the Execution Events and
  every other object of the operation, keeping observation auditable.

---

## 8. Versioning Rules

- **Additive evolution only.** New optional descriptive fields (e.g. predictive /
  forecasting indicators — doc 09 *Future Evolution*) may be added without breaking
  existing consumers, provided Observation stays descriptive (never evaluative).
- **Published shape is immutable.** The meaning of an existing field is never changed in
  place; a recorded Observation must remain replayable forever (ADR-001 §6 upcasting).
- **Ownership is fixed.** Any change letting another layer produce Observations would
  violate INV-11 and requires an ADR superseding ADR-003 §3.4.
- **Required fields are stable.** Promoting an optional field to required, or removing a
  field, requires a new object version (and an ADR if it alters supervision semantics).
- **Determinism preserved.** Any new field influencing health derivation must be captured
  as recorded data so replay stays deterministic (INV-17).
