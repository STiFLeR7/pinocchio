# Acceptance Engine

Status: Target Architecture (design only)

---

# Purpose

The **Acceptance Engine** is the deterministic decision function at the heart of Knowledge. Given a
Knowledge Candidate, the current Knowledge state for its subject, and the Persistence Policy, it
returns exactly one governed outcome — **accept (create)**, **accept (evolve)**, **merge**, or
**reject** — with an explainable rationale. It is Knowledge's analogue of the Validation Engine's
rule evaluator and the Recovery Engine's decision precedence: pure, evidence-driven, no AI, no
heuristics.

---

# Inputs

- the **Knowledge Candidate** (`02`);
- the **existing Knowledge state** for the candidate's Subject Key (the current Item + version
  chain, or none);
- the **Persistence Policy** (`04`).

The Engine reads these and nothing else. It has no clock in its decision path (timestamps are
injected), no randomness, and no learned parameters.

---

# Deterministic decision procedure

```
1. Provenance & evidence check (INV-24)
     • resolve every evidence_ref; require validated origin if the policy demands it
     • fail → REJECT (rationale: "provenance not validated" / "insufficient evidence")

2. Eligibility check (Persistence Policy thresholds)
     • confidence ≥ minimum_confidence, evidence ≥ minimum_evidence, kind ∈ accepted_kinds
     • fail → REJECT (rationale names the unmet threshold)

3. Subject-key resolution (03)
     • no existing Item for the key  → ACCEPT (CREATE): new Item at Accepted, initial confidence
     • existing Item for the key     → go to (4)

4. Duplicate / evolution decision (duplicate_strategy)
     • candidate adds new independent evidence or a stronger statement → ACCEPT (EVOLVE): new version
     • candidate corroborates without changing the statement           → MERGE: accumulate evidence + promote confidence
     • candidate adds nothing new (evidence already recorded)           → REJECT (rationale: "duplicate")
```

The precedence is fixed and total: **provenance → eligibility → create-vs-evolve → merge-vs-reject**.
Every path terminates in exactly one outcome and records a rationale (INV-31).

---

# Outcomes

| Outcome | Effect on Knowledge | Event (`07`) |
|---|---|---|
| **Accept (create)** | a new Knowledge Item is created in `Accepted` | `knowledge.item_created` |
| **Accept (evolve)** | a new immutable version is appended; statement/confidence advance | `knowledge.item_evolved` |
| **Merge** | evidence accumulates; confidence promotes per policy; statement unchanged | `knowledge.item_evolved` |
| **Reject** | no Item changes; the rejection is recorded with its reason | `knowledge.candidate_rejected` |

Every ingestion first emits `knowledge.candidate_received` and, on any accept/merge, persists the
updated Item projection.

---

# Never accept on recommendation alone

The Engine's first two steps exist specifically to enforce the program rule: a candidate is
accepted only after *its own* provenance and evidence clear policy — **never** because Reflection
recommended it. Reflection's confidence is an *input* to eligibility, not a substitute for it. This
is the same discipline Validation applies to runtime self-reports (INV-20) and Recovery applies to
verdicts: trust the evidence, not the claim.

---

# Explainability

Each decision produces a rationale trace (`step: outcome — reason`) and records the **policy
version** it evaluated against, the **evidence** it relied on, and the **prior Item version** (if
any). Any acceptance or rejection is fully reconstructable from the audit alone (INV-31, ADR-001) —
a reviewer can see exactly why a piece of understanding was or was not persisted.

---

# Determinism guarantee

For identical `(candidate, existing state, policy)` the Engine yields an identical outcome, item
version, and event stream. Two Knowledge stores fed the same candidate history converge to
byte-identical Items — the property that makes Knowledge replayable and auditable.

---

# Boundary

The Acceptance Engine **decides**; it does not serve queries (`09`), compute freshness (`11`), or
evaluate governance policy (INV-28). It is invoked only by the Knowledge Engine's ingest operation
(`01`).

---

# North Star

The Acceptance Engine is the deterministic conscience of Knowledge: a single, replayable function
that turns a proposal plus its evidence into a durable, on-the-record decision — and refuses
everything that cannot earn its place.
