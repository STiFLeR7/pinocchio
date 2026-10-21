# Nexus — Architecture Constitution

Status: **Canonical.** This is the single architectural reference for Nexus v2 and beyond. Where any
other document, narrative, or diagram conflicts with this one on *architecture*, this document governs —
**except** the 39 ratified Architectural Invariants (`99_ARCHITECTURAL_INVARIANTS.md`) and the frozen
`contracts/`, which this Constitution is built to obey, not amend.

Authority basis: this Constitution **changes no invariant, no contract, and no ADR.** It reconciles the
architectural *narrative* — which has forked across five design corpora — so that the narrative finally
matches the invariants, which already form a consistent core. Every ruling below is grounded in a ratified
invariant (`INV-xx`) or an ADR (`ADR-00x`) where one exists; where none exists, the ruling is marked
**[Constitutional — ratify via new ADR]** so the reader knows what still requires a formal Phase-0 act.

First principle, against which everything is measured:

> **Runtime executes. Nexus thinks about execution.**

Read once, kept throughout: a subsystem earns its place only if it either *thinks about execution* (the
Nexus side) or *executes under Nexus's governance* (the runtime side). Anything that does neither is
removed or merged.

---

## Executive Summary

Nexus's architecture is not broken — it is **forked**. Three prior assessments established that the
subsystems are individually well-designed but exist as **five unreconciled narratives** (the numbered
layer model, `engineering/`, `runtime/`, `actuation/`, `human_interaction/`), with two direct
contradictions (who owns work-classification; who owns the human channel), three genuine voids (Policy
Engine, Estimation/Operations, durable Memory), and a linear-layer framing that no longer fits the
cross-cutting subsystems the platform has grown.

This Constitution resolves that in one move that costs nothing in invariants: **it recognizes that the 39
invariants are already a consistent constitution, and it makes the narrative conform to them.** Every
conflict lives in prose *above* the invariant layer. Concretely:

- **INV-02** ("one responsibility per layer") *requires* that "understand what the operator wants" and
  "decide how to engineer it" be **two** capabilities — which settles the Executive-Intelligence /
  Intent-Resolution fork in favor of keeping both, distinct.
- **INV-28** already *mandates* a **Policy Engine** as the sole evaluator of governance. It is not an
  optional idea; it is a ratified-but-undesigned subsystem. The Constitution elevates it to first-class.
