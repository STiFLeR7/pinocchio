# Nexus v2 — Roadmap

Status: Engineering Plan
References: `00_IMPLEMENTATION_OVERVIEW.md`, `01_PHASES.md`,
`02_ACTION_POINTS.md`, `03_DEPENDENCY_GRAPH.md`, `04_IMPLEMENTATION_ORDER.md`

---

## Purpose

This document sequences the six engineering phases of `01_PHASES.md` into a
delivery arc of milestones and demonstrable capability increments. It is
**engineering phasing**, not a calendar and not a set of marketing release
names. Duration is expressed only as the S/M/L/XL effort sizes in
`02_ACTION_POINTS.md` and the critical path in `04_IMPLEMENTATION_ORDER.md`.
Convert effort sizes to dates at phase-planning time; do not encode dates here.

Every milestone is anchored to stable AP IDs and is closed by the phase
validation gate defined in `01_PHASES.md` (and elaborated in
`10_VALIDATION_STRATEGY.md` / `11_TESTING_STRATEGY.md`).

---

## Roadmap Overview — the Arc

The program moves through one arc:

```
decisions ─► contracts ─► substrate ─► understanding ─► execution ─►
            self-correction ─► self-improving platform
```

- **Phase 0 (decisions)** removes architectural ambiguity.
- **Phase 1 (contracts)** fixes the shared language as one schema per object.
- **Phase 2 (substrate)** builds the cross-cutting spine the pipeline rides on.
- **Phase 3 (understanding)** turns a Goal into an executable plan with **no
  runtime invoked** — the platform's differentiator.
- **Phase 4 (execution)** performs the work under governance.
- **Phase 5 (self-correction)** observes, verifies by evidence, and recovers.
- **Phase 6 (self-improving)** closes the learning loop: validated outcomes
  feed future planning.

**Guiding principle.** Each phase yields *executable software plus a passed
validation gate*. A phase is not "done" because its code exists; it is done
when its gate passes. Implementation never skips a gate
(`01_PHASES.md` — Phase Validation Gate Pattern). The standard gate sequence
that closes every milestone:

```
Contracts Complete → Architecture Review → Integration Review →
Smoke / Scenario Tests → Documentation Review → Gate Pass → Next Milestone
```

---

## The Critical-Path Spine

The longest chain of hard dependencies (from `04_IMPLEMENTATION_ORDER.md`)
determines overall sequence. Each node below sits on a milestone; protect this
spine — any slip here slips the whole program.

```
M0          M1                  M2            M3                 M4          M5            M6
AP-001 ─► AP-101 ─► AP-105 ─► AP-201 ─► AP-203 ─► AP-303 ─► AP-306 ─► AP-307 ─► AP-401 ─►
Persist   Schema    WP        Event     State     Context   Plan      Graph     Orchestr.
model     format    schema    bus       engine    Eng.      Engine    Builder

   ─► AP-405 ─► AP-502 ─► AP-503 ─► AP-601 ─► AP-602 ─► AP-603
      Exec.      Valid.    Recovery  Reflect.  Knowl.    Retrieval/feedback
                                                          ← learning loop closes
```

**Pacing items — staff first, split into sub-APs at phase planning.** The
XL/Critical APs on or governing the spine set the program tempo:

| AP | Role | Complexity / Effort | Milestone |
|----|------|---------------------|-----------|
| AP-001 | Persistence & event-sourcing model | Critical / M | M0 |
| AP-201 | Event bus + store | Critical / XL | M2 |
| AP-306 | Planning Engine | High / XL | M3 |
| AP-401 | Orchestration Coordinator | Critical / XL | M4 |
| AP-503 | Recovery Engine | Critical / XL | M5 |

AP-001 is the deepest root (AP-101, AP-112, AP-201, AP-203, AP-204 all trace to
it) — it is M (not XL) but must be staffed heaviest and started first because
the entire program waits behind it. AP-201, AP-306, AP-401, AP-503 are the XL
spine items flagged for sub-AP splitting in `02_ACTION_POINTS.md` (Coverage
Note) and `04_IMPLEMENTATION_ORDER.md` (Staffing Guidance).

---

## Milestones

Each milestone corresponds to one phase. Capability statements are concrete and
**demonstrable**; they describe what can be shown end-to-end at that point.

### M0 — Decisions Ratified

