# Risk Model

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence assesses **risk** and expresses a **risk
envelope** — the facet that anchors validation rigor (`07`) and autonomy (`08`) and gives Governance
a work-grounded basis for its decisions.

---

# Risk is assessed, not enforced

Engineering Intelligence *assesses* risk and records the assessment as a facet of the Strategy. It
does not *enforce* anything with it — enforcement is Governance's (INV-29), evaluated by the Policy
Engine (INV-28). EI's risk assessment is an input to those decisions and a driver of its own
coherence rules; it is never a governance rule EI evaluates itself.

---

# The three dimensions

EI assesses risk along three dimensions. Together they define the risk envelope.

## 1. Blast radius

*How far damage could spread if the work goes wrong.*

Examples: a scratch file (self); a single module (local); a shared library (broad); production
infrastructure or an external party (systemic).

## 2. Reversibility

*How hard it is to undo.*

Examples: uncommitted edit (trivial — discard); branch commit (easy — revert); merge to main (medium
— revert PR); deploy (hard — rollback + side effects); external message / irreversible delete (none).

## 3. Confidence

*How sure EI is about the approach and the situation.*

Derived from Goal confidence (`../16`), repository understanding completeness (`10`), and Knowledge
support (`02`). Low confidence *raises* effective risk even when blast radius is small.

---

# The risk envelope

The **risk envelope** is the bounded risk the Strategy accepts. It is the composition of the three
dimensions into a single accepted bound, plus the actions that fall *outside* it and therefore must
be gated or blocked.

```
Risk Assessment:
  blast radius:   partner's repository (local–broad)
  reversibility:  high (branch + revert available) — except commit-to-shared (medium)
  confidence:     medium (report is clear; root cause not yet located)
  envelope:       medium
  outside envelope: commit-to-shared, report-send  → require approval gates (`08`)
```

Actions inside the envelope proceed at the chosen autonomy level; actions outside it force a gate
(or, if policy forbids them outright, block the work and surface the reason).

---

# How risk drives the other facets

Risk is the anchor facet. The coherence rules (`04`) bind the others to it:

| Rule | Direction |
|---|---|
| **Autonomy ≤ f(risk)** | higher risk → lower autonomy, more gates (`08`) |
| **Validation Rigor ≥ g(risk)** | higher risk → stronger mandatory evidence (`07`) |
| **Coordination checkpoints ← risk** | irreversible steps get a checkpoint before them (`04`) |
| **Runtime posture ← risk** | higher-stakes work prefers higher-capability, observable runtimes (`06`) |

This is why risk is assessed *before* the dependent facets are finalized in the interpret→strategize
pipeline (`01`).

---

# Blast-radius and reversibility as first-class safety

The operational gap analysis flagged **actuation safety / blast-radius control** as a prerequisite
for safe autonomy. EI's risk model is where that judgment is *made*; enforcement is Governance's and
Orchestration's. The division:

- **EI (here):** classifies each consequential action's blast radius and reversibility, sets the
  envelope, and marks out-of-envelope actions for gating.
- **Governance / Policy Engine:** evaluates whether an action is permitted at all (INV-28/29).
- **Orchestration:** enacts the checkpoint-before-irreversible-step and the pause at each gate
  (INV-23), and every execution remains checkpoint-aware so a risky step can be resumed from the
  nearest valid checkpoint, never from operator intent (INV-18).

EI supplies the *judgment* that a step is dangerous; the platform supplies the *guardrails*.

---

# Uncertainty raises risk

A distinctive rule: **low confidence increases effective risk**, independent of blast radius.

If EI cannot locate the defect, or the repository understanding is thin, or Knowledge offers no
prior for this class of work, the assessment tightens the envelope — lowering autonomy and raising
rigor — even for nominally small changes. This encodes the engineering instinct that *"I'm not sure
what this touches"* is itself a risk. It also aligns with Intent Resolution's principle that low
confidence should prefer clarification over assumption (`../16`).

---

# Boundary summary

| Risk facet | Enforced by |
|---|---|
| ✓ EI assesses blast radius, reversibility, confidence | own responsibility |
| ✓ EI sets a risk envelope | own responsibility |
| ✓ EI marks out-of-envelope actions for gating | drives autonomy (`08`) |
| ✓ EI raises effective risk under uncertainty | own responsibility |
| ✗ EI never enforces risk | Governance (INV-29) |
| ✗ EI never evaluates policy | Policy Engine (INV-28) |
| ✗ EI never enacts checkpoints/pauses | Orchestration (INV-18/23) |

---

# North Star

Engineering Intelligence answers: *how dangerous is this, and how sure are we?*

That answer anchors how much the platform may do alone and how hard it must prove it succeeded. Risk
is judged here; it is guarded elsewhere.
