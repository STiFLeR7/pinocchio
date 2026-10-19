# Governance

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence remains auditable, explainable, governed, and
provider-independent — and how it *evolves* over time without ever becoming a self-modifying,
ungoverned oracle.

---

# EI proposes; Governance authorizes

The foundational rule: Engineering Intelligence **proposes** an approach; it never **authorizes**
anything.

- EI does not evaluate policy. Only the Policy Engine evaluates policy (INV-28).
- EI does not authorize actions. Governance authorizes; it never executes, plans, supervises, or
  validates (INV-29).
- EI's proposed autonomy and risk envelope are *inputs* to Governance, bounded by policy that fails
  closed (INV-30).

EI is upstream advisory cognition operating inside a governance ceiling it does not set.

---

# Auditability and explainability (INV-31)

Every Engineering Strategy, and every facet within it, records its rationale as log data:

- *why* this classification and approach,
- *why* this rigor, autonomy, and risk envelope,
- *what* the Goal, repository, knowledge, and preferences contributed,
- *what* assumptions were made and *what* was uncertain,
- *what* coherence adjustments were applied and why.

An operator (or auditor) can therefore answer "why did the platform decide to pursue this work this
way?" entirely from the record — the same explainability standard every governance decision,
recovery choice, and validation verdict already meets (INV-31).

---

# Determinism on replay (INV-17)

EI's reasoning may be heuristic, but its output is captured as an immutable decision event, and
replay reproduces the pipeline from that event without re-inference (`12`). This makes EI:

- **testable** exactly like the prior engines — identical inputs (Goal + situation) plus the
  recorded Strategy reproduce identical downstream behavior;
- **replayable** — the event log remains the single source of truth (INV-13); the Strategy is a
  derived-once, then-fixed decision, never recomputed;
- **non-authoritative in its cognition, authoritative in its record** — the recorded Strategy is
  what the platform acts on, not a re-run of the model.

---

# How Engineering Intelligence evolves

The user asked whether EI should learn, consume Knowledge, consume Memory, and update itself. The
answers, each grounded in an existing invariant:

## Should it learn? — Yes, but indirectly.

EI improves as the platform accumulates Knowledge about which strategies worked. But it **never
learns by self-modification**. The loop is the platform's existing learning loop:

```
EI emits Strategy ─► work runs ─► Validation ─► Reflection observes strategy outcomes
   ▲                                                     │
   │                                                     ▼
   └──────── consumes read-only ◄──── Knowledge ◄──── Knowledge Candidates
```

Reflection observes how a strategy fared (accepted? overridden? did the approach succeed?) and
produces Knowledge Candidates; the Knowledge Engine decides persistence; EI consumes the persisted
result on its next run. This preserves INV-25 (Reflection proposes, Knowledge decides) and INV-26
(consumers reach learning only through Knowledge, never Reflection directly).

## Should it consume Knowledge? — Yes, read-only.

Exactly as Planning does (`../knowledge/09`, INV-26). EI queries Knowledge for prior successful
approaches and anti-patterns and biases its strategy accordingly. It never writes Knowledge.

## Should it consume Memory? — Indirectly, through references.

Operator Preferences and repository history may be Memory-backed, but EI consumes them as read-only
profiles/facts (`02`, `10`), referencing Memory rather than embedding it (INV-27). Memory remains a
separate subsystem (`../knowledge/` names it as out-of-scope-but-referenced); EI does not own it.

## Should it update itself? — No.

EI holds **no durable state of its own**. It is a stateless decision function over read-only inputs.
All learning lives in Knowledge and Preferences, written only through the governed Reflection →
Knowledge path. A self-updating EI would (a) violate INV-25/26 by creating a second, ungoverned
learning path, and (b) break determinism-on-replay by making EI's behavior depend on hidden internal
state. Statelessness is a hard design property, not an implementation convenience.

---

# Provider independence — permanently

Can EI remain provider-independent forever? **Yes**, and the design guarantees it three ways:

1. **EI reasons about capabilities, not models** (INV-32; Vision "Capabilities over Models"). Every
   facet references capabilities and skills, never providers (`05`, `06`).
2. **EI's own reasoning engine is itself a capability.** If EI uses an LLM to generate strategy, that
   LLM is accessed as a provider-independent runtime/harness capability (INV-34/36), swappable like
   any execution runtime. EI's *logic* does not change when the model behind it changes.
3. **The output names nothing provider-specific.** Because the Engineering Strategy never contains a
   provider, model, or version, adding/retiring/swapping any runtime changes nothing in EI — the
   same property that lets one Skill run on any runtime (INV-33), applied at the strategy layer.

Provider independence is therefore not a temporary state EI might outgrow; it is structural. As long
as the platform reasons in capabilities, EI stays provider-independent by construction.

---

# Relationship with the Policy Engine and Governance

| Interaction | Rule |
|---|---|
| EI reads Policy Context as decision inputs | it never evaluates policy (INV-28) |
| EI proposes autonomy/risk within a policy ceiling | Governance authorizes (INV-29) |
| Where policy is silent, EI assumes denial + gates | fail closed (INV-30) |
| EI records every decision with rationale | auditable (INV-31) |
| EI influences no governance rule | Policy Engine owns evaluation (INV-28) |

EI *informs* governance with a well-grounded risk assessment and autonomy proposal; governance
*decides*. The relationship mirrors Knowledge's: Knowledge "influences but never evaluates
governance policy" (`../knowledge/ARCHITECTURE_REVIEW.md §3`) — so does EI.

---

# Governance boundary summary

| Engineering Intelligence | Enforced by |
|---|---|
| ✓ proposes approach, autonomy, risk within policy | own responsibility |
| ✓ records rationale for every decision | INV-31 |
| ✓ deterministic on replay | INV-17, INV-13 |
| ✓ learns only through Reflection → Knowledge | INV-25/26 |
| ✓ provider-independent, permanently | INV-32/33 |
| ✗ never evaluates policy | Policy Engine (INV-28) |
| ✗ never authorizes actions | Governance (INV-29) |
| ✗ never holds durable state / self-updates | statelessness (this doc) |

---

# North Star

Engineering Intelligence is a governed advisor, not an oracle.

It proposes within a ceiling it does not set, explains every choice, commits its choices to the
record, learns only through the platform's one governed learning path, and never names a provider.
Its intelligence grows; its accountability never leaks.
