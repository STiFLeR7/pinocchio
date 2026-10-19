# Nexus v2 — Risk Register

Status: Engineering Plan
Scope: Ranked, AP-tied risk register for implementing the Nexus v2 target
architecture (`docs/v2/`) along the phases of `01_PHASES.md` and the Action
Points of `02_ACTION_POINTS.md`.

---

## How to Read This Register

Each risk has a stable identifier (`R-NN`), a category, a likelihood and impact
rating, a derived severity, an early-warning trigger, a mitigation strategy, the
Action Point(s) that own the mitigation, and the residual risk that remains
after the mitigation is in place.

**Severity** is a function of likelihood × impact:

| Impact ↓ / Likelihood → | Low    | Med      | High     |
|-------------------------|--------|----------|----------|
| **High**                | Medium | High     | Critical |
| **Med**                 | Low    | Medium   | High     |
| **Low**                 | Low    | Low      | Medium   |

Risk IDs are stable. Do not renumber; deprecate and supersede. Every risk ties
to one or more Action Points. A risk is "owned" by the AP whose acceptance
criteria, when met, retire or contain it.

Risks are sorted by severity (Critical → High → Medium → Low).

---

## Severity Summary Matrix

| Severity | Count | Risk IDs |
|----------|-------|----------|
| Critical | 4     | R-01, R-02, R-03, R-04 |
| High     | 8     | R-05, R-06, R-07, R-08, R-09, R-10, R-11, R-12 |
| Medium   | 7     | R-13, R-14, R-15, R-16, R-17, R-18, R-19 |
| Low      | 2     | R-20, R-21 |
| **Total**| **21**|        |

By category: Architectural 5 · Implementation 5 · Operational 5 ·
Scalability/Maintainability 5 · Migration 1.

---

## Top 5 to Watch

These five have the highest combination of severity, blast radius, and how early
they can derail the program. They are the standing agenda for every phase-gate
review.

1. **R-01 — Persistence model undecided** (AP-001). Gates all of Phase 2. Wrong
   choice forces re-implementation of Event, State, and Checkpoint.
2. **R-04 — Work Package contract drift** (AP-105). Defined three different ways
   today; the highest contract-drift risk in the platform. If the producer
   (Planning) and consumer (Execution) bind to different shapes, the pipeline
   cannot integrate.
3. **R-02 — Execution Graph as single source of truth** (AP-104, AP-307). One
   topology drives orchestration, recovery, and resume. Its persistence and
   consistency must be airtight or the operation has no recoverable position.
4. **R-05 — Duplicate-driven state corruption** (AP-201, AP-202, AP-203).
   At-least-once delivery plus "exactly one event per transition" with no shared
   idempotency mechanism corrupts state silently and irreversibly.
5. **R-09 — Non-rollbackable side effects** (AP-503). Sent emails and external
   API mutations cannot be rolled back; recovery can leave the world in an
   inconsistent state with no clean path back.

---

## Risk Register

### R-01 — Persistence / event-sourcing model undecided
- **Category.** Architectural
- **Likelihood.** High · **Impact.** High · **Severity.** Critical
- **Description.** The single source of operational truth across Event (23),
  State (24), and Checkpoint (25) is deferred in every infrastructure document.
  Three potential sources of truth (event log, stored state, checkpoints)
  coexist with no ruling on which is authoritative for "where is this execution
  now." Every Phase 2 substrate AP implements against this decision.
- **Trigger / early-warning.** Phase 2 work starting while ADR-001 is still in
  "proposed" state; two substrate APs assuming different authoritative stores;
  recovery spike unable to answer "reconstruct from what?"
- **Mitigation.** Ratify ADR-001 in Phase 0 with a worked failure-and-recovery
  example tracing one Work Package's state/events/checkpoints; publish a one-page
  persistence contract that all Phase 2 APs cite. No Phase 2 AP may begin until
  the ADR is accepted, not merely proposed.