- **Capability demonstrated.** The architecture has no unmade foundational
  decision and no empty/duplicate spec; CI is green on an empty skeleton and the
  contract-test harness asserts against a schema fixture. *Nothing runs yet —
  this milestone removes ambiguity, not behavior.*
- **APs.** AP-001 (persistence model), AP-002 (registry unification), AP-003
  (object reconciliation), AP-004 (policy/approval/determinism), AP-005
  (scaffold + CI), AP-006 (contract-test harness), AP-007 (glossary + index).
- **Decision checkpoints closed.** ADR-001 (persistence), ADR-002 (registry),
  ADR-003 (object model), ADR-004 (policy/approval) — see Decision Checkpoints
  below.
- **Gate (Phase 0).** All four ADRs accepted; CI runs green on the skeleton; a
  deliberately-wrong import fails the architecture-fitness test; contract
  harness self-tests; glossary + index correct.
- **Unblocks.** All of Phase 1 (AP-001/AP-003 → AP-101; AP-002 → AP-108/109;
  AP-004 → AP-106/112).

### M1 — Object Contracts Frozen

- **Capability demonstrated.** Every architectural object has exactly one
  authoritative, runtime-independent schema with a round-trip serialization
  test, and every documented seam (Context Engineering → Planning, Planning →
  Orchestration, Execution → Validation) has a passing contract test built from
  real fixtures. The three divergent Work Package definitions are collapsed into
  one.
- **APs.** AP-101 (schema format/identity/versioning — gates the phase), then
  the parallel fan-out AP-102→AP-103→AP-105 (WP sub-chain), AP-104, AP-106,
  AP-107, AP-108, AP-109, AP-110, AP-111, AP-112.
- **Gate (Phase 1).** One schema per object; round-trip tests pass; every
  documented seam has a passing contract test.
- **Unblocks.** Phase 2 substrate (AP-112 → AP-201/203/205; AP-111 → AP-204/206;
  AP-108/109 → AP-207).

### M2 — Substrate Live

- **Capability demonstrated.** A synthetic object is driven through its state
  machine emitting exactly one replayable event per transition; a checkpoint is
  written and restored with reference validation; a policy is registered,
  versioned, evaluated deterministically and simulated; an artifact is produced,
  versioned and referenced without duplication; a reference harness registers
  and is discovered by capability; idempotency holds under duplicate delivery.
- **APs.** AP-201 (event bus + store — gates the substrate) → AP-202
  (idempotency/correlation), then parallel AP-203 (state) → AP-204 (checkpoint),
  AP-205 (policy), AP-206 (artifact store), AP-207 (Harness SDK).
- **Gate (Phase 2).** State machine emits exactly-one-event-per-transition;
  checkpoint write/restore; policy deterministic + simulated; artifact
  immutable; reference harness registered + discovered; idempotency proven.
- **Unblocks.** The entire understanding and execution pipeline. AP-207 in
  particular is the integration root inherited by AP-302 (context), AP-403
  (runtime), and later validation/communication harnesses.

### M3 — Goal Becomes an Execution Graph (No Runtime)

- **Capability demonstrated.** A Goal becomes a persisted, valid, acyclic
  Execution Graph of well-formed Work Packages — each carrying required
  capabilities, selected skills, constraints, validation requirements, and
  completion criteria — with an attached Execution Strategy, **and zero runtime
  invoked.** Planning refuses to proceed on an invalid Context Package; every
  decision is explainable (rationale persisted).
- **APs.** Track 1: AP-302 (context harnesses) ∥ AP-301 (intent) → AP-303
  (context engineering). Track 2: AP-304 → AP-305. Planning core: AP-306 →
  AP-307 → AP-308 → AP-309.
- **Gate (Phase 3).** Representative multi-domain goals produce valid acyclic
  Execution Graphs of well-formed Work Packages; Planning refuses invalid
  Context Packages; decisions explainable. **No runtime invoked.**
- **Unblocks.** Phase 4 — AP-307 + AP-308 are the inputs to Orchestration
  (AP-401); AP-309's ready Work Packages are what Execution performs.

### M4 — Work Executes Under Governance

- **Capability demonstrated.** A multi-node Execution Graph runs to "waiting
  validation" across at least two runtime adapters; execution never begins until
  dependency/constraint/approval/resource gates pass; a forced runtime failure
  pauses (does not crash) the operation; every orchestration decision is
  replayable from the event log; the governance gate denies a policy-violating
  action and records an immutable audit entry. Execution never self-declares
  completion — it emits evidence *candidates*.
