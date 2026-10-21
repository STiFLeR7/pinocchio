# Decision Flow

Status: Target Architecture (design only)

---

# Purpose

This document traces the end-to-end flow through Engineering Intelligence — from the Goal arriving
to the Strategy being consumed — and marks exactly where heuristics are permitted and where
determinism binds.

---

# The flow, end to end

```
Operator
   │  request
   ▼
Intent Resolution ──────────────► Goal                                (../16)
   │
   ▼
[ Engineering Intelligence ]
   │
   │  reads (all read-only / by value):
   │    • Goal
   │    • Repository Understanding        (Repository Intelligence, `10`)
   │    • Knowledge                       (read-only query, `../knowledge/09`)
   │    • Operator Preferences            (`02`)
   │    • Policy Context                  (Policy Engine inputs, INV-28)
   │    • Environment Facts               (Harness Registry, INV-36)
   │
   ▼
Work Classification ──► Situation Assessment ──► Approach Selection
   │
   ▼
Facet Determination
   • Context Objectives   • Skill Requirements   • Runtime Preferences
   • Validation Rigor     • Coordination Intent  • Autonomy Level   • Risk Assessment
   │
   ▼
Coherence Check  (facets mutually consistent? — `04`)
   │  (adjust facets until coherent; record why)
   ▼
Emit Engineering Strategy  ──► recorded as an immutable decision event  (INV-17)
   │
   ├──► Context Engineering   (Context Objectives)
   ├──► Planning              (Approach + constraints)
   ├──► Execution Strategy    (Coordination Intent)
   ├──► Skill Selection       (Skill Requirements)
   ├──► Orchestration         (Runtime Preferences, Autonomy gates)
   └──► Validation            (Validation Rigor)
```

Everything above the "Emit" line is EI. Everything below is the existing platform, unchanged, now
parameterized by the Strategy.

---

# Where heuristics are permitted

Engineering Intelligence *reasons*. Classification, situation assessment, and approach selection are
judgment calls that may use a reasoning capability (an LLM, accessed as a provider-independent
runtime capability — `06`, INV-32). This is heuristic, probabilistic cognition, and that is
appropriate: choosing an engineering approach is not a lookup.

Heuristics are permitted **only** in the generation stages:

- Work Classification
- Situation Assessment
- Approach Selection
- Facet Determination (the *reasoning* that proposes each facet)

---

# Where determinism binds — absolutely

The moment a Strategy is **emitted**, determinism takes over and never relaxes:

- **The output is captured as data (INV-17).** The emitted Engineering Strategy — every facet, every
  rationale — is recorded as an immutable event. The heuristic reasoning that produced it is *not*
  re-run on replay; its *result* is replayed.
- **Replay reproduces the pipeline exactly.** Given the same recorded Strategy, every downstream
  engine produces the same governed outcome, with no re-inference — identical to how recorded LLM
  execution outputs replay (INV-17), and how Knowledge/Runtime already behave.
- **The coherence check is deterministic.** Given the facets, the coherence rules (`04`) are a pure
  function; the same facets always yield the same accept/adjust outcome.
- **Every decision is auditable (INV-31).** The recorded Strategy explains itself; an operator can
  read *why* the platform chose this approach and reproduce it.

This is the **determinism seam**: heuristic *before* emission, deterministic *at and after*
emission. It is the identical pattern the platform already uses at the execution boundary — an LLM
runtime reasons non-deterministically, but its output is recorded and replayed as data. EI applies
that pattern one layer up, at the *strategy* boundary instead of the *execution* boundary.

```
        heuristic  │  deterministic
  reasoning ──────►│──────► recorded Strategy ──────► replayable pipeline
   (may use LLM)   │        (immutable, INV-17)       (no re-inference)
                 EMIT
```

---

# Why this is safe

A skeptic might object: "if EI uses an LLM, the pipeline is no longer deterministic." The seam
answers it. The pipeline is deterministic **on replay** because the LLM's contribution is frozen as
a recorded decision at emission — exactly the guarantee INV-17 was written to provide for
non-deterministic values anywhere in the platform. Nexus already trusts this pattern for the
highest-stakes non-determinism it has (runtime execution). EI is a strictly easier case: its
non-determinism is confined to *one* decision, recorded *once*, before any work happens.

---

# Re-strategizing within the flow

If execution surfaces information that invalidates the Strategy (a discovery, a recovery
escalation), the platform requests a **new** Strategy — a fresh pass through this flow — which
supersedes the prior one by reference (`04`). The old Strategy is never mutated. Each re-strategize
is itself a recorded, bounded, explainable event (INV-22-style discipline), so the audit trail
remains complete and replay remains exact.

---

# North Star

Engineering Intelligence thinks freely, then commits its thinking to the record.

Judgment is heuristic; the record is deterministic. After emission, the platform never guesses
again — it replays.
