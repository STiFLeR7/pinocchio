# Nexus v2 — Technical Debt Register

Status: Engineering Plan
Scope: Forward-looking, deliberate-debt planning for implementing the Nexus v2
target architecture (`docs/v2/`) along the phases of `01_PHASES.md` and the
Action Points of `02_ACTION_POINTS.md`.

---

## What This Document Is

The Nexus v2 codebase does not exist yet. This is therefore not a record of debt
already taken — it is a **plan for which debt the program will deliberately
incur to reach a working pipeline sooner, and which debt it must never incur
because it is architecturally load-bearing.**

Two kinds of entries:

- **Sanctioned debt.** A deliberate shortcut the plan permits to deliver a
  capability increment earlier, paired with an explicit repayment trigger and the
  phase/AP that owns repayment. Each maps to a "Future Evolution" the
  architecture docs already defer.
- **Forbidden debt (anti-debt).** A shortcut that must never be taken because the
  architecture depends on it from day one. Taking it produces structural drift
  that later phases cannot cheaply undo. These are enforced as build-time or
  gate-time rules, not aspirations.

Every entry ties to stable AP IDs. **Interest** is the cost of leaving the debt
unpaid (for sanctioned) or of incurring it (for forbidden).

---

## Design Principle

Build the **understanding pipeline** broad and the **execution/runtime,
distribution, and learning** surfaces narrow first. Defer breadth (more
runtimes, more connectors, distributed transport, semantic retrieval, real cost
models) behind contracts that already exist, so breadth is added later without
reshaping the spine. Never defer the contracts, invariants, and idempotency that
the spine is made of.

---

## Sanctioned Debt (deliberate, repayable)

| ID | Title | Type | Repayment trigger & owning phase/AP |
|----|-------|------|--------------------------------------|
| TD-01 | Heuristic Planning estimation before a real cost model | Sanctioned | Replace when validated Knowledge feedback exists — Phase 6, AP-603 (model), AP-306 (consumer) |
| TD-02 | Read-only context connectors before write | Sanctioned | Add write/mutation connectors after read path is proven and an auth/write-safety model exists — Phase 3+, AP-302 |
| TD-03 | First single runtime adapter before multi-runtime | Sanctioned | Add ≥2 heterogeneous adapters to prove runtime independence — Phase 4, AP-404 (after AP-403) |
| TD-04 | In-process event bus before distributed transport | Sanctioned | Move to distributed transport when load/soak exceeds the in-process envelope — Phase 6, AP-604 (behind AP-201 contract) |
| TD-05 | Deferred confidence-scoring calibration | Sanctioned | Replace placeholder confidence with calibrated scoring once outcome history exists — Phase 6, AP-601/AP-602 |
| TD-06 | Deferred semantic Knowledge retrieval | Sanctioned | Upgrade from structural/keyword retrieval to semantic once the graph is populated and freshness is enforced — Phase 6, AP-603 (behind AP-602) |
| TD-07 | Static Execution Graph before dynamic expansion | Sanctioned | Add mid-execution graph expansion when a goal class requires it — Phase 3/4, AP-307 (schema must not preclude it, AP-104) |
| TD-08 | Bounded artifact archival before full GC policy | Sanctioned | Implement archival/GC of unreferenced artifacts when storage growth crosses the envelope — Phase 2/6, AP-206 (with AP-604) |
| TD-09 | Heuristic Supervision health thresholds before learned indicators | Sanctioned | Replace fixed thresholds with tuned/learned indicators once operational history exists — Phase 5/6, AP-501 (with AP-602) |
| TD-10 | Mock/local runtime for early pipeline validation | Sanctioned | Replace with a real runtime adapter once the Harness SDK is stable — Phase 4, AP-403 |

### TD-01 — Heuristic Planning estimation before a real cost model
- **Type.** Sanctioned.
- **Description.** Planning estimates complexity, cost, duration, and risk using
  explicit documented heuristics rather than a calibrated cost model.