- **APs.** AP-401 (orchestration — the hub) ∥ AP-403 (runtime adapter SDK +
  first adapter), then AP-402 (resources), AP-405 (execution), AP-406
  (governance gate) into AP-401; AP-404 (more adapters) after AP-403.
- **Gate (Phase 4).** Multi-node graph reaches "waiting validation" across ≥2
  adapters; no execution before gates pass; forced runtime failure pauses;
  decisions replayable; governance denies + audits a violation.
- **Unblocks.** Phase 5 — Execution's output stream (observations, evidence
  candidates, checkpoints, events) is the input to Supervision, Validation, and
  Recovery; AP-401 is the actuator Supervision and Recovery attach to.

### M5 — Loop Closes: Observe, Verify, Recover

- **Capability demonstrated.** A failing Work Package is detected by Supervision,
  classified by Recovery, restored from the latest valid checkpoint, retried
  within bounds, and either recovered or escalated — without losing context or
  validated evidence. Validation independently passes/fails/partials a Work
  Package from evidence alone; a runtime "success" with insufficient evidence
  does **not** complete. The pause/resume/escalate verbs each have exactly one
  owner.
- **APs.** AP-501 (supervision) ∥ AP-502 (validation), then AP-503 (recovery)
  after AP-501.
- **Gate (Phase 5).** Failing WP detected → classified → restored → retried in
  bounds → recovered or escalated, no context/evidence loss; validation decides
  from evidence alone; insufficient-evidence "success" does not complete;
  pause/resume/escalate each have exactly one owner.
- **Unblocks.** Phase 6 — only validated outcomes (AP-502) may proceed to
  Reflection and Knowledge.

### M6 — Self-Improving Platform

- **Capability demonstrated.** A **second run of a previously executed goal
  class measurably reuses validated knowledge** in planning/context; only
  validated outcomes enter Knowledge; reflections are evidence-sourced;
  end-to-end observability and audit cover every layer; the platform meets its
  stated performance and recoverability targets under load.
- **APs.** Linear core AP-601 (reflection) → AP-602 (knowledge store/ingestion)
  → AP-603 (retrieval/feedback); AP-604 (operational maturity) parallel late.
- **Gate (Phase 6).** Second-run knowledge reuse demonstrated; only validated
  outcomes enter Knowledge; reflections evidence-sourced; full
  observability/audit; performance + recoverability targets met under load.
- **Unblocks.** Defines "Nexus v2 core complete" (see Exit Definition).

---

## Capability-Increment View (Cumulative)

After each milestone, what the platform can demonstrably DO end-to-end —
each row includes everything above it.

| After | Cumulative end-to-end capability |
|-------|----------------------------------|
| **M0** | No buildable behavior yet; every foundational decision recorded as an accepted ADR; skeleton compiles, CI green, contract harness asserts against a fixture. |
| **M1** | Any architectural object can be serialized, versioned, and round-tripped against one authoritative schema; every documented seam is contract-tested. |
| **M2** | An object can be driven through its state machine with one replayable event per transition; checkpoints restore by reference; policies evaluate deterministically; artifacts are immutable and referenceable; a harness registers and is discovered by capability. |
| **M3** | An operator Goal is turned into a persisted, valid, acyclic Execution Graph of execution-ready Work Packages with an attached Execution Strategy — explainable, refusing invalid context — **without invoking any runtime.** |
| **M4** | That graph executes to "waiting validation" across ≥2 runtimes under governance; gates block premature execution; failures pause not crash; every decision replays; Execution emits evidence candidates and never self-completes. |
| **M5** | Executions are continuously observed; completion is determined only by independently verifiable evidence; failures recover from the latest valid checkpoint instead of restarting; control verbs have single owners. |
| **M6** | Completed operations contribute reflections and validated knowledge; a second run of a goal class reuses that knowledge in planning/context; the platform is fully observable, auditable, and meets performance/recoverability targets under load. |

---

## Parallelization Across the Arc

Teams may work concurrently within a milestone but never across an unpassed
gate (from `04_IMPLEMENTATION_ORDER.md` — Parallelization Summary). The
contract-test harness (AP-006) is the enforcement mechanism: do not start a
pipeline AP whose schema (Phase 1) or substrate (Phase 2) dependency has not
passed its contract/gate test.