- **Owning AP(s).** AP-001 (decision); AP-101, AP-201, AP-203, AP-204 (implement
  the contract).
- **Residual risk.** Low–Medium. A ratified model can still prove operationally
  awkward at scale; contained because the decision is recorded, testable, and
  rehearsed against a recovery example before substrate build.

### R-02 — Execution Graph as single source of truth (single point of failure)
- **Category.** Architectural
- **Likelihood.** Med · **Impact.** High · **Severity.** High → escalated to
  Critical given dependence of Orchestration, Recovery, and resume on one object
- **Description.** A single Execution Graph is the operational topology that
  Orchestration drives, Recovery restores, and resume reconstructs from. Any
  corruption, divergence, or non-airtight persistence of the graph removes the
  platform's only authoritative "current position," making the whole operation
  unrecoverable on the critical path.
- **Trigger / early-warning.** Graph state mutated outside the State Model;
  resume-from-state test failing intermittently; graph and event log disagreeing
  on node status after a forced failure.
- **Mitigation.** Treat the Execution Graph schema as airtight: acyclicity
  validator, typed edges, deterministic conditions, recovery edges, and
  resumable node state (AP-104, AP-307). Persist and mutate graph state only
  through the State Model and event log per the AP-001 persistence contract.
  Replay tests must reconstruct identical graph state.
- **Owning AP(s).** AP-104 (schema), AP-307 (builder), AP-203 (state),
  AP-001 (persistence).
- **Residual risk.** Medium. Static graph remains a coordination bottleneck and
  a single object to keep consistent; dynamic expansion is explicitly deferred
  (see R-17).

### R-03 — Determinism asserted but inherently non-deterministic in places
- **Category.** Architectural
- **Likelihood.** High · **Impact.** High · **Severity.** Critical
- **Description.** The architecture asserts deterministic policy evaluation and
  replayable decisions, but Intent Resolution and Execution use LLMs, and
  Governance approvals and Validation include human steps — all non-deterministic.
  If determinism is assumed uniformly, replay, recovery, and "explainable
  decision" guarantees become misleading where they cannot hold.
- **Trigger / early-warning.** Replay producing divergent downstream state at an
  LLM or human step; recovery logic assuming a step is reproducible when it is
  not; tests asserting bit-identical re-execution of an LLM call.
- **Mitigation.** In ADR-004 define explicit determinism boundaries: where it is
  guaranteed (policy evaluation, state transitions, graph conditions) and where
  it is not (LLM intent, LLM execution, human approval/validation). Persist
  non-deterministic outputs as recorded facts so replay reproduces *recorded
  outcomes*, not the computation. Document LLM runtimes as "deterministic
  attempt," not guarantee.
- **Owning AP(s).** AP-004 (boundary definition); AP-205 (deterministic policy
  core); AP-301, AP-403 (LLM steps); AP-502, AP-406 (human steps).
- **Residual risk.** Medium. Replay reproduces recorded outcomes but not the
  reasoning that produced them; acceptable if the boundary is documented and
  enforced.

### R-04 — Work Package contract drift (highest contract risk)
- **Category.** Architectural
- **Likelihood.** High · **Impact.** High · **Severity.** Critical
- **Description.** The Work Package is the universal runtime contract, yet it is
  defined three different ways across docs 04 and 05. If not collapsed into one
  schema before Phase 1, the producer (Planning) and the consumer (Execution),
  plus Orchestration and Validation, bind to divergent shapes and the pipeline
  cannot integrate. This is the single highest contract-drift risk in the
  platform.
- **Trigger / early-warning.** Two layers referencing different WP fields;
  multi-seam contract test absent or passing against only one definition; the
  embedded Context Package shaped differently by producer and consumer.
- **Mitigation.** Reconcile to one WP definition in ADR-003, then implement a
  single unified schema with its status machine (AP-105). Every binding layer
  (Planning, Orchestration, Execution, Validation) must pass a multi-seam
  contract test against this one schema before Phase 4.
