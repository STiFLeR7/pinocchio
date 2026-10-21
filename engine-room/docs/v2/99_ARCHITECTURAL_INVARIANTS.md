# Nexus v2 — Architectural Invariants

Status: Ratified (Phase 0)
Authority: These rules are permanent guardrails. They outrank convenience,
performance, and implementation simplicity. A change to any invariant requires an
ADR that supersedes the relevant decision.

> An invariant is a rule that must **never** be violated by any subsystem, in any
> phase, for any reason. Code review, architecture-fitness tests, and phase
> validation gates exist to enforce them.

---

## How to Use This Document

Each invariant has an ID (`INV-xx`), the rule, the rationale, and how it is
enforced. Invariants are grouped by concern. They are derived from the layer
rules in `01_ARCHITECTURE.md`, the object rules in `02_OBJECT_MODEL.md`, the
subsystem boundary sections of docs `03`–`26`, and the Phase-0 decisions in
`adr/ADR-001..004`.

---

## A. Layer Boundaries & Dependency Direction

**INV-01 — One-way dependency flow.** Higher (understanding) layers never depend
on lower (execution) layers at build time. Lower layers never influence
higher-level architectural decisions. *Enforced:* architecture-fitness/dependency
test (AP-005); the runtime feedback edges (Supervision→Orchestration,
Recovery→Orchestration, Knowledge→Planning) are data flows, not build
dependencies.

**INV-02 — One responsibility per layer.** No layer assumes a responsibility the
Object Model assigns to another. *Enforced:* ownership tables; review.

**INV-03 — Planning never executes.** Planning decides *what* work happens and
never performs it. *Enforced:* Planning has no runtime/harness access.

**INV-04 — Execution never plans.** Execution performs assigned Work Packages and
never decomposes goals, selects strategy, or assigns its own runtime. *Enforced:*
Execution receives Work Packages only (INV-19).

**INV-05 — Execution Strategy never executes.** It declares coordination
behavior; Orchestration enacts it. Orchestration never invents coordination not
in the Strategy.

**INV-06 — Context Engineering consumes Knowledge; it never owns it.** *Enforced:*
Knowledge is read-only to Context.

---

## B. Objects & Contracts

**INV-07 — One canonical schema per object.** Every architectural object has
exactly one schema (frozen in `contracts/`). No subsystem introduces an
alternative representation for an existing concept. *Enforced:* contract tests
(AP-006); "defined twice" scan (ADR-003).

**INV-08 — Goals describe outcomes, never procedures.** A Goal carries no plan,
work package, runtime, or step. *Enforced:* Goal contract; negative tests.

**INV-09 — Runtimes receive Work Packages, never Goals or raw operator
requests.** *Enforced:* Work Packaging is the only producer of the runtime
contract; INV-19.

**INV-10 — The Execution Graph is a sibling artifact referenced by the Plan, not
nested in it.** Dependencies are edges in the graph; there is no separate
Dependency Graph object. *(ADR-003.)*

**INV-11 — Observation is owned by Supervision.** Execution emits raw Execution
Events; only Supervision produces Observations. *(ADR-003.)*

**INV-12 — Evidence is produced by Validation; Execution produces only Evidence
Candidates.** Artifacts reference Evidence by id; they never embed it. *(ADR-003.)*

---

## C. Persistence, State & Events *(ADR-001)*

**INV-13 — The append-only Event Log is the single source of operational
truth.** Nothing not in the log is true. *Enforced:* event store is authoritative
(AP-201).

**INV-14 — State and Checkpoints are derived, never authoritative.** Current
State is a deterministic projection of the log; a Checkpoint is a snapshot tied
to a log position. Both are rebuildable from the log. *Enforced:* replay-
equivalence test (AP-203).

**INV-15 — Every operational state transition emits exactly one Event.**
*Enforced:* state-machine engine invariant (AP-203).

**INV-16 — Consumers are idempotent.** At-least-once delivery requires dedup by
event identity; duplicate or out-of-order delivery causes no duplicate state
change. *Enforced:* platform idempotency framework (AP-202).

**INV-17 — Non-deterministic values are captured as data, never recomputed on
replay.** LLM/human/clock outputs are recorded events. Replay reproduces governed
outcomes without re-inference. *(ADR-001/004.)*

**INV-18 — Every execution is checkpoint-aware.** Long-running work can resume
from the nearest valid checkpoint plus event replay — never from operator intent.
*Enforced:* recover-and-resume test (AP-204/503).

---

## D. Execution, Validation & Recovery

**INV-19 — Execution never receives raw operator requests.** Only fully-formed
Work Packages reach a runtime. *(Restates INV-09 at the execution boundary.)*

