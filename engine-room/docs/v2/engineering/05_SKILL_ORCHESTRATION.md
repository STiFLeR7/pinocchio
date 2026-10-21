# Skill Orchestration

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence expresses **skill requirements and composition
intent**, and why that is distinct from Skill Selection (`../06`).

The distinction is the same producer/enactor discipline used everywhere in this design: EI decides
*which capabilities the approach needs and how they compose*; Skill Selection resolves *which
concrete Skills satisfy them*.

---

# Two different questions

| Question | Owner |
|---|---|
| "What capabilities does this approach require, and in what composition?" | **Engineering Intelligence** |
| "Which registered Skills satisfy those capabilities?" | Skill Selection (`../06`) |
| "Who (which runtime) performs the selected Skill?" | Orchestration (INV-37) |

The frozen architecture already separates the last two (`../06`: "Planning determines what
capabilities are required; Skill Selection determines which Skills satisfy those capabilities").
Engineering Intelligence supplies the *first* question's answer — the capability requirement — which
today the operator supplies by hand.

---

# What EI produces: Skill Requirements

A **Skill Requirement** in the Engineering Strategy is:

- a set of **required capabilities**, referenced by the frozen Capability model (INV-32) — never
  concrete Skill identities;
- a **composition intent** — how the capabilities relate (sequential, parallel, conditional,
  iterative);
- **rationale** — why the approach demands each capability (INV-31).

Example (bug-fix approach):

```
Skill Requirements:
  capabilities: [ root-cause-analysis, implementation, regression-testing, reporting ]
  composition:  root-cause-analysis → implementation → regression-testing → reporting  (sequential)
  rationale:    a partner-reported production bug requires diagnosis before change,
                regression proof after change, and a report as the deliverable
```

EI stops here. It does not name a Skill, choose a Skill version, or bind a runtime.

---

# What EI does NOT do

- **Does not resolve Skills.** Skill Selection maps capabilities → concrete registered Skills using
  capability, context, constraints, and evidence requirements (`../06`). EI never touches the Skill
  Registry.
- **Does not bind runtimes.** Skills are runtime-independent (INV-33); the same Skill runs on any
  runtime. EI's runtime *preference* is a separate facet (`06`), evaluated by Orchestration.
- **Does not define Skill procedures.** A Skill's procedure/validation/recovery is the Skill's own
  (`../06`). EI only asks *for the capability*.

---

# Composition intent, not a workflow

EI expresses how capabilities *compose*, but it must not smuggle a concrete plan into that
composition (which would usurp Planning, INV-03).

The line:

- **Composition intent (EI):** "diagnose before you change; prove no regression after you change."
  This is an ordering *constraint on capabilities*.
- **Plan (Planning):** "Work Package 1: bisect commits a1..a9; Work Package 2: patch module X;
  Work Package 3: run suite Y." This is *concrete decomposition* — Planning's job.

EI's composition intent shapes the plan; it is not the plan. Planning may expand one capability into
several Work Packages, or combine several, as long as it honors the composition intent and approach.

---

# Skill composition and the Skills doc

The frozen Skills architecture already anticipates composition (`../06`, "Skill Composition":
`Resolve Production Bug → Root Cause Analysis → Repository Analysis → Implementation → Testing →
Documentation → Validation`). That example is exactly a **composition intent**. What the frozen doc
left unowned is *who decides that composition for a novel goal*. Engineering Intelligence is that
owner. It fills the gap the Skills doc named but did not assign.

---

# Interaction with Knowledge and Preferences

- **Knowledge** may tell EI that, for similar past goals, a particular capability composition
  succeeded or a particular one failed (an anti-pattern). EI consumes this read-only (INV-26) to
  bias composition intent.
- **Preferences** may tell EI that this operator always wants a code-review capability before
  reporting. EI honors that within policy (`02`).

Neither lets EI reach into Skill Selection; both only shape the *requirement* EI emits.

---

# Boundary summary

| Skill Orchestration facet | Enforced by |
|---|---|
| ✓ EI declares required capabilities | Capability model (INV-32) |
| ✓ EI declares composition intent | own responsibility |
| ✓ EI records rationale | INV-31 |
| ✗ EI never resolves concrete Skills | Skill Selection (`../06`) |
| ✗ EI never binds a runtime to a Skill | Orchestration (INV-37), Skills runtime-independent (INV-33) |
| ✗ EI never defines a Skill's procedure | Skills own their procedure (`../06`) |
| ✗ EI never emits a concrete plan as "composition" | Planning (INV-03) |

---

# North Star

Engineering Intelligence decides *what capabilities the work needs and how they fit together*.

Skill Selection decides *which Skills those are*. Runtimes decide nothing about capability — they
provide it.