- **Owning AP(s).** AP-003 (reconciliation), AP-105 (unified schema), AP-309
  (assembly), AP-401/AP-405/AP-502 (consumers).
- **Residual risk.** Low. Once one schema exists and contract tests guard every
  seam, drift is caught at build time.

### R-05 — Duplicate-driven state corruption (no shared idempotency)
- **Category.** Implementation
- **Likelihood.** High · **Impact.** High · **Severity.** High
- **Description.** The Event Model specifies at-least-once delivery and "exactly
  one event per state transition" and *requires* consumer idempotency, but
  specifies no shared idempotency mechanism. Without one, each subsystem reinvents
  dedup, and any gap lets a duplicate event drive a second state change —
  silent, compounding corruption.
- **Trigger / early-warning.** A consumer applying a transition twice under
  duplicate delivery; per-subsystem ad-hoc dedup appearing in review; missing
  idempotency keys on emitted events.
- **Mitigation.** Build the shared idempotency + correlation framework (AP-202)
  before any consumer, and mandate its use. Prove with a duplicate-delivery
  property test that a reference consumer makes no duplicate state change.
- **Owning AP(s).** AP-202 (framework), AP-201 (delivery), AP-203 (state
  consumer).
- **Residual risk.** Low–Medium. Centralized idempotency closes the systemic
  hole; residual risk is consumers that bypass the framework, caught by the
  anti-debt rule (see `06_TECHNICAL_DEBT.md`, TD on idempotency).

### R-06 — Policy Engine as central evaluator on the hot path
- **Category.** Implementation
- **Likelihood.** Med · **Impact.** High · **Severity.** High
- **Description.** The Policy Engine is called on every Planning, Execution,
  Recovery, Governance, and Validation decision. As a single central evaluator it
  is both a latency bottleneck and a single point of failure on the critical
  decision path.
- **Trigger / early-warning.** Decision latency rising with policy-set size;
  evaluator becoming a synchronous dependency with no fallback; throughput
  capped by policy evaluation under load tests.
- **Mitigation.** Keep evaluation deterministic and side-effect free so results
  are cacheable; version evaluation records; provide simulation that never
  touches production (AP-205). Establish a performance envelope and backpressure
  for the evaluator under AP-604.
- **Owning AP(s).** AP-205 (engine), AP-004 (condition language), AP-604
  (performance envelope).
- **Residual risk.** Medium. Centralization persists by design; mitigated by
  caching, determinism, and a measured performance envelope, not eliminated.

### R-07 — Context source sprawl with no connector/auth contract
- **Category.** Implementation
- **Likelihood.** High · **Impact.** Med · **Severity.** High
- **Description.** Context Engineering ingests 10+ external sources (Repo, FS,
  Drive, Notion, Slack, Email, Calendar, Jira, Linear, …) with no connector
  contracts and no described auth/permission model. This invites connector
  sprawl and exposes external-data security and authorization gaps.
- **Trigger / early-warning.** A second connector implemented without conforming
  to a single contract; a source read without an authorization check; credentials
  handled inconsistently per connector.
- **Mitigation.** Build all context access as Context Harnesses atop the Harness
  SDK with one connector contract, an explicit authorization boundary, and
  read-only connectors first (AP-302, AP-207). Failures surface as harness
  failures; an auth-denied path is tested.
- **Owning AP(s).** AP-302 (connector framework), AP-207 (Harness SDK), AP-303
  (consumer).
- **Residual risk.** Medium. The contract bounds sprawl, but each new source
  still adds surface area; write access deferred (see `06_TECHNICAL_DEBT.md`).

### R-08 — "Minimal complete context" has no sufficiency metric
- **Category.** Implementation
- **Likelihood.** Med · **Impact.** High · **Severity.** High
- **Description.** Context Engineering must produce "minimal complete context"
  but no sufficiency metric is defined. Without one, the engine either
  under-collects (context starvation → bad plans) or over-collects (bloat,
  latency, cost), and active discovery adds unbounded latency and cost.
