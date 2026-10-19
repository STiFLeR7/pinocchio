# Engineering Intelligence — Overview

Status: Target Architecture (design only)

---

# Purpose

Engineering Intelligence is the platform's **strategy-cognition layer**.

It sits between understanding a goal and pursuing it.

Intent Resolution decides *what* the operator wants.

Execution performs work.

Engineering Intelligence decides *how* the work should proceed — before any context is gathered,
any plan is drawn, or any runtime is chosen.

It produces one coherent artifact, the **Engineering Strategy**, that parameterizes every
downstream engine.

---

# The gap it closes

The pipeline below runs today.

```
Goal → Context → Planning → Execution Strategy → Skills → Work Packaging
     → Orchestration → Execution → Supervision → Validation → Recovery
     → Reflection → Knowledge
```

Every layer after understanding assumes its inputs were *decided by someone*.

Planning assumes the work breakdown, the required capabilities, the validation bar, and the
runtime posture were chosen with judgment.

Today that judgment is the operator's. When a human writes the submission, the human is the
engineering intelligence.

Engineering Intelligence is the subsystem that performs that judgment inside the platform.

---

# Architectural position

Engineering Intelligence is a **single new layer** inserted between two existing layers. It adds
one artifact; it changes no existing engine's responsibility.

```
Operator
   │
   ▼
Intent Resolution                         (../16 — understand → Goal)
   │  Goal
   ▼
Engineering Intelligence                  (THIS — decide → Engineering Strategy)
   │  Engineering Strategy
   ├──────────────► Context Engineering    (consumes Context Objectives)
   ├──────────────► Planning               (consumes approach + constraints)
   ├──────────────► Execution Strategy     (consumes coordination + recovery intent)
   ├──────────────► Skill Selection        (consumes skill requirements)
   ├──────────────► Orchestration          (consumes runtime preferences)
   └──────────────► Validation             (consumes validation rigor + evidence intent)
```

Engineering Intelligence **consumes** the Goal. It **emits** the Engineering Strategy. The
existing engines **enact** it. No engine reaches *up* into EI (INV-01).

---

# Why a new layer and not an extension of an existing one

Each existing layer owns exactly one responsibility (INV-02). None of them owns *cross-cutting
engineering judgment*:

- Intent Resolution owns intent, not approach. It must not begin choosing skills or rigor, or it
  would stop being a pure `request → Goal` normalizer (`11`).
- Planning owns decomposition, not the *envelope* the decomposition happens inside. Planning is
  handed an approach; it does not choose whether the work is exploratory or surgical.
- Execution Strategy owns *declarative coordination given a plan*. It is downstream of Planning; it
  cannot set the strategy that shapes the plan itself.
- Skill Selection resolves capabilities into concrete Skills. It does not decide which capabilities
  the work *needs*.

The judgment that spans all of these — "this is a surgical production bug fix, so: minimal context,
root-cause + implementation + regression skills, high validation rigor, a code-capable runtime,
supervised autonomy, medium-high risk because it touches production" — has no owner. That coherent,
cross-cutting decision is Engineering Intelligence.

---

# Inputs (canonical — see `02`)

Engineering Intelligence receives, all **read-only / by value**:

- **Goal** — the normalized outcome from Intent Resolution (`../16`).
- **Repository Understanding** — from Repository Intelligence (`10`).
- **Knowledge** — prior validated understanding, read-only (`../knowledge/09`).
- **Operator Preferences** — how this operator engineers (a Knowledge/Memory-backed profile).
- **Policy Context** — the governing constraints EI must respect (evaluated by the Policy Engine,
  never by EI — INV-28).
- **Environment Facts** — available capabilities and their health, from the Harness Registry
  (INV-36), as capability availability only.

---

# Outputs (canonical — see `03`)

Engineering Intelligence produces exactly one artifact:

- **Engineering Strategy** (`04`) — a declarative decision object containing the engineering
  approach, context objectives, skill requirements, runtime preferences, validation rigor, autonomy
  level, and risk assessment.

Everything EI "produces" is a facet of that one artifact. There is no second output object, no
side-channel, and no direct call into a downstream engine that bypasses the Strategy.

---

# Dependency direction

```
nexus_engineering → { nexus_core, nexus_infra }        (only)

Repository Intelligence ─┐
Knowledge (read-only) ───┼─► Engineering Intelligence ─► Engineering Strategy ─► downstream engines
Preferences (read-only) ─┤                                                        (read-only)
Policy Context ──────────┘
```

- EI imports no downstream engine (not Planning, not Execution, not Validation).
- EI is imported by nothing upstream.
- Because EI imports no downstream engine, downstream engines **cannot reach EI through their
  inputs** — they receive the Strategy by value, exactly as Planning receives Knowledge by value.
- This matches the direction of every layer built so far
  (`nexus_knowledge → {nexus_core, nexus_infra}`; `nexus_runtime → {nexus_core, nexus_infra}`).

---

# Canon glossary

| Term | Meaning |
|---|---|
| **Engineering Intelligence (EI)** | The subsystem specified here; decides the engineering approach. |
| **Engineering Strategy** | The one declarative artifact EI emits (`04`). |
| **Approach** | The engineering posture (e.g., exploratory, surgical, research-first, refactor). |
| **Repository Understanding** | Repository facts served by Repository Intelligence (`10`). |
| **Operator Preferences** | The durable profile of how an operator engineers (`02`). |
| **Autonomy Level** | How much EI/the platform may decide without human approval (`08`). |
| **Risk Envelope** | The bounded risk the Strategy accepts (`09`). |
| **Determinism seam** | Heuristic generation, immutable recorded output, deterministic replay (`13`). |

---

# North Star

Execution performs work.

Intent Resolution understands the goal.

Engineering Intelligence decides how to pursue it.

Nexus should never *pursue* what it has not first decided how to pursue — just as it should never
execute what it has not first understood.
