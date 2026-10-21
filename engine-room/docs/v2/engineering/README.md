# Nexus v2 — Engineering Intelligence Architecture (design only)

> **Status:** Architecture & design specification. **No implementation.** This directory
> defines *what* Engineering Intelligence is and *how* it must behave, so that a future
> implementation team can build it without making new architectural decisions. It introduces
> **no** production code, Protocols, classes, algorithms, or APIs. It amends **no** ADR,
> contract, or invariant; where the existing architecture needs clarification, that is recorded
> as a *recommendation* in [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md), not applied.
> It expands the frozen capability layers (`../01_ARCHITECTURE.md`, `../16_INTENT_RESOLUTION.md`,
> `../13_EXECUTION_STRATEGY.md`, `../06_SKILLS.md`) into a new subsystem *above* them; it never
> contradicts them.

## Why this exists

Nexus has a complete operational pipeline. Given a well-formed Goal with declared work, the
platform plans, packages, orchestrates, executes, validates, recovers, reflects, and learns —
deterministically and under governance. Every layer *after* understanding already runs.

The layer that decides **how engineering work should proceed** does not exist.

Today a human performs it. When an operator hand-authors a submission —

```
GoalSubmission(outcome="ship the feature", steps=("design", "implement", "verify"), …)
```

— the human has already done the engineering thinking: decomposed the intent into an approach,
chosen the rigor, implied the skills, set the validation bar, and accepted the risk. The platform
receives the *conclusion* of engineering judgment, never performs it. Nexus executes the shape of
an engineer's workflow; it does not yet supply the engineer.

**Engineering Intelligence (EI)** is the subsystem that supplies it. Given a normalized Goal, an
understanding of the repository, prior Knowledge, operator preferences, and governing policy, EI
produces one coherent **Engineering Strategy** that parameterizes the existing engines. It answers
exactly one question:

> Given a normalized Goal and the operational situation around it, **how should this engineering
> work proceed** — what approach, what skills, what validation rigor, what runtime posture, what
> autonomy, and at what risk — expressed as a declarative strategy the existing engines enact,
> without EI ever building context, planning, selecting runtimes, executing, or validating?

**Intent Resolution decides *what* the goal is. Engineering Intelligence decides *how* to pursue
it. The existing engines *enact* that decision.** That single sentence is the spine of every
document here.

## What Engineering Intelligence is NOT

EI is a coordinator of existing engines, not a replacement for any of them. It never absorbs a
responsibility the Object Model already assigns (INV-02).

| Concern | Owner — **not** EI |
|---|---|
| Understand the operator request; normalize it into a **Goal** | Intent Resolution (`../16`) |
| Index and serve repository facts | **Repository Intelligence** (`10`, a *separate* subsystem EI consumes) |
| Assemble the Context Package | Context Engineering (`../03`) |
| Decide *what* work exists; decompose the Goal into Work Packages | Planning (`../04`) |
| Formalize declarative coordination/retry/timeout behavior | Execution Strategy (`../13`) |
| Resolve concrete Skills for required capabilities | Skill Selection (`../06`) |
| Select the runtime for a Work Package | Orchestration (INV-37) |
| Evaluate governance policy | Policy Engine (ADR-004, INV-28) |
| Determine completion from evidence | Validation (`../14`, INV-20) |
| Interpret outcomes; produce Knowledge Candidates | Reflection (`../26`, INV-25) |
| Decide what becomes durable understanding | Knowledge Engine (`../knowledge/`) |

EI **consumes** these. It **coordinates** them. It **does not replace** them.

## The boundary, stated precisely

| Concern | Owner |
|---|---|
| Normalize operator intent into a **Goal** | Intent Resolution (design frozen, `../16`) |
| **Decide the engineering approach — produce the `Engineering Strategy`** | **Engineering Intelligence (this design)** |
| Serve repository understanding to EI and Context | Repository Intelligence (this design, `10`) |
| Gather context the Strategy calls for | Context Engineering |
| Decompose the Goal within the Strategy | Planning |
| Enact coordination/skills/runtime/validation | Execution Strategy / Skill Selection / Orchestration / Validation |

## Reading order

