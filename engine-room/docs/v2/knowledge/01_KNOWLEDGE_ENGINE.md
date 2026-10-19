# Knowledge Engine

Status: Target Architecture (design only)

---

# Purpose

The Knowledge Engine is the subsystem that **decides persistence**. It receives advisory
Knowledge Candidates, judges each against a declarative Persistence Policy, and either accepts it
(creating or evolving a durable Knowledge Item), merges it into existing understanding, or rejects
it — recording every decision as immutable, explainable audit. It then serves the resulting
Knowledge read-only to Planning and Context Engineering.

The Engine decides, preserves, evolves, expires, and serves. **It never executes, analyses,
validates, retries, or recovers work.**

---

# Responsibilities

The Knowledge Engine is responsible for

- accepting or rejecting Knowledge Candidates (deterministically, under policy)
- deduplicating knowledge (mapping candidates to a durable Item by subject key)
- evolving existing knowledge (versioned, provenance-preserving)
- expiring obsolete knowledge (freshness, staleness, supersession)
- recording confidence (derived from accumulated corroboration)
- maintaining provenance (candidate → pattern → evidence → outcome)
- serving Planning (read-only retrieval)
- serving Context Engineering (read-only retrieval)

The Knowledge Engine never

- executes work
- analyses work (that is Reflection)
- validates work (that is Validation)
- retries work / performs recovery (that is Recovery)
- assembles Context Packages (that is Context Engineering)
- evaluates governance policy (that is the Policy Engine, INV-28)
- mutates Reflection, Planning, or any upstream output

---

# The ingest → serve pipeline

The Engine exposes two deterministic operations. Neither runs inline with an execution.

## 1. Ingest (candidate → decision)

```
Knowledge Candidate
   ↓  (emit knowledge.candidate_received)
Provenance & evidence check      ── verify the candidate traces to validated outcomes (INV-24)
   ↓
Subject-key resolution           ── map to an existing Item, or a new subject
   ↓
Duplicate / merge detection      ── same subject already known?
   ↓
Acceptance Engine (deterministic accept / reject / merge under Persistence Policy)
   ↓
Apply decision:
   • accept  → create Item (Accepted) or evolve existing Item (new version)  ── emit knowledge.item_created / knowledge.item_evolved
   • merge   → accumulate evidence + confidence into the existing Item        ── emit knowledge.item_evolved
   • reject  → record rejection with rationale                                ── emit knowledge.candidate_rejected
   ↓
Persist Item projection + append events
```

## 2. Serve (query → read-only view)

```
Consumer query (subject / kind / confidence / freshness filter)
   ↓
Resolve Active (and optionally Historical) Items
   ↓
Return immutable Knowledge views by reference    ── no mutation, no side effects (emit knowledge.item_served, optional)
```

The two operations share the same event-sourced store: a Knowledge Item is a **projection** of
its `knowledge.*` event stream (ADR-001). "Evolution" is always a *new event*, never an in-place
rewrite of history.

---

# Determinism

Given the same candidate, the same existing Knowledge state, and the same Persistence Policy, the
Engine produces the **same decision, the same Item version, and the same event stream**. There is
no clock in the decision path (timestamps are injected, INV-17); no randomness; no learned or AI
scoring. This makes acceptance reproducible and auditable — the platform can replay how any piece
of understanding came to exist.

---

# Hard boundaries

| The Engine must… | The Engine must never… |
|---|---|
| judge candidates against declared policy | accept a candidate solely because Reflection recommended it |
| require validated-evidence provenance (INV-24) | originate knowledge from assumptions |
| reference artifacts/evidence by id (INV-27) | duplicate artifact or evidence content |
| evolve items through versioned, auditable steps | mutate an Item's history in place |
| serve consumers read-only views | let a consumer write, or reach Reflection through it (INV-26) |
| record a rationale for every decision (INV-31) | make an unexplainable or non-reproducible decision |

---

# North Star

The Knowledge Engine is the deterministic gate between *proposed* understanding and *durable*
understanding. Nothing becomes Knowledge without evidence, policy, and an auditable rationale —
and once it is Knowledge, it evolves without ever losing the trail of how it was learned.