- **Why acceptable now.** A real cost model needs outcome history that does not
  exist until the platform has run; heuristics with persisted rationale unblock
  Phase 3 strategy selection immediately.
- **Repayment trigger & owner.** When validated Knowledge accumulates, replace
  heuristics with a knowledge-fed cost model. **AP-603** supplies the feedback;
  **AP-306** consumes it. Ties to the Phase 6 feedback-loop Future Evolution.
- **Interest.** Strategy selection rests on unjustified numbers (Risk R-16);
  bounded by requiring every estimate to be explainable today.

### TD-02 — Read-only context connectors before write
- **Type.** Sanctioned.
- **Description.** Context Harnesses provide read-only access to sources
  (repository, filesystem, docs) first; write/mutation connectors come later.
- **Why acceptable now.** The understanding pipeline only needs to read context;
  write access multiplies the auth/safety surface with no Phase 3 benefit.
- **Repayment trigger & owner.** When a use case requires writing back to a
  source and a write-safety/auth model is defined. **AP-302** (connector
  framework atop **AP-207**). Ties to the context-source Future Evolution.
- **Interest.** Use cases needing write-back are blocked until repaid; low while
  the pipeline is understanding-first.

### TD-03 — First single runtime adapter before multi-runtime
- **Type.** Sanctioned.
- **Description.** Phase 4 ships one real runtime adapter through the uniform
  Runtime Interface before proving heterogeneity.
- **Why acceptable now.** End-to-end execution can be validated on one adapter;
  the SDK and Orchestration are exercised without the cost of many adapters.
- **Repayment trigger & owner.** Immediately after AP-403 stabilizes, add ≥2
  heterogeneous adapters (Claude Code, Gemini, Human Operator) to prove the same
  WP runs unmodified. **AP-404** (after **AP-403**). Ties to runtime-independence.
- **Interest.** Runtime independence is asserted but unproven until repaid; a
  hidden single-runtime assumption could leak (guarded by anti-debt TD-A6).

### TD-04 — In-process event bus before distributed transport
- **Type.** Sanctioned.
- **Description.** The Event Bus first runs in-process behind the AP-201 contract
  (publish/subscribe, persistence, replay, dead-letter), not a distributed broker.
- **Why acceptable now.** Correctness (ordering, replay, idempotency) is what the
  pipeline depends on, and that is provable in-process; distribution is a
  transport swap behind a stable contract.
- **Repayment trigger & owner.** When load/soak exceeds the in-process
  performance envelope. **AP-604** measures the envelope; the swap stays behind
  **AP-201**'s contract. Ties to operational-maturity Future Evolution.
- **Interest.** Throughput ceiling until repaid; low risk *provided* the contract
  and idempotency (anti-debt TD-A2) are honored so the swap is transparent.

### TD-05 — Deferred confidence-scoring calibration
- **Type.** Sanctioned.
- **Description.** Confidence values on Goals, Context Packages, Reflections, and
  Knowledge are laddered/placeholder rather than statistically calibrated.
- **Why acceptable now.** Calibration needs outcome history; placeholder
  confidence still lets the pipeline reason about uncertainty and gate
  clarifications.
- **Repayment trigger & owner.** When outcome history supports calibration.
  **AP-601/AP-602** (reflection + knowledge confidence). Ties to the
  confidence/freshness lifecycle Future Evolution.
- **Interest.** Decisions keyed on miscalibrated confidence; bounded because
  confidence is advisory, not a completion authority (completion is evidence-based
  per anti-debt TD-A4).

### TD-06 — Deferred semantic Knowledge retrieval
- **Type.** Sanctioned.
- **Description.** Knowledge retrieval into Context/Planning starts
  structural/keyword-based, not semantic/vector-based.
- **Why acceptable now.** The graph is empty early; semantic retrieval adds cost
  and tuning before there is a corpus to retrieve from.