| # | Document | Defines |
|---|---|---|
| — | [`00_OVERVIEW.md`](00_OVERVIEW.md) | The subsystem, placement, inputs/outputs, dependency direction, canon glossary |
| — | [`01_ENGINEERING_INTELLIGENCE.md`](01_ENGINEERING_INTELLIGENCE.md) | Responsibilities, the interpret→strategize pipeline, hard boundaries |
| — | [`02_INPUT_MODEL.md`](02_INPUT_MODEL.md) | The canonical inputs EI receives and where each originates |
| — | [`03_OUTPUT_MODEL.md`](03_OUTPUT_MODEL.md) | The canonical outputs EI produces and who consumes each |
| — | [`04_ENGINEERING_STRATEGY.md`](04_ENGINEERING_STRATEGY.md) | The `Engineering Strategy` artifact — the one coherent decision object |
| — | [`05_SKILL_ORCHESTRATION.md`](05_SKILL_ORCHESTRATION.md) | Skill *requirements & composition intent* vs. Skill Selection |
| — | [`06_RUNTIME_STRATEGY.md`](06_RUNTIME_STRATEGY.md) | Runtime *preference by capability* vs. Orchestration's selection (INV-37) |
| — | [`07_VALIDATION_STRATEGY.md`](07_VALIDATION_STRATEGY.md) | Validation *rigor & evidence intent* vs. Validation's verdict (INV-20) |
| — | [`08_AUTONOMY_MODEL.md`](08_AUTONOMY_MODEL.md) | Autonomy levels, approval requirements, human authority |
| — | [`09_RISK_MODEL.md`](09_RISK_MODEL.md) | Risk assessment, blast radius, reversibility, risk envelope |
| — | [`10_REPOSITORY_INTELLIGENCE.md`](10_REPOSITORY_INTELLIGENCE.md) | The separate repository-understanding subsystem EI consumes |
| — | [`11_INTENT_INTERPRETATION.md`](11_INTENT_INTERPRETATION.md) | Why Intent Understanding stays in Intent Resolution, not EI |
| — | [`12_DECISION_FLOW.md`](12_DECISION_FLOW.md) | The end-to-end decision flow and where determinism binds |
| — | [`13_GOVERNANCE.md`](13_GOVERNANCE.md) | Auditability, explainability, determinism-on-replay, policy relationship |
| — | [`14_GAPS.md`](14_GAPS.md) | Open questions and deferred decisions |
| — | [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) | Correctness, completeness, readiness, ratification verdict |

## Canon (binding for every document)

These terms and rules are **fixed**. No document may redefine them, invent a parallel layer, or
coin a competing artifact name:

- **Engineering Intelligence (EI)** — the subsystem specified here. Decides the engineering
  approach; never builds context, plans, packages, selects runtimes, executes, or validates.
- **Engineering Strategy** — the single, coherent, declarative artifact EI produces (`04`). The
  boundary contract between EI and every downstream engine. It carries *intent and envelopes*
  (approach, skill requirements, validation rigor, runtime preferences, autonomy level, risk
  assessment, context objectives) — never concrete selections the downstream engines own.
- **Repository Understanding** — the artifact produced by Repository Intelligence (`10`), consumed
  read-only by both EI and Context Engineering.
- **Dependency direction** — `nexus_engineering → {nexus_core, nexus_infra}` only. EI consumes the
  Goal, Repository Understanding, Knowledge, Preferences, and Policy inputs **by value / read-only**
  at its boundary; it is imported by nothing upstream. Downstream engines consume the Engineering
  Strategy **read-only**. Higher (understanding) layers never depend on lower (execution) layers
  (INV-01).
- **Determinism seam** — EI *generation* may be heuristic (it may reason with an LLM capability);
  its *output is captured as an immutable recorded decision* (INV-17). Replay reproduces the
  governed pipeline from the recorded Engineering Strategy without re-inference. Heuristics are
  permitted only at strategy generation; determinism is absolute at enactment, replay, and audit.
- **Binding invariants** — INV-01/02 (layer boundaries), INV-08 (Goals describe outcomes, never
  procedures — EI never writes a plan into the Goal), INV-17 (non-deterministic values captured as
  data), INV-26 (Planning reaches learning only through Knowledge), INV-28 (only the Policy Engine
  evaluates policy), INV-31 (every decision explainable/auditable), INV-32/33 (capabilities &
  skills are provider-independent), INV-37 (runtime selection is Orchestration's). No document may
  weaken these.