- **Trigger / early-warning.** Planning failing on under-specified context that
  passed validation; Context Packages growing without bound; discovery latency
  dominating pipeline time.
- **Mitigation.** Define validation dimensions (completeness, consistency,
  availability, freshness, authorization, quality) with confidence and
  known-unknowns; have Context Engineering certify exactly one Context Package
  per Goal and refuse to certify incomplete context; have Planning hard-refuse an
  invalid package (AP-303, AP-306).
- **Owning AP(s).** AP-303 (engine + validation), AP-306 (refusal on invalid
  context), AP-103 (schema fields).
- **Residual risk.** Medium. Validation dimensions approximate sufficiency but do
  not formally guarantee minimality; refined as Knowledge feedback matures
  (AP-603).

### R-09 — Non-rollbackable side effects leave inconsistent state
- **Category.** Operational
- **Likelihood.** High · **Impact.** High · **Severity.** Critical
- **Description.** Recovery is explicitly not universally rollbackable. Side
  effects such as sent emails and external API mutations cannot be undone. After
  a failure, restoring from checkpoint can leave the external world inconsistent
  with restored internal state, with no clean recovery.
- **Trigger / early-warning.** A Rollback strategy selected for a node that
  performed an irreversible action; recovery restoring state without accounting
  for already-committed external effects; no classification of effects as
  reversible vs. irreversible.
- **Mitigation.** In Recovery, classify failures and restrict Rollback/Checkpoint
  Restore to reversible effects; for irreversible effects use Continue/Resume,
  compensating actions, or Human Review rather than silent rollback; never
  discard validated evidence (AP-503). Pair with checkpoint pre-restore
  validation (AP-204).
- **Owning AP(s).** AP-503 (recovery strategy selection), AP-204 (restore
  validation), AP-106 (recovery policy).
- **Residual risk.** Medium–High. Some irreversible effects have no clean
  recovery by nature; the platform can detect and escalate but not undo —
  residual risk is intrinsic and must be operationally accepted.

### R-10 — Human escalation paths have no timeout
- **Category.** Operational
- **Likelihood.** High · **Impact.** Med · **Severity.** High
- **Description.** Human escalation (Governance approval, Validation human/hybrid,
  Recovery human review) has no timeout. An operation can stall indefinitely
  waiting on an operator, consuming reserved resources and blocking dependent
  work.
- **Trigger / early-warning.** An approval-required or escalated step with no
  deadline; resources held by a stalled, human-blocked operation; no alert on
  long-pending human steps.
- **Mitigation.** Every human-blocking step carries a timeout with a defined
  expiry action; Recovery escalation acceptance criteria require a timeout;
  Supervision detects stalled operations and emits alerts/recommendations
  (AP-503, AP-406, AP-501).
- **Owning AP(s).** AP-503 (escalation timeout), AP-406 (approval workflow),
  AP-501 (stall detection).
- **Residual risk.** Low–Medium. Timeouts bound the stall; the trade-off between
  waiting and a forced expiry action remains a policy decision per operation.

### R-11 — Runtime capability over-claiming (no trust/verification model)
- **Category.** Operational
- **Likelihood.** Med · **Impact.** High · **Severity.** High
- **Description.** Runtime capability advertisement is self-reported with no
  trust or verification model. A runtime can over-claim capabilities; Capability
  Resolution and Orchestration may then assign work a runtime cannot actually
  perform, surfacing only as a late execution failure.
- **Trigger / early-warning.** A WP assigned on advertised capability then
  failing for "unsupported"; no conformance check between advertised and actual
  capability; adapters self-declaring without validation.
- **Mitigation.** Require capability-advertisement conformance tests in the
  adapter SDK and per adapter; treat advertised capability as a claim verified by
  the adapter conformance suite; let failures surface as harness failures to
  Supervision (AP-403, AP-404, AP-207, AP-501).