- **Repayment trigger & owner.** When the graph is populated and freshness is
  enforced. **AP-603** (retrieval) behind **AP-602** (store/freshness). Ties to
  the Knowledge retrieval Future Evolution.
- **Interest.** Lower retrieval precision/recall until repaid (Risk R-18);
  bounded by freshness filtering excluding deprecated knowledge regardless of
  retrieval method.

### TD-07 — Static Execution Graph before dynamic expansion
- **Type.** Sanctioned.
- **Description.** The Execution Graph is fully built before execution; no
  mid-run node discovery.
- **Why acceptable now.** Most goal classes decompose up front; static graphs are
  simpler to persist, validate, and resume.
- **Repayment trigger & owner.** When a goal class cannot be fully decomposed
  before execution. **AP-307** (builder); the **AP-104** schema must be designed
  to not preclude expansion. Ties to the dynamic-graph Future Evolution and Risk
  R-17.
- **Interest.** A class of goals unsupported until repaid; bounded by designing
  the schema to allow later expansion.

### TD-08 — Bounded artifact archival before full GC policy
- **Type.** Sanctioned.
- **Description.** The Artifact Store enforces immutability and lineage but ships
  without a complete garbage-collection/archival policy.
- **Why acceptable now.** Immutability and reference resolution are the
  load-bearing parts; archival is a growth-management concern that only bites at
  scale.
- **Repayment trigger & owner.** When storage growth crosses the envelope.
  **AP-206** (archival of unreferenced artifacts) with **AP-604** (envelope). Ties
  to artifact-storage Future Evolution and Risk R-19. **Immutability of
  referenced artifacts is never traded away** (anti-debt TD-A5).
- **Interest.** Unbounded storage growth and orphan accumulation until repaid.

### TD-09 — Heuristic Supervision health thresholds before learned indicators
- **Type.** Sanctioned.
- **Description.** Operational health (Healthy/Degraded/Stalled/…) is derived from
  fixed heuristic thresholds rather than tuned or learned indicators.
- **Why acceptable now.** Fixed thresholds make Supervision functional in Phase 5
  without an operational baseline to learn from.
- **Repayment trigger & owner.** When operational history supports tuning.
  **AP-501** (indicators → thresholds) with **AP-602** (history). Ties to
  operational-maturity Future Evolution.
- **Interest.** False positives/negatives in stall/degradation detection until
  repaid; bounded because Supervision only *recommends*, never controls
  (anti-debt TD-A6 boundary).

### TD-10 — Mock/local runtime for early pipeline validation
- **Type.** Sanctioned.
- **Description.** Early end-to-end validation may use a mock or local-shell
  runtime before a production runtime adapter exists.
- **Why acceptable now.** It exercises Orchestration, Execution, events, and
  checkpoints without depending on an external runtime being ready.
- **Repayment trigger & owner.** When the Harness SDK stabilizes, replace with a
  real adapter. **AP-403**. Ties to runtime-adapter Future Evolution.
- **Interest.** Validation results not representative of a real runtime until
  repaid; bounded by replacing before the Phase 4 gate.

---

## Forbidden Debt (anti-debt — must hold from day one)

These are architecturally load-bearing. They are cheap to honor at the start and
prohibitively expensive to retrofit. Each is enforced at a gate or in CI.

