# Contract — Reflection

Status: Frozen (Phase 0 contract freeze)
Object: Reflection
Primary source: `docs/v2/26_REFLECTION.md`
Binding ADRs: ADR-003 (canonical object model; reflection produces candidates),
ADR-001 (event-sourced state; operates on validated outcomes from the log)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Reflection is the **interpretation** of one or more **validated operational outcomes**
into reusable operational understanding. Execution performs work; Validation determines
correctness; Reflection explains **why** an outcome occurred, **what** was learned, and
**how** future operations should improve (doc 26 *Purpose*).

It does **one job**: analyze validated outcomes and **produce Knowledge Candidates** (and
their supporting lessons, patterns, anti-patterns, and recommendations) for the Knowledge
System to consider. A Reflection is **advisory until Knowledge accepts** it (doc 26
*Recommendation Model*, *Relationship with Knowledge*). Reflection **never performs
execution, never validates outcomes, never creates or modifies plans, and never updates
Knowledge directly** (INV-25; doc 26 *Architectural Boundaries*).

Reflection operates **only on validated operational outcomes** — it never infers lessons
from unverified execution (doc 26 *Evidence First*, *Architectural Position*).

---

## 2. Ownership

- **Produced by / owned by:** the **Reflection** layer exclusively. It owns the
  interpretation and all state transitions of a Reflection object.
- **Independent** from Execution, Planning, and Knowledge Storage; its sole
  responsibility is interpretation (doc 26 *Independent*).
- **Outputs are candidates, not commitments.** Reflection produces **Knowledge
  Candidates** and recommendations; the **Knowledge System** alone decides what becomes
  persistent operational understanding (INV-25; doc 26 *Relationship with Knowledge*).
  Reflection never writes Knowledge.
- **Downstream coupling rule:** **Planning never depends directly on Reflection** (INV-26).
  Reflection reaches Planning only indirectly, through persisted Knowledge.
- A Reflection carries **no** provider/runtime/health state (ADR-002) and defines **no**
  independent authoritative store — its current state is a projection of the event log
  (INV-13/14).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14). Every transition emits
exactly one event (INV-15). A Reflection moves through (doc 26 *Reflection Lifecycle*):

- **Pending** — a validated outcome (or set of outcomes) has been admitted as a
  reflection opportunity; analysis has not begun.
- **Analyzing** — evidence analysis is underway over the validated inputs (evidence
  analysis → pattern identification → lesson extraction — doc 26 *Reflection Lifecycle*).
- **CandidatesProposed** — interpretation produced its outputs (lessons, patterns,
  anti-patterns, recommendations, Knowledge Candidates, confidence assessment), proposed
  to the Knowledge System. Terminal for the Reflection's production responsibility.
- **Discarded** — the opportunity yielded no actionable insight; per the *Actionable*
  principle, observations without actionable insight do not become candidates (doc 26
  *Actionable*). Terminal.

After **CandidatesProposed**, the *disposition* of each candidate (accepted / rejected)
is owned by the Knowledge System on the **Knowledge Entry's** lifecycle, not the
Reflection's (`knowledge.md` §3); the Reflection remains advisory and unchanged.
Non-deterministic interpretation outputs (LLM reasoning, confidence judgments) are
captured as recorded event data and reproduced on replay, never recomputed (INV-17).

---

## 4. Required Fields

- **identity** — stable, unique identifier for this Reflection; addressable and
  replayable for the life of the platform.
- **correlation** — correlation / trace lineage tying the Reflection to the validated
  operation(s) it interprets and to every candidate it proposes, so its provenance is
  auditable end to end.
- **category** — the reflection category (doc 26 *Reflection Categories*): one of
  `Success`, `Failure`, `Process`, `Strategy`, `Knowledge` reflection.
- **inputs** — references (by id) to the validated operational inputs analyzed. Drawn
  only from: **Validated Artifacts, Execution History, Operational Events, Validation
  Reports, Recovery History, Supervision Observations** (doc 26 *Inputs*). All inputs are
  validated outcomes; a Reflection never operates on incomplete operational information
  (doc 26 *Inputs*, *Evidence First*).
- **findings** — the interpretation produced: what happened, why it happened, what worked,
  what failed, what should change (doc 26 *Explainable*, *Reflection Questions*). The
  explanatory substance of the Reflection.
- **confidence** — the Reflection's confidence on the ladder shared with Knowledge
  (`knowledge.md`): `Experimental`, `Observed`, `Validated`, `Proven` (doc 26
  *Confidence*). Knowledge prioritizes higher-confidence reflections.
- **status** — the projected lifecycle state (§3). Derived, never authoritative.

---

## 5. Optional Fields

- **lessons** — lessons learned: discrete, actionable takeaways from the validated
  outcome (doc 26 *Outputs*).
- **patterns** — identified operational patterns: repeated successes, common bottlenecks,
  effective recovery strategies, high-value context, reusable execution strategies,
  emerging practices (doc 26 *Outputs*, *Pattern Identification*).
- **anti_patterns** — identified failure patterns / things that should never be repeated
  (doc 26 *Outputs*, *Reflection Questions*).
- **recommendations** — improvement recommendations, advisory until accepted: planning,
  context, new skills, updated policies, recovery, validation, documentation, or
  architecture improvements (doc 26 *Recommendation Model*).