- **Owning AP(s).** AP-403/AP-404 (adapters + conformance), AP-207 (registry),
  AP-304 (resolution).
- **Residual risk.** Medium. Conformance tests reduce but do not eliminate
  over-claiming for runtimes whose behavior varies by input; a full trust model
  is deferred.

### R-12 — Runtime abstraction leakage across heterogeneous runtimes
- **Category.** Operational
- **Likelihood.** Med · **Impact.** High · **Severity.** High
- **Description.** Claude Code, browser, Gemini CLI, and a Human Operator have
  wildly different semantics, yet are exposed through one uniform Runtime
  Interface. A single uniform contract may not capture their differences, leaking
  runtime-specific concerns upward and violating the "no runtime leakage above
  Execution" invariant.
- **Trigger / early-warning.** Runtime-specific fields appearing in a Work
  Package or above Execution; an adapter unable to honor the uniform interface
  without escaping it; the same WP behaving incompatibly across adapters.
- **Mitigation.** Define the uniform Runtime Interface and adapter SDK with
  cancel/recovery/event/artifact obligations; validate runtime independence by
  running the same WP unmodified across ≥3 adapters including Human Operator
  (AP-403, AP-404). Enforce the no-leakage rule as an anti-debt rule (see
  `06_TECHNICAL_DEBT.md`).
- **Owning AP(s).** AP-403 (SDK + first adapter), AP-404 (heterogeneous
  adapters), AP-005 (dependency-direction fitness test).
- **Residual risk.** Medium. The abstraction holds for the first adapters; new
  runtime categories may stress it and require SDK evolution.

### R-13 — Non-observable / uncooperative runtimes break the observability invariant
- **Category.** Operational
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** The platform invariant "every execution observable" assumes
  cooperative runtimes that emit events and observations. A non-cooperative or
  opaque runtime (or human) breaks this, leaving Supervision blind and creating
  observability gaps in the end-to-end trace.
- **Trigger / early-warning.** A runtime emitting no progress/health events;
  trace coverage gaps in the observability audit; Supervision unable to derive
  health for a given adapter.
- **Mitigation.** Require minimal event/health emission in the adapter SDK
  conformance; for opaque runtimes, derive health from external probes and
  timeouts; measure trace coverage and flag gaps in operational maturity
  (AP-501, AP-604, AP-403).
- **Owning AP(s).** AP-501 (health derivation), AP-604 (trace coverage),
  AP-403/AP-404 (adapter emission).
- **Residual risk.** Medium. Fully opaque runtimes can only be observed
  externally (timeouts, probes), not internally.

### R-14 — Registry convergence drift (Harness · Runtime · Resource · Capability)
- **Category.** Architectural
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** Four near-identical registration contracts (docs 11, 15, 21,
  22) overlap on Provider, Availability, Health, and Version. Without one
  field-ownership model, these fields gain dual owners and drift between
  registries.
- **Trigger / early-warning.** Two registries reporting different
  availability/health for the same provider; a schema (AP-108/AP-109) not derived
  from the AP-002 ownership table.
- **Mitigation.** Ratify ADR-002 with one authoritative field-ownership table
  (Capability = abstract *what*; Harness = integration boundary; Resource =
  allocatable instance; Runtime = a Harness category); derive AP-108 and AP-109
  schemas directly from it; conformance-test field ownership (AP-002, AP-108,
  AP-109).
- **Owning AP(s).** AP-002 (ownership table), AP-108 (Capability schema), AP-109
  (Resource/Harness schemas), AP-207 (registry).
- **Residual risk.** Low. With one ownership table and conformance tests, drift
  is structurally prevented.

### R-15 — Multiple un-reconciled state machines
- **Category.** Maintainability
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** Skill lifecycle, Orchestration state, Execution lifecycle,
  Validation states, and Resource availability are separate state machines. If
  not reconciled into the unified State Model, the platform holds inconsistent
  operational state and conflicting "Active" vs "Executing" vocabularies.
