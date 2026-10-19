# Execution Strategy — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Primary source: `docs/v2/13_EXECUTION_STRATEGY.md`
Binding: ADR-004 (single approval taxonomy; policy/validation/recovery precedence;
determinism boundaries), ADR-001 (state is projection)

> Logical specification only. No serialization, storage, API, or code. Fields are
> logical (name + meaning + required/optional).

---

## 1. Purpose

An **Execution Strategy** declares *how* operational work should be coordinated
and governed during execution, without performing any execution. Planning
determines *what* work happens (Plan + Work Packages); the Execution Strategy
determines *how* that work is coordinated, approved, retried, timed, validated,
recovered, and checkpointed.

It sits logically between Planning and Orchestration: it converts a plan into
declarative operational behavior that Orchestration enacts. It is **runtime-,
provider-, and transport-agnostic** and never references specific
implementations. Orchestration never invents coordination behavior not declared
in the Strategy (INV-05).

The Strategy *declares* policy; it never *evaluates* it. Validation owns the
verdict; Recovery owns strategy selection at failure time; Governance/Policy owns
authorization (ADR-004 §3.4 — declaration ≠ evaluation).

---

## 2. Ownership

- **Produced by:** Planning. Planning authors Execution Strategies as part of the
  Plan (INV-03).
- **State owned by:** Planning (authoring/finalization/supersession). Per ADR-001
  any current state is a projection of the Event Log.
- **Consumed by:** Orchestration (enacts coordination, approval, retry, timeout,
  checkpoint policy) and Recovery (consults recovery/retry policy at failure
  time). Governance evaluates the declared approval level against Policy.
  Supervision evaluates execution against the Strategy's expected behavior.
- **Boundary:** An Execution Strategy never executes, never selects runtimes,
  never validates Evidence, and never supervises (doc 13 boundaries; INV-05).

---

## 3. Lifecycle

State is a projection of the Event Log (ADR-001, INV-13/INV-14); every transition
emits exactly one Event (INV-15). A Strategy is a declarative, largely static
artifact; its lifecycle tracks authoring and applicability, not live execution
progress (that lives in the Execution Graph / Work Package state).

| State | Meaning |
|-------|---------|
| `Draft` | Under construction by Planning. |
| `Active` | Finalized; in force for the Work Packages / graph nodes that reference it. |
| `Superseded` | Replaced by a newer Strategy version (e.g. on replanning). |
| `Retired` | No longer referenced by any live Work Package or graph node. |

```
Draft → Active → Superseded | Retired
Active → Retired
```

A Strategy is reusable: multiple Work Packages may reference the same Active
Strategy.

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| `identity` | Stable unique id; participates in correlation/trace lineage. |
| `coordination` | The coordination model: e.g. `Sequential`, `Parallel`, `Hybrid`, `Pipeline`, `EventDriven`, `ApprovalDriven`. Declares ordering/concurrency intent; Orchestration enacts it. |
| `runtime_policy` | Required capabilities, runtime preferences, and runtime restrictions — expressed as capability requirements, **never specific implementations** (provider independence, ADR-002). Selection remains Orchestration's (INV-37). |
| `approval_policy` | The required approval level using the **single platform taxonomy** (ADR-004 §3.3): `Automatic`, `HumanReview`, `MultiStage`, `Deferred`. The Strategy declares the level; Governance evaluates and enforces it. No divergent approval vocabulary is permitted. |
| `retry_policy` | Declarative retry behavior: e.g. `NeverRetry`, `FixedRetry`, `ExponentialRetry`, `RuntimeSwitch`, `HumanEscalation`, including bounds. Declares intent; Recovery selects the actual strategy at failure (ADR-004 §3.2 — retry is not a Policy Decision). |
| `timeout_policy` | Maximum execution duration, maximum waiting duration, and maximum retry duration. Timeout elapse is a recoverable failure category (ADR-004 §7). |
| `validation_policy` | Declares required Evidence, required validators, and completion conditions. **Declaration only** — the Validation layer owns the verdict (INV-20, ADR-004 §3.4). Execution never determines completion. |
| `recovery_policy` | Declarative recovery behavior: `Pause`, `Resume`, `Retry`, `Escalate`, `Abort`, with deterministic selection rules. Declares options; Recovery owns selection (INV-22, ADR-004 §3.2). |
| `checkpoint_policy` | Checkpoint frequency, required checkpoints, and recovery checkpoints. Long-running execution must be checkpoint-aware (INV-18). |

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| `escalation_policy` | How and to whom unresolved conditions (e.g. `Deferred` approval timeouts, exhausted retries) escalate. |
| `expected_behavior` | The declared assumptions, coordination model description, and expected operational behavior Supervision evaluates execution against. |
| `cost_policy` | Declarative cost bounds / cost-awareness inputs (deferred cost-aware strategies extend here). |
| `skill_overrides` | Where this Strategy intentionally overrides a Skill's default validation/recovery guidance, recorded explicitly (precedence: Governance/Policy → Execution Strategy → Skill default, ADR-004 §3.4). |
| `correlation` | Correlation/trace identifiers tying the Strategy to its Plan/Goal lineage. |
| `version` | Strategy version for supersession tracking. |

