# Intent Interpretation

Status: Target Architecture (design only)

---

# Purpose

This document answers a specific architectural question:

> Should Intent Understanding be a subsystem, a service, part of Engineering Intelligence, or
> something else?

**Verdict: it is already a ratified layer — Intent Resolution (`../16`) — and it stays there.**
Engineering Intelligence does **not** absorb it. EI consumes the Goal that Intent Resolution
produces.

This document justifies keeping the boundary and shows how EI and Intent Resolution compose.

---

# Intent Understanding already has an owner

The frozen architecture defines the first capability layer as **Intent Resolution** (`../16`; per
ADR-003 the canonical name, formerly "Executive Intelligence"). Its ratified responsibility:

> transform raw operator requests into normalized operational Goals — understand intent, resolve
> ambiguity, determine scope, request clarification, estimate confidence.

This is a complete, owned responsibility with a frozen output (`contracts/goal.md`, `contracts/
intent.md`). Engineering Intelligence must not re-open it, or the platform would have two layers
interpreting intent — a direct INV-02 and INV-07 violation.

---

# Why EI must not absorb intent understanding

## 1. Two responsibilities would collapse into one layer (INV-02)

Understanding *what* is asked and deciding *how* to pursue it are different acts of cognition.
Merging them creates a single layer that both parses language and designs engineering approaches —
untestable as one responsibility and impossible to reason about in isolation.

## 2. The Goal is a clean, frozen contract (INV-07/08)

Intent Resolution's output is a Goal that **describes an outcome, never a procedure** (INV-08). That
contract is the perfect input for EI: unambiguous, normalized, procedure-free. If EI reached back
into raw text, it would depend on an unnormalized, ambiguous input and re-derive what Intent
Resolution already settled.

## 3. Ambiguity belongs before EI, not inside it

Intent Resolution prefers clarification over assumption when confidence is low (`../16`). That gate
must fire *before* EI runs. EI should never receive an ambiguous goal and "guess" an approach — it
should receive a resolved Goal (or a clarification loop should have already run). Keeping intent
understanding upstream preserves this ordering.

## 4. Domain-agnostic intent vs. engineering-specific strategy

Intent Resolution is deliberately **domain-agnostic** — it works for research, writing, operations,
personal productivity (`../16`). Engineering Intelligence is **engineering-specific** — its
approaches, skills, and risk model are about *building software systems*. Collapsing them would
either pollute the domain-agnostic intent layer with engineering concerns or dilute EI's engineering
focus. They are cleanly separable and should stay separate.

---

# How they compose

```
Operator request (natural language, any modality)
        │
        ▼
Intent Resolution        understand → resolve ambiguity → normalize
        │   Goal  (outcome, domain, scope, constraints, priority, confidence)
        ▼
Engineering Intelligence  classify → assess → choose approach → compose Strategy
        │   Engineering Strategy
        ▼
downstream engines
```

- Intent Resolution answers **what** and hands EI a Goal.
- EI answers **how** and hands the engines a Strategy.
- Neither re-does the other's work. Intent Resolution never chooses an approach; EI never
  re-interprets intent.

---

# The "understands how I engineer" step

The original vision listed two distinct understanding steps:

```
Nexus understands intent          ← Intent Resolution (../16)
Nexus understands how I engineer  ← Engineering Intelligence (Operator Preferences, `02`)
```

These are *different*. "Understands intent" is about *this request*. "Understands how I engineer" is
about *this operator across requests* — a durable preference profile EI consumes (`02`). Placing the
first in Intent Resolution and the second in EI keeps each where its data and lifecycle belong:
per-request normalization vs. cross-request personalization.

---

# What about a shared "service"?

Could intent understanding be a stateless *service* both layers call? No — and it need not be. It is
already a *layer* with a frozen contract and a clear position in the one-way pipeline (INV-01). A
"service" framing would invite callers to invoke it from multiple layers, breaking the strict
layering the architecture depends on. Intent Resolution is a pipeline stage, not a utility; EI
consumes its *output*, not its *behavior*.

---

# Boundary summary

| Concern | Owner |
|---|---|
| Parse request, resolve ambiguity, normalize to a Goal | Intent Resolution (`../16`) |
| Estimate intent confidence; request clarification | Intent Resolution |
| Classify engineering work; choose approach | Engineering Intelligence |
| Understand *how this operator engineers* | Engineering Intelligence (Preferences, `02`) |
| Re-interpret operator intent | nobody downstream — Planning must not either (`../16`) |

---

# North Star

Intent understanding is not part of Engineering Intelligence. It is the layer above it, already
ratified.

EI begins where Intent Resolution ends: with a clear Goal, and the question *how should we pursue
it?*
