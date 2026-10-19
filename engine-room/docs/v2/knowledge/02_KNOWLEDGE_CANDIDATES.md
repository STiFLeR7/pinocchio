# Knowledge Candidates

Status: Target Architecture (design only)

---

# Purpose

A **Knowledge Candidate** is the immutable, advisory unit that Reflection produces and Knowledge
consumes. It is the **single boundary contract** between the two subsystems and the only input to
the Knowledge Engine's ingestion path. It carries a proposed piece of understanding together with
everything needed to judge it: its provenance, its supporting evidence, and its confidence.

Candidates are **advisory until accepted** (INV-25). Reflection *recommends*; the Knowledge Engine
*decides*. A candidate is never persisted as Knowledge merely because it exists.

---

# Origin (already implemented in Reflection)

Reflection emits Knowledge Candidates only from **confirmed, actionable** operational patterns
over validated history (doc 26). The candidate therefore arrives already grounded in validated
outcomes — but the Knowledge Engine re-verifies that grounding at acceptance (`05`); it does not
trust the recommendation itself (INV-24, mirroring the "never trust a self-report" discipline).

---

# Structure (the boundary contract)

A Knowledge Candidate is an immutable value carrying:

| Field | Meaning |
|---|---|
| `identity` | the candidate's stable id (e.g. Reflection's `kc-{scope}-{seq}`) |
| `kind` | the proposed knowledge kind (pattern / lesson / strategy / constraint / finding …) |
| `subject` | *what the understanding is about* — the basis of the deterministic subject key (`03`) |
| `summary` | the proposed understanding, as an operational statement (not raw text/log) |
| `confidence` | the doc-26 level Reflection assessed (Experimental / Observed / Validated / Proven) |
| `originating_reflection_ref` | the Reflection Report that produced it, **by id** |
| `source_pattern_ref` | the Operational Pattern it was derived from, **by id** |
| `evidence_refs` | the supporting Evidence / operation references, **by id** (never embedded) |
| `correlation_identifier` | the operation lineage it belongs to (INV-39) |

The candidate references artifacts and evidence **by id and never duplicates their content**
(INV-27). It carries no runtime state, no clock-derived value, and no secret.

---

# Immutability

Knowledge Candidates are **immutable**. A candidate is a fact about what Reflection proposed at a
point in time; it is never edited. If Reflection later proposes a refined understanding, that is a
*new* candidate (typically a new version of the subject), which the Engine evolves into the
existing Item (`10`). The contrast is deliberate and canonical:

> **Knowledge Candidates are immutable. Knowledge is mutable through controlled evolution.**

---

# Consumption boundary

- The Engine consumes candidates **by value** at its ingestion boundary. It does **not** import
  Reflection; the orchestrating caller passes candidates from a Reflection Report into the ingest
  operation. This keeps `nexus_knowledge → {nexus_core, nexus_infra}` only and prevents any
  backward coupling (`00`).
- A candidate is consumed **exactly once** per ingestion; ingestion is idempotent by candidate
  identity (INV-16), so re-submitting the same candidate produces no duplicate effect.

---

# What a candidate is not

- **Not Knowledge.** It is a proposal; only the Engine's acceptance makes it durable.
- **Not evidence.** It *references* Evidence; it does not contain it.
- **Not a command.** Knowledge cannot execute, retry, or plan on a candidate's behalf.
- **Not mutable.** It is a fixed record of what was proposed.

---

# North Star

The Knowledge Candidate is the clean seam between interpretation and persistence. Reflection can
propose freely; nothing crosses into durable understanding until the Knowledge Engine has judged
the candidate on its provenance, evidence, and policy — deterministically and on the record.