| ID | Rule (must hold) | Type | Enforced by |
|----|------------------|------|-------------|
| TD-A1 | Exactly one Work Package schema — never per-layer WP shapes | Forbidden | AP-003, AP-105 + multi-seam contract test |
| TD-A2 | Idempotency from the first consumer — shared mechanism, never per-subsystem | Forbidden | AP-202 + duplicate-delivery property test |
| TD-A3 | One-way dependency flow — no lower layer importing a higher layer | Forbidden | AP-005 architecture-fitness test |
| TD-A4 | Evidence-based completion — never runtime self-report/confidence | Forbidden | AP-405 (no self-completion), AP-502 (evidence) |
| TD-A5 | Immutable audit and immutable referenced artifacts — never overwrite | Forbidden | AP-111, AP-206 (artifacts), AP-406 (audit) |
| TD-A6 | No runtime leakage above Execution — uniform interface only | Forbidden | AP-403 SDK + AP-005 fitness test |
| TD-A7 | Single authoritative source of truth per persistence concern | Forbidden | AP-001 persistence contract; AP-203/AP-204 |
| TD-A8 | One field-ownership across the four registries | Forbidden | AP-002 ownership table; AP-108/AP-109 |
| TD-A9 | One event per state transition | Forbidden | AP-203 transition→event invariant |
| TD-A10 | Knowledge ingestion gated on validation — no unverified learning | Forbidden | AP-601 (validated input), AP-602 (ingestion gate) |

### TD-A1 — Single Work Package schema
- **Type.** Forbidden.
- **Why forbidden.** The WP is the universal runtime contract; three divergent
  definitions exist today (docs 04/05). Per-layer shapes guarantee
  producer/consumer drift (Risk R-04) that no later phase can cheaply unwind.
- **Owner.** **AP-003** reconciles; **AP-105** implements one schema; every
  binding layer (Planning, Orchestration, Execution, Validation) passes the
  multi-seam contract test.
- **Interest if incurred.** The pipeline cannot integrate; the highest
  contract-drift cost in the platform.

### TD-A2 — Idempotency from the first consumer
- **Type.** Forbidden.
- **Why forbidden.** Delivery is at-least-once and transitions are
  one-event-each; without a shared idempotency mechanism from the first consumer,
  duplicates silently corrupt state (Risk R-05), and per-subsystem dedup
  guarantees gaps.
- **Owner.** **AP-202** (shared idempotency + correlation), used by **AP-201**
  and **AP-203**; proven by a duplicate-delivery property test.
- **Interest if incurred.** Silent, compounding state corruption — the most
  expensive class of defect to diagnose after the fact.

### TD-A3 — One-way dependency flow
- **Type.** Forbidden.
- **Why forbidden.** The phase order and the whole architecture assume lower
  layers never depend on higher ones. A single wrong-direction import erodes the
  layering and reintroduces circular coupling.
- **Owner.** **AP-005** architecture-fitness test fails the build on a
  wrong-direction dependency.
- **Interest if incurred.** Progressive architectural decay; phases stop being
  independently buildable.

### TD-A4 — Evidence-based completion
- **Type.** Forbidden.
- **Why forbidden.** "Completion by evidence, not runtime confidence" is a core
  invariant. Letting a runtime self-declare completion collapses Validation and
  makes the whole supervision/validation/recovery loop meaningless.
- **Owner.** **AP-405** (Execution never self-completes; emits evidence
  *candidates*), **AP-502** (completion only from verified evidence).
- **Interest if incurred.** Unverifiable completions; Knowledge poisoned by
  unvalidated outcomes; the platform's central guarantee lost.

### TD-A5 — Immutable audit and immutable referenced artifacts
- **Type.** Forbidden.
- **Why forbidden.** Replay, recovery, lineage, and governance all assume audit
  records and referenced artifacts are never overwritten. Mutating them breaks
  checkpoint restore, lineage walks, and the governance audit trail.