- **INV-23** already resolves the supervise/coordinate overlap ("Supervision recommends; Orchestration
  acts; Orchestration is the single owner of pause/resume/cancel").
- **INV-11/12/20/21/22/25/37** already assign observation, evidence, completion, continuation, learning-
  persistence, and runtime-selection to exactly one owner each.

**The canonical shape.** Nexus is **not a linear stack of ~12 layers**. It is a **thin reasoning spine
riding on cross-cutting planes**, expressed as **capabilities** (verbs), not layers (nouns):

> **Understand → Reason → Ground → Contextualize → Plan → Coordinate → Execute → Act → Observe → Validate
> → Recover → Reflect → Learn**, governed throughout by **Govern (Policy + Human Interaction)** and
> measured throughout by **Operate (Observability + Operations)**, all on a **Foundation** of durable
> Memory, the Event Log, and the Harness Registry.

**What this Constitution changes about how Nexus is described:** it retires the name "Executive
Intelligence," splits its responsibilities correctly (Understand vs Reason), promotes the Policy Engine
and Operations to first-class capabilities, folds Communication/Channel-Harness into the Communication
*Harness category* + Human Interaction, merges Execution-Strategy/Skill-Selection/Work-Packaging into
Planning-parameterized-by-Strategy, and reframes the whole system from layers to capabilities on planes —
**without violating a single invariant.**

**Final answer to "is the architecture ready to build against?"** Yes — *this* document is the stable
foundation the three assessments were converging toward. Future subsystems (Engineering Intelligence,
Repository Intelligence, Policy Engine, Operations, Estimation, Human Interaction) are now to be built
against this Constitution, each in exactly one capability, each with one owner.

---

## Architectural Philosophy

Six principles. Each is a lens for evaluating any future subsystem.

1. **Runtime executes; Nexus thinks about execution.** The dividing line of the whole system. Reasoning,
   grounding, planning, governance, and learning are Nexus. Doing the work is the runtime, behind a
   replaceable Harness (INV-34/35/36).

2. **Capabilities, not layers.** A capability is a *verb the platform performs* with one owner. Layers
   are an implementation of dependency order, not the primary model. We count owners, not layers.

3. **One responsibility, one owner, one decision-point.** INV-02. If two subsystems can decide the same
   thing, the architecture is wrong, not the code. Every decision in this document has exactly one owner.

4. **Reason freely, then commit to the record.** Reasoning (LLM/heuristic) is confined to the *decide*
   capabilities and *always* emits an immutable recorded decision (INV-17). After emission, everything is
   deterministic and replayable. This is the determinism seam, applied uniformly.

5. **Govern by policy, fail closed.** No subsystem hardcodes governance; the Policy Engine evaluates all
   policy, deterministically, and denies by default (INV-28/29/30). Governance authorizes; it never acts.

6. **Evidence over confidence; the log is truth.** Completion is evidence-based (INV-20); the append-only
   Event Log is the single source of operational truth (INV-13); every cross-subsystem interaction is a
   correlated event (INV-39). Nothing not in the log is true.

---

## Canonical Capability Model

Nexus performs **thirteen operational capabilities** on the spine, **three governing/operating
capabilities** across all planes, and rests on **one Foundation**. Each has: purpose · owner · inputs ·
outputs · responsibilities · non-responsibilities. "Owner" names the single subsystem accountable.

### The Reasoning Spine (sequential; INV-01 one-way flow)

**1. UNDERSTAND** — *what does the operator want?*
- **Owner:** Intent Resolution (`docs/v2/16`; contract `intent.md`, `goal.md`).
- **Inputs:** raw operator request, constraints, conversation. **Outputs:** a **Goal** (frozen contract;
  outcomes never procedures — INV-08).
- **Responsibilities:** normalize request → Goal; detect domain; resolve ambiguity (may clarify via Human
  Interaction *before* emitting). **Reasons** (may use an LLM), emits a recorded Goal.
- **Non-responsibilities:** does **not** classify engineering *kind*, choose skills, estimate, or set
  rigor. [Constitutional] Retire the numbered model's assignment of "classify work / identify complexity"
  here — that is Reason, not Understand.

**2. REASON** — *how should this work proceed?*
- **Owner:** **Engineering Intelligence** (EI) (`docs/v2/engineering/`; output = **Engineering
  Strategy**). [Constitutional — ratify via new ADR-005; the name "Executive Intelligence" is retired,
  its responsibilities split between Understand (intent) and Reason (approach).]
- **Inputs (all read-only, by value):** Goal, Repository Understanding, Knowledge, Operator Profile,
  Policy Context, Environment Facts (INV-32/36). **Output:** one **Engineering Strategy** — an immutable
  recorded decision (INV-17) with facets: classification, approach, context objectives, skill
  requirements, runtime posture, validation rigor, coordination intent, autonomy level, risk, **and
  estimates (complexity/duration/cost)**.
- **Responsibilities:** classify the engineering work; assess situation; select approach; propose autonomy
  and risk envelope; **estimate complexity/duration/cost** (see Estimation, Object Model). Reasons freely,
  commits to the record.
- **Non-responsibilities:** builds no context, writes no plan, selects no concrete skill or runtime,
  executes nothing, authorizes nothing (proposes gates; Policy decides — INV-28/29), writes no Knowledge.

**3. GROUND** — *what is true about the world this work touches?*
- **Owners (a grounding family, each its own subsystem, different lifecycles):**
  **Repository Intelligence** (repository facts → *Repository Understanding*), **Operator Profile**
  (how this operator engineers), **Knowledge** (validated prior understanding, read-only query — INV-24),
  **Execution History** (what happened before). **[Constitutional]** Repository Intelligence, Operator
  Profile, and Execution History require their own design packages; only Knowledge is built.
- **Inputs:** repository, event log, prior Knowledge. **Outputs:** read-only understanding artifacts
  consumed by Reason and Contextualize.
- **Non-responsibilities:** grounding never plans, decides, or executes. It serves facts (by reference,
  never embedded content — INV-27), then stops.

**4. CONTEXTUALIZE** — *assemble the execution context.*
- **Owner:** Context Engineering (`docs/v2/03`; contract `context_package.md`).
- **Inputs:** Goal + Engineering Strategy's *context objectives* + grounding. **Output:** **Context
  Package**.
- **Responsibilities:** collect, enrich, rank (deterministically), validate completeness. **Consumes**
  Knowledge; never owns it (INV-06).
- **Non-responsibilities:** never plans, never decides approach (receives it from Reason).

**5. PLAN** — *turn the decided approach into executable work.* **[Constitutional — merges three
former layers.]**
- **Owner:** Planning (`docs/v2/04/05`; contracts `plan.md`, `work_package.md`, `execution_graph.md`,
  `execution_strategy.md`, `skill.md`). Planning now **absorbs** Execution-Strategy formalization, Skill
  Selection (resolution), and Work Packaging — these were never independent decisions, only facets of
  "package the work" (see Simplifications).
- **Inputs:** Goal, Context Package, Engineering Strategy. **Outputs:** Plan + Work Packages + Execution
  Graph (sibling artifact, INV-10) + resolved Skills + formalized Execution Strategy.
- **Responsibilities:** decompose the Goal within EI's approach envelope; resolve capability requirements →
  concrete Skills (INV-33); identify approval gates; formalize coordination (INV-05).
- **Non-responsibilities:** never executes (INV-03); never chooses the approach (receives it); never
  selects the concrete runtime (Orchestration does — INV-37).

**6. COORDINATE** — *drive the work through runtimes.*
- **Owner:** Orchestration (`docs/v2/07`).
- **Inputs:** Plan, Execution Graph, Execution Strategy, Environment Facts. **Outputs:** runtime
  allocations, coordination events.
- **Responsibilities:** schedule, sequence, parallelize, **select the runtime** (INV-37), enact
  coordination, own **pause/resume/cancel** (INV-23), direct retries/escalations that Recovery decides.
- **Non-responsibilities:** never understands work, never plans, never decides *whether* to retry (Recovery
  does — INV-22), never invents coordination not in the Strategy (INV-05).

**7. EXECUTE** — *drive one runtime attempt.*
- **Owner:** Execution Engine (`docs/v2/08`; `nexus_execution`).
- **Inputs:** a Work Package + an allocated Runtime (via Harness). **Outputs:** raw Execution Events,
  Evidence Candidates (INV-12).
- **Responsibilities:** generic, provider-blind drive of a runtime through its Adapter; emit facts.
- **Non-responsibilities:** never plans (INV-04), never validates or declares completion (INV-21), never
  selects its runtime, never receives a Goal (INV-09/19).

**8. ACT** — *realize what touching a real environment means.*
- **Owner:** Actuation (`docs/v2/actuation/`; nouns Environment/Session/Workspace/Permission).
  **[Constitutional]** first-class capability *beneath* the runtime-adapter boundary. **[Contracts not yet
  frozen.]**
- **Inputs:** a Work Package's interactions, a Permission Envelope. **Outputs:** `actuation.*` facts,
  Evidence Candidates, governed-action audit.
- **Responsibilities:** provision/own Environments; run long-lived reattachable Sessions; enforce Workspace
  containment and governed git primitives; **enforce** the Permission Envelope and pause on gates; record
  everything.
- **Non-responsibilities:** decides nothing — never authorizes (Policy does — INV-28), never chooses the
  runtime (INV-37), never chooses recovery (Recovery does — INV-22); cannot reach the Goal by construction
  (INV-22).

**9. OBSERVE** — *derive meaning from execution facts.*
- **Owner:** Supervision (`docs/v2/09`; contract `observation.md`).
- **Inputs:** raw Execution/`actuation.*` events. **Outputs:** **Observations**, health, progress,
  intervention **recommendations**.
- **Responsibilities:** turn facts into Observations (INV-11); recommend intervention.
- **Non-responsibilities:** never controls execution (INV-23 — it recommends; Orchestration acts); never
  validates.

**10. VALIDATE** — *decide completion from evidence.*
- **Owner:** Validation (`docs/v2/14`; produces Evidence, promotes Candidates).
- **Inputs:** Evidence Candidates + artifacts. **Output:** completion verdict + **Evidence** (INV-12).
- **Responsibilities:** determine completion from independently verifiable Evidence (INV-20).
- **Non-responsibilities:** never trusts runtime self-report (INV-20); never recovers, never executes.

**11. RECOVER** — *decide continuation on failure.*
- **Owner:** Recovery (`docs/v2/19`; contract `recovery` / `checkpoint.md`).
- **Inputs:** failure class, Observations, last checkpoint. **Output:** **Recovery Plan** (decision only).
- **Responsibilities:** decide resume/reattach/recreate/restart/retry (bounded), or escalate; Orchestration
  directs, Actuation enacts (INV-22).
- **Non-responsibilities:** never restarts from the Goal, never mutates Goal/Plan, never bypasses
  Governance, never discards validated evidence (INV-22).

**12. REFLECT** — *explain outcomes.*
- **Owner:** Reflection (`docs/v2/26`; contract `reflection.md`).
- **Inputs:** the episode's execution/validation/recovery results. **Output:** **Reflection Report** +
  **Knowledge Candidates**.
- **Responsibilities:** deterministic aggregation of why/what/patterns; propose candidates.
- **Non-responsibilities:** never updates Knowledge directly (INV-25); never calls Planning (INV-26).

**13. LEARN** — *persist validated operational knowledge.*
- **Owner:** Knowledge (`docs/v2/knowledge/`, `10`; contract `knowledge.md`).
- **Inputs:** Knowledge Candidates. **Output:** accepted/evolved **Knowledge** (the operational learning
  graph).
- **Responsibilities:** govern acceptance (accept/evolve/merge/reject); serve read-only Knowledge; hold
  typed relationships. Only validated outcomes become Knowledge (INV-24).
- **Non-responsibilities:** never executes (Rule 4); never mutates Planning (INV-26); never *is* the
  grounding subsystems — Repository/Operator/Execution intelligence are separate producers (see
  Simplifications, Knowledge split).

### The Governing & Operating Capabilities (cross-cutting; touch every spine capability)

**14. GOVERN** — *authorize; never act.*
- **Owners:** **Policy Engine** (evaluates all policy — INV-28; contract `policy.md`) + **Human
  Interaction** (the human surface; `docs/v2/human_interaction/`) + Audit (log events).
- **Responsibilities:** Policy Engine decides *required* approvals and permissions, deterministically,
  fail-closed (INV-30); Human Interaction *reaches the human and collects the answer* across any channel;
  the **approver** decides the outcome. Governance authorizes and audits; it never executes, plans,
  supervises, or validates (INV-29).
- **Non-responsibilities:** Policy never executes; Human Interaction never decides (records who did).
  **[Constitutional]** The Policy Engine requires its own design package — it is invariant-mandated
  (INV-28) but undesigned.

**15. OPERATE** — *observe and account for the whole platform.*
- **Owners:** Observability (instrumentation sink) + **Operations** (operational intelligence:
  health, cost, utilization, failures, success/recovery rate, tool/skill performance, bottlenecks) +
  **Estimation/Cost Intelligence** (feeds EI and budgets). **[Constitutional — Operations and Estimation
  are undesigned voids to be built.]**
- **Responsibilities:** derive platform health and cost from the event log; report; never decide operational
  strategy.
- **Non-responsibilities:** never reasons, plans, or governs.

### Foundation (substrate all capabilities stand on)

**Durable Memory / Persistence** (the Event Log is truth — INV-13; state/checkpoints are projections —
INV-14) · **Event Gateway** (all cross-subsystem interaction is correlated events — INV-39) · **Harness
Registry** (single source of provider availability/health — INV-36) · **Runtime** (an interchangeable
Harness of category Runtime — INV-36; *executes, never reasons*) · **Scheduler**. **[Constitutional]** A
durable operational-memory backing is undefined and blocks all learning/graph claims.

---

## Canonical Dependency Rules

The law is one-way down the spine; cross-cutting planes couple only through **read-only seams and events**
(INV-01, INV-39). "Depends on" = build-time import / synchronous call. Feedback edges
(Supervision→Orchestration, Recovery→Orchestration, Knowledge→Planning) are **data flows via the log, not
dependencies** (INV-01).

**MAY depend on (down-spine, by value):**
- Reason (EI) **may** read Grounding, Knowledge, Policy Context, Environment Facts — all read-only.
- Contextualize **may** depend on Grounding and Knowledge (read-only, INV-06).
- Plan **may** depend on Context and the Engineering Strategy.
- Coordinate **may** depend on Plan, Strategy, Harness Registry.
- Execute **may** depend on Runtime (via Harness) and a Work Package.
- Act **may** depend on `{core, infra}` only; consumed behind the adapter boundary.
- Validate/Recover/Reflect **may** read execution facts from the log.

**MUST NEVER depend on (constitutional prohibitions, each grounded):**
- **Runtime must never reason.** (First principle; INV-35 — harnesses expose capabilities, not business
  logic.)
- **Execution must never plan** (INV-04); **Planning must never execute** (INV-03).
- **Execution/Actuation must never authorize** (INV-28/29 — only Policy).
- **Actuation must never reach the Goal** (INV-22, structural).
- **Human Interaction must never decide** an outcome (INV-29; it surfaces, the approver decides).
- **Policy must never execute, plan, supervise, or validate** (INV-29).
- **Supervision must never control execution** (INV-23 — recommends only; Orchestration owns pause/resume/
  cancel).
- **Reflection must never call Planning** (INV-26); **Reflection must never write Knowledge** (INV-25).
- **Knowledge must never mutate Planning** (INV-26) and **must never execute** (Rule 4).
- **Context must never own Knowledge** (INV-06).
- **Reason (EI) must never import any downstream engine** (`engineering/00`; keeps INV-01 unbreakable) and
  **must never authorize** (proposes; Policy decides).
- **Capability resolution must never select a runtime** (INV-37 — Orchestration selects).
- **No subsystem may introduce a second schema for an existing object** (INV-07) or **duplicate the Harness
  Registry** (INV-36).

**The single most important new rule this Constitution adds [Constitutional]:** *Every governed decision
depends on the Policy Engine; therefore the Policy Engine may depend on **nothing** but the Event Log and
policy data.* A universal dependency must be a leaf.

---

## Canonical Decision Ownership

One owner per decision. No duplication. Grounded in invariants where ratified.

| Decision | **Sole owner** | Basis |
|---|---|---|
| Intent (what is wanted) | Intent Resolution (Understand) | `16`; INV-08 |
| Engineering classification (kind of work) | **Engineering Intelligence (Reason)** | INV-02 [ADR-005 to ratify] |
| Complexity / Duration / Cost estimate | **Engineering Intelligence (Reason)** via Estimation | [Constitutional void to design] |
| Engineering approach / rigor / autonomy proposal | Engineering Intelligence (Reason) | `engineering/`; INV-17 |
| Context objectives | Engineering Intelligence; **assembled by** Context Engineering | INV-06 |
| Work breakdown / packages / graph | Planning | INV-03/10 |
| Skill resolution (concrete skill) | Planning (Skill Selection, merged) | INV-33 |
| Runtime selection | Orchestration | **INV-37** |
| Coordination formalization | Planning (Execution Strategy, merged); enacted by Orchestration | INV-05 |
| Pause / resume / cancel control | Orchestration | **INV-23** |
| Approval *required?* + permissions | **Policy Engine** | **INV-28/30** |
| Approval *outcome* | The approver (surfaced by Human Interaction) | INV-29 |
| Retry (whether/bounds) | Recovery (Orchestration directs) | **INV-22** |
| Escalation (whether) | Recovery | INV-22 |
| Observation (facts→meaning) | Supervision | **INV-11/23** |
| Completion verdict | Validation | **INV-20/21** |
| Continuation on failure | Recovery | INV-21/22 |
| Reflection (candidates) | Reflection | **INV-25** |
| Knowledge persistence | Knowledge (Acceptance) | **INV-24/25** |
| Human channel / reach the human | Human Interaction | `human_interaction/`; INV-34 |
| Operational metrics / cost accounting | Operations | [Constitutional void] |

Every previously-contested decision (classification, retry/escalate/suspend, channel, approval) now has
exactly one owner, and every ruling is either an invariant or an explicitly-flagged constitutional act.

---

## Canonical Object Model

The durable nouns of Nexus. **Frozen** = a `contracts/*.md` schema exists (INV-07). **Proposed** = a
frontier corpus specifies it but it is not yet a frozen contract.

| Object | Status | Owner (single writer) | Producer → Consumer | Lifecycle |
|---|---|---|---|---|
| **Intent** | Frozen | Intent Resolution | operator → EI | per request |
| **Goal** | Frozen | Intent Resolution | Intent Resolution → EI/Context/Planning | per request, immutable (INV-08) |
| **Engineering Strategy** | **Proposed** | Engineering Intelligence | EI → all downstream engines | per goal, immutable recorded decision (INV-17) |
| **Repository Understanding** | Proposed | Repository Intelligence | Repo Intel → EI/Context | cached, refreshed |
| **Operator Profile** | Proposed | Operator Profile subsystem | → EI | durable, evolving |
| **Context Package** | Frozen | Context Engineering | → Planning | per goal |
| **Capability** | Frozen | (definition) | Planning/Orchestration | provider-independent (INV-32) |
| **Skill** | Frozen | Skill registry | Planning → Execution | durable; **needs completion (below)** |
| **Plan** | Frozen | Planning | → Orchestration | per goal |
| **Work Package** | Frozen | Work Packaging (in Planning) | → Runtime (INV-09/19) | per unit of work |
| **Execution Graph** | Frozen | Planning | → Orchestration | sibling of Plan (INV-10) |
| **Execution Strategy** | Frozen | Planning (formalizes EI intent) | → Orchestration | per plan |
| **Environment / Session / Workspace / Permission** | **Proposed** | Actuation | Actuation → Execution | Session long-lived, reattachable |
| **Resource** | Frozen | Harness Registry | → Orchestration | live |
| **Event** | Frozen | every subsystem (append-only) | → all (INV-13/39) | permanent, immutable |
| **Observation** | Frozen | Supervision | → Orchestration/Operations | per episode (INV-11) |
| **Artifact** | Frozen | Execution/Actuation | referenced, never embedded (INV-27) | per execution |
| **Checkpoint** | Frozen | Execution/Recovery | → Recovery | projection of log (INV-14/18) |
| **Validation Report / Evidence** | Frozen | Validation | → Recovery/Knowledge | per episode (INV-12/20) |
| **Recovery Plan** | Frozen | Recovery | → Orchestration | per failure (INV-22) |
| **Reflection Report** | Frozen | Reflection | → Knowledge (candidates) | per episode (INV-25) |
| **Knowledge** | Frozen | Knowledge Acceptance | → EI/Context/Planning (read-only) | durable graph (INV-24) |
| **Interaction / Session (human)** | **Proposed** | Human Interaction | → the approver | durable, resumable |
| **Policy** | Frozen | Policy Engine | → all governed actions | versioned (INV-28) |
| **Estimation (complexity/duration/cost)** | **Void** | Engineering Intelligence | → EI/Operations | per goal |

**Skill completion [Constitutional].** For Skills to be "engineering knowledge, not prompts" (INV-33), the
frozen `skill.md` should own the full set: capability, `required_context`, `execution_strategy`,
`validation_strategy`, `expected_artifacts`, `recovery_strategy`, **`success_criteria`** (currently on
Work Package), `tool_requirements`, `runtime_preferences` (posture, not provider — INV-33), and
`cost_expectations` / `approval_expectations`. Then EI declares *requirements*, Planning resolves a
*fully-specified* Skill, and no facet is invented downstream.

**The un-frozen nouns are exactly the un-built subsystems' outputs** (Engineering Strategy, Repository
Understanding, Operator Profile, Environment/Session, Interaction, Estimation). Freezing each contract is
the gate for building its subsystem — freeze only when a second subsystem depends on the shape (the
platform's own "don't pre-freeze" discipline).

---

## Canonical Information Flow

Six flows, drawn separately (they overlay the same capabilities but carry different things).

**Information flow** (what is known):
```
operator → Intent Resolution → Goal → Engineering Intelligence ← {Repository Understanding, Knowledge,
   Operator Profile, Policy Context, Environment Facts} → Engineering Strategy → Context Engineering →
   Context Package → Planning → Plan/Packages/Graph
```

**Decision flow** (what is chosen — each arrow is a recorded decision, one owner):
```
Intent(IR) → Classification+Estimate+Approach(EI) → Breakdown+Skills(Planning) → Runtime(Orchestration)
   → Approval-required(Policy) → Completion(Validation) → Continuation(Recovery) → Persist(Knowledge)
```

**Execution flow** (what is done):
```
Orchestration → Runtime Manager → Execution Engine → (adapter boundary) → Actuation → External Environment
```

**Observation flow** (what is seen):
```
Execution/Actuation facts → Event Log → Supervision → Observations → Operations (metrics/cost)
```

**Learning flow** (what is retained — across time, via the log, never a call cycle — INV-26):
```
Validation(Evidence) → Reflection(Candidates) → Knowledge(accept) → [future] EI/Context/Planning grounding
```

**Approval flow** (who says yes — one owner per hop):
```
Planning identifies gate → Policy Engine decides required(INV-28) → Orchestration coordinates →
   Runtime/Actuation enforces the pause → Human Interaction surfaces → the approver decides(INV-29) →
   Runtime/Actuation projects the decision → audit event
```

No flow crosses an ownership boundary twice; no two flows decide the same thing.

---

## Canonical Intelligence Model

Where reasoning belongs, and where determinism binds. The rule: **reasoning lives only in the *decide*
capabilities and always emits a recorded decision (INV-17); everything else is deterministic; policy is a
hard ceiling over all of it (INV-28/30).**

| Capability | Reasons? | Deterministic? | LLM? | Heuristics? | Policy-only? |
|---|---|---|---|---|---|
| Understand (Intent Resolution) | **Yes** | after emit | **Yes** (recorded) | Yes | No |
| Reason (Engineering Intelligence) | **Yes** | after emit | **Yes** (recorded) | Yes | No |
| Ground (Repo Intel / Knowledge query) | No | **Yes** | No | No | No |
| Contextualize (Context Engineering) | No | **Yes** | No | ranking only | No |
| Plan (Planning) | No | **Yes** | No | No | No |
| Coordinate (Orchestration) | No | **Yes** | No | No | No |
| Execute (Execution Engine) | No | **Yes** | No (drives an LLM *runtime*, doesn't reason) | No | No |
| Act (Actuation) | No | **Yes** | No | No | enforce only |
| Observe (Supervision) | No | **Yes** | No | thresholds | No |
| Validate | No | **Yes** | No | No | No |
| Recover | No | **Yes** | No | rule table | No |
| Reflect | No | **Yes** | No | counting | No |
| Learn (Knowledge acceptance) | No | **Yes** | No | No | governed |
| Govern (Policy Engine) | No | **Yes** | **Never** | **Never** | **Only** (INV-28) |
| Operate (Operations/Estimation) | Estimation may reason (recorded); metrics deterministic | mostly | Estimation may | Yes | No |

**Two and a half places reason:** Understand, Reason, and (for estimation) Operate — and *only* through the
determinism seam. **The Policy Engine must never reason** — governance is deterministic policy evaluation,
because non-deterministic authorization is unsafe. **Runtime reasons only as the execution backend**, never
about the operation. This table is the constitutional answer to "where should reasoning begin and
determinism bind."

---

## Cross-Cutting Architecture

**Verdict: Nexus is a capability architecture — a thin reasoning spine on cross-cutting planes — not a
linear layer stack.** The spine (Understand→…→Learn) is sequential and obeys INV-01. The following are
**planes**, not stages: they touch every spine capability through read-only seams and events (INV-39), and
forcing them into the linear stack is what created every overlap the assessments found.

| Plane | Subsystems | Verb | Touches |
|---|---|---|---|
| **Governance** | Policy Engine, Human Interaction, Audit | **Decide/authorize** | every governed action |
| **Operations** | Observability, Operations, Estimation/Cost | **Observe/account** | every execution |
| **Grounding** | Repository Intelligence, Operator Profile, Execution History, Knowledge | **Ground** | Reason, Contextualize |
| **Foundation** | Event Log/Memory, Event Gateway, Harness Registry, Runtime, Scheduler, Security | **Persist/transport/execute** | all |

```
   ┌──────────────── REASONING SPINE (sequential, INV-01) ─────────────────┐
   Understand → Reason → Contextualize → Plan → Coordinate → Execute → Act
                    │        │            │        │           │        │
   ── GOVERNANCE ───┼────────┼────────────┼────────┼───────────┼────────┼──  Policy · Human Interaction
   ── GROUNDING ────┴────────┘  (read-only facts feed Reason/Contextualize) Repo · Operator · Knowledge
   ── OPERATIONS ─────────────────── observes all → metrics/cost ─────────── Observability · Operations
   ── FOUNDATION ── Event Log (truth) · Harness Registry · Runtime · Memory ─────────────────────────────
```

**Communication** is **not** a plane and **not** a service: it is the **Harness *category*** (INV-34/36)
through which Human Interaction reaches humans and Notifications go out. **Security** is a property of the
Foundation and Governance planes (secret-reference-only, redaction at edges), not a separate subsystem.

---

## Architecture Simplifications

Complexity must earn its existence. The following reductions are justified strongly enough to be
constitutional:

1. **MERGE** Execution Strategy + Skill Selection + Work Packaging **into Planning** (parameterized by the
   Engineering Strategy). *Why:* none owns an independent *decision* — they are facets of "turn the decided
   approach into executable work." Removes three stage-boundaries carrying no independent owner. (INV-05
   preserved: Planning formalizes coordination; Orchestration enacts.)
2. **MERGE** the "Supervision" layer into the **Operations/Observe** capability. *Why:* it observes; it is
   not a pipeline stage. INV-23 already forbids it from controlling — so it is observation, full stop.
3. **RETIRE** "Executive Intelligence" the name; **SPLIT** its responsibilities: intent → Understand
   (Intent Resolution), approach/estimation → Reason (Engineering Intelligence). *Why:* INV-02. The name
   caused the fork; the split ends it. [ADR-005 to ratify.]
4. **RETIRE** the vague Layer-0 "Communication" service and the never-defined "Channel Harness";
   **FOLD** into (a) the **Communication Harness category** (transport, INV-34) and (b) **Human
   Interaction** (the interaction lifecycle). *Why:* three names for one concern.
5. **SPLIT Knowledge** from the grounding subsystems it conflates. Knowledge = the **operational learning
   graph**; Repository/Operator/Execution intelligence are **separate Grounding subsystems** that produce/
   consume Knowledge. *Why:* different lifecycles; INV-24 keeps Knowledge evidence-backed while grounding is
   raw fact.
6. **PROMOTE** the **Policy Engine**, **Operations**, and **Estimation** from "referenced" to first-class
   capabilities. *Why:* INV-28 already mandates Policy; the vision mandates Operations; EI mathematically
   needs Estimation. They are not new — they are unbuilt necessities.
7. **KEEP** (do not merge) Validation, Recovery, Reflection, Knowledge as distinct — each owns a distinct
   decision (completion / continuation / candidates / persistence), each backed by an invariant. Their
   distinctness earns its existence.

Net effect: ~16 numbered "layers" collapse to **13 spine capabilities + 4 planes + 1 foundation**, with
*more* clarity and *fewer* ownership boundaries.

---

## Migration Guidance

From today's three-narrative reality to this Constitution. No code in this document; these are the ordered
architectural acts.

**Stage 0 — Ratify this Constitution** as the canonical reference; mark the numbered `01_ARCHITECTURE.md`
and the frontier corpora as *subordinate detail* that must conform to it.

**Stage 1 — Enact the reconciliations that need an ADR:**
- ADR-005: reinstate Engineering Intelligence as the Reason capability; retire "Executive Intelligence";
  move "classify work / estimate complexity" from Intent Resolution to EI. (No invariant changes; INV-02
  already supports it.)
- ADR-006: name the Policy Engine, Operations, and Repository Intelligence as first-class subsystems with
  their own design packages (`docs/v2/policy/`, `operations/`, `repository/`).

**Stage 2 — Freeze the proposed contracts** as their subsystems are built (Engineering Strategy, Repository
Understanding, Environment/Session, Interaction, Estimation) — one at a time, only when a second consumer
needs the shape (INV-07 discipline).

**Stage 3 — Build against the Constitution, one vertical at a time** (the A0/A1/A2 discipline), and —
critically, per `VISION_ALIGNMENT_AUDIT.md` — **connect each vertical to the running product**, closing the
v1/v2 disconnection. Priority order by dependency: **durable Memory → Policy Engine → Engineering
Intelligence → Repository Intelligence → Human Interaction channel → Operations/Estimation.**

**Migration impact of the losing narratives:**
- The numbered linear stack: *demoted, not deleted* — its per-capability detail (docs 03–26) remains valid
  where it conforms; its top-level "12 sequential layers" framing is superseded by planes.
- "Executive Intelligence = Intent Resolution" (ADR-003 prose): the *name* deprecation stands; the *implied
  merge of responsibilities* is retired by ADR-005. Low impact — no invariant depended on it.
- "Communication"/"Channel Harness": low impact — they were never built in v2 (per the audit); folding them
  into Communication-Harness + Human-Interaction costs nothing already-shipped.

---

## Architecture Constitution (the enduring articles)

The condensed, permanent statement. Every future subsystem derives from these.

- **Article I.** Runtime executes; Nexus thinks about execution. A subsystem that does neither does not
  exist.
- **Article II.** Nexus is capabilities on planes, not layers. The reasoning spine is sequential and
  one-way (INV-01); Governance, Operations, Grounding, and Foundation are cross-cutting.
- **Article III.** One responsibility, one owner, one decision-point (INV-02). Overlap is an architecture
  defect, resolved in favor of the single owner named here.
- **Article IV.** Reasoning lives only in Understand, Reason, and Estimation, and always emits an immutable
  recorded decision (INV-17). Everything else is deterministic and replayable.
- **Article V.** All governance is evaluated by the Policy Engine, deterministically, fail-closed
  (INV-28/29/30). Governance authorizes; it never acts. Human Interaction surfaces; it never decides.
- **Article VI.** The Event Log is the single source of truth (INV-13); state and checkpoints are
  projections (INV-14); every cross-subsystem interaction is a correlated event (INV-39).
- **Article VII.** Completion is evidence-based (INV-20); Execution never declares its own completion
  (INV-21); Recovery recovers without ever restarting from the Goal (INV-22).
- **Article VIII.** Every object has one canonical schema (INV-07); grounding subsystems serve facts by
  reference (INV-27) and never plan, decide, or execute.
- **Article IX.** Runtimes and all external systems integrate only through Harnesses (INV-34/35), whose
  availability lives in one registry (INV-36); runtime selection is Orchestration's alone (INV-37).
- **Article X.** Learning flows only Reflection → Knowledge → future Planning, across time, via the log —
  never a direct call (INV-25/26). Knowledge is evidence-backed (INV-24) and is not the grounding
  subsystems.
- **Article XI.** Complexity must earn its existence. Prefer merging to adding; prefer capability ownership
  to layer count; retire any subsystem that owns no distinct decision.
- **Article XII.** This Constitution obeys the 39 invariants and the frozen contracts absolutely. Any
  future change to those requires a superseding ADR; any future architectural narrative must conform to
  this document.

---

## Final Verdict

**Is there now a single canonical architecture for Nexus? Yes — this document.** The forks that the three
prior assessments exposed were narrative, not structural: the 39 ratified invariants already formed a
consistent constitutional core, and the conflicts all lived in prose above them. This Constitution makes
the narrative conform to the invariants and, in doing so, resolves every open conflict:

- The Executive-Intelligence / Intent-Resolution fork → **split into Understand and Reason** (INV-02).
- The Communication / Channel-Harness / Human-Interaction overlap → **Communication Harness category +
  Human Interaction** (INV-34).
- The retry/escalate/suspend triple-ownership → **Recovery decides, Orchestration acts** (INV-22/23).
- The linear-vs-cross-cutting tension → **capabilities on planes.**
- The three voids → **Policy Engine, Operations, Estimation promoted to first-class** (INV-28 + vision).

**Would this architecture still make sense after thousands of repositories, hundreds of runtimes,
continuous autonomous operation, and multiple operators in production?** Yes — because scale lands in
exactly one place each: more runtimes → the Foundation's Harness Registry (Runtime executes); more
repositories → the Grounding plane (Repository Intelligence); more operators → the Governance plane
(multi-tenant Policy + Human Interaction); portfolio reasoning → above the Reason capability; cost at scale
→ the Operations plane. Nothing above the changing part must change. That is the test of a five-year
architecture, and the capability-on-planes model passes it where a 12-layer linear stack would not.

**One-line verdict.** *Nexus's architecture is now singular: a thin reasoning spine — Understand, Reason,
Plan, Coordinate — that thinks about execution, riding on cross-cutting planes of Governance, Grounding,
Operations, and a Foundation on which an interchangeable Runtime merely executes. Runtime executes; Nexus
thinks about execution — and every capability, dependency, decision, object, and flow in this Constitution
exists to keep that sentence true.*

---

*This is the constitutional reference for Nexus v2 and future versions. It modifies no invariant, contract,
or ADR; it reconciles the architectural narrative to them. Items marked [Constitutional] identify where a
future ADR is required to formally enact a ruling. This document supersedes conflicting architectural
narratives; it does not supersede the ratified invariants or frozen contracts it is built to obey.*
