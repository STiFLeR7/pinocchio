# Knowledge Consumption

Status: Target Architecture (design only)

---

# Purpose

This document freezes how downstream subsystems consume Knowledge. Consumption is the point where
accumulated understanding **influences future work** — and it is deliberately constrained:
consumers **read**, never write, and they reach learning **only through Knowledge**, never through
Reflection (INV-26).

---

# Who consumes, and for what

| Consumer | Consumes Knowledge to… |
|---|---|
| **Planning** | choose strategies, avoid known anti-patterns, prefer proven approaches |
| **Context Engineering** | enrich Context Packages with relevant operational understanding |
| **Orchestration** | inform coordination/ordering with known bottlenecks and risks |

These mirror the retrieval consumers named in `../10_KNOWLEDGE.md`. Supervision and future
subsystems may consume through the same read-only interface.

---

# The read-only retrieval contract

Consumers obtain Knowledge through a **query → immutable view** interface (`01` serve operation):

```
Consumer query  (subject / kind / confidence floor / freshness filter / relationship traversal)
      ↓
Knowledge Engine resolves matching Items (Active by default)
      ↓
Returns immutable Knowledge views by reference   (no mutation, no side effects)
```

- **Read-only.** A retrieval never changes Knowledge state. The returned views are immutable value
  objects referencing Items by id; a consumer cannot accept, evolve, deprecate, or expire anything.
- **Current by default.** Only `Active` Items are returned by default; `Deprecated` / `Superseded`
  / `Expired` / `Archived` are excluded unless a consumer explicitly requests historical scope for
  audit (`06`/`11`). Planning therefore *prefers current knowledge* (`../10_KNOWLEDGE.md`).
- **Confidence-aware.** Queries may set a confidence floor; consumers may choose strategies by
  confidence (Experimental … Proven), exactly as `../10_KNOWLEDGE.md` intends.
- **Graph-aware.** Retrieval may traverse typed relationships (`03`) to return connected
  understanding, not isolated records.

---

# The INV-26 boundary (why this matters)

Learning reaches Planning **only** through persisted Knowledge:

```
Reflection ──candidates──▶ Knowledge ──read-only views──▶ Planning / Context / Orchestration
     ▲                                                        │
     └───────────────  no direct dependency  ◀────────────────┘   (INV-26)
```

- No consumer imports `nexus_reflection` to obtain learning; the only path is a Knowledge query.
- Because Knowledge itself imports no upstream layer (`00`), a consumer of Knowledge cannot reach
  Reflection *through* Knowledge either. The invariant is preserved **structurally**, not by
  convention.
- Planning can therefore evolve freely as Knowledge accumulates, without any code path to
  Reflection — the decoupling the loop was designed for.

---

# Retrieval semantics

Retrieval answers *"what operational understanding is relevant now?"* (`../10_KNOWLEDGE.md`), not
*"what information exists?"*. It is:

- **Deterministic** — the same query against the same Knowledge state returns the same views.
- **Side-effect-free** — modulo an optional, sampled `knowledge.item_served` observability event
  (`07`/`12`) that records *that* a retrieval happened, never mutating Knowledge.
- **Reference-based** — views carry artifact/evidence references (INV-27), never embedded content;
  a consumer resolves references itself if it needs the underlying artifact.

---

# What consumers may not do

- may not write, evolve, deprecate, expire, or archive Knowledge;
- may not obtain learning by any path other than a Knowledge query (INV-26);
- may not treat a retrieved view as mutable or authoritative-for-write;
- may not embed Knowledge content into an artifact in a way that duplicates referenced material
  (INV-27).

---

# North Star

Consumption is the payoff of the whole loop: future work begins already knowing what past work
learned — delivered read-only, current-first, confidence-aware, and reachable only through
Knowledge, so that influence flows forward without ever coupling Planning back to Reflection.
