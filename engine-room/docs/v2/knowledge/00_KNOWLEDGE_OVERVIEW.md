# Knowledge Overview

Status: Target Architecture (design only)

---

# Purpose

The Knowledge Engine transforms Reflection's advisory **Knowledge Candidates** into durable,
evolving **operational understanding** that improves future work. It is the platform's memory
of *why* things worked or failed — not a store of raw information (that is Memory, a separate
future subsystem), but a store of validated, reusable understanding.

Knowledge is the first subsystem that **influences future executions**. It closes the operational
loop: Execution creates results, Validation establishes truth, Reflection creates understanding,
**Knowledge preserves understanding**, and future Planning begins with more understanding than the
last.

---

# Position in the pipeline

```
… → Validation → Recovery → Reflection → Knowledge → (future Planning / Context Engineering)
                              (candidates)   (persistence)      (read-only consumption)
```

Knowledge sits *after* Reflection and *before* the next Planning cycle. It never runs inline with
an execution; it operates on the immutable outputs the pipeline has already produced.

---

# Inputs and outputs

## Inputs (consumed by value / reference — never mutated)

- **Knowledge Candidates** — the immutable, advisory units Reflection emits inside a Reflection
  Report (`02`). This is the single ingestion contract.
- **Provenance references** — the candidate's originating Reflection Report, source Operational
  Pattern, and supporting Evidence, all **by id** (INV-12/INV-27).

## Outputs (Knowledge-owned, produced by the Engine)

- **Knowledge Items** — the durable units of understanding (`03`), a projection of the
  append-only `knowledge.*` event stream (ADR-001).
- **`knowledge.*` events** — the immutable audit of every accept/reject/evolve/expire (`07`).
- **Read-only Knowledge views** — served to consumers on query (`09`).

---

# Dependency direction

```
nexus_knowledge → { nexus_core, nexus_infra }        (only)
```

- Knowledge **consumes Knowledge Candidates by value** at its ingestion boundary — the
  orchestrating caller hands candidates to the Engine. Knowledge imports **no** upstream layer
  (not `nexus_reflection`, not `nexus_validation`), so learning cannot leak backward and
  Planning cannot reach Reflection through Knowledge's imports (INV-26 preserved structurally).
- Knowledge is **imported by nothing upstream**. Planning, Context Engineering, and Orchestration
  consume Knowledge **read-only** through a retrieval interface (`09`); they never mutate it and
  never import Reflection to obtain learning (INV-26).
- Knowledge reuses the Phase-2 substrate unchanged (event store, repositories, observability) —
  it invents no new persistence mechanism (ADR-001).

---

# What Knowledge is, and is not

| Knowledge **is** | Knowledge **is not** |
|---|---|
| a decision layer over advisory candidates | a producer of candidates (that is Reflection) |
| durable, evolving operational understanding | a store of raw information (that is Memory) |
| evidence-backed and validation-gated (INV-24) | a place assumptions become fact |
| read-only to its consumers | a thing Planning/Context can write |
| a reference-holder of artifacts (INV-27) | a duplicator of artifact content |
| deterministic and auditable | heuristic, learned, or AI-scored |

---

# Canon glossary

- **Knowledge Candidate** — immutable advisory unit from Reflection; the ingestion contract (`02`).
- **Knowledge Item** — durable unit of understanding; mutable only via versioned evolution (`03`).
- **Knowledge Subject Key** — the deterministic identity of *what an item is about* (kind +
  canonical subject); recurring candidates about the same subject map to the same Item, enabling
  evolution and accumulation (`03`/`10`).
- **Acceptance Engine** — deterministic accept/reject/merge under the Persistence Policy (`05`).
- **Persistence Policy** — the declarative thresholds and requirements governing acceptance (`04`).
- **Knowledge Lifecycle** — Candidate → Accepted → Active → Superseded → Deprecated → Expired →
  Archived (+ Rejected) (`06`).
- **Confidence Level** — doc-10/doc-26 canon: Experimental / Observed / Validated / Proven.

---

# North Star

Knowledge is where Nexus stops *remembering* work and starts *understanding* it. Reflection
proposes; Knowledge decides, preserves, evolves, and serves. Every validated operation makes the
durable understanding of the platform a little stronger — and every future plan begins from it.
