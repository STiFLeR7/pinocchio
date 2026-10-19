# The Engineering Strategy

Status: Target Architecture (design only)

---

# Purpose

The Engineering Strategy is the single artifact Engineering Intelligence produces. This document
specifies its shape, its facets, its coherence rules, and its lifecycle.

It is the boundary contract between EI and every downstream engine. It is **declarative** — it
describes an engineering approach; it never performs one.

---

# Design principles

## Declarative

The Strategy describes *how work should proceed*. It does not proceed. Like Execution Strategy
(`../13`), which describes coordination without coordinating, the Engineering Strategy describes
approach without executing it.

## Coherent

The Strategy is not a bag of independent settings. Its facets constrain one another and are checked
for internal consistency before the Strategy is emitted (`01`). Producing *one coherent decision* is
EI's whole reason to exist.

## Intent-bearing, not instruction-bearing

Every facet carries intent, preference, requirement, or envelope — never the concrete artifact a
downstream engine owns (`03`).

## Immutable once emitted

A Strategy is recorded as an immutable decision (INV-17). Downstream engines read it; none mutates
it. If the situation changes mid-flight, the platform produces a *new* Strategy, it never edits the
old one (see Lifecycle).

## Explainable

Every facet records its rationale (INV-31).

---

# Facets

The Strategy contains the following facets. Each is detailed in its own document; this is the
canonical assembly.

## 1. Classification

What kind of engineering work this is.

Examples: `bug-fix`, `feature`, `refactor`, `investigation`, `migration`, `research`,
`documentation`, `release`.

Classification is the seed from which the other facets follow.

## 2. Approach

The engineering posture.

Examples: `surgical` (minimal change), `exploratory`, `research-first`, `validation-first`,
`refactor-safe`, `incremental`, `spike-then-implement`.

The Approach shapes how Planning decomposes and how much context is gathered.

## 3. Context Objectives (→ Context Engineering)

What must be understood before work begins — expressed as objectives, not gathered content.

Examples: "understand the authentication flow and its tests"; "identify the failing module and its
recent change history"; "survey prior art for the research question."

## 4. Skill Requirements (→ Skill Selection, `05`)

The operational capabilities the approach demands and how they compose — as capability references,
never concrete Skills.

Example: `[root-cause-analysis → implementation → regression-testing]`, composed sequentially.

## 5. Runtime Preferences (→ Orchestration, `06`)

The capability posture a runtime must have — as capabilities, never providers (INV-32).

Example: "prefer high-context, code-generation-capable, filesystem-and-VCS-capable; avoid
low-context runtimes for this work."

## 6. Validation Rigor (→ Validation, `07`)

How strong the completion bar must be, and which evidence classes are mandatory.

Example: "high rigor; mandatory evidence: passing regression tests + unchanged public contract; a
runtime self-report of success is insufficient (INV-20)."

## 7. Coordination Intent (→ Execution Strategy)

The coordination and recovery posture — as intent the Execution Strategy layer formalizes (INV-05).

Example: "sequential; retry-then-escalate on failure; checkpoint before the production-touching
step."

## 8. Autonomy Level (→ Governance / Orchestration, `08`)

How much may proceed without human approval, and where approval gates belong.

Example: "supervised; human approval required before any irreversible action (commit to main,
deploy)."

## 9. Risk Assessment (→ Governance / Planning, `09`)

Blast radius, reversibility, and the accepted risk envelope.

Example: "blast radius: production auth; reversibility: medium (revert possible); envelope:
medium-high — gate the irreversible step."

---

# Coherence rules

Before a Strategy is emitted, EI checks that its facets are mutually consistent. These are hard
rules, not guidelines:

| Rule | Reason |
|---|---|
| **Autonomy ≤ what Risk + Policy permit.** High autonomy on high-risk/irreversible actions is invalid; EI must insert an approval gate. | Autonomy never exceeds risk tolerance (`08`, `09`, INV-30). |
| **Runtime Preferences ⊆ available capabilities.** EI never prefers a capability no healthy harness offers. | Feasibility (`02`, INV-36). |
| **Validation Rigor ≥ Risk floor.** Higher risk mandates stronger evidence classes. | Evidence-backed completion (INV-20). |
| **Skill Requirements ⊆ capabilities that exist.** EI never requires a capability the platform cannot provide. | Capability model (INV-32). |
| **No procedure in the Goal.** EI never writes steps/plan back into the Goal. | INV-08. |
| **Nothing concrete.** No facet names a runtime, resolves a Skill, or fixes a completion verdict. | Producer/enactor discipline (`03`). |

A Strategy that fails a coherence rule is not emitted; EI adjusts a facet (typically by lowering
autonomy or raising rigor / inserting a gate) until the Strategy is coherent, and records why.

---

# Worked example — the reference request

Operator request (via Intent Resolution) → Goal:

```
Goal: resolve the bug reported by the design partner in D:/project_x, then report back.
Domain: software-engineering. Priority: high. Confidence: medium.
```

Engineering Strategy EI would produce:

```
Classification:       bug-fix (production-adjacent, partner-reported)
Approach:             investigate-first → surgical minimal-change
Context Objectives:   locate the defect from the report; understand the failing module +
                      its tests + recent change history
Skill Requirements:   [root-cause-analysis → implementation → regression-testing → reporting],
                      composed sequentially
Runtime Preferences:  prefer code-generation + filesystem + VCS-capable, high-context
Validation Rigor:     high; mandatory evidence = reproduction fixed + regression suite green +
                      no unrelated diff; runtime "done" is insufficient (INV-20)
Coordination Intent:  sequential; retry-once-then-escalate; checkpoint before commit
Autonomy Level:       supervised; approval gate before commit and before report-send
Risk Assessment:      blast radius = partner's repo; reversibility = high (revert/branch);
                      envelope = medium — gate the commit
Rationale:            recorded per facet (INV-31)
```

Note what EI did **not** do: it did not open Claude Code, gather the files, decompose into concrete
work packages, pick a runtime, run tests, decide the fix was correct, or commit. It decided *how the
work should proceed* and handed a coherent Strategy to the engines that do those things.

---

# Lifecycle

```
Requested        (EI invoked with a Goal + situation)
   ↓
Assessed         (classification + situation assessment)
   ↓
Composed         (facets determined, coherence-checked)
   ↓
Emitted          (immutable decision event recorded — INV-17)
   ↓
Consumed         (downstream engines read facets)
```

Re-strategizing:

- The Strategy is **immutable**. If new information invalidates it (a discovery mid-execution, a
  recovery escalation), the platform requests a **new** Strategy from EI, superseding the old one by
  reference — never editing it. This mirrors Knowledge's supersession model (`../knowledge/10`) and
  keeps the event log the single source of truth (INV-13).
- Re-strategizing is a *governed* event: it is recorded, explainable, and bounded, exactly like
  recovery re-decisions (INV-22).

---

# North Star

The Engineering Strategy is one coherent, immutable, declarative decision: how this work should
proceed.

It is the artifact that was missing — the written-down judgment an engineer makes before starting,
now produced by the platform and enacted by its engines.