---

## 6. Invariants

- **INV-05:** The Execution Strategy declares coordination behavior and never
  executes; Orchestration enacts it and never invents coordination not declared
  here.
- **ADR-004 §3.3 (single approval taxonomy):** `approval_policy` uses only
  `{Automatic, HumanReview, MultiStage, Deferred}`. Governance and Execution
  Strategy share exactly this vocabulary.
- **ADR-004 §3.4 (precedence):** Governance/Policy (hard constraints) → Execution
  Strategy → Skill default. The Strategy is authoritative over Skill defaults for
  validation/recovery guidance but subordinate to Policy.
- **Declaration ≠ evaluation:** The Strategy declares validation and recovery
  policy; Validation owns the verdict (INV-20/INV-21) and Recovery owns strategy
  selection (INV-22). The Strategy never decides completion or executes recovery.
- **ADR-004 §3.2:** Retry/Rollback/Abort are recovery strategies, not governance
  Policy Decisions; the Strategy declares retry/recovery options, Recovery
  selects.
- **INV-28:** Approval/governance policy declared here is *evaluated only by the
  Policy Engine*; the Strategy hardcodes no governance rule.
- **ADR-002 / INV-37:** `runtime_policy` is capability-based and provider-
  independent; it never names a runtime implementation and never selects one.
- **INV-07 / INV-13–INV-15:** One Strategy schema; state is a projection; every
  transition emits one Event.

---

## 7. Relationships

- **Part of / referenced by `plan.md`:** Planning authors the Strategy as part of
  the planning cycle.
- **Referenced by `work_package.md`** (`execution_strategy_ref`) and by
  **`execution_graph.md`** Nodes: the unit of work carries its governing Strategy
  by reference; a Strategy may be shared (reusable) across many Work Packages.
- **Evaluated against `policy.md`:** Governance evaluates the declared
  `approval_policy` and constraints via the Policy Engine (INV-28).
- **Consumed by `execution_graph.md` policies:** graph-level Policies and the
  Strategy together govern enactment; Approval edges in the graph correspond to
  the Strategy's `approval_policy`.
- **References `skill.md`:** `skill_overrides` records where the Strategy
  overrides a Skill's default validation/recovery guidance (precedence per
  ADR-004 §3.4).
- **Read by** Orchestration (enact), Recovery (consult), Supervision (evaluate
  against expected behavior) — none mutate it.

---

## 8. Versioning Rules

- **Additive evolution.** New optional fields (adaptive/learned/cost-aware
  strategy inputs, deferred in doc 13) are added without breaking the schema.
  Required policy fields are never removed or repurposed in place.
- **Approval taxonomy is closed and versioned.** The four approval terms are the
  shared vocabulary; new approval semantics require an ADR superseding ADR-004
  §3.3, never an ad-hoc term.
- **Strategy changes create a new version**, not in-place mutation of an Active
  Strategy in force; the prior version is retained immutably and marked
  `Superseded` (ADR-001 replay/audit). Identity is stable within a version.
- **Predicate/policy vocabulary grows additively** (ADR-004 §10): new retry/
  recovery/validation options extend the declared sets without redefining the
  contract or the evaluation boundary.