- **Owner.** **AP-111**/**AP-206** (new-version-never-overwrite), **AP-406**
  (immutable governance audit).
- **Interest if incurred.** Irrecoverable history; checkpoint restore and audit
  become untrustworthy. (Archival/GC of *unreferenced* artifacts is the
  *sanctioned* TD-08; immutability of referenced artifacts is never traded.)

### TD-A6 — No runtime leakage above Execution
- **Type.** Forbidden.
- **Why forbidden.** "Skills describe capability, not runtime" and runtime
  independence depend on runtime-specific concerns staying below the uniform
  Runtime Interface. Leakage upward (Risk R-12) couples Planning/Skills/WP to a
  runtime and defeats adapter replaceability.
- **Owner.** **AP-403** (uniform interface + adapter SDK), **AP-005** fitness
  test; WP/Skill schemas (AP-105/AP-107) carry no runtime references.
- **Interest if incurred.** Runtime independence becomes fiction; swapping a
  runtime requires reshaping the understanding pipeline.

### TD-A7 — Single authoritative source of truth per persistence concern
- **Type.** Forbidden.
- **Why forbidden.** Event, State, and Checkpoint must not each claim to be
  authoritative for "where is this execution now" (Risk R-01/R-02). Multiple
  sources of truth make recovery non-deterministic.
- **Owner.** **AP-001** persistence contract; **AP-203** (state), **AP-204**
  (checkpoint) implement against it.
- **Interest if incurred.** Recovery cannot reliably answer the current position;
  forces rework of all of Phase 2.

### TD-A8 — One field-ownership across the four registries
- **Type.** Forbidden.
- **Why forbidden.** Provider/Availability/Health/Version must have exactly one
  owning registry, or Harness/Runtime/Resource/Capability registries drift (Risk
  R-14).
- **Owner.** **AP-002** ownership table; **AP-108**/**AP-109** schemas derive from
  it and conformance-test it.
- **Interest if incurred.** Conflicting availability/health reports; allocation
  decisions made on stale or contradictory data.

### TD-A9 — One event per state transition
- **Type.** Forbidden.
- **Why forbidden.** Replay correctness and the event-as-record-of-change model
  depend on each transition emitting exactly one event. Zero or multiple events
  per transition makes replay and audit diverge from reality.
- **Owner.** **AP-203** transition→event invariant test.
- **Interest if incurred.** Replay and audit no longer reconstruct true state;
  undermines TD-A2 and TD-A7.

### TD-A10 — Knowledge ingestion gated on validation
- **Type.** Forbidden.
- **Why forbidden.** Reflection and Knowledge must source only from validated
  evidence; ingesting unverified outcomes poisons future planning (Risk R-18) and
  violates the evidence invariant.
- **Owner.** **AP-601** (only validated input; outputs are candidates),
  **AP-602** (ingestion gated on validation).
- **Interest if incurred.** Self-reinforcing bad knowledge; the learning loop
  amplifies errors instead of correcting them.

---

## How Debt Is Tracked Through the Phases

- **Sanctioned debt** is admitted at the phase that takes the shortcut and is
  reviewed at every later phase gate until its repayment AP closes it. The
  repayment trigger is a gate item, not a backlog wish.
- **Forbidden debt** is checked at every gate. A violation is a gate failure, not
  a tracked item: it is remediated before later-phase work proceeds (see
  `01_PHASES.md`, Phase Validation Gate Pattern).

| Phase | Sanctioned debt admitted | Forbidden rules first enforced |
|-------|--------------------------|--------------------------------|
| 0 | — | TD-A1, TD-A3, TD-A7, TD-A8 (decisions/scaffold) |
| 1 | — | TD-A1, TD-A5, TD-A8 (schemas) |
| 2 | TD-04, TD-08 | TD-A2, TD-A5, TD-A7, TD-A9 (substrate) |
| 3 | TD-01, TD-02, TD-07 | TD-A6 (no runtime in WP/Skill) |
| 4 | TD-03, TD-10 | TD-A4, TD-A5 (audit), TD-A6 |
| 5 | TD-09 | TD-A4 (evidence-based completion) |
| 6 | TD-05, TD-06 | TD-A10 |

Each sanctioned item maps to a "Future Evolution" the architecture explicitly
defers; each forbidden item maps to an architectural invariant in
`00_IMPLEMENTATION_OVERVIEW.md`. Debt IDs are stable; do not renumber.