| Milestone | Max useful parallel tracks | Serializing bottleneck |
|-----------|----------------------------|------------------------|
| M0 | 4 (the four ADRs) + scaffold track (AP-005→AP-006) | AP-007 waits on AP-002/003/004 |
| M1 | ~9 schema owners after AP-101 | AP-101 first; AP-102→AP-103→AP-105 sub-chain |
| M2 | ~4 after AP-201/202 | AP-201 → AP-202 |
| M3 | 2–3 tracks (intent/context ∥ capability/skill) | AP-306 → AP-307 → AP-309 core |
| M4 | 2 (orchestration ∥ adapters; both ← AP-207) | AP-401 hub |
| M5 | 2 (supervision ∥ validation) | AP-503 last |
| M6 | core linear + AP-604 aside | AP-601 → AP-602 → AP-603 |

Highest-yield concurrency: M1's schema fan-out (one engineer per object schema
after AP-101 lands) and M4's orchestration-vs-adapters split (AP-401 ∥ AP-403,
both gated only on AP-207).

---

## Decision Checkpoints (Roadmap Gates)

The Phase-0 ADRs are roadmap gates. Each MUST close before the downstream work
that depends on it begins.

| ADR | Decision | Closes at | Blocks until closed |
|-----|----------|-----------|---------------------|
| ADR-001 | Persistence / event-sourcing model (AP-001) | M0 | All of Phase 2 (AP-201/203/204) and AP-101/112 in Phase 1 |
| ADR-002 | Registry/capability unification (AP-002) | M0 | AP-108, AP-109, AP-207, AP-304 |
| ADR-003 | Object-model reconciliation (AP-003) | M0 | The entire Phase-1 schema set |
| ADR-004 | Policy language + approval taxonomy + determinism (AP-004) | M0 | AP-106, AP-112, AP-205, AP-406 |

ADR-001's event-bus/delivery/idempotency consequences carry into M2 (AP-201,
AP-202). **All four ADRs gate M0's exit** — Phase 1 and Phase 2 work depending
on them must not begin until they are accepted, not merely proposed.

**De-risking property.** M3 (Phase 3) can be **built and validated with no
runtime at all** — it depends only on the object model (M1) and substrate (M2),
not on execution. Sequencing the differentiator before execution de-risks the
program early: the highest-value capability is proven before the most
replaceable layer exists.

---

## Risk-Aware Sequencing

The highest-leverage early de-risking moves, in order:

1. **Persistence decision first (AP-001, M0).** The deepest dependency root; a
   wrong choice forces rework of all of Phase 2. Start it first, staff it
   heaviest, validate it with a throwaway state-reconstruction spike before any
   substrate work begins.
2. **Harness SDK as reusable leverage (AP-207, M2).** Invest in its quality
   once; AP-302 (context), AP-403 (runtime), and later validation/communication
   harnesses all inherit from it. A leaky base abstraction here multiplies
   across every later integration.
3. **Understanding before execution (M3 before M4).** Build and validate the
   Goal→Execution-Graph pipeline with no runtime, then add the "smallest and
   most replaceable" execution layer. This proves the platform's differentiating
   value early and keeps execution swappable.

Corollary: split the XL/Critical pacing APs (AP-201, AP-306, AP-401, AP-503)
into sub-APs at phase planning and assign one owner each, so the spine never
stalls behind a single oversized unit.

---

## Exit Definition

**"Nexus v2 core complete"** is the passing of the M6 / Phase-6 gate: the
learning loop closes — a **second run of a previously executed goal class
measurably reuses validated knowledge** in planning and context, only validated
outcomes enter Knowledge, reflections are evidence-sourced, and the platform
meets its stated observability, audit, performance, and recoverability targets
under load. At that point the full one-way pipeline (Intent → Context → Plan →
Strategy → Skills → Work Packaging → Orchestration → Execution → Supervision →
Validation → Recovery → Reflection → Knowledge) is operational and
self-improving.

**Explicitly OUT of this arc** (the architecture's deferred "Future Evolution"):
distributed / multi-node coordination, collaborative multi-operator workflows,
predictive planning, adaptive self-tuning, and organization-wide capabilities.
These are not in any of M0–M6 and are not implied by "core complete." They are
post-core evolution, to be planned as a separate program after the M6 gate
passes.
