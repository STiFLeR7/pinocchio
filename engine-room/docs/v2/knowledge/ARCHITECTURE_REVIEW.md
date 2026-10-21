# Knowledge Engine — Architecture Review & Ratification

Status: Design review (design only). No implementation, no ADR/contract/invariant change.

This review evaluates the frozen Knowledge architecture (`00`–`14`) for correctness, completeness,
and readiness, and answers the five ratification questions. Its purpose is to certify that a future
team can build the Knowledge Engine **without making new architectural decisions**.

---

# 1. Dependency direction

**Verdict: sound and structurally enforced.**

```
Reflection ──candidates (by value)──▶ Knowledge ──read-only views──▶ Planning / Context / Orchestration
nexus_knowledge → { nexus_core, nexus_infra }   (only)
```

- Knowledge imports **no** upstream layer (not `nexus_reflection`, not `nexus_validation`); it
  consumes candidates by value at its ingestion boundary (`00`/`02`). This matches the runtime rule
  (`nexus_runtime → {nexus_core, nexus_infra}`) and the pattern of every layer built so far.
- Knowledge is imported by nothing upstream; consumers hold read-only views (`09`).
- Because Knowledge imports no upstream layer, **consumers cannot reach Reflection *through*
  Knowledge**, so INV-26 holds by construction, not convention.
- The one open ownership choice (candidate as shared `nexus_core` contract vs. adapted at the
  boundary, G9) does **not** affect the direction — both options keep it clean.

---

# 2. Lifecycle completeness

**Verdict: complete and closed.**

- States cover the full arc: Candidate → (Rejected | Accepted → Active → {Active evolves} →
  Superseded/Deprecated → Expired → Archived) (`06`).
- Every transition has a **deterministic trigger and rule** (`06`/`10`/`11`); none is
  clock-driven-nondeterministic (TTL uses recorded timestamps as data, INV-17).
- No destructive deletion — "forgetting" is a state (`11`), so provenance is never lost.
- Reactivation on stronger evidence is defined (`11`), so staleness is not a dead end.
- Ingestion is idempotent (INV-16), so replay/duplication cannot corrupt the lifecycle.

No reachable state is undefined; no transition is ambiguous.

---

# 3. Governance

**Verdict: strong.**

- Every decision is an immutable, explainable event carrying rationale, policy version, and evidence
  (`07`/`08`) — INV-31 satisfied for Knowledge.
- Provenance is first-class and only-grows across evolution (`08`/`10`) — INV-24 satisfied
  structurally.
- Ownership is explicit: the Engine is the sole writer; the Persistence Policy has a named owner;
  consumers own nothing (`08`).
- Knowledge influences but never **evaluates** governance policy (INV-28); its own acceptance policy
  is distinct from platform governance and fails closed (`04`).

---

# 4. Scalability

**Verdict: adequate for the defined scope; large-scale concerns are named, not hand-waved.**

- Event-sourced projections + deterministic subject-key identity give O(1) dedup/evolution routing
  (`03`) and replayable state (ADR-001) — the same substrate that scales the prior layers.
- Read-only retrieval is side-effect-free and cacheable (`09`).
- Long-horizon retention, log compaction/snapshotting, and semantic retrieval at scale are
  **explicitly deferred** (`14` G3/G8), with the event model already supporting snapshots. No scale
  assumption is silently baked in.

---

# 5. Operational readiness

**Verdict: ready to implement.**

- Reuses the Phase-2 substrate unchanged (event store, repositories, observability) — no new
  mechanism to build or operate.
- Observability defines acceptance/rejection/evolution/expiration rates and confidence distribution
  (`12`), all derived and decision-neutral.
- Determinism end-to-end makes it testable exactly like the prior engines (identical inputs →
  identical Items, versions, and event streams).
- Security posture is defined for the single-operator, Reflection-only path; multi-tenant/at-rest
  concerns are deferred with intent (`13`/`14`).

---

# 6. Interaction with Reflection

**Verdict: clean seam, correct direction.**

- Reflection *proposes* (immutable candidates); Knowledge *decides* (`01`/`02`/`05`) — INV-25 holds.
- Knowledge **re-verifies** provenance/evidence at acceptance rather than trusting Reflection's
  recommendation (`05`) — the same "never trust the claim, trust the evidence" discipline as
  Validation (INV-20) and Recovery. This is the architectural teeth behind "never accept solely
  because Reflection recommends."
- No backward coupling: Knowledge does not import Reflection (`00`).

---

# 7. Interaction with Planning

**Verdict: correct and future-safe.**

- Planning consumes Knowledge read-only (`09`); it never writes and never imports Reflection —
  INV-26 holds structurally.
- Planning can evolve independently as Knowledge accumulates; the only contract between them is the
  read-only retrieval interface.
- Confidence- and freshness-aware retrieval lets Planning prefer current, proven understanding
  (`09`/`11`), exactly as `../10_KNOWLEDGE.md` intends.

---

# Ratification questions

### 1. Can Knowledge be implemented without architectural ambiguity?
**Yes.** The subsystem, dependency direction, object model, deterministic identity, acceptance
procedure, lifecycle, events, evolution, expiration, consumption, governance, observability, and
security are all specified (`00`–`13`). Open items are explicitly deferred and non-blocking (`14`).
The one Phase-0 choice (G9 candidate-contract ownership) has two spelled-out options that both
preserve the architecture. A team can build the core with no new architectural decisions.

### 2. Does Knowledge preserve INV-25?
**Yes.** Reflection produces immutable candidates; only the Knowledge Engine's Acceptance Engine
creates or evolves durable Knowledge (`01`/`05`). Reflection has no write path into Knowledge.

### 3. Does Knowledge preserve INV-26?
**Yes — structurally.** Learning reaches Planning only through read-only Knowledge queries (`09`).
Knowledge imports no upstream layer, so no consumer can reach Reflection through Knowledge; Planning
never depends on Reflection directly or transitively-by-import.

### 4. Can Planning evolve without depending directly on Reflection?
**Yes.** The only Planning↔learning contract is the Knowledge retrieval interface (`09`). Planning
imports Knowledge, never Reflection. Knowledge can change how it accepts/evolves understanding
without Planning changing, and Planning can change how it consumes without touching Reflection.

### 5. Is Knowledge future-proof for Memory, Research, and Autonomous Workflows?
**Yes, with named seams.** Memory is a separate subsystem Knowledge references rather than embeds
(INV-27; G1). The candidate contract is generic enough to admit Research/external ingestion later
(G2), and the read-only consumption contract is intended to serve Autonomous Workflows unchanged
(G10). None of these require reopening the frozen core; each is a defined extension point.

---

# Certification

The Knowledge architecture is **internally consistent, invariant-preserving (INV-24/25/26/27),
deterministic, auditable, and complete for its defined scope**, with all frontier concerns named and
deferred (`14`). It amends no ADR, contract, or invariant, and contradicts nothing in
`../10_KNOWLEDGE.md`.

**Recommendation: ratify and freeze.** A future implementation team may proceed to build the
`nexus_knowledge` engine directly against these documents.
