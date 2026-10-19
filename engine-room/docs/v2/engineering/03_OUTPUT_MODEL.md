# Output Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the **canonical output** of Engineering Intelligence, who consumes each part
of it, and the discipline that keeps EI's output *directive-but-not-usurping* — it tells each
downstream engine *what to aim for* without doing that engine's job.

---

# One artifact

Engineering Intelligence produces exactly one artifact: the **Engineering Strategy** (`04`).

There is no second output object, no side-channel, and no direct call into a downstream engine that
bypasses the Strategy. Everything EI "produces" is a **facet** of this single, coherent artifact.

```
Engineering Intelligence ──► Engineering Strategy
                                 ├─ Approach
                                 ├─ Context Objectives      ──► Context Engineering
                                 ├─ Skill Requirements       ──► Skill Selection
                                 ├─ Runtime Preferences      ──► Orchestration
                                 ├─ Validation Rigor         ──► Validation
                                 ├─ Coordination Intent      ──► Execution Strategy
                                 ├─ Autonomy Level           ──► Governance / Orchestration
                                 └─ Risk Assessment          ──► Governance / Planning
```

The Strategy is emitted as an **immutable recorded decision event** (INV-17). Its content is fixed
once recorded; replay reproduces the downstream pipeline from it without re-inference (`13`).

---

# The facets and their consumers

| Facet | Consumer | What EI supplies | What the consumer still owns |
|---|---|---|---|
| **Approach** | Planning | the engineering posture (surgical, exploratory, refactor…) | the concrete decomposition into Work Packages |
| **Context Objectives** | Context Engineering | what must be understood before work begins | gathering, enriching, organizing the context |
| **Skill Requirements** | Skill Selection (`05`) | required capabilities + composition intent | resolving concrete Skills that satisfy them |
| **Runtime Preferences** | Orchestration (`06`) | the capability posture a runtime needs | selecting the concrete runtime (INV-37) |
| **Validation Rigor** | Validation (`07`) | how strong the completion bar is; evidence classes | judging completion from actual evidence (INV-20) |
| **Coordination Intent** | Execution Strategy | sequential/parallel/approval posture, recovery bias | formalizing the declarative strategy (INV-05) |
| **Autonomy Level** | Governance / Orchestration (`08`) | how much may proceed unattended; gate placement | authorizing and enacting gates |
| **Risk Assessment** | Governance / Planning (`09`) | blast radius, reversibility, risk envelope | policy evaluation and decomposition within it |

---

# The producer/enactor discipline

Every facet is expressed as **intent, preference, requirement, or envelope** — never as the concrete
artifact the downstream engine owns. This is the rule that lets EI direct the platform without
violating a single existing invariant.

Concretely:

- EI says *"prefer a code-capable, high-context runtime."* It does **not** name Claude or Gemini.
  Orchestration selects (INV-37).
- EI says *"require root-cause-analysis, implementation, and regression-testing capabilities,
  composed sequentially."* It does **not** pick the concrete Skill objects. Skill Selection resolves
  them (INV-33).
- EI says *"high validation rigor; regression evidence is mandatory; a runtime 'success' without a
  passing regression check does not complete the work."* It does **not** judge whether the work is
  done. Validation does, from evidence (INV-20).
- EI says *"decompose within a surgical, minimal-change approach."* It does **not** create the Work
  Packages. Planning does (INV-03).

If EI ever emitted a concrete plan, a chosen runtime, a resolved Skill, or a completion verdict, it
would be doing a downstream engine's job. The Strategy is deliberately one level of abstraction
above every consumer.

---

# How the Strategy reaches consumers without changing their contracts

The Engineering Strategy is a **new, additive artifact** with its own contract (proposed
`contracts/engineering_strategy.md`; see `14`). It does not modify any existing contract.

The downstream engines already accept these decisions as inputs — today authored by the operator.
When a human writes `GoalSubmission(steps=…, capability_requirements=…, validation=…)`, the engines
consume operator-authored strategy. Engineering Intelligence becomes the **author** of that same
information. The engines' input contracts are unchanged; only the *source* of the declaration moves
from human to platform.

This is the crucial compatibility property: **EI adds a producer, not a mutation.** Every existing
engine keeps its contract, its responsibility, and its tests.

---

# What the output is NOT

| Not an EI output | Why | Owner |
|---|---|---|
| A Plan / Work Packages / Execution Graph | EI sets the approach, not the decomposition | Planning (INV-03) |
| A concrete runtime selection | capability preference only | Orchestration (INV-37) |
| A resolved Skill set | capability requirement only | Skill Selection (INV-33) |
| A Context Package | context objectives only | Context Engineering |
| A completion verdict / Evidence | rigor intent only | Validation (INV-20) |
| A governance decision | proposes within policy; never authorizes | Governance (INV-29) |
| A modified Goal | Goals are outcomes, immutable to EI | Intent Resolution (INV-08) |

---

# Explainability of the output

Every facet of the Strategy carries its rationale (INV-31):

- *why* this approach (what in the Goal/repository/knowledge drove it),
- *why* this rigor, *why* this autonomy level, *why* this risk envelope,
- *what assumptions* were made and *what was uncertain*.

The Strategy is therefore auditable end-to-end: an operator can read *why the platform decided to
pursue the work this way*, and replay reproduces that decision exactly (`13`).

---

# North Star

Engineering Intelligence emits one coherent decision, expressed as intent rather than instruction.

It points every downstream engine at the right target and trusts each to hit it its own way.
