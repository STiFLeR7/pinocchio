# Persistence Policy

Status: Target Architecture (design only)

---

# Purpose

The **Persistence Policy** is the declarative bundle that governs whether a Knowledge Candidate
becomes durable Knowledge. It is the data-driven contract the Acceptance Engine (`05`) evaluates —
never hardcoded logic, never a heuristic. It exists to enforce the program's central rule:

> **Knowledge must never be accepted solely because Reflection recommends it.**

Acceptance requires *independent* satisfaction of policy thresholds and evidence requirements —
mirroring INV-24 (evidence-backed) and the platform-wide "never trust a self-report" discipline.

---

# Policy dimensions

The policy is a small, immutable, deterministic bundle:

| Dimension | Governs |
|---|---|
| `minimum_confidence` | the lowest doc-26 level a candidate may carry to be eligible (e.g. ≥ Observed) |
| `minimum_evidence` | the minimum count of independent supporting evidence references required |
| `require_validated_provenance` | that supporting evidence must trace to **validated** outcomes (INV-24) |
| `accepted_kinds` | the knowledge kinds eligible for persistence (others are held/rejected) |
| `duplicate_strategy` | how a subject-key match is handled: **merge** / **evolve** / **reject-as-duplicate** |
| `confidence_promotion` | how accumulated corroboration raises an item's confidence (`10`) |
| `rejection_is_terminal` | whether a rejected candidate may be reconsidered on stronger evidence |
| `owner` | the responsible policy owner (governance/provenance, `08`) |

The policy is versioned and referenced by every acceptance decision, so any decision can be replayed
against the exact policy that produced it.

---

# Acceptance thresholds

A candidate is **eligible** only if *all* hold (fail-closed — any unmet requirement blocks
acceptance):

1. `confidence ≥ minimum_confidence`;
2. `count(evidence_refs) ≥ minimum_evidence`;
3. if `require_validated_provenance`, every supporting reference resolves to a **validated**
   outcome (a Validation Report / validated Evidence), not merely to execution output;
4. `kind ∈ accepted_kinds`.

Eligibility is necessary, not sufficient: the Acceptance Engine still applies duplicate/merge logic
(`05`) before creating or evolving an Item.

---

# Rejection policy

A candidate that fails eligibility is **rejected** (or **held**, if the policy allows
reconsideration). Rejection is deterministic and explainable: the decision records *which*
requirement failed (INV-31). Rejection never mutates any existing Item. If `rejection_is_terminal`
is false, a later, stronger candidate for the same subject may still be accepted — rejection of a
weak proposal does not blacklist the subject.

---

# Duplicate detection

Duplication is detected **deterministically by Knowledge Subject Key** (`03`), never by fuzzy text
similarity:

- **No match** → candidate is a *creation* (subject to eligibility).
- **Match** → candidate is a *duplicate of a known subject*; `duplicate_strategy` decides:
  - **evolve** — apply as a new version if it strengthens/refines the Item (`10`);
  - **merge** — accumulate its evidence and (per `confidence_promotion`) its confidence into the
    current version;
  - **reject-as-duplicate** — if it adds nothing (same evidence set already recorded).

Idempotency (INV-16): re-submitting an already-ingested candidate (same identity) is a no-op.

---

# Evidence requirements (INV-24)

Evidence is the gate. The policy demands that a candidate's understanding be **backed by
independent, validated evidence** — the count (`minimum_evidence`) and the origin
(`require_validated_provenance`) are both enforced. This is what makes Knowledge *earned* rather
than *asserted*, and it is the architectural reason Reflection's recommendation alone is never
enough.

---

# Determinism & governance

The policy is pure data; the Acceptance Engine is a pure function of `(candidate, existing Item,
policy)`. The policy is owned and audited (`08`); changing it is a governed act, and every decision
records the policy version it used. Knowledge **never evaluates governance policy itself** — that
remains the Policy Engine's role (INV-28); the Persistence Policy is Knowledge's *own* acceptance
configuration, distinct from platform governance policy.

---

# North Star

The Persistence Policy is the written, replayable answer to "why is this Knowledge and that not?"
Nothing durable exists that cannot point to the threshold it cleared and the evidence that cleared
it.
