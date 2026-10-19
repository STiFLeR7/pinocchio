# Input Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the **canonical inputs** to Engineering Intelligence: what EI receives, where
each input originates, and the form it takes at the boundary.

The governing rule: EI consumes every input **read-only or by value**. It owns none of them, writes
none of them back, and imports no subsystem that produces one downstream of it (INV-01).

---

# The six canonical inputs

```
                 ┌─────────────────────────────┐
   Goal ─────────►                             │
   Repository ───►                             │
   Understanding │   Engineering Intelligence  ├──► Engineering Strategy
   Knowledge ────►                             │
   Preferences ──►                             │
   Policy Ctx ───►                             │
   Environment ──►                             │
                 └─────────────────────────────┘
```

| Input | Origin | Form at boundary | Binding |
|---|---|---|---|
| **Goal** | Intent Resolution (`../16`) | value (frozen `contracts/goal.md`) | INV-08 |
| **Repository Understanding** | Repository Intelligence (`10`) | read-only view | INV-27 |
| **Knowledge** | Knowledge Engine (`../knowledge/09`) | read-only query result | INV-26 |
| **Operator Preferences** | Preference profile (Knowledge/Memory-backed) | read-only view | INV-24 |
| **Policy Context** | Policy Engine (ADR-004) | read-only decision inputs | INV-28 |
| **Environment Facts** | Harness Registry (INV-36) | capability availability only | INV-32/36 |

Anything not on this list is **not** an EI input. EI does not read raw operator text (that is
Intent Resolution's), raw runtime output, or execution events.

---

# 1. Goal

The normalized outcome from Intent Resolution.

- Carries the objective, domain, scope, constraints, priority, and confidence (`../16`).
- Describes an **outcome, never a procedure** (INV-08). EI must never receive — or write back — a
  plan, step, work package, or runtime inside the Goal.
- Is the *only* representation of operator intent EI sees. EI never re-interprets intent; if the
  Goal is ambiguous or low-confidence, that is Intent Resolution's concern, surfaced *before* EI
  runs (`11`).

The Goal answers **what**. EI's job begins at **how**.

---

# 2. Repository Understanding

The facts about the target system, served by Repository Intelligence (`10`).

- Structure, languages, entry points, test presence, architectural markers (ADRs, contracts),
  recent change history, and known prior failures — as **references and facts**, never as embedded
  file content (INV-27).
- Read-only. EI never mutates the repository or its understanding.
- Optional-by-availability: for a non-repository goal (pure research, writing), Repository
  Understanding may be empty. EI's approach selection must tolerate its absence.

Repository Understanding answers **what system are we operating on**. It grounds the approach in
reality rather than assumption.

---

# 3. Knowledge

Prior validated operational understanding, retrieved read-only from the Knowledge Engine.

- Consumed exactly as Planning consumes it: by read-only query, never by importing Reflection
  (INV-26). EI depends on *learning* only through persisted Knowledge.
- Supplies confidence- and freshness-aware understanding: prior successful approaches for similar
  work, known anti-patterns, effective validation strategies (`../knowledge/09`).
- EI **reads** Knowledge; it never writes it. New learning about EI's own strategies flows back only
  through Reflection → Knowledge (`13`), never by EI self-updating.

Knowledge answers **what has worked before**.

---

# 4. Operator Preferences

The durable profile of *how this operator engineers* — the "understands how I engineer" step of the
original vision.

- Coding preferences, review habits, architectural preferences, repository-specific practices,
  risk tolerance, and preferred autonomy defaults.
- Modeled as a **read-only profile backed by Knowledge/Memory**, not a store EI owns. This keeps EI
  stateless of its own learning and preserves the single writer rule for durable understanding
  (INV-24, INV-25).
- Preferences *bias* the Strategy; they never *override* policy. A preference for high autonomy
  cannot exceed what Policy Context permits (INV-28, INV-30).

Preferences answer **how does this operator like work done**. They personalize the approach.

> **Provenance note.** Preferences are learned, not declared once. See `09`/`13` for how Reflection
> observes accepted/overridden strategies and feeds preference evolution through Knowledge — EI
> consumes the result, it does not author it.

---

# 5. Policy Context

The governing constraints EI must respect.

- Supplied as **decision inputs the Policy Engine evaluates**, not as rules EI interprets. EI never
  hardcodes or evaluates a governance rule (INV-28).
- Establishes hard ceilings on autonomy, permitted risk, allowed runtimes/capabilities, and
  approval requirements.
- Fails closed: where policy does not permit an action, EI must assume it is denied and route to an
  approval gate rather than proceed (INV-30).

Policy Context answers **what is allowed**. It bounds every facet of the Strategy.

---

# 6. Environment Facts

What the platform can actually do right now.

- Available capabilities and their health, from the single source of truth — the Harness Registry
  (INV-36). Provider-independent: capabilities, not providers (INV-32).
- EI uses this to keep the Strategy *feasible* — it does not prefer a runtime capability that no
  healthy harness offers. It expresses preference by capability; Orchestration still selects the
  concrete runtime (INV-37).

Environment Facts answer **what is currently possible**. They keep the Strategy realizable.

---

# Input coherence rules

- **Read-only, always.** No input is mutated or written back. EI has no side effects on its inputs.
- **By value at the boundary.** Like Knowledge Candidates into the Knowledge Engine, inputs cross
  the EI boundary as values/read-only views, so EI imports no downstream subsystem (INV-01).
- **Absence-tolerant.** Repository Understanding, Knowledge, and Preferences may be empty (first
  run, non-repo goal, new operator). EI must degrade to a conservative default approach, not fail.
- **Policy is a ceiling, not a suggestion.** Preferences and Knowledge bias *within* Policy Context;
  they never exceed it.

---

# What EI never receives

| Not an input | Why | Who handles it |
|---|---|---|
| Raw operator text / conversation | EI begins at the Goal | Intent Resolution (`../16`) |
| Raw file content | reference, never embed | Repository Intelligence (`10`, INV-27) |
| Reflection outputs directly | learning flows through Knowledge | Knowledge Engine (INV-26) |
| Execution events / runtime output | EI is upstream of execution | Supervision / Validation |
| Provider identities / model names | capabilities, not providers | Harness Registry (INV-32) |

---

# North Star

Engineering Intelligence is only as good as its situational awareness.

It reads the goal, the system, the history, the operator, the rules, and the environment — all
read-only — and owes an approach grounded in every one of them.