- **Trigger / early-warning.** A subsystem defining its own transitions outside
  the State Model engine; "Active"/"Executing" used inconsistently; a transition
  with no corresponding event.
- **Mitigation.** Drive every lifecycle through the State Machine Engine with
  illegal-transition rejection and exactly-one-event-per-transition; reconcile
  naming and Resource state per ADR-002/003 (AP-203, AP-109, AP-105).
- **Owning AP(s).** AP-203 (engine), AP-109 (resource state), AP-105 (WP state),
  AP-003 (reconciliation).
- **Residual risk.** Low–Medium. One engine reduces drift; per-subsystem state
  semantics still require discipline to keep mapped.

### R-16 — Planning estimation methodology unspecified
- **Category.** Implementation
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** Planning estimates complexity, cost, duration, and risk to
  drive strategy selection, but no estimation methodology is specified. Arbitrary
  estimates produce arbitrary strategy selection.
- **Trigger / early-warning.** Strategy selection swinging on unexplained
  estimates; estimates with no recorded basis; downstream decisions sensitive to
  unjustified numbers.
- **Mitigation.** Start with explicit, documented heuristic estimation in the
  Planning Engine with persisted rationale for every decision; treat estimation
  as sanctioned debt to be replaced by a real cost model once Knowledge feedback
  exists (AP-306, AP-603). See `06_TECHNICAL_DEBT.md`.
- **Owning AP(s).** AP-306 (heuristic estimation + rationale), AP-603 (knowledge
  feedback for a real model).
- **Residual risk.** Medium until the heuristic is replaced; bounded by requiring
  every estimate to be explainable.

### R-17 — Static graph vs. future dynamic expansion
- **Category.** Maintainability
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** The Execution Graph is built statically up front. Work that
  requires discovering new nodes mid-execution (dynamic expansion) is not
  supported, and retrofitting it touches the graph schema, builder, and
  orchestration.
- **Trigger / early-warning.** A goal class that cannot be fully decomposed
  before execution; pressure to mutate the graph during a run; orchestration
  needing nodes that did not exist at plan time.
- **Mitigation.** Keep static graphs for the first delivery; design the graph
  schema and resume-from-state to not preclude later dynamic expansion; record
  dynamic expansion as deferred Future Evolution (AP-307, AP-104). See
  `06_TECHNICAL_DEBT.md`.
- **Owning AP(s).** AP-307 (builder), AP-104 (schema).
- **Residual risk.** Medium. Static graphs limit a class of goals until dynamic
  expansion is built.

### R-18 — Knowledge growth and stale-knowledge poisoning of planning
- **Category.** Scalability
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** The operational knowledge graph grows unbounded, and stale or
  superseded knowledge can poison planning and context if freshness and
  supersession decay are not enforced. Retrieval relevance and precision are also
  unproven.
- **Trigger / early-warning.** Deprecated knowledge surfacing in plans; the graph
  growing with no archival; retrieval returning low-precision matches.
- **Mitigation.** Enforce a confidence/freshness lifecycle
  (Current/Historical/Deprecated/Archived/Superseded), gate ingestion on
  validation, exclude deprecated knowledge on retrieval, and prefer
  current/higher-confidence entries (AP-602, AP-603, AP-601). Semantic retrieval
  is sanctioned deferred debt; see `06_TECHNICAL_DEBT.md`.
- **Owning AP(s).** AP-602 (freshness/supersession), AP-603 (retrieval filtering),
  AP-601 (validated-only candidates).
- **Residual risk.** Medium. Lifecycle controls staleness; retrieval precision
  improves only as the corpus and ranking mature.

### R-19 — Artifact/lineage unbounded growth and orphans
- **Category.** Scalability
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** Artifacts are immutable-by-default across multiple storage
  backends, and the lineage graph (Goal→Plan→WP→Execution→Artifact→Knowledge)
  grows without bound. New-version-never-overwrite plus multiple backends implies
  unbounded storage, GC pressure, and orphaned artifacts/lineage nodes.
