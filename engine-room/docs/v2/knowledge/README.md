# Nexus v2 — Knowledge Engine Architecture (design only)

> **Status:** Architecture & design specification. **No implementation.** This directory
> defines *what* the Knowledge Engine is and *how* it must behave, so that a future
> implementation team can build it without making new architectural decisions. It introduces
> **no** production code, Protocols, classes, algorithms, or APIs. It amends **no** ADR,
> contract, or invariant; where the existing architecture needs clarification, that is recorded
> as a *recommendation* in [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md), not applied.
> It expands the frozen [`../10_KNOWLEDGE.md`](../10_KNOWLEDGE.md) into an implementable
> subsystem; it never contradicts it.

## Why this exists

Nexus has reached the end of its operational pipeline. Ten layers now run and govern work:

```
Goal → Context Engineering → Planning → Orchestration → Harness → Runtime → Execution
     → Validation → Recovery → Reflection → ▮ Knowledge ▮ → (future) Planning
                                             (decides persistence)   (consumes understanding)
```

Reflection produces immutable **Knowledge Candidates** — advisory observations. Knowledge is
the **first subsystem that will influence future executions**, so its architecture must be
frozen before engineering begins. The Knowledge Engine answers exactly one question:

> Given advisory Knowledge Candidates produced by Reflection, how does Nexus **decide what
> becomes durable operational understanding**, evolve it as evidence accumulates, expire it when
> obsolete, and serve it read-only to Planning and Context Engineering — deterministically,
> auditably, and without ever executing, analysing, or validating work?

**Reflection produces observations. Knowledge decides persistence. Planning consumes Knowledge.**
That single sentence is the spine of every document here.

## The boundary, stated precisely

| Concern | Owner |
|---|---|
| Interpret validated outcomes; emit advisory **Knowledge Candidates** | Reflection (implemented) |
| **Accept/reject candidates, deduplicate, evolve, expire, and serve durable Knowledge** | **Knowledge Engine (this design)** |
| Decide *what* work exists, consuming Knowledge read-only | Planning |
| Assemble operational understanding, consuming Knowledge read-only | Context Engineering |
| Evaluate governance policy | Policy Engine (ADR-004) |
| Store raw information (not understanding) | Memory (future, out of scope) |

## Reading order

| # | Document | Defines |
|---|---|---|
| — | [`00_KNOWLEDGE_OVERVIEW.md`](00_KNOWLEDGE_OVERVIEW.md) | The subsystem, inputs/outputs, dependency direction, canon glossary |
| — | [`01_KNOWLEDGE_ENGINE.md`](01_KNOWLEDGE_ENGINE.md) | Responsibilities, the ingest→serve pipeline, hard boundaries |
| — | [`02_KNOWLEDGE_CANDIDATES.md`](02_KNOWLEDGE_CANDIDATES.md) | The candidate contract: identity, provenance, confidence, immutability |
| — | [`03_KNOWLEDGE_MODEL.md`](03_KNOWLEDGE_MODEL.md) | The Knowledge Item object model, identity, versioning, relationships |
| — | [`04_PERSISTENCE_POLICY.md`](04_PERSISTENCE_POLICY.md) | Acceptance thresholds, rejection, dedup, evidence requirements |
| — | [`05_ACCEPTANCE_ENGINE.md`](05_ACCEPTANCE_ENGINE.md) | Deterministic accept/reject/merge decisioning |
| — | [`06_KNOWLEDGE_LIFECYCLE.md`](06_KNOWLEDGE_LIFECYCLE.md) | The canonical lifecycle state machine and transitions |
| — | [`07_KNOWLEDGE_EVENTS.md`](07_KNOWLEDGE_EVENTS.md) | The canonical `knowledge.*` event taxonomy |
| — | [`08_KNOWLEDGE_GOVERNANCE.md`](08_KNOWLEDGE_GOVERNANCE.md) | Auditability, explainability, provenance, ownership, policy influence |
| — | [`09_KNOWLEDGE_CONSUMPTION.md`](09_KNOWLEDGE_CONSUMPTION.md) | Read-only retrieval by Planning / Context / Orchestration |
| — | [`10_KNOWLEDGE_EVOLUTION.md`](10_KNOWLEDGE_EVOLUTION.md) | Versioning, superseding, merging, confidence & evidence accumulation |
| — | [`11_KNOWLEDGE_EXPIRATION.md`](11_KNOWLEDGE_EXPIRATION.md) | Freshness, staleness, supersession, expiry, archival |
| — | [`12_KNOWLEDGE_OBSERVABILITY.md`](12_KNOWLEDGE_OBSERVABILITY.md) | Acceptance/rejection/evolution/expiration rates, confidence distribution |
| — | [`13_KNOWLEDGE_SECURITY.md`](13_KNOWLEDGE_SECURITY.md) | Reference-not-duplicate, provenance integrity, read-only, secret exclusion |
| — | [`14_KNOWLEDGE_GAPS.md`](14_KNOWLEDGE_GAPS.md) | Open questions and deferred decisions |
| — | [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) | Correctness, scalability, readiness, and the five ratification questions |

## Canon (binding for every document)

These terms and rules are **fixed**. No document may redefine them, invent a parallel
lifecycle, or coin a competing event name:

- **Knowledge Engine (KE)** — the subsystem specified here. Decides persistence; never executes,
  analyses, or validates.
- **Knowledge Candidate** — the immutable, advisory unit Reflection produces (`02`). The
  boundary contract between Reflection and Knowledge.
- **Knowledge Item** — the durable unit of operational understanding, mutable **only through
  controlled, versioned evolution** (`03`).
- **Acceptance Engine** — the deterministic decision function that accepts, rejects, or merges a
  candidate under the Persistence Policy (`04`/`05`).
- **Dependency direction** — `nexus_knowledge → {nexus_core, nexus_infra}` only. It consumes
  Knowledge Candidates **by value** at its ingestion boundary and is imported by nothing
  upstream. Planning/Context/Orchestration consume Knowledge **read-only** (`00`/`09`).
- **Binding invariants** — INV-24 (evidence-backed), INV-25 (Reflection produces candidates;
  Knowledge decides persistence), INV-26 (Planning never depends directly on Reflection), INV-27
  (reference artifacts, never duplicate). No document may weaken these.