- **knowledge_candidates** — references to the **Knowledge Candidates** this Reflection
  proposes for ingestion (`knowledge.md`). Each candidate carries the understanding plus
  its supporting evidence refs so Knowledge can validate-gate it (INV-24). Present once
  the Reflection reaches **CandidatesProposed**.
- **root_causes** — for Failure/Process reflections, the analyzed root causes and the
  effectiveness of any recovery (doc 26 *Failure Reflection*).
- **assumptions_assessment** — which assumptions proved correct and which proved
  incorrect (doc 26 *Reflection Questions*).
- **evidence_refs** — explicit references (by id) to the validated evidence underpinning
  the findings, carried so that any resulting Knowledge Entry remains evidence-backed
  (INV-24).
- **rationale** — explanation of how the findings follow from the evidence
  (explainability).
- **metadata** — non-behavioral descriptive attributes (tags, ownership notes) that do
  not affect the interpretation.

---

## 6. Invariants

- **INV-25 — Candidates only.** Reflection produces **Knowledge Candidates** and never
  updates Knowledge directly; Knowledge decides persistence. A Reflection is advisory
  until Knowledge accepts (doc 26 *Responsibilities*, *Relationship with Knowledge*).
- **INV-26 — Planning independence.** Planning never depends directly on Reflection
  outputs; learning reaches Planning only through persisted Knowledge. No field of this
  object is consumed directly by Planning.
- **Validated inputs only.** `inputs` are exclusively validated outcomes (Validated
  Artifacts, Execution History, Operational Events, Validation Reports, Recovery History,
  Supervision Observations — doc 26 *Inputs*). Reflection never analyzes unverified
  execution (doc 26 *Evidence First*) and never operates on incomplete information.
- **Actionable gate.** Observations without actionable insight do not become Knowledge
  Candidates (doc 26 *Actionable*); such a Reflection terminates **Discarded**.
- **Confidence ladder is shared.** `confidence` uses the same four levels as
  `knowledge.md` (Experimental / Observed / Validated / Proven), so a candidate's
  confidence carries through ingestion unchanged.
- **INV-07.** Exactly one canonical schema for a Reflection; no subsystem introduces an
  alternative representation of operational interpretation.
- **INV-13 / INV-14.** The Reflection's current state is a derived projection of the
  append-only event log; nothing not in the log is true.
- **INV-15.** Every Reflection state transition emits exactly one event.
- **INV-17 (replay without re-inference).** Non-deterministic interpretation outputs
  (LLM reasoning, confidence judgments) are captured as recorded event data and
  reproduced on replay, never recomputed (ADR-001/004 determinism boundaries).
- **INV-31 (explainable & auditable).** Each Reflection records what it analyzed, what it
  concluded, and why, as reconstructable log data (doc 26 *Explainable*).
- **No boundary crossing.** Reflection never performs execution, validates outcomes,
  creates/modifies plans, or modifies Knowledge directly (doc 26 *Architectural
  Boundaries*).
- **Provider independence (ADR-002).** No provider/runtime/health state is embedded.

---

## 7. Relationships

- **Consumes →** validated inputs by reference: `artifact.md` (Validated Artifacts),
  Execution History and Operational Events (`event.md`), Validation Reports and Evidence
  (Validation layer), Recovery History (Recovery), and Supervision Observations
  (`observation.md`). All inputs are validated; references, never copies.
- **Produces →** Knowledge Candidates consumed by the **Knowledge System**
  (`knowledge.md`). Knowledge validate-gates and accepts/rejects each candidate (INV-25);
  an accepted candidate becomes a Knowledge Entry whose `candidate_ref` points back to
  this Reflection's proposal.
- **Does not feed Planning directly.** Per INV-26, Planning consumes only persisted
  Knowledge; this object has **no** direct Planning consumer relationship.
- **May recommend policy changes** that target `policy.md` (as advisory recommendations
  only — doc 26 *Recommendation Model*); Reflection never authors or evaluates policy.
- **Distinct from Validation.** Validation answers "did it succeed?"; Reflection answers
  "what did we learn?" — separate responsibilities, separate objects (doc 26
  *Relationship with Validation*).
- **Correlation lineage:** shares correlation/trace identity with the validated operation
  it interprets and with the Knowledge Candidates it proposes.

---

## 8. Versioning Rules

- **Additive evolution only.** New optional fields (e.g., cross-project reflection links,
  strategy-effectiveness scores, reflection-quality metrics — doc 26 *Future Evolution*)
  may be added without breaking existing consumers.
- **Published shape is immutable.** A recorded Reflection — its inputs, findings, and
  proposed candidates — remains replayable forever; existing fields are never redefined
  in place (ADR-001 event upcasting / append-only).
- **Confidence ladder is fixed** at the architecture level and shared with
  `knowledge.md`; changing the ladder requires an ADR, never an ad-hoc field.
- **Candidate-only output is permanent.** A change that would let Reflection write
  Knowledge directly is forbidden and would require superseding INV-25.
- **Determinism preserved.** Any new field influencing interpretation must be captured as
  recorded data so replay stays deterministic (INV-17).
- **Required fields are stable.** Promoting an optional field to required, or removing any
  field, requires a new object version (and an ADR if it alters the candidate-only or
  validated-inputs-only semantics). Old Reflections remain replayable under their
  original version via upcasting.