- **Trigger / early-warning.** Storage growth with no GC policy; lineage nodes
  with no resolvable references; backend cost growth tracking artifact count.
- **Mitigation.** Provide a storage-backend abstraction with reference resolution
  and lineage walks; preserve immutability while planning archival/GC of
  unreferenced artifacts; validate references resolve (AP-206, AP-111). Bounded
  GC is sanctioned deferred debt; see `06_TECHNICAL_DEBT.md`.
- **Owning AP(s).** AP-206 (store + GC), AP-111 (lineage + immutability).
- **Residual risk.** Medium. Immutability is non-negotiable; growth is managed by
  archival, not deletion of referenced artifacts.

### R-20 — Human-as-Resource scheduling assumptions
- **Category.** Maintainability
- **Likelihood.** Med · **Impact.** Low · **Severity.** Low
- **Description.** Modeling humans as allocatable Resources imports assumptions —
  scheduling, availability, utilization, failure-count — that do not hold for
  people the way they do for machine resources, risking unsafe scheduling and
  misleading metrics.
- **Trigger / early-warning.** A human scheduled like a machine; utilization or
  failure-count metrics applied to a person; allocation assuming instant
  availability.
- **Mitigation.** Model human resources explicitly without unsafe scheduling
  assumptions; route human work through the Human Operator harness with realistic
  availability and the no-timeout-free escalation rule from R-10 (AP-402, AP-404,
  AP-503).
- **Owning AP(s).** AP-402 (allocation), AP-404 (Human Operator harness), AP-503
  (escalation timeout).
- **Residual risk.** Low. Explicit human modeling avoids the worst assumptions;
  human availability remains inherently uncertain.

### R-21 — v1→v2 migration: preserving v1 guarantees while layering v2
- **Category.** Migration
- **Likelihood.** Med · **Impact.** Med · **Severity.** Medium
- **Description.** Nexus v1 exists with operational guarantees (governance,
  memory, runtime registry, communication, scheduling, agent runtime). v2 is a
  higher architecture layer. Incremental migration risks breaking v1 guarantees
  while introducing v2 objects; greenfield risks losing proven v1 operational
  behavior.
- **Trigger / early-warning.** v2 objects bypassing a v1 guarantee; a v1
  subsystem and its v2 counterpart disagreeing; no decided migration path
  (incremental vs greenfield).
- **Mitigation.** Decide the migration approach in Phase 0 alongside the
  reconciliation ADRs; where v1 subsystems map to v2 Harnesses (runtime registry,
  communication, governance), wrap them behind the Harness SDK so v1 guarantees
  are preserved as v2 integration boundaries (AP-002, AP-207, AP-001). Record as
  a cross-cutting decision.
- **Owning AP(s).** AP-002 (registry unification), AP-207 (Harness SDK as the
  wrap boundary), AP-001 (persistence reconciliation with v1 memory/state).
- **Residual risk.** Medium. Migration sequencing remains a program-level risk
  until the approach is ratified and v1↔v2 boundaries are wrapped and tested.

---

## Risk-to-Phase Map

| Phase | Primary risks in scope |
|-------|------------------------|
| 0 | R-01, R-03, R-04, R-14, R-21 (all decision/reconciliation risks) |
| 1 | R-04, R-14, R-15, R-19 (schema/contract risks) |
| 2 | R-01, R-02, R-05, R-06, R-19 (substrate risks) |
| 3 | R-07, R-08, R-16, R-17 (understanding-pipeline risks) |
| 4 | R-02, R-11, R-12, R-13, R-20 (execution-coordination risks) |
| 5 | R-09, R-10, R-13 (supervision/validation/recovery risks) |
| 6 | R-18, R-19 (knowledge/maturity risks) |

A risk is retired only when its owning AP's acceptance criteria pass at the
phase gate. Open risks for a phase are reviewed at that phase's Architecture
Review and Integration Review (see `01_PHASES.md`, Phase Validation Gate
Pattern).
