# Knowledge Governance

Status: Target Architecture (design only)

---

# Purpose

This document freezes how Knowledge is governed: how every decision is **auditable and
explainable**, how **provenance** is preserved, who **owns** knowledge and its policy, and how
Knowledge may **influence** governance without ever *evaluating* it. Governance is what makes
durable understanding trustworthy.

---

# Auditability

Every Knowledge decision is an immutable event (`07`) in the append-only store (ADR-001):
acceptance, rejection, evolution, supersession, deprecation, expiration, archival. There is no
out-of-band mutation and no delete. The complete history of *what became understanding and why* is
reconstructable at any time by replaying the `knowledge.*` stream. This directly realises INV-31
(every operational decision is explainable and auditable) for the Knowledge layer.

---

# Explainability

Every acceptance or rejection records:

- the **rationale** (`step: outcome — reason`) from the Acceptance Engine (`05`);
- the **Persistence Policy version** it was evaluated against (`04`);
- the **evidence** it relied on, by id;
- the **prior Item version**, if an evolution.

A reviewer can answer, from the record alone: *Why is this Knowledge? Why was that candidate
rejected? On what evidence? Under which policy?* No decision is a black box.

---

# Provenance

Provenance is a first-class, unbroken chain, preserved across every evolution:

```
Knowledge Item version
   └─ accepted Candidate(s)  ──▶ Reflection Report ──▶ Operational Pattern ──▶ Evidence ──▶ validated Outcome
        (all by id, never duplicated — INV-27)
```

Evolution **accumulates** provenance; it never discards it (`10`). An Item can always name the
candidates, patterns, evidence, and validated outcomes that justify each version of its statement.
This is the structural enforcement of INV-24 (Knowledge is evidence-backed).

---

# Ownership

- **The Knowledge Engine owns Knowledge** — creation, evolution, expiration, and serving. No other
  subsystem writes Knowledge (INV-25: even Reflection only proposes).
- **The Persistence Policy has a named owner** (`04`) — changing acceptance thresholds is a
  governed act, recorded and versioned; decisions cite the policy version they used.
- **Consumers own nothing in Knowledge** — Planning, Context, and Orchestration hold read-only
  views (`09`); they can neither write nor deprecate.

---

# Policy influence (without policy evaluation)

Knowledge may *inform* governance — e.g. a Proven anti-pattern or constraint becomes understanding
that Planning and, indirectly, policy authors can act on. But Knowledge **never evaluates governance
policy**: that is the exclusive role of the Policy Engine (INV-28), and governed actions fail closed
(INV-30). The separation is strict:

| Knowledge may… | Knowledge must never… |
|---|---|
| record understanding that influences future policy authoring | evaluate or enforce a governance policy |
| serve constraints/anti-patterns read-only to Planning | mutate a policy, or gate a governed action |
| carry its own **acceptance** (Persistence) policy | conflate its acceptance policy with platform governance |

Knowledge's own Persistence Policy (`04`) governs *what becomes Knowledge*; it is distinct from the
platform governance the Policy Engine evaluates.

---

# Tamper evidence & integrity

Because Knowledge is event-sourced and reference-based (INV-27), it is **tamper-evident**: history
cannot be silently altered without leaving the log inconsistent, and no Item can smuggle in
artifact content it should only reference. Integrity of understanding rests on the integrity of the
append-only store, which the Phase-2 substrate already guarantees (optimistic concurrency,
idempotent projection).

---

# North Star

Governed Knowledge is Knowledge you can trust to steer future work: every unit names its evidence,
every decision names its policy and rationale, one subsystem owns it, and its consumers can only
read. Understanding influences the platform — but only through the front door, on the record.