**INV-20 — Validation never trusts runtime self-reporting.** Completion is
determined from independently verifiable Evidence; a runtime "success" with
insufficient evidence does not complete the work. *Enforced:* evidence-
insufficiency test (AP-502).

**INV-21 — Execution never declares its own completion.** It exposes outputs and
failures; Validation decides completion; Recovery decides continuation.

**INV-22 — Recovery recovers, it never restarts from the Goal, never changes the
Goal or Plan, and never bypasses Governance.** Validated evidence is never
discarded; retries are always bounded. *(Doc 19; ADR-001/004.)*

**INV-23 — Supervision recommends; Orchestration acts.** Supervision observes,
derives health, and *recommends* intervention; it never directly controls
execution. Orchestration is the single owner of pause/resume/cancel control.
*(Doc 09; resolves the verb-overlap.)*

---

## E. Knowledge & Reflection

**INV-24 — Knowledge is evidence-backed.** Only validated outcomes become
Knowledge; Knowledge never originates from assumptions or unvalidated execution.
*Enforced:* validation-gated ingestion (AP-602).

**INV-25 — Reflection never updates Knowledge directly.** Reflection produces
Knowledge *Candidates*; Knowledge decides persistence. *(Doc 26.)*

**INV-26 — Planning never depends directly on Reflection.** Learning reaches
Planning only indirectly, through persisted Knowledge. *(Doc 26.)*

**INV-27 — Knowledge references Artifacts; it never duplicates their content.**
*(Doc 17.)*

---

## F. Governance, Policy & Capability

**INV-28 — Policies are evaluated only by the Policy Engine.** No subsystem
hardcodes governance rules; evaluation is centralized, data-driven, and
deterministic. *(ADR-004.)*

**INV-29 — Governance authorizes; it never executes, plans, supervises, or
validates.** It returns decisions and writes immutable audit (as log events).
*(Doc 12; ADR-001/004.)*

**INV-30 — Governed actions fail closed.** When no policy matches a governed
action, the Default Policy denies. *(ADR-004; honors v1 A-001.)*

**INV-31 — Every operational decision is explainable and auditable.** Each
governance decision, intervention, recovery choice, and validation verdict
records its rationale as log data. *(Docs 01/09/12/19; ADR-001.)*

**INV-32 — Capabilities remain provider-independent.** A Capability defines
*what* can be done with no provider/health/availability state; provider state
lives only in the Harness Registry. *(ADR-002.)*

**INV-33 — Skills describe operational capability, never runtime
implementation.** The same Skill runs on any runtime unchanged. *(Doc 06.)*

---

## G. Harness & Integration *(ADR-002)*

**INV-34 — Every external system integrates through a Harness.** Provider-specific
implementation details never leak above the Harness boundary. *(Doc 11.)*

**INV-35 — Harnesses expose capabilities, not business logic.** A Harness never
plans, understands goals, orchestrates, or creates Work Packages. *(Doc 11.)*

**INV-36 — There is one source of truth for provider availability and health: the
Harness Registry.** No other registry duplicates it. A Runtime is a Harness of
category Runtime. *(ADR-002.)*

**INV-37 — Runtime selection is Orchestration's; capability resolution returns
candidates only.** Resolution never selects a runtime; allocation never
re-discovers capabilities. *(ADR-002.)*

---

## H. Observability

**INV-38 — Every execution is observable.** A runtime that cannot expose
observable state cannot be trusted to complete governed work. *(Doc 01 Rule 8.)*

**INV-39 — Every cross-subsystem interaction is an Event with correlation and
trace identity.** Subsystems communicate through Events, not direct calls that
bypass the log. *(Doc 23; ADR-001.)*

---

## Enforcement Summary

| Mechanism | Invariants enforced |
|-----------|---------------------|
| Architecture-fitness / dependency test (AP-005) | INV-01, INV-02 |
| Contract-test harness (AP-006) | INV-07, INV-08, INV-09, INV-10, INV-11, INV-12 |
| Substrate tests (AP-201/202/203/204) | INV-13–INV-18, INV-39 |
| Execution/Validation/Recovery scenario tests (Phase 5) | INV-19–INV-23 |
| Knowledge/Reflection gate tests (Phase 6) | INV-24–INV-27 |
| Policy/Governance tests (AP-205/406) | INV-28–INV-32, INV-30, INV-31 |
| Harness conformance tests (AP-207) | INV-32–INV-37 |
| Observability/audit coverage (AP-604) | INV-31, INV-38, INV-39 |

A phase validation gate (`blueprint/v2/10_VALIDATION_STRATEGY.md`) does not pass
while any invariant it covers is violated. A violated invariant is a release
blocker, not a defect to triage.
